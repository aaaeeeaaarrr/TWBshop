"""
Repeatable tests for hire_bot/scorer.py.

Run with: python3 -m pytest tests/test_hire_scorer.py -v
Or: python3 tests/test_hire_scorer.py

Tests:
  1. Perfect candidate       — max A/B, correct D1, 0 contradictions
  2. Half-answer candidate   — 2 critical A wrong, D1 wrong, triggers fire
  3. Contradictory candidate — ticks clean, written contradicts, contradictions detected
  4. Not-sure critical       — "not_sure" on critical question flags correctly
  5. D1 wrong order          — tablet last, phone first = score 0
  6. Schedule conflict       — A1-Q5 + A1-Q7 wrong = schedule red_flag override
"""
import sys
import json
import os

sys.path.insert(0, '/root/TWBshop')

import psycopg2
from secrets import DATABASE_URL
from hire_bot.scorer import auto_grade, detect_contradictions

# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn():
    return psycopg2.connect(DATABASE_URL)


def _get_quiz_version_id(cur):
    cur.execute("SELECT id FROM hiring_quiz_versions WHERE version_name = 'Final v3'")
    return cur.fetchone()[0]


def _load_correct_answers(cur):
    cur.execute("""
        SELECT id, part, correct_answer, severity_if_wrong, requires_verbal_retest
        FROM hiring_quiz_questions WHERE active = TRUE
    """)
    return {r[0]: {"part": r[1], "correct": r[2], "severity": r[3], "verbal": r[4]}
            for r in cur.fetchall()}


def _make_candidate(cur, name):
    cur.execute("""
        INSERT INTO hiring_candidates (name, candidate_type, notes)
        VALUES (%s, 'applicant', 'AUTO-GENERATED TEST DATA — safe to delete')
        RETURNING id
    """, (name,))
    return cur.fetchone()[0]


def _make_attempt(cur, cid, vid):
    cur.execute("""
        INSERT INTO hiring_quiz_attempts
            (candidate_id, quiz_version_id, started_at, completed_at, arrival_status)
        VALUES (%s, %s, NOW(), NOW(), 'on_time')
        RETURNING id
    """, (cid, vid))
    return cur.fetchone()[0]


def _insert(cur, attempt_id, question_id, response, skipped=False):
    cur.execute("""
        INSERT INTO hiring_quiz_answers (attempt_id, question_id, raw_answer, skipped)
        VALUES (%s, %s, %s, %s)
    """, (attempt_id, question_id, json.dumps(response) if response else None, skipped))


def _cleanup(cur, candidate_ids):
    cur.execute("""
        DELETE FROM hiring_contradictions WHERE attempt_id IN (
            SELECT id FROM hiring_quiz_attempts WHERE candidate_id = ANY(%s)
        )
    """, (candidate_ids,))
    cur.execute("""
        DELETE FROM hiring_quiz_answers WHERE attempt_id IN (
            SELECT id FROM hiring_quiz_attempts WHERE candidate_id = ANY(%s)
        )
    """, (candidate_ids,))
    cur.execute("DELETE FROM hiring_quiz_attempts WHERE candidate_id = ANY(%s)", (candidate_ids,))
    cur.execute(
        "DELETE FROM hiring_candidates WHERE id = ANY(%s) AND name LIKE %s",
        (candidate_ids, r'__TEST_%')
    )


def _fill_correct_ab(cur, attempt_id, answers, overrides=None):
    """Insert all Part A and B answers correctly, with optional per-question overrides."""
    overrides = overrides or {}
    for qid, meta in answers.items():
        if meta["part"] not in ("A", "B"):
            continue
        correct = meta["correct"]
        if not isinstance(correct, dict) or "answer" not in correct:
            continue
        if qid in overrides:
            _insert(cur, attempt_id, qid, {"answer": overrides[qid]})
        else:
            _insert(cur, attempt_id, qid, {"answer": correct["answer"]})


def _correct_d1():
    return {"order": [
        "Check orders/delivery tablet",
        "Check low stock",
        "Refill items",
        "Prepare for next rush if trained",
        "Clean customer and work area",
        "Ask management what needs help",
        "Use personal phone",
    ]}


# ── Test runner ───────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  ✓ {label}")
        PASS += 1
    else:
        print(f"  ✗ FAIL: {label}" + (f" — {detail}" if detail else ""))
        FAIL += 1


def run_tests():
    global PASS, FAIL
    PASS = FAIL = 0

    conn = _conn()
    cur = conn.cursor()
    vid = _get_quiz_version_id(cur)
    answers = _load_correct_answers(cur)
    a_questions = {k: v for k, v in answers.items() if v["part"] == "A"}
    candidate_ids = []

    try:
        # ── Test 1: Perfect candidate ─────────────────────────────────────────
        print("\nTest 1: Perfect candidate")
        cid = _make_candidate(cur, "__TEST_Perfect__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers)
        _insert(cur, aid, "D1", _correct_d1())
        _insert(cur, aid, "C-Q4", {"text": "My manager would say I need to improve my speed during rush hour. I am working on this by practising my station setup before peak time."})
        _insert(cur, aid, "C-Q8", {"text": "I would not hide the mistake. I would tell my manager immediately, fix it, and report so we can prevent it again."})
        _insert(cur, aid, "C-Q12", {"text": "During quiet time I check stock, restock, clean, and ask management if there is anything else. Quiet time is not free time."})
        conn.commit()

        r = auto_grade(aid)
        c = detect_contradictions(aid)
        check("score_a = 60", r["summary"]["score_a"] == 60, r["summary"]["score_a"])
        check("score_b = 22", r["summary"]["score_b"] == 22, r["summary"]["score_b"])
        check("d1_priority_score = 3", r["summary"]["d1_priority_score"] == 3)
        check("no critical_wrong", r["summary"]["critical_wrong"] == [])
        check("no triggers", r["triggers"] == [])
        check("0 contradictions (perfect tick = no contradiction rows)", len(c) == 0, f"got {len(c)}")

        # ── Test 2: Half-answer candidate ─────────────────────────────────────
        print("\nTest 2: Half-answer candidate (2 critical wrong, D1 wrong)")
        cid = _make_candidate(cur, "__TEST_HalfAnswer__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers, overrides={
            "A1-Q5": "yes",  # busy tomorrow = ok (wrong, critical)
            "A4-Q38": "no",  # good staff don't need to work unwatched (wrong, critical)
        })
        _insert(cur, aid, "D1", {"order": [
            "Use personal phone",
            "Clean customer and work area",
            "Check orders/delivery tablet",
            "Check low stock",
            "Refill items",
            "Ask management what needs help",
            "Prepare for next rush if trained",
        ]})
        _insert(cur, aid, "C-Q12", {"text": "I would wait for customers."})
        conn.commit()

        r = auto_grade(aid)
        c = detect_contradictions(aid)
        trigger_types = [t["type"] for t in r["triggers"]]
        check("A1-Q5 in critical_wrong", "A1-Q5" in r["summary"]["critical_wrong"])
        check("A4-Q38 in critical_wrong", "A4-Q38" in r["summary"]["critical_wrong"])
        check("d1_priority_score = 0", r["summary"]["d1_priority_score"] == 0)
        check("verbal_retest triggers fired", "verbal_retest" in trigger_types)
        check("d1_wrong_priority trigger fired", "d1_wrong_priority" in trigger_types)
        check("contradictions detected (wrong ticks fire contradiction check)", len(c) > 0)

        # ── Test 3: Contradictory candidate ───────────────────────────────────
        print("\nTest 3: Contradictory candidate (all ticks correct, written contradicts)")
        cid = _make_candidate(cur, "__TEST_Contradictory__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers)  # ALL ticks correct
        _insert(cur, aid, "D1", _correct_d1())
        _insert(cur, aid, "C-Q8", {"text": "I would handle it quietly and fix it myself without telling management."})
        _insert(cur, aid, "C-Q10", {"text": "Just talk to each other and try to keep good feelings."})
        _insert(cur, aid, "C-Q12", {"text": "I would sit and wait or maybe check my phone a little."})
        _insert(cur, aid, "C-Q16", {"text": "It is fine if you need to go. People have to do what is best for them."})
        conn.commit()

        r = auto_grade(aid)
        c = detect_contradictions(aid)
        check("all ticks correct (score_a = 60)", r["summary"]["score_a"] == 60)
        check("no critical_wrong from ticks", r["summary"]["critical_wrong"] == [])
        check("0 triggers from auto_grade (ticks clean)", r["triggers"] == [])
        check("0 contradictions (correct ticks → no rows, even with bad written)", len(c) == 0,
              f"got {len(c)} — correct-tick pairs should NOT be stored as contradictions")

        # ── Test 4: Not-sure on critical question ─────────────────────────────
        print("\nTest 4: 'not_sure' on critical question")
        cid = _make_candidate(cur, "__TEST_NotSure__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers, overrides={
            "A2-Q13": "not_sure",  # not sure whether hiding mistakes is worse
        })
        _insert(cur, aid, "D1", _correct_d1())
        conn.commit()

        r = auto_grade(aid)
        check("A2-Q13 in not_sure_critical", "A2-Q13" in r["summary"]["not_sure_critical"])
        check("not_sure_critical trigger fired", any(t["type"] == "not_sure_critical" for t in r["triggers"]))
        check("score_a < 60 (not_sure = not correct)", r["summary"]["score_a"] < 60)

        # ── Test 5: D1 wrong order ────────────────────────────────────────────
        print("\nTest 5: D1 wrong order (phone first)")
        cid = _make_candidate(cur, "__TEST_D1Wrong__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers)
        _insert(cur, aid, "D1", {"order": [
            "Use personal phone",
            "Check orders/delivery tablet",
            "Check low stock",
            "Refill items",
            "Prepare for next rush if trained",
            "Clean customer and work area",
            "Ask management what needs help",
        ]})
        conn.commit()

        r = auto_grade(aid)
        check("d1_priority_score = 0 (phone first, tablet not last)", r["summary"]["d1_priority_score"] == 0)
        check("d1_wrong_priority trigger fired", any(t["type"] == "d1_wrong_priority" for t in r["triggers"]))

        # ── Test 6: Schedule conflict ─────────────────────────────────────────
        print("\nTest 6: Schedule conflict (A1-Q5 + A1-Q7 both wrong)")
        cid = _make_candidate(cur, "__TEST_Schedule__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers, overrides={
            "A1-Q5": "yes",   # busy tomorrow = ok (wrong, critical)
            "A1-Q7": "no",    # hiding schedule = honest (wrong, critical)
        })
        _insert(cur, aid, "D1", _correct_d1())
        conn.commit()

        r = auto_grade(aid)
        check("A1-Q5 in critical_wrong", "A1-Q5" in r["summary"]["critical_wrong"])
        check("A1-Q7 in critical_wrong", "A1-Q7" in r["summary"]["critical_wrong"])
        check("verbal_retest triggers for both", sum(1 for t in r["triggers"] if t["type"] == "verbal_retest") >= 2)

    finally:
        _cleanup(cur, candidate_ids)
        conn.commit()
        cur.close()
        conn.close()

    print(f"\n{'='*50}")
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")
    return FAIL == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
