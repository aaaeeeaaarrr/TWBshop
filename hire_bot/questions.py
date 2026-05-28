"""
Question sequencing and loading for the hiring bot.

QUESTION_SEQUENCE defines the exact presentation order:
  C-Q1, C-Q2          — background profile (last jobs, daily tasks)
  A1-Q1 … A6-Q60      — Part A: 60 yes/no/not_sure (by section: A1 schedule, A2 honesty,
                          A3 customer, A4 quiet-time, A5 team, A6 commitment)
  B-Q1 … B-Q22        — Part B: 22 single-choice scenario questions
  C-Q3 … C-Q24        — Part C: 22 written scenario questions
  D1, D2, D3, D4,     — Part D: ranking + free text
  D-Final

Total: 111 questions.

After all 111, Part E hiring-facts runs:
  E-A1               — exact start date (free text)
  E-A2               — 30-day availability (free text)
  E-A3a              — currently studying? (structured Yes/No single_choice)
  E-A3b              — currently working elsewhere? (structured Yes/No single_choice)
  E-A4               — known leave / exams next 30 days (free text)
  E-A5               — transport + backup plan (free text)

Triggers evaluated once after E-A5 — rule-based, no AI:
  E-T1 (trigger)     — E-A3a=Yes OR exam keywords in E-A4 → exam communication timing
  E-T2 (trigger)     — E-A3b=Yes → last working day + salary breakdown (answer_sensitivity=owner_only)
  E-T3 (trigger)     — delay keywords in E-A1 → why not sooner? (Lyhouy trigger)
  E-Final            — first-3-days self-commitment (always last)

Trigger state is stored in both context.user_data AND hiring_quiz_attempts.part_e_triggered
so Part E survives bot restarts and can be resumed from DB.
"""
import json
import logging
import sys
from typing import Optional

sys.path.insert(0, '/root/TWBshop')
logger = logging.getLogger(__name__)

# ── Canonical presentation order ─────────────────────────────────────────────

QUESTION_SEQUENCE: list[str] = (
    # Background profile questions (come before the tick section)
    ["C-Q1", "C-Q2"]
    # Part A: attitude / values — 60 yes/no/not_sure questions
    + [f"A1-Q{i}" for i in range(1, 11)]   # A1: schedule & time (10 Qs)
    + [f"A2-Q{i}" for i in range(11, 21)]  # A2: honesty & mistakes (10 Qs)
    + [f"A3-Q{i}" for i in range(21, 31)]  # A3: customer service (10 Qs)
    + [f"A4-Q{i}" for i in range(31, 41)]  # A4: quiet-time ethic (10 Qs)
    + [f"A5-Q{i}" for i in range(41, 51)]  # A5: team & gossip (10 Qs)
    + [f"A6-Q{i}" for i in range(51, 61)]  # A6: commitment & training (10 Qs)
    # Part B: scenario multiple-choice — 22 questions
    + [f"B-Q{i}" for i in range(1, 23)]
    # Part C: written scenarios — 22 questions (C-Q3 onwards; C-Q1/Q2 are profile above)
    + [f"C-Q{i}" for i in range(3, 25)]
    # Part D: ranking + written — 5 questions
    + ["D1", "D2", "D3", "D4", "D-Final"]
)

# Section labels for progress display
SECTION_LABEL: dict[str, str] = {
    "C-Q1": "Profile", "C-Q2": "Profile",
    **{f"A1-Q{i}": "Part A — Schedule & Time" for i in range(1, 11)},
    **{f"A2-Q{i}": "Part A — Honesty & Mistakes" for i in range(11, 21)},
    **{f"A3-Q{i}": "Part A — Customer Service" for i in range(21, 31)},
    **{f"A4-Q{i}": "Part A — Quiet-Time Ethic" for i in range(31, 41)},
    **{f"A5-Q{i}": "Part A — Team & Communication" for i in range(41, 51)},
    **{f"A6-Q{i}": "Part A — Commitment" for i in range(51, 61)},
    **{f"B-Q{i}": "Part B — Scenarios" for i in range(1, 23)},
    **{f"C-Q{i}": "Part C — Written" for i in range(3, 25)},
    **{"D1": "Part D — Priority", "D2": "Part D — Analysis",
       "D3": "Part D — Situations", "D4": "Part D — Rewrite",
       "D-Final": "Part D — Final Reflection"},
    **{"E-A1a": "Part E — Hiring Facts",
       "E-A1": "Part E — Hiring Facts", "E-A2": "Part E — Hiring Facts",
       "E-A3": "Part E — Hiring Facts",   # legacy (deactivated in v2)
       "E-A3a": "Part E — Hiring Facts", "E-A3b": "Part E — Hiring Facts",
       "E-A4": "Part E — Hiring Facts", "E-A5": "Part E — Hiring Facts",
       "E-T1": "Part E — Clarification", "E-T2": "Part E — Clarification",
       "E-T3": "Part E — Clarification",
       "E-Final": "Part E — Commitment"},
}

# ── Part E constants ──────────────────────────────────────────────────────────

# Always asked, in this order — E-A1a is the structured start-gate (before free-text E-A1)
PART_E_ALWAYS: list[str] = ["E-A1a", "E-A1", "E-A2", "E-A3a", "E-A3b", "E-A4", "E-A5"]

# Trigger question IDs — evaluated once after E-A5 (last always-asked question)
PART_E_CONDITIONAL: list[str] = ["E-T1", "E-T2", "E-T3"]

# Always the last Part E question
PART_E_FINAL: str = "E-Final"

# Questions whose answers contain salary/compensation data — must never appear in group/
# management summaries. Matches answer_sensitivity='owner_only' in hiring_quiz_questions.
# Keep in sync with any new owner_only DB seeds.
OWNER_ONLY_QUESTION_IDS: frozenset[str] = frozenset({"E-T2"})


def filter_shareable_answers(answers: dict) -> dict:
    """
    Remove owner_only answers from a {question_id: answer_value} dict.
    Call this before sending any answer set to a group chat or non-owner report.
    """
    return {qid: val for qid, val in answers.items()
            if qid not in OWNER_ONLY_QUESTION_IDS}


# E-T1: exam keywords in E-A4 free-text (E-A3a=Yes already triggers E-T1 directly)
_STUDY_KEYWORDS = {"school", "university", "study", "studying", "class", "classes",
                   "lecture", "exam", "exams", "college", "institute",
                   "semester", "morning class", "royal university",
                   "ppp", "bbu", "rupp", "iu", "paragon", "norton"}

# E-T2: legacy fallback only — E-A3b=Yes is the primary trigger now
_JOB_KEYWORDS = {"work", "working", "job", "salary", "employer", "company",
                 "restaurant", "cafe", "coffee", "shop", "hotel", "currently",
                 "still working", "part time", "part-time", "yes"}

# E-T3: delay keywords in E-A1 free-text start-date answer (Lyhouy trigger)
_DELAY_KEYWORDS = {"next month", "first of", "1st of", "cannot start", "can't start",
                   "not yet", "need to finish", "need to quit", "need to resign",
                   "serving notice", "notice period", "end of month", "end of the month",
                   "after my", "after the", "need time", "few weeks", "two weeks",
                   "one month", "30 days", "14 days", "haven't told", "have not told",
                   "didn't tell", "my employer", "my current job"}

# Cache loaded from DB
_cache: dict[str, dict] = {}


def _conn():
    from secrets import DATABASE_URL
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


# ── Part E helpers ────────────────────────────────────────────────────────────

def evaluate_e_triggers(attempt_id: int, _rows: dict = None) -> list[str]:
    """
    Return triggered E question IDs. Call after PART_E_ALWAYS[-1] so all inputs are available.
    Rule-based only — no AI.

    Trigger rules:
      E-T1: E-A3a answer = 'A' (Yes, studying) OR exam/study keywords in E-A4 free text
      E-T2: E-A3b answer = 'A' (Yes, working elsewhere)
      E-T3: E-A1a answer = 'B' or 'C' (not starting within 3 days) OR delay keywords in E-A1

    _rows: pass a pre-built dict for unit testing (skips DB). DB load when None.
    Legacy fallback: if E-A3 (old single-field) is present, keyword matching is used.
    """
    import json as _json

    if _rows is None:
        conn = _conn()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT question_id, raw_answer
                FROM hiring_quiz_answers
                WHERE attempt_id = %s
                  AND question_id IN ('E-A1a', 'E-A1', 'E-A3', 'E-A3a', 'E-A3b', 'E-A4', 'C-Q1')
            """, (attempt_id,))
            _rows = {}
            for qid, raw in cur.fetchall():
                try:
                    _rows[qid] = _json.loads(raw) if isinstance(raw, str) else (raw or {})
                except Exception:
                    _rows[qid] = {}
        finally:
            cur.close()
            conn.close()

    def _text(d: dict) -> str:
        return (d.get("text") or d.get("answer") or "").lower()

    def _answer(d: dict) -> str:
        return (d.get("answer") or "").upper()

    triggered: list[str] = []

    # ── E-T1: study / exam conflict ───────────────────────────────────────────
    study_triggered = (
        _answer(_rows.get("E-A3a", {})) == "A"               # structured: Yes, studying
        or any(kw in _text(_rows.get("E-A4", {}))             # exam keywords in leave/dates field
               for kw in _STUDY_KEYWORDS)
        or any(kw in _text(_rows.get("E-A3", {}))             # legacy single-field fallback
               for kw in _STUDY_KEYWORDS)
    )
    if study_triggered:
        triggered.append("E-T1")

    # ── E-T2: current job ─────────────────────────────────────────────────────
    if _answer(_rows.get("E-A3b", {})) == "A":               # structured: Yes, working elsewhere
        triggered.append("E-T2")
    else:
        # Legacy: keyword fallback for old sessions that used E-A3 free-text
        e_a3_text = _text(_rows.get("E-A3", {}))
        c_q1_text = _text(_rows.get("C-Q1", {}))
        combined = e_a3_text + " " + c_q1_text
        if (any(kw in combined for kw in _JOB_KEYWORDS)
                and "no" not in e_a3_text[:30]):
            triggered.append("E-T2")

    # ── E-T3: delayed start — structured E-A1a takes priority over keyword fallback ──
    e_a1a_ans = _answer(_rows.get("E-A1a", {}))
    delay_triggered = (
        e_a1a_ans in ("B", "C")                              # structured: No / Not sure
        or any(kw in _text(_rows.get("E-A1", {})) for kw in _DELAY_KEYWORDS)  # keyword fallback
    )
    if delay_triggered:
        triggered.append("E-T3")

    return triggered


def get_next_part_e_question(e_answered: set[str], triggered_ids: list[str]) -> Optional[str]:
    """Return next unanswered Part E question, or None if Part E is complete."""
    sequence = PART_E_ALWAYS + triggered_ids + [PART_E_FINAL]
    for qid in sequence:
        if qid not in e_answered:
            return qid
    return None


def get_part_e_progress(qid: str, triggered_ids: list[str]) -> str:
    """Progress label for a Part E question, e.g. 'E 2/7'."""
    sequence = PART_E_ALWAYS + triggered_ids + [PART_E_FINAL]
    try:
        pos = sequence.index(qid) + 1
    except ValueError:
        return "E"
    return f"E {pos}/{len(sequence)}"


def is_part_e_question(qid: str) -> bool:
    return qid.startswith("E-")


def load_all_questions() -> dict[str, dict]:
    """Load all active questions from DB into cache. Call once on startup."""
    global _cache
    if _cache:
        return _cache
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, part, section, answer_type,
                   question_text_en, question_text_km,
                   options, correct_answer
            FROM hiring_quiz_questions WHERE active = TRUE
        """)
        for qid, part, section, answer_type, en, km, options_raw, correct_raw in cur.fetchall():
            options = options_raw if isinstance(options_raw, dict) else (
                json.loads(options_raw) if options_raw else {})
            correct = correct_raw if isinstance(correct_raw, dict) else (
                json.loads(correct_raw) if correct_raw else {})
            _cache[qid] = {
                "id": qid,
                "part": part,
                "section": section,
                "answer_type": answer_type,
                "en": en or "",
                "km": km or "",
                "options": options,
                "correct": correct,
            }
        logger.info("load_all_questions: loaded %s questions", len(_cache))
        return _cache
    finally:
        cur.close()
        conn.close()


def get_question(qid: str) -> Optional[dict]:
    """Return question dict for a given ID, loading from DB if needed."""
    if not _cache:
        load_all_questions()
    return _cache.get(qid)


def get_next_question_id(answered: set) -> Optional[str]:
    """Return the next question ID not yet answered, or None if all done."""
    for qid in QUESTION_SEQUENCE:
        if qid not in answered:
            return qid
    return None


def get_progress(qid: str) -> str:
    """Return a short progress string like '34/111' for display."""
    try:
        pos = QUESTION_SEQUENCE.index(qid) + 1
    except ValueError:
        return ""
    return f"{pos}/{len(QUESTION_SEQUENCE)}"


def parse_d1_items(question: dict) -> list[str]:
    """
    Return the 7 D1 ranking items in SORTED (alphabetical) order for button display.
    Uses correct_order labels as canonical names so stored answers match scorer expectations.
    Sorting scrambles the correct sequence so it's not obvious to the candidate.
    """
    correct = question.get("correct", {})
    order = correct.get("correct_order", [])
    if len(order) == 7:
        return sorted(order)  # Alphabetical = scrambled vs. correct order
    return []


def parse_b_options(question: dict) -> dict[str, str]:
    """
    Parse Part B multiple-choice options.
    Returns dict like {"A": "text", "B": "text", ...}
    Options stored in question.options as {"A": "...", "B": "...", "C": "...", "D": "..."}
    or in question_text_en embedded.
    """
    opts = question.get("options", {})
    if isinstance(opts, dict) and opts:
        return {k: v for k, v in opts.items() if k in ("A", "B", "C", "D")}
    return {}
