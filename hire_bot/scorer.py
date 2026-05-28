"""
Scoring engine for the hiring bot.

Phase 1 (in-session, immediate):
  auto_grade(attempt_id)             — Part A, B, D1; stores score_summary + is_correct per answer
  detect_contradictions(attempt_id)  — rule-based pairs; stores to hiring_contradictions

Phase 2 (post-session, async):
  draft_rubric_scores(attempt_id)    — Claude grades Part C, D2–D4, Final; stores scores
  build_risk_profile(attempt_id)     — aggregates all scores into risk_profile JSONB

Schema reference (actual DB columns):
  hiring_quiz_answers: id, attempt_id, question_id, raw_answer TEXT, normalized_answer,
                       is_correct BOOL, completeness_score INT, contradiction_score INT,
                       time_spent_seconds, skipped, graded_by, graded_at, grader_notes
  hiring_quiz_attempts: ..., score_summary JSONB, risk_profile JSONB
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import psycopg2

logger = logging.getLogger(__name__)


# ── Connection helper ────────────────────────────────────────────────────────

def _conn():
    import sys
    sys.path.insert(0, '/root/TWBshop')
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)


# ── Answer cache ─────────────────────────────────────────────────────────────

_answer_cache: dict = {}


def _load_answers(cur) -> dict:
    """Returns {question_id: {correct_answer, severity, requires_verbal_retest, part}}"""
    if _answer_cache:
        return _answer_cache
    cur.execute("""
        SELECT id, part, correct_answer, severity_if_wrong, requires_verbal_retest
        FROM hiring_quiz_questions
        WHERE active = TRUE
    """)
    for qid, part, correct_ans, severity, verbal in cur.fetchall():
        _answer_cache[qid] = {
            "part": part,
            "correct_answer": correct_ans,
            "severity": severity,
            "requires_verbal_retest": verbal,
        }
    return _answer_cache


def _parse_answer(raw: Optional[str]) -> dict:
    """Parse raw_answer TEXT into dict. Handles JSON strings and plain text."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"text": raw}
    except (json.JSONDecodeError, TypeError):
        return {"text": raw}


# ── Phase 1: Auto-grade ──────────────────────────────────────────────────────

def auto_grade(attempt_id: int) -> dict:
    """
    Grades Part A, Part B, and D1 for a completed attempt.
    Sets is_correct on each answer row.
    Stores score_summary in hiring_quiz_attempts.
    Returns a triggers dict used by the bot to decide follow-up questions.
    """
    conn = _conn()
    cur = conn.cursor()
    try:
        answers = _load_answers(cur)

        cur.execute("""
            SELECT a.question_id, a.raw_answer, a.skipped
            FROM hiring_quiz_answers a
            JOIN hiring_quiz_questions q ON q.id = a.question_id
            WHERE a.attempt_id = %s AND q.part IN ('A', 'B', 'D')
        """, (attempt_id,))
        rows = cur.fetchall()

        score_a = 0
        score_b = 0
        d1_priority_score = None
        critical_wrong = []
        not_sure_critical = []

        for qid, raw_answer, skipped in rows:
            if skipped or raw_answer is None:
                cur.execute("""
                    UPDATE hiring_quiz_answers SET is_correct = NULL, graded_by = 'auto',
                    graded_at = NOW() WHERE attempt_id = %s AND question_id = %s
                """, (attempt_id, qid))
                continue

            meta = answers.get(qid)
            if not meta:
                continue

            part = meta["part"]
            correct = meta["correct_answer"]
            severity = meta["severity"]
            resp = _parse_answer(raw_answer)
            is_correct = None

            # Part A — yes/no/not_sure
            if part == "A":
                given = resp.get("answer", "").lower()
                expected = correct.get("answer", "").lower() if isinstance(correct, dict) else ""

                if given == "not_sure" and severity in ("critical", "moderate"):
                    not_sure_critical.append(qid)
                    is_correct = False
                elif given == expected:
                    score_a += 1
                    is_correct = True
                else:
                    is_correct = False
                    if severity == "critical":
                        critical_wrong.append(qid)

            # Part B — single_choice
            elif part == "B":
                given = resp.get("answer", "").upper()
                expected = correct.get("answer", "").upper() if isinstance(correct, dict) else ""
                is_correct = (given == expected)
                if is_correct:
                    score_b += 1
                elif severity == "critical":
                    critical_wrong.append(qid)

            # D1 — ranking
            elif part == "D" and qid == "D1":
                d1_priority_score = _score_d1_ranking(resp, correct)
                is_correct = (d1_priority_score == 3)

            cur.execute("""
                UPDATE hiring_quiz_answers
                SET is_correct = %s, graded_by = 'auto', graded_at = NOW()
                WHERE attempt_id = %s AND question_id = %s
            """, (is_correct, attempt_id, qid))

        summary = {
            "score_a": score_a,
            "score_a_max": 60,
            "score_b": score_b,
            "score_b_max": 22,
            "d1_priority_score": d1_priority_score,
            "written_sections_scored": False,
            "contradiction_count": 0,
            "critical_wrong": critical_wrong,
            "not_sure_critical": not_sure_critical,
            "auto_graded_at": datetime.now(timezone.utc).isoformat(),
        }

        cur.execute("""
            UPDATE hiring_quiz_attempts SET score_summary = %s WHERE id = %s
        """, (json.dumps(summary), attempt_id))
        conn.commit()
        logger.info("auto_grade: attempt %s scored A=%s/60 B=%s/22 D1=%s",
                    attempt_id, score_a, score_b, d1_priority_score)

        return {"attempt_id": attempt_id, "triggers": _build_triggers(summary, attempt_id, cur),
                "summary": summary}

    finally:
        cur.close()
        conn.close()


def _score_d1_ranking(resp: dict, correct: dict) -> int:
    """
    0: clearly wrong (phone first or tablet last)
    1: neither first nor last correct
    2: only first correct (tablet/orders first)
    3: first AND last correct (tablet first, phone last)
    """
    given = resp.get("order", [])
    expected = correct.get("correct_order", [])
    if not given or not expected:
        return 0
    score = 0
    if given[0] == expected[0]:
        score += 2
    if given[-1] == expected[-1]:
        score += 1
    return min(score, 3)


def _build_triggers(summary: dict, attempt_id: int, cur) -> list[dict]:
    triggers = []

    for qid in summary["critical_wrong"]:
        triggers.append({"type": "verbal_retest", "question_id": qid})

    for qid in summary["not_sure_critical"]:
        triggers.append({"type": "not_sure_critical", "question_id": qid})

    if summary["d1_priority_score"] is not None and summary["d1_priority_score"] < 2:
        triggers.append({"type": "d1_wrong_priority"})

    # Current-job flag from notes field
    cur.execute("""
        SELECT c.notes FROM hiring_quiz_attempts a
        JOIN hiring_candidates c ON c.id = a.candidate_id
        WHERE a.id = %s
    """, (attempt_id,))
    row = cur.fetchone()
    if row and row[0]:
        notes = (row[0] or "").lower()
        if any(kw in notes for kw in ("current job", "other job", "still working")):
            triggers.append({"type": "current_job_conflict"})

    return triggers


# ── Phase 1: Contradiction detection ────────────────────────────────────────

# (tick_qid, written_qid, type, severity, description)
CONTRADICTION_PAIRS = [
    ("A2-Q13", "C-Q8",
     "tick_vs_written", "critical",
     "Ticked that hiding mistakes is wrong, but written may show avoidance or 'handle quietly'"),

    ("A4-Q34", "C-Q12",
     "tick_vs_written", "critical",
     "Ticked quiet time = work time, but written says 'wait' or 'check phone'"),

    ("A4-Q38", "C-Q4",
     "tick_vs_written", "moderate",
     "Ticked self-discipline matters, but written self-review avoids accountability"),

    ("A5-Q42", "C-Q20",
     "tick_vs_written", "moderate",
     "Ticked anti-gossip but written answer reveals team-talk culture"),

    ("A6-Q58", "C-Q16",
     "tick_vs_written", "moderate",
     "Ticked sudden leaving hurts team, but commitment answer is vague or contradicts"),

    ("A6-Q51", "D3",
     "tick_vs_written", "moderate",
     "Ticked training is valuable, but step-up answer has no real training plan"),
]


def detect_contradictions(attempt_id: int) -> list[dict]:
    """
    Checks contradiction pairs. Stores flagged pairs in hiring_contradictions.
    All contradictions require human_confirmed before acting on them.
    Returns list of flagged contradictions.
    """
    conn = _conn()
    cur = conn.cursor()
    flagged = []
    try:
        cur.execute("""
            SELECT question_id, raw_answer, skipped
            FROM hiring_quiz_answers
            WHERE attempt_id = %s
        """, (attempt_id,))
        answers_by_q = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

        tick_meta = _load_answers(cur)

        for qa_id, qb_id, ctype, severity, description in CONTRADICTION_PAIRS:
            raw_a, skip_a = answers_by_q.get(qa_id, (None, True))
            raw_b, skip_b = answers_by_q.get(qb_id, (None, True))

            if skip_a or skip_b or raw_a is None or raw_b is None:
                continue

            if _should_flag(qa_id, raw_a, tick_meta):
                cur.execute("""
                    INSERT INTO hiring_contradictions
                        (attempt_id, question_id_a, question_id_b, contradiction_type,
                         severity, description, ai_flagged)
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                    RETURNING id
                """, (attempt_id, qa_id, qb_id, ctype, severity, description))
                cid = cur.fetchone()[0]
                flagged.append({"id": cid, "qa": qa_id, "qb": qb_id,
                                "severity": severity, "description": description})

        if flagged:
            cur.execute("""
                UPDATE hiring_quiz_attempts
                SET score_summary = jsonb_set(
                    COALESCE(score_summary, '{}'::jsonb),
                    '{contradiction_count}',
                    %s::jsonb
                )
                WHERE id = %s
            """, (json.dumps(len(flagged)), attempt_id))

        conn.commit()
        logger.info("detect_contradictions: attempt %s — %s flagged", attempt_id, len(flagged))
        return flagged

    finally:
        cur.close()
        conn.close()


def _should_flag(qa_id: str, raw_a: str, tick_meta: dict) -> bool:
    """
    For Part A tick questions: flag if the tick was wrong OR if the question is critical.
    For non-tick questions: always flag (human will confirm).
    """
    meta = tick_meta.get(qa_id, {})
    if meta.get("part") != "A":
        return True  # non-tick — always send for human review

    correct = meta.get("correct_answer", {})
    resp = _parse_answer(raw_a)
    given = resp.get("answer", "").lower()
    expected = correct.get("answer", "").lower() if isinstance(correct, dict) else ""

    if given != expected:
        return True  # tick was wrong → contradiction likely
    # Tick was right but still flag critical pairs for human review
    return meta.get("severity") == "critical"


# ── Phase 2: Claude rubric scoring ──────────────────────────────────────────

RUBRIC_PROMPT = """You are scoring a job application answer for a bakery in Phnom Penh, Cambodia.
Grade honestly — do not be generous with vague or one-line answers.

Question: {question_en}
Rubric guidance: {rubric}
Candidate's answer: {answer}

Score each dimension 0–3:

completeness_score:
  0 = blank or completely off-topic
  1 = answers only one small part of the question
  2 = answers the main point but misses important parts
  3 = fully answers with action + reason + prevention or follow-up

specificity_score:
  0 = generic ("be good", "try hard", no real content)
  1 = vague but related to the topic
  2 = specific action mentioned
  3 = specific action + reason + follow-up or context

responsibility_score:
  0 = blames others, avoids the issue, or denies
  1 = admits but proposes no fix
  2 = reports and fixes
  3 = reports, fixes, and prevents repeat

Return ONLY valid JSON:
{{
  "completeness_score": 0-3,
  "specificity_score": 0-3,
  "responsibility_score": 0-3,
  "notes": "one sentence on the most important gap or strength"
}}"""


def draft_rubric_scores(attempt_id: int) -> dict:
    """
    Calls Claude to score Part C, D2, D3, D4, and D-Final.
    Stores completeness_score and grader_notes on each answer row.
    Returns {question_id: rubric_scores_dict}.
    """
    try:
        from shared.ai_client import get_client
        client = get_client()
    except Exception as e:
        logger.error("draft_rubric_scores: AI client unavailable — %s", e)
        return {}

    conn = _conn()
    cur = conn.cursor()
    results = {}

    try:
        cur.execute("""
            SELECT a.id, a.question_id, a.raw_answer,
                   q.question_text_en, q.correct_answer, q.answer_type
            FROM hiring_quiz_answers a
            JOIN hiring_quiz_questions q ON q.id = a.question_id
            WHERE a.attempt_id = %s
              AND q.part IN ('C', 'D')
              AND q.answer_type IN ('free_text', 'rewrite')
              AND a.skipped = FALSE
              AND a.raw_answer IS NOT NULL
        """, (attempt_id,))
        rows = cur.fetchall()

        for ans_id, qid, raw_answer, question_en, correct_answer, _ in rows:
            rubric = ""
            if isinstance(correct_answer, dict):
                rubric = correct_answer.get("rubric", "")

            resp = _parse_answer(raw_answer)
            answer_text = resp.get("text", "") or resp.get("answer", "") or raw_answer or ""

            if not answer_text.strip():
                continue

            prompt = RUBRIC_PROMPT.format(
                question_en=question_en,
                rubric=rubric,
                answer=answer_text,
            )

            try:
                response = client.messages.create(
                    model="claude-opus-4-7",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = response.content[0].text.strip()
                scores = json.loads(raw)
                scores["scored_at"] = datetime.now(timezone.utc).isoformat()

                cur.execute("""
                    UPDATE hiring_quiz_answers
                    SET completeness_score = %s,
                        grader_notes = %s,
                        graded_by = 'claude_opus',
                        graded_at = NOW()
                    WHERE id = %s
                """, (
                    scores.get("completeness_score", 0),
                    json.dumps(scores),
                    ans_id,
                ))
                results[qid] = scores
                logger.info("rubric: %s comp=%s spec=%s resp=%s",
                            qid, scores.get("completeness_score"),
                            scores.get("specificity_score"),
                            scores.get("responsibility_score"))

            except Exception as e:
                logger.error("draft_rubric_scores: failed on %s — %s", qid, e)
                continue

        cur.execute("""
            UPDATE hiring_quiz_attempts
            SET score_summary = jsonb_set(
                COALESCE(score_summary, '{}'::jsonb),
                '{written_sections_scored}',
                'true'::jsonb
            )
            WHERE id = %s
        """, (attempt_id,))
        conn.commit()
        return results

    finally:
        cur.close()
        conn.close()


# ── Phase 2: Risk profile builder ────────────────────────────────────────────

def build_risk_profile(attempt_id: int) -> dict:
    """
    Aggregates all scores into an 8-category risk profile.
    Stores result in hiring_quiz_attempts.risk_profile.
    Call after draft_rubric_scores completes.
    """
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT score_summary FROM hiring_quiz_attempts WHERE id = %s", (attempt_id,))
        row = cur.fetchone()
        summary = row[0] if row and row[0] else {}

        score_a = summary.get("score_a", 0)
        score_b = summary.get("score_b", 0)
        critical_wrong = set(summary.get("critical_wrong", []))
        not_sure_critical = set(summary.get("not_sure_critical", []))
        contradiction_count = summary.get("contradiction_count", 0)
        d1_score = summary.get("d1_priority_score")

        # Load rubric scores from grader_notes (stored as JSON in TEXT field)
        cur.execute("""
            SELECT a.question_id, a.completeness_score, a.grader_notes
            FROM hiring_quiz_answers a
            JOIN hiring_quiz_questions q ON q.id = a.question_id
            WHERE a.attempt_id = %s AND q.part IN ('C','D')
        """, (attempt_id,))
        rubric_by_q: dict[str, dict] = {}
        for qid, comp, notes_raw in cur.fetchall():
            try:
                notes = json.loads(notes_raw) if notes_raw else {}
            except Exception:
                notes = {}
            notes["completeness_score"] = comp or 0
            rubric_by_q[qid] = notes

        def written_avg(qids: list[str], dim: str) -> float:
            vals = [rubric_by_q[q].get(dim, 0) for q in qids if q in rubric_by_q]
            return sum(vals) / len(vals) if vals else 0.0

        # Honesty
        honesty_wrong = len({"A2-Q13", "A1-Q7"} & critical_wrong)
        honesty_written = written_avg(["C-Q8", "C-Q4"], "responsibility_score")
        if honesty_wrong == 0 and honesty_written >= 2.5 and contradiction_count == 0:
            honesty = "strong"
        elif honesty_wrong == 0 and honesty_written >= 1.5:
            honesty = "medium"
        else:
            honesty = "weak"

        # Schedule clarity
        schedule_wrong = len({"A1-Q5", "A1-Q7", "A1-Q6"} & critical_wrong)
        schedule_ns = len({"A1-Q5", "A1-Q6"} & not_sure_critical)
        if schedule_wrong == 0 and schedule_ns == 0:
            schedule = "clean"
        elif schedule_wrong <= 1 or schedule_ns <= 1:
            schedule = "unclear"
        else:
            schedule = "red_flag"

        # Completion discipline
        comp_avg = written_avg(list(rubric_by_q.keys()), "completeness_score")
        if comp_avg >= 2.5:
            completion = "strong"
        elif comp_avg >= 1.5:
            completion = "half_answer_risk"
        else:
            completion = "weak"

        # Customer instinct
        customer_wrong = len({"B-Q3", "B-Q8", "B-Q9", "B-Q19", "B-Q21", "B-Q22"} & critical_wrong)
        customer_written = written_avg(["C-Q12", "C-Q20"], "specificity_score")
        if customer_wrong == 0 and customer_written >= 2.0:
            customer = "strong"
        elif customer_wrong <= 1:
            customer = "trainable"
        else:
            customer = "weak"

        # Quiet-time work ethic
        quiet_wrong = len({"A4-Q34", "A4-Q38"} & (critical_wrong | not_sure_critical))
        quiet_written = written_avg(["C-Q12"], "completeness_score")
        if quiet_wrong == 0 and quiet_written >= 2.0:
            quiet = "strong"
        elif quiet_wrong == 0:
            quiet = "unclear"
        else:
            quiet = "weak"

        # Experience credibility
        a_pct = score_a / 60
        if a_pct >= 0.90:
            experience = "verified"
        elif a_pct >= 0.80:
            experience = "unclear"
        else:
            experience = "inflated"

        # Leadership potential
        leadership_written = written_avg(["C-Q20", "D3"], "specificity_score")
        if leadership_written >= 2.5:
            leadership = "strong"
        elif leadership_written >= 1.5:
            leadership = "emerging"
        else:
            leadership = "none"

        # Trial recommendation
        critical_count = len(critical_wrong)
        if critical_count >= 3 or honesty == "weak" or schedule == "red_flag":
            recommendation = "reject"
        elif critical_count == 0 and honesty == "strong" and a_pct >= 0.90:
            recommendation = "hire"
        else:
            recommendation = "trial"

        profile = {
            "honesty_logic": honesty,
            "schedule_clarity": schedule,
            "completion_discipline": completion,
            "customer_instinct": customer,
            "quiet_time_work_ethic": quiet,
            "experience_credibility": experience,
            "leadership_potential": leadership,
            "trial_recommendation": recommendation,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        cur.execute("""
            UPDATE hiring_quiz_attempts SET risk_profile = %s WHERE id = %s
        """, (json.dumps(profile), attempt_id))
        conn.commit()
        logger.info("build_risk_profile: attempt %s → %s", attempt_id, recommendation)
        return profile

    finally:
        cur.close()
        conn.close()
