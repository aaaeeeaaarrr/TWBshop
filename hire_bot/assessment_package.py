"""
Assessment evidence package builder — Sonnet's job.

Collects ALL raw evidence for a completed quiz attempt into one structured
dict that gets passed to run_final_hiring_assessment() (Opus).

Opus receives raw evidence, not pre-digested summaries.
"""

import json
import logging
import psycopg2
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

PP_TZ = ZoneInfo("Asia/Phnom_Penh")
logger = logging.getLogger(__name__)

# ── Critical-signal phrase rules (Sonnet catches obvious phrasing) ─────────────
# Opus does a second semantic pass — these are the unambiguous rule hits.
CRITICAL_PHRASE_RULES: list[dict] = [
    {
        "signal": "hiding_reflex_phrase",
        "severity": "critical",
        "phrases": [
            "before supervisor see", "before manager see",
            "before boss see", "without telling",
            "quietly fix", "fix quietly", "fix it without",
            "solve without reporting", "handle without telling",
            "solved it quietly", "handle it quietly", "resolved it quietly",
            "dealt with it quietly", "sorted it quietly",
            "nobody need to know", "no one need to know",
        ],
    },
    {
        "signal": "old_way_resistance",
        "severity": "moderate",
        "phrases": [
            "my old job", "at my previous job we", "in my last job we",
            "where i worked before we", "old place did it",
        ],
    },
    {
        "signal": "blame_shifting_customer",
        "severity": "serious",
        "phrases": [
            "customer is wrong", "customer fault", "customer mistake",
            "customer should know", "not my fault the customer",
        ],
    },
    {
        "signal": "avoids_team_accountability",
        "severity": "moderate",
        "phrases": [
            "not my job to check", "not my responsibility to check others",
            "i only do my own", "my job is my area only",
        ],
    },
]

# ── Expected fields for multi-part questions (partial-answer detection) ─────────
MULTI_PART_EXPECTED: dict[str, list[str]] = {
    "E-T2": ["current_job", "last_working_day", "current_salary_or_range", "notice_status"],
    "C-Q8": ["what_went_wrong", "what_you_did"],
    "D3":   ["situation_described", "action_taken", "outcome"],
}


def _db():
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)


def _get_attempt(attempt_id: int) -> dict | None:
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT a.id, a.attempt_status, a.score_summary, a.risk_profile,
                   a.abandoned_at_question_id, a.part_e_triggered, a.resume_count,
                   c.id AS candidate_id, c.name, c.position, c.candidate_type,
                   s.id AS session_id, s.telegram_username, s.telegram_user_id
            FROM hiring_quiz_attempts a
            JOIN hiring_sessions s ON s.id = a.session_id
            JOIN hiring_candidates c ON c.id = a.candidate_id
            WHERE a.id = %s
        """, (attempt_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = ["attempt_id","attempt_status","score_summary","risk_profile",
                "abandoned_at_question_id","part_e_triggered","resume_count",
                "candidate_id","name","position","candidate_type",
                "session_id","telegram_username","telegram_user_id"]
        return dict(zip(cols, row))
    finally:
        cur.close(); conn.close()


def _get_quiz_answers(attempt_id: int) -> list[dict]:
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT question_id, raw_answer, is_correct, completeness_score,
                   contradiction_score, time_spent_seconds, skipped
            FROM hiring_quiz_answers WHERE attempt_id = %s ORDER BY id
        """, (attempt_id,))
        cols = ["question_id","raw_answer","is_correct","completeness_score",
                "contradiction_score","time_spent_seconds","skipped"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        cur.close(); conn.close()


def _get_intake(telegram_user_id: int | None) -> dict | None:
    if not telegram_user_id:
        return None
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, intake_status, language, cv_submitted, cv_format,
                   voice_strike_count, cv_deflection_count,
                   intake_blocked_reason, appointment_slot,
                   intake_owner_notified_status
            FROM hiring_intake_sessions
            WHERE telegram_user_id = %s
            ORDER BY created_at DESC LIMIT 1
        """, (telegram_user_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = ["intake_id","intake_status","language","cv_submitted","cv_format",
                "voice_strikes","cv_deflection_count","blocked_reason",
                "appointment_slot","owner_notified_status"]
        return dict(zip(cols, row))
    finally:
        cur.close(); conn.close()


def _get_intake_flags(intake_id: int) -> list[dict]:
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT flag, severity FROM hiring_intake_flags
            WHERE intake_id = %s ORDER BY id
        """, (intake_id,))
        return [{"flag": r[0], "severity": r[1]} for r in cur.fetchall()]
    finally:
        cur.close(); conn.close()


def _get_intake_events_summary(intake_id: int) -> dict:
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT event_type, COUNT(*) FROM hiring_intake_events
            WHERE intake_id = %s GROUP BY event_type
        """, (intake_id,))
        counts = {r[0]: r[1] for r in cur.fetchall()}

        # Last 5 text messages for Opus context
        cur.execute("""
            SELECT text FROM hiring_intake_events
            WHERE intake_id = %s AND event_type = 'text' AND text IS NOT NULL
            ORDER BY created_at DESC LIMIT 5
        """, (intake_id,))
        last_messages = [r[0] for r in reversed(cur.fetchall())]

        return {
            "event_counts": counts,
            "total_events": sum(counts.values()),
            "file_count": counts.get("photo", 0) + counts.get("document", 0),
            "voice_count": counts.get("voice", 0) + counts.get("video_note", 0),
            "button_taps": counts.get("callback", 0),
            "last_text_messages": last_messages,
        }
    finally:
        cur.close(); conn.close()


def _get_haiku_intent(intake_id: int) -> dict | None:
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT intent, confidence, action_taken, input_text
            FROM hiring_intake_ai_events
            WHERE intake_id = %s AND stage = 'intent_check'
            ORDER BY created_at LIMIT 1
        """, (intake_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"intent": row[0], "confidence": row[1],
                "action": row[2], "input_text": row[3]}
    finally:
        cur.close(); conn.close()


# ── Rule-based detectors ──────────────────────────────────────────────────────

def detect_critical_signal_hits(answers: list[dict]) -> list[dict]:
    """Match known dangerous phrases in written answers."""
    hits = []
    for ans in answers:
        if not ans.get("raw_answer"):
            continue
        text_lower = (ans["raw_answer"] or "").lower()
        for rule in CRITICAL_PHRASE_RULES:
            matched = [p for p in rule["phrases"] if p in text_lower]
            if matched:
                hits.append({
                    "signal": rule["signal"],
                    "severity": rule["severity"],
                    "question_id": ans["question_id"],
                    "raw_answer": ans["raw_answer"],
                    "matched_phrases": matched,
                    "source": "rule",
                })
    return hits


def detect_rule_contradictions(attempt_id: int) -> list[dict]:
    """Use existing CONTRADICTION_PAIRS from scorer.py."""
    try:
        from hire_bot.scorer import detect_semantic_contradictions
        rows = detect_semantic_contradictions(attempt_id)
        return [{"question_a": r["q1"], "question_b": r["q2"],
                 "description": r.get("description", ""),
                 "severity": r.get("severity", "moderate")} for r in (rows or [])]
    except Exception as e:
        logger.warning("detect_rule_contradictions failed: %s", e)
        return []


def detect_partial_answers(answers: list[dict]) -> list[dict]:
    """
    For multi-part questions, estimate completeness by character count and
    field-presence heuristics. Opus does the real interpretation.
    """
    results = []
    for ans in answers:
        qid = ans["question_id"]
        if qid not in MULTI_PART_EXPECTED:
            continue
        raw = (ans["raw_answer"] or "").strip()
        expected = MULTI_PART_EXPECTED[qid]
        n_expected = len(expected)
        # Rough heuristic: each expected field needs ~10 chars
        char_per_field = max(1, len(raw)) / max(1, n_expected * 10)
        completeness = min(1.0, round(char_per_field, 2))
        # Very short = almost certainly incomplete
        if len(raw) < 20 * n_expected:
            completeness = min(completeness, 0.5)
        results.append({
            "question_id": qid,
            "raw_answer": raw,
            "expected_fields": expected,
            "completeness_estimate": completeness,
            "is_partial": completeness < 0.7,
            "char_count": len(raw),
        })
    return results


def check_start_date_consistency(part_e_answers: dict) -> dict:
    """
    E-A1a = Yes/No/Not sure + E-A1 = free text date.
    Compare E-A1a 'within 3 days' claim against the date given in E-A1.
    All calculations in Phnom Penh time.
    """
    a1a = part_e_answers.get("E-A1a", "")
    a1  = part_e_answers.get("E-A1", "")

    result = {"status": "ok", "note": "", "a1a_answer": a1a, "a1_answer": a1}

    if not a1a or not a1:
        result["status"] = "missing_data"
        return result

    claimed_within_3 = "A" in (a1a or "").upper() or "yes" in (a1a or "").lower()
    if not claimed_within_3:
        return result

    # Try to find a date or "next Monday/Tuesday/etc" in E-A1 text
    today_pp = datetime.now(PP_TZ).date()
    a1_lower = a1.lower()
    days_map = {"monday": 0, "tuesday": 1, "wednesday": 2,
                "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    for day_name, dow in days_map.items():
        if day_name in a1_lower:
            current_dow = today_pp.weekday()
            diff = (dow - current_dow) % 7
            if diff == 0:
                diff = 7  # "next X" usually means next week
            target_date = today_pp + timedelta(days=diff)
            days_away = (target_date - today_pp).days
            if days_away > 3:
                result["status"]  = "minor_inconsistency"
                result["note"]    = (
                    f"E-A1a says within 3 days but E-A1 gives "
                    f"{day_name.title()} = {days_away} days away "
                    f"(today PP = {today_pp}). Clarify in person."
                )
            return result

    return result


def check_cv_vs_parte_consistency(cv_text: str | None, part_e_answers: dict) -> dict:
    """
    Compare current employer in CV vs E-T2 / E-A3b.
    Flags if CV says left a job but E-T2 says still working there.
    """
    result = {"status": "ok", "note": ""}
    if not cv_text or not part_e_answers.get("E-T2"):
        result["status"] = "missing_data"
        return result
    cv_lower   = cv_text.lower()
    e_t2_lower = part_e_answers.get("E-T2", "").lower()

    # Very simple: if E-T2 mentions a place that the CV says was left
    # This is a heuristic; Opus does the real interpretation
    left_phrases = ["left because", "already left", "not working there anymore",
                    "resigned from", "quit", "no longer work"]
    cv_has_left = any(p in cv_lower for p in left_phrases)
    if cv_has_left and e_t2_lower:
        result["status"] = "possible_inconsistency"
        result["note"]   = (
            "CV mentions leaving a previous job. "
            "E-T2 mentions current employment. Opus should check if these refer "
            "to different jobs or if the timeline is contradictory."
        )
    return result


# ── Main package builder ──────────────────────────────────────────────────────

def collect_assessment_package(attempt_id: int) -> dict:
    """
    Build the full evidence package for Opus.
    Returns a dict ready to be JSON-serialised and sent to the model.
    """
    attempt = _get_attempt(attempt_id)
    if not attempt:
        raise ValueError(f"Attempt {attempt_id} not found")

    answers  = _get_quiz_answers(attempt_id)
    intake   = _get_intake(attempt.get("telegram_user_id"))
    intake_id = intake["intake_id"] if intake else None

    intake_flags   = _get_intake_flags(intake_id) if intake_id else []
    intake_events  = _get_intake_events_summary(intake_id) if intake_id else {}
    haiku_intent   = _get_haiku_intent(intake_id) if intake_id else None

    # Separate Part E answers
    part_e_answers = {}
    quiz_answers   = []
    for ans in answers:
        raw = None
        try:
            parsed = json.loads(ans["raw_answer"]) if ans["raw_answer"] else {}
            raw = parsed.get("answer") or ans["raw_answer"]
        except Exception:
            raw = ans["raw_answer"]
        if ans["question_id"].startswith("E-"):
            part_e_answers[ans["question_id"]] = raw
        quiz_answers.append({
            "question_id":        ans["question_id"],
            "raw_answer":         ans["raw_answer"],
            "raw_answer_parsed":  raw,
            "is_correct":         ans["is_correct"],
            "completeness_score": ans["completeness_score"],
            "skipped":            ans["skipped"],
        })

    # Run Sonnet detectors
    critical_hits  = detect_critical_signal_hits(answers)
    contradictions = detect_rule_contradictions(attempt_id)
    partial_answers = detect_partial_answers(answers)
    start_date_check = check_start_date_consistency(part_e_answers)
    cv_consistency   = check_cv_vs_parte_consistency(
        intake.get("cv_format") if intake else None, part_e_answers
    )

    # Mechanical scores
    score_summary_raw = attempt.get("score_summary")
    score_summary = json.loads(score_summary_raw) if score_summary_raw else {}

    package = {
        "package_version": "v1",
        "attempt_id":       attempt_id,
        "candidate": {
            "candidate_id":    attempt["candidate_id"],
            "name":            attempt["name"],
            "position":        attempt["position"],
            "candidate_type":  attempt["candidate_type"],
            "telegram_user_id": attempt.get("telegram_user_id"),
            "telegram_username": attempt.get("telegram_username"),
        },
        "intake": {
            "intake_id":            intake_id,
            "language":             intake.get("language") if intake else None,
            "cv_submitted":         intake.get("cv_submitted") if intake else None,
            "voice_strikes":        intake.get("voice_strikes", 0) if intake else 0,
            "cv_deflections":       intake.get("cv_deflection_count", 0) if intake else 0,
            "flags":                intake_flags,
            "events_summary":       intake_events,
            "haiku_intent":         haiku_intent,
        },
        "mechanical_scores": score_summary,
        "quiz_attempt": {
            "attempt_status":           attempt["attempt_status"],
            "abandoned_at_question_id": attempt["abandoned_at_question_id"],
            "part_e_triggered":         attempt["part_e_triggered"] or [],
            "resume_count":             attempt["resume_count"],
        },
        "quiz_answers":     quiz_answers,
        "part_e_answers":   part_e_answers,
        "sonnet_detections": {
            "critical_signal_hits":    critical_hits,
            "rule_contradictions":     contradictions,
            "partial_answers":         partial_answers,
            "start_date_consistency":  start_date_check,
            "cv_vs_parte":             cv_consistency,
        },
        "meta": {
            "built_at":    datetime.now(timezone.utc).isoformat(),
            "built_by":    "sonnet_assessment_package_v1",
        },
    }
    return package
