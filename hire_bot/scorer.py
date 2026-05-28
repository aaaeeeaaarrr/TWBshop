"""
Scoring engine for the hiring bot.

Phase 1 (in-session, immediate):
  auto_grade(attempt_id)         — Part A, B, D1; stores score_summary; returns triggers
  detect_contradictions(attempt_id) — rule-based pairs; stores to hiring_contradictions

Phase 2 (post-session, async):
  draft_rubric_scores(attempt_id)  — Claude grades Part C, D2–D4, Final; stores ai_score_details
  build_risk_profile(attempt_id)   — aggregates all scores into risk_profile JSONB

NOT in this module: the bot conversation flow, session/token management, coaching messages.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import psycopg2

logger = logging.getLogger(__name__)


# ── Connection helper ────────────────────────────────────────────────────────

def _conn():
    import sys, os
    sys.path.insert(0, '/root/TWBshop')
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)


# ── Part A / B correct answers (loaded once from DB) ────────────────────────

_answer_cache: dict = {}

def _load_answers(cur) -> dict:
    """Returns {question_id: {correct_answer, severity_if_wrong, requires_verbal_retest, part}}"""
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


# ── Phase 1: Auto-grade ──────────────────────────────────────────────────────

def auto_grade(attempt_id: int) -> dict:
    """
    Grades Part A, Part B, and D1 for a completed attempt.
    Stores score_summary in hiring_quiz_attempts.
    Returns a triggers dict used by the bot to decide follow-up questions.
    """
    conn = _conn()
    cur = conn.cursor()
    try:
        answers = _load_answers(cur)

        cur.execute("""
            SELECT a.question_id, a.response_raw, a.skipped
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

        for qid, response_raw, skipped in rows:
            if skipped or response_raw is None:
                continue
            meta = answers.get(qid)
            if not meta:
                continue

            part = meta["part"]
            correct = meta["correct_answer"]
            severity = meta["severity"]
            verbal = meta["requires_verbal_retest"]

            # Part A — yes/no/not_sure
            if part == "A":
                given = response_raw.get("answer", "").lower() if isinstance(response_raw, dict) else ""
                expected = correct.get("answer", "").lower() if isinstance(correct, dict) else ""

                if given == "not_sure" and severity in ("critical", "moderate"):
                    not_sure_critical.append(qid)
                elif given == expected:
                    score_a += 1
                else:
                    if severity == "critical":
                        critical_wrong.append(qid)

            # Part B — single_choice
            elif part == "B":
                given = response_raw.get("answer", "").upper() if isinstance(response_raw, dict) else ""
                expected = correct.get("answer", "").upper() if isinstance(correct, dict) else ""
                if given == expected:
                    score_b += 1
                elif severity == "critical":
                    critical_wrong.append(qid)

            # D1 — ranking (orders/tablet must be index 0, personal phone last)
            elif part == "D" and qid == "D1":
                d1_priority_score = _score_d1_ranking(response_raw, correct)

        summary = {
            "score_a": score_a,
            "score_a_max": 60,
            "score_b": score_b,
            "score_b_max": 22,
            "d1_priority_score": d1_priority_score,   # 0–3
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

        return _build_triggers(summary, attempt_id, cur)

    finally:
        cur.close()
        conn.close()


def _score_d1_ranking(response_raw: dict, correct: dict) -> int:
    """
    Scores D1 priority ranking on 0–3 scale.
    3: orders/tablet first AND personal phone last
    2: orders/tablet first but phone not last
    1: neither condition met but some correct adjacencies
    0: clearly wrong order (e.g. personal phone first, tablet last)
    """
    if not response_raw or not correct:
        return 0
    given = response_raw.get("order", [])
    expected = correct.get("correct_order", [])
    if not given or not expected:
        return 0

    score = 0
    if given and expected and given[0] == expected[0]:
        score += 2  # first item correct (orders/tablet)
    if given and expected and given[-1] == expected[-1]:
        score += 1  # last item correct (personal phone)
    return min(score, 3)


def _build_triggers(summary: dict, attempt_id: int, cur) -> dict:
    """
    Returns curated follow-up triggers based on auto-grade results.
    The bot uses this dict to decide which follow-up questions to ask.
    """
    triggers = []

    # Critical wrong answers → verbal retest required
    for qid in summary["critical_wrong"]:
        triggers.append({"type": "verbal_retest", "question_id": qid})

    # "Not sure" on critical questions → clarification
    for qid in summary["not_sure_critical"]:
        triggers.append({"type": "not_sure_critical", "question_id": qid})

    # D1 wrong priority → schedule risk follow-up
    if summary["d1_priority_score"] is not None and summary["d1_priority_score"] < 2:
        triggers.append({"type": "d1_wrong_priority"})

    # Check for schedule risk from candidate profile
    cur.execute("""
        SELECT c.current_job, c.notes
        FROM hiring_quiz_attempts a
        JOIN hiring_candidates c ON c.id = a.candidate_id
        WHERE a.id = %s
    """, (attempt_id,))
    row = cur.fetchone()
    if row:
        current_job, notes = row
        if current_job:
            triggers.append({"type": "current_job_conflict", "job": current_job})

    return {"attempt_id": attempt_id, "triggers": triggers, "summary": summary}


# ── Phase 1: Contradiction detection ────────────────────────────────────────

# Defined pairs: (tick_question_id, written_question_id, contradiction_type, severity, description)
CONTRADICTION_PAIRS = [
    # Hiding mistakes: A2-Q13 (hiding mistake is worse) vs C-Q8 (how to handle a mistake at work)
    ("A2-Q13", "C-Q8",
     "tick_vs_written", "critical",
     "Ticked that hiding mistakes is wrong, but written answer may show avoidance or 'handle quietly'"),

    # Quiet time: A4-Q34 (quiet time = find work) vs C-Q12 (what do you do in quiet time?)
    ("A4-Q34", "C-Q12",
     "tick_vs_written", "critical",
     "Ticked that quiet time should be productive, but written answer says 'wait' or 'find customers'"),

    # Working without being watched: A4-Q38 (good staff work when not watched) vs C-Q4 (what would old manager say to improve?)
    ("A4-Q38", "C-Q4",
     "tick_vs_written", "moderate",
     "Ticked that self-discipline matters, but written self-review avoids accountability"),

    # Gossip: A5-Q42 (gossip is harmful) vs C-Q20 (how to make the shop run smoothly without you?)
    ("A5-Q42", "C-Q20",
     "tick_vs_written", "moderate",
     "Ticked anti-gossip, but written answer reveals team-talk patterns"),

    # Resignation responsibility: A6-Q58 (sudden resignation hurts the team) vs written start date / commitment
    ("A6-Q58", "C-Q16",
     "tick_vs_written", "moderate",
     "Ticked that sudden leaving hurts team, but start date or commitment answer is vague"),

    # Training mindset: A6-Q51 (training new staff costs time/money) vs D3 (what to do if staff won't follow training)
    ("A6-Q51", "D3",
     "tick_vs_written", "moderate",
     "Ticked training is valuable, but step-up answer shows no real training plan"),
]


def detect_contradictions(attempt_id: int) -> list[dict]:
    """
    Checks contradiction pairs for this attempt.
    Stores each detected contradiction in hiring_contradictions.
    Returns list of flagged contradictions.
    """
    conn = _conn()
    cur = conn.cursor()
    flagged = []
    try:
        # Load all written answers for this attempt
        cur.execute("""
            SELECT question_id, response_raw, skipped
            FROM hiring_quiz_answers
            WHERE attempt_id = %s
        """, (attempt_id,))
        answers_by_q = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

        tick_answers = _load_answers(cur)

        for qa_id, qb_id, ctype, severity, description in CONTRADICTION_PAIRS:
            resp_a, skip_a = answers_by_q.get(qa_id, (None, True))
            resp_b, skip_b = answers_by_q.get(qb_id, (None, True))

            if skip_a or skip_b or resp_a is None or resp_b is None:
                continue

            # For tick questions: check if answer is wrong (already flagged by auto_grade)
            # For contradictions we look for semantic mismatch — flag all pairs where
            # at least one side is problematic (human confirms via Telegram button)
            is_flagged = _check_pair(qa_id, resp_a, qb_id, resp_b, tick_answers)
            if is_flagged:
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
        logger.info("detect_contradictions: attempt %s — %s flagged", attempt_id, len(flagged))
        return flagged

    finally:
        cur.close()
        conn.close()


def _check_pair(qa_id: str, resp_a: dict, qb_id: str, resp_b: dict,
                tick_answers: dict) -> bool:
    """
    Returns True if this pair shows a likely contradiction.
    For Part A tick questions: checks if the tick answer was wrong.
    All flagged pairs go to human confirmation — we flag liberally, not conservatively.
    """
    meta_a = tick_answers.get(qa_id, {})
    part_a = meta_a.get("part", "")

    if part_a == "A":
        # Tick was wrong → likely contradiction with anything written
        correct = meta_a.get("correct_answer", {})
        given = resp_a.get("answer", "").lower() if isinstance(resp_a, dict) else ""
        expected = correct.get("answer", "").lower() if isinstance(correct, dict) else ""
        if given != expected:
            return True
        # Tick was right but written answer may still contradict — flag for human review
        # on critical pairs
        severity = meta_a.get("severity", "minor")
        return severity == "critical"

    # For written-vs-written: always flag for human review (Claude will score later)
    return True


# ── Phase 2: Claude rubric scoring ──────────────────────────────────────────

RUBRIC_PROMPT = """You are scoring a job application answer for a bakery in Phnom Penh, Cambodia.
The candidate answered in English or Khmer (or both). Grade honestly — do not be generous with vague answers.

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

responsibility_score (how the candidate handles mistakes or problems):
  0 = blames others, avoids the issue, or denies
  1 = admits but proposes no fix
  2 = reports and fixes
  3 = reports, fixes, and prevents it repeating

Return ONLY valid JSON, no explanation outside it:
{
  "completeness_score": 0-3,
  "specificity_score": 0-3,
  "responsibility_score": 0-3,
  "notes": "one sentence explaining the most important gap or strength"
}"""


def draft_rubric_scores(attempt_id: int) -> dict:
    """
    Calls Claude to score Part C, D2, D3, D4, and D-Final for this attempt.
    Stores scores in hiring_quiz_answers.ai_score_details.
    Updates score_summary.written_sections_scored = true when done.
    Returns dict of {question_id: scores}.
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
            SELECT a.id, a.question_id, a.response_raw,
                   q.question_text_en, q.correct_answer
            FROM hiring_quiz_answers a
            JOIN hiring_quiz_questions q ON q.id = a.question_id
            WHERE a.attempt_id = %s
              AND q.part IN ('C', 'D')
              AND q.answer_type IN ('free_text', 'rewrite')
              AND a.skipped = FALSE
              AND a.response_raw IS NOT NULL
        """, (attempt_id,))
        rows = cur.fetchall()

        for ans_id, qid, response_raw, question_en, correct_answer in rows:
            rubric = ""
            if isinstance(correct_answer, dict):
                rubric = correct_answer.get("rubric", "")

            answer_text = ""
            if isinstance(response_raw, dict):
                answer_text = response_raw.get("text", "") or response_raw.get("answer", "")

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
                    SET ai_score = %s,
                        ai_score_details = %s,
                        scored_by = 'claude_opus'
                    WHERE id = %s
                """, (
                    (scores.get("completeness_score", 0) +
                     scores.get("specificity_score", 0) +
                     scores.get("responsibility_score", 0)),
                    json.dumps(scores),
                    ans_id,
                ))
                results[qid] = scores
                logger.info("draft_rubric_scores: %s scored comp=%s spec=%s resp=%s",
                            qid, scores.get("completeness_score"),
                            scores.get("specificity_score"),
                            scores.get("responsibility_score"))

            except Exception as e:
                logger.error("draft_rubric_scores: failed on %s — %s", qid, e)
                continue

        # Mark written sections as scored
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
        logger.info("draft_rubric_scores: attempt %s — %s written answers scored",
                    attempt_id, len(results))
        return results

    finally:
        cur.close()
        conn.close()


# ── Phase 2: Risk profile builder ────────────────────────────────────────────

def build_risk_profile(attempt_id: int) -> dict:
    """
    Aggregates all scores into an 8-category risk profile.
    Stores result in hiring_quiz_attempts.risk_profile.
    Should be called after draft_rubric_scores completes.
    """
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT score_summary FROM hiring_quiz_attempts WHERE id = %s
        """, (attempt_id,))
        row = cur.fetchone()
        summary = row[0] if row and row[0] else {}

        score_a = summary.get("score_a", 0)
        score_b = summary.get("score_b", 0)
        critical_wrong = set(summary.get("critical_wrong", []))
        not_sure_critical = set(summary.get("not_sure_critical", []))
        contradiction_count = summary.get("contradiction_count", 0)
        d1_score = summary.get("d1_priority_score")

        # Load rubric scores for written answers
        cur.execute("""
            SELECT a.question_id, a.ai_score_details, a.skipped
            FROM hiring_quiz_answers a
            JOIN hiring_quiz_questions q ON q.id = a.question_id
            WHERE a.attempt_id = %s
        """, (attempt_id,))
        written_scores: dict[str, dict] = {}
        for qid, details, skipped in cur.fetchall():
            if not skipped and details:
                written_scores[qid] = details if isinstance(details, dict) else {}

        def _written_avg(qids: list[str], dim: str) -> float:
            vals = [written_scores[q].get(dim, 0) for q in qids if q in written_scores]
            return sum(vals) / len(vals) if vals else 0.0

        # ── Honesty logic ──
        # A2-Q13 (hiding mistake), A1-Q7 (schedule honesty), C-Q8 (mistake handling rubric)
        honesty_wrong = len({"A2-Q13", "A1-Q7"} & critical_wrong)
        honesty_written = _written_avg(["C-Q8", "C-Q4"], "responsibility_score")
        if honesty_wrong == 0 and honesty_written >= 2.5 and contradiction_count == 0:
            honesty = "strong"
        elif honesty_wrong == 0 and honesty_written >= 1.5:
            honesty = "medium"
        else:
            honesty = "weak"

        # ── Schedule clarity ──
        # A1-Q5 (busy tomorrow), A1-Q6 (school schedule), A1-Q7 (hiding schedule)
        schedule_wrong = len({"A1-Q5", "A1-Q7", "A1-Q6"} & critical_wrong)
        schedule_ns = len({"A1-Q5", "A1-Q6"} & not_sure_critical)
        if schedule_wrong == 0 and schedule_ns == 0:
            schedule = "clean"
        elif schedule_wrong <= 1 or schedule_ns <= 1:
            schedule = "unclear"
        else:
            schedule = "red_flag"

        # ── Completion discipline ──
        # Part C written completeness scores
        completion_avg = _written_avg(list(written_scores.keys()), "completeness_score")
        if completion_avg >= 2.5:
            completion = "strong"
        elif completion_avg >= 1.5:
            completion = "half_answer_risk"
        else:
            completion = "weak"

        # ── Customer instinct ──
        # B-questions about customer situations, C-Q12 (quiet time = find customers?)
        customer_wrong = len({"B-Q3", "B-Q8", "B-Q9", "B-Q19", "B-Q21", "B-Q22"} & critical_wrong)
        customer_written = _written_avg(["C-Q12", "C-Q20"], "specificity_score")
        if customer_wrong == 0 and customer_written >= 2.0:
            customer = "strong"
        elif customer_wrong <= 1:
            customer = "trainable"
        else:
            customer = "weak"

        # ── Quiet-time work ethic ──
        # A4-Q34, A4-Q38 (work without watching), C-Q12 written score
        quiet_wrong = len({"A4-Q34", "A4-Q38"} & (critical_wrong | not_sure_critical))
        quiet_written = _written_avg(["C-Q12"], "completeness_score")
        if quiet_wrong == 0 and quiet_written >= 2.0:
            quiet = "strong"
        elif quiet_wrong == 0:
            quiet = "unclear"
        else:
            quiet = "weak"

        # ── Experience credibility ──
        # High Part A + B = credible. Low A with experience claimed = inflated.
        a_pct = score_a / 60
        b_pct = score_b / 22
        if a_pct >= 0.93 and b_pct >= 0.95:
            experience = "verified"
        elif a_pct >= 0.85:
            experience = "verified"
        elif a_pct >= 0.75:
            experience = "unclear"
        else:
            experience = "inflated"

        # ── Leadership potential ──
        # C-Q20 (run smoothly without me) specificity + D3 (training problem) completeness
        leadership_written = _written_avg(["C-Q20", "D3"], "specificity_score")
        if leadership_written >= 2.5:
            leadership = "strong"
        elif leadership_written >= 1.5:
            leadership = "emerging"
        else:
            leadership = "none"

        # ── Trial recommendation ──
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
        logger.info("build_risk_profile: attempt %s → recommendation=%s", attempt_id, recommendation)
        return profile

    finally:
        cur.close()
        conn.close()
