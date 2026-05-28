"""
Scoring engine for the hiring bot.

Phase 1 (in-session, immediate):
  auto_grade(attempt_id)                   — Part A, B, D1 grading; stores score_summary +
                                             is_correct per answer row; returns trigger list.
                                             Produces NO contradiction rows — all objective
                                             flags (critical_wrong, not_sure_critical, D1 score)
                                             are already in score_summary.

Phase 2 (post-session, async — runs after session ends):
  draft_rubric_scores(attempt_id)          — Claude Opus scores Part C, D2–D4, Final written
                                             answers using completeness/specificity/responsibility
                                             rubric (0–3 each); stores in grader_notes + completeness_score.
  detect_semantic_contradictions(attempt_id) — runs AFTER rubric scoring. Creates rows in
                                             hiring_contradictions ONLY for real semantic conflicts:
                                             tick=correct AND written=low responsibility. This is the
                                             "polished liar" case — they know the right answer but
                                             reveal opposite behavior in writing. Also detects
                                             written-vs-written inconsistencies.
  build_risk_profile(attempt_id)           — aggregates all scores into 8-category risk_profile JSONB.

Design rule: hiring_contradictions contains only confirmed semantic conflicts.
Wrong ticks alone are NOT contradictions — they are objective failures already in score_summary.

Schema reference (actual DB columns):
  hiring_quiz_answers: id, attempt_id, question_id, raw_answer TEXT, normalized_answer,
                       is_correct BOOL, completeness_score INT, contradiction_score INT,
                       time_spent_seconds, skipped, graded_by, graded_at, grader_notes TEXT
  hiring_quiz_attempts: ..., score_summary JSONB, risk_profile JSONB,
                        attempt_status TEXT, abandoned_at_question_id TEXT, resume_count INT
  hiring_sessions: ..., status TEXT, resume_count INT, reopened_by TEXT
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


# ── Phase 2: Semantic contradiction detection ────────────────────────────────
#
# DESIGN: Phase 1 (auto_grade) produces NO contradiction rows.
# All objective flags (wrong tick, not_sure, D1, schedule) live in score_summary.
# Only Phase 2 — after written answers have been rubric-scored — can detect
# whether a candidate's written behavior contradicts their tick answer.
#
# The case that matters most: tick=CORRECT but written=low responsibility score.
# This is the "polished liar" — they know the right answer to tick, then reveal
# the real behavior in writing. That person is more dangerous than someone who
# simply ticked wrong.
#
# Contradiction pairs: (tick_qid, written_qid, type, severity, description)
CONTRADICTION_PAIRS = [
    # Strong pairs — direct logical link between tick value and written behavior

    ("A2-Q13", "C-Q8",
     "tick_vs_written", "critical",
     "Ticked hiding mistakes is worse than honest mistake, but written answer avoids reporting or 'handles quietly'"),

    ("A4-Q34", "C-Q12",
     "tick_vs_written", "critical",
     "Ticked quiet time should be productive, but written describes waiting, resting, or checking phone"),

    ("A4-Q38", "C-Q12",
     "tick_vs_written", "critical",
     "Ticked good staff work even when not watched, but quiet-time answer shows passive or phone behavior"),

    # Revised from C-Q20 (systems thinking / resignation — weak link):
    # C-Q11 directly asks what they do when there is a problem with another staff member.
    # A gossip-culture person writes "tell others" or "let it go" rather than going to management.
    ("A5-Q42", "C-Q11",
     "tick_vs_written", "moderate",
     "Ticked gossip is harmful, but written conflict-handling answer reveals sideways talk vs management escalation"),

    ("A6-Q58", "C-Q16",
     "tick_vs_written", "moderate",
     "Ticked sudden leaving hurts the team, but resignation reasoning is self-focused or vague"),

    ("A6-Q51", "D3",
     "tick_vs_written", "moderate",
     "Ticked training costs time and money, but step-up answer shows no real training plan or system thinking"),
]

# Written-vs-written pairs checked in Phase 2 after rubric scoring
# (tick_qid is None for these — both sides are free-text)
WRITTEN_CONTRADICTION_PAIRS = [
    # C-Q3 "what mistake did you make and what did you learn?" vs C-Q8 "friend asks to hide mistake"
    # If C-Q3 says "I told my boss" but C-Q8 says "I would help my friend quietly" → honesty inconsistency
    ("C-Q3", "C-Q8",
     "written_vs_written", "critical",
     "Claims to have reported past mistake (C-Q3) but says would help friend hide mistake (C-Q8)"),
]


def detect_semantic_contradictions(attempt_id: int) -> list[dict]:
    """
    Phase 2 function — runs AFTER draft_rubric_scores() has scored written answers.

    Creates rows in hiring_contradictions when:
      - Tick answer is CORRECT but written answer scores responsibility ≤ 1
        (the polished liar: knows what to tick, reveals opposite behavior in writing)
      - Written-vs-written: one written answer contradicts another after rubric scoring

    Does NOT run in Phase 1. Phase 1 objective flags live in score_summary.
    All stored rows require human_confirmed before any decision is made.
    """
    conn = _conn()
    cur = conn.cursor()
    flagged = []

    try:
        # Load all answers for this attempt (tick is_correct + written rubric scores)
        cur.execute("""
            SELECT question_id, is_correct, completeness_score, grader_notes, skipped
            FROM hiring_quiz_answers
            WHERE attempt_id = %s
        """, (attempt_id,))
        answers: dict[str, dict] = {}
        for qid, is_correct, comp, notes_raw, skipped in cur.fetchall():
            try:
                notes = json.loads(notes_raw) if notes_raw else {}
            except Exception:
                notes = {}
            notes["completeness_score"] = comp or 0
            answers[qid] = {
                "is_correct": is_correct,
                "skipped": skipped,
                "responsibility": notes.get("responsibility_score"),
                "specificity": notes.get("specificity_score"),
                "completeness": notes.get("completeness_score", 0),
            }

        def _insert_contradiction(qa_id, qb_id, ctype, severity, description):
            cur.execute("""
                INSERT INTO hiring_contradictions
                    (attempt_id, question_id_a, question_id_b, contradiction_type,
                     severity, description, ai_flagged)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT DO NOTHING
                RETURNING id
            """, (attempt_id, qa_id, qb_id, ctype, severity, description))
            row = cur.fetchone()
            if row:
                flagged.append({"id": row[0], "qa": qa_id, "qb": qb_id,
                                "severity": severity, "description": description})

        # ── Tick-vs-written pairs ─────────────────────────────────────────────
        for qa_id, qb_id, ctype, severity, description in CONTRADICTION_PAIRS:
            ans_a = answers.get(qa_id, {})
            ans_b = answers.get(qb_id, {})

            if ans_a.get("skipped") or ans_b.get("skipped"):
                continue

            # Skip if written answer hasn't been rubric-scored yet
            if ans_b.get("responsibility") is None:
                continue

            tick_correct = ans_a.get("is_correct")
            written_responsibility = ans_b.get("responsibility", 2)
            written_completeness = ans_b.get("completeness", 0)

            # Only flag when:
            # tick=CORRECT AND written answer shows avoidance/blame/no fix (responsibility ≤ 1)
            # AND the written answer actually says something (completeness ≥ 1, not blank)
            if (tick_correct is True
                    and written_responsibility <= 1
                    and written_completeness >= 1):
                _insert_contradiction(qa_id, qb_id, ctype, severity, description)

        # ── Written-vs-written pairs ──────────────────────────────────────────
        for qa_id, qb_id, ctype, severity, description in WRITTEN_CONTRADICTION_PAIRS:
            ans_a = answers.get(qa_id, {})
            ans_b = answers.get(qb_id, {})

            if ans_a.get("skipped") or ans_b.get("skipped"):
                continue
            if ans_a.get("responsibility") is None or ans_b.get("responsibility") is None:
                continue

            # C-Q3 high responsibility + C-Q8 low responsibility = inconsistency
            # (claimed to report their own mistake, but would hide a friend's)
            resp_a = ans_a.get("responsibility", 0)
            resp_b = ans_b.get("responsibility", 0)
            if resp_a >= 2 and resp_b <= 1 and ans_b.get("completeness", 0) >= 1:
                _insert_contradiction(qa_id, qb_id, ctype, severity, description)

        # Update contradiction_count in score_summary
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
        logger.info("detect_semantic_contradictions: attempt %s — %s found", attempt_id, len(flagged))
        return flagged

    finally:
        cur.close()
        conn.close()


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

        # ── Category-gated scoring ───────────────────────────────────────────
        # Rule: critical wrong answers on category-specific questions OVERRIDE
        # the percentage-based calculation for that category.
        # A 95% score with A2-Q13 wrong is NOT a strong honesty result.

        a_pct = score_a / 60

        # Honesty — gated on honesty-specific critical questions
        # Any wrong answer on hiding mistakes (A2-Q13) or schedule honesty (A1-Q7)
        # forces "weak" regardless of overall score or written quality.
        honesty_critical_wrong = {"A2-Q13", "A1-Q7"} & critical_wrong
        honesty_critical_ns = {"A2-Q13"} & not_sure_critical
        honesty_written = written_avg(["C-Q8", "C-Q4"], "responsibility_score")
        if honesty_critical_wrong or honesty_critical_ns:
            honesty = "weak"  # override — specific question failed
        elif honesty_written >= 2.5 and contradiction_count == 0:
            honesty = "strong"
        elif honesty_written >= 1.5:
            honesty = "medium"
        else:
            honesty = "medium"  # written sections not scored yet

        # Schedule clarity — gated on schedule-specific questions
        # A1-Q5 (busy tomorrow) or A1-Q7 wrong = at minimum "unclear"
        schedule_critical_wrong = {"A1-Q5", "A1-Q7"} & critical_wrong
        schedule_ns = len({"A1-Q5", "A1-Q6"} & not_sure_critical)
        schedule_other_wrong = len({"A1-Q6"} & critical_wrong)
        if len(schedule_critical_wrong) >= 2 or (schedule_critical_wrong and schedule_ns):
            schedule = "red_flag"
        elif schedule_critical_wrong or schedule_ns or schedule_other_wrong:
            schedule = "unclear"
        else:
            schedule = "clean"

        # Completion discipline — based purely on written completeness scores
        comp_avg = written_avg(list(rubric_by_q.keys()), "completeness_score")
        if comp_avg >= 2.5:
            completion = "strong"
        elif comp_avg >= 1.5:
            completion = "half_answer_risk"
        else:
            completion = "weak"

        # Customer instinct — gated on customer scenario questions
        # Wrong on critical B scenarios AND low written customer instinct = weak
        customer_critical_wrong = {"B-Q3", "B-Q8", "B-Q9", "B-Q19", "B-Q21", "B-Q22"} & critical_wrong
        customer_written = written_avg(["C-Q21", "C-Q22", "C-Q23", "C-Q24"], "specificity_score")
        if len(customer_critical_wrong) >= 2:
            customer = "weak"
        elif customer_written >= 2.0 and not customer_critical_wrong:
            customer = "strong"
        else:
            customer = "trainable"

        # Quiet-time work ethic — gated on A4 questions AND C-Q12
        # Wrong on A4-Q34 or A4-Q38 overrides to "weak" regardless of written
        quiet_critical_wrong = {"A4-Q34", "A4-Q38"} & critical_wrong
        quiet_critical_ns = {"A4-Q34", "A4-Q38"} & not_sure_critical
        quiet_written = written_avg(["C-Q12"], "completeness_score")
        if quiet_critical_wrong:
            quiet = "weak"  # override — core value failed
        elif quiet_critical_ns:
            quiet = "unclear"  # not sure on a core value = uncertain
        elif quiet_written >= 2.0:
            quiet = "strong"
        else:
            quiet = "unclear"

        # Experience credibility — still uses a_pct as base, but food safety
        # and dishonesty critical wrongs reduce credibility even at high scores
        safety_wrong = {"A2-Q20"} & critical_wrong  # floor food can be sold = disqualifying
        if safety_wrong:
            experience = "red_flag"  # food safety failure overrides everything
        elif a_pct >= 0.90 and not honesty_critical_wrong:
            experience = "verified"
        elif a_pct >= 0.80:
            experience = "unclear"
        else:
            experience = "inflated"

        # Leadership potential — pure written score, no tick override
        leadership_written = written_avg(["C-Q20", "D3"], "specificity_score")
        if leadership_written >= 2.5:
            leadership = "strong"
        elif leadership_written >= 1.5:
            leadership = "emerging"
        else:
            leadership = "none"

        # Trial recommendation — category results gate the final decision
        critical_count = len(critical_wrong)
        is_honesty_failure = honesty == "weak"
        is_safety_failure = experience == "red_flag"
        is_schedule_failure = schedule == "red_flag"

        if is_honesty_failure or is_safety_failure or is_schedule_failure or critical_count >= 3:
            recommendation = "reject"
        elif critical_count == 0 and honesty == "strong" and schedule == "clean" and a_pct >= 0.90:
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
