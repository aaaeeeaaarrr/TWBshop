"""
Repeatable tests for hire_bot/scorer.py.

Run with: python3 tests/test_hire_scorer.py
Or:       python3 -m pytest tests/test_hire_scorer.py -v

Phase 1 tests (no Claude API needed):
  1. Perfect candidate       — max A/B, correct D1, 0 triggers, 0 Phase-1 contradiction rows
  2. Half-answer candidate   — 2 critical wrong, D1 wrong, triggers fire
  3. Contradictory candidate — all ticks correct + bad written = 0 Phase-1 contradiction rows
                               (Phase 2 semantic scoring will detect these — not Phase 1)
  4. Not-sure critical       — "not_sure" on A2-Q13 flags correctly
  5. D1 wrong order          — phone first = d1_priority_score 0
  6. Schedule conflict       — A1-Q5 + A1-Q7 both wrong = verbal_retest x2

Phase 2 test (no Claude API — pre-scored rubric data inserted manually):
  7. Semantic contradiction  — tick=correct + responsibility_score=0 → contradiction row created
                               tick=correct + responsibility_score=2 → no row
                               tick=wrong  + responsibility_score=0 → no row (consistent failure, not contradiction)
"""
import sys
import json

sys.path.insert(0, '/root/TWBshop')

import psycopg2
from shared.database import raw_connect
from hire_bot.scorer import auto_grade, detect_semantic_contradictions

# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn():
    return raw_connect()


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


def _insert_with_rubric(cur, attempt_id, question_id, response,
                        is_correct=None, responsibility=2, specificity=2, completeness=2):
    """Insert an answer with pre-scored rubric data (for Phase 2 tests, no Claude needed)."""
    notes = json.dumps({
        "responsibility_score": responsibility,
        "specificity_score": specificity,
        "completeness_score": completeness,
        "notes": "pre-scored for test"
    })
    cur.execute("""
        INSERT INTO hiring_quiz_answers
            (attempt_id, question_id, raw_answer, is_correct, completeness_score, grader_notes,
             graded_by, skipped)
        VALUES (%s, %s, %s, %s, %s, %s, 'test_pre_scored', FALSE)
    """, (attempt_id, question_id, json.dumps(response) if response else None,
          is_correct, completeness, notes))


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
        "Check orders/delivery tablet", "Check low stock", "Refill items",
        "Prepare for next rush if trained", "Clean customer and work area",
        "Ask management what needs help", "Use personal phone",
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
    candidate_ids = []

    try:
        # ── Test 1: Perfect candidate ─────────────────────────────────────────
        print("\nTest 1: Perfect candidate (Phase 1)")
        cid = _make_candidate(cur, "__TEST_Perfect__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers)
        _insert(cur, aid, "D1", _correct_d1())
        _insert(cur, aid, "C-Q8", {"text": "I would not hide the mistake. I would tell my manager immediately and report what happened."})
        conn.commit()

        r = auto_grade(aid)
        check("score_a = 60", r["summary"]["score_a"] == 60, r["summary"]["score_a"])
        check("score_b = 22", r["summary"]["score_b"] == 22)
        check("d1_priority_score = 3", r["summary"]["d1_priority_score"] == 3)
        check("no critical_wrong", r["summary"]["critical_wrong"] == [])
        check("no triggers (Phase 1)", r["triggers"] == [])

        # ── Test 2: Half-answer candidate ─────────────────────────────────────
        print("\nTest 2: Half-answer (2 critical wrong, D1 wrong) — Phase 1")
        cid = _make_candidate(cur, "__TEST_HalfAnswer__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers, overrides={
            "A1-Q5": "yes",   # busy tomorrow = ok (wrong, critical)
            "A4-Q38": "no",   # good staff don't work unwatched (wrong, critical)
        })
        _insert(cur, aid, "D1", {"order": [
            "Use personal phone", "Clean customer and work area",
            "Check orders/delivery tablet", "Check low stock",
            "Refill items", "Ask management what needs help",
            "Prepare for next rush if trained",
        ]})
        conn.commit()

        r = auto_grade(aid)
        trigger_types = [t["type"] for t in r["triggers"]]
        check("A1-Q5 in critical_wrong", "A1-Q5" in r["summary"]["critical_wrong"])
        check("A4-Q38 in critical_wrong", "A4-Q38" in r["summary"]["critical_wrong"])
        check("d1_priority_score = 0", r["summary"]["d1_priority_score"] == 0)
        check("verbal_retest trigger fired", "verbal_retest" in trigger_types)
        check("d1_wrong_priority trigger fired", "d1_wrong_priority" in trigger_types)

        # ── Test 3: Contradictory candidate — Phase 1 only ───────────────────
        print("\nTest 3: Contradictory candidate — Phase 1 produces 0 contradiction rows")
        print("  (Phase 2 semantic scoring will detect these — that is correct behavior)")
        cid = _make_candidate(cur, "__TEST_Contradictory__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers)   # ALL ticks correct
        _insert(cur, aid, "D1", _correct_d1())
        _insert(cur, aid, "C-Q8", {"text": "I would handle it quietly and fix it myself without telling management."})
        _insert(cur, aid, "C-Q11", {"text": "I would just talk to friends about it and try to move on."})
        _insert(cur, aid, "C-Q12", {"text": "I would sit and wait or check my phone."})
        conn.commit()

        r = auto_grade(aid)
        check("all ticks correct (score_a = 60)", r["summary"]["score_a"] == 60)
        check("no critical_wrong (ticks are all right)", r["summary"]["critical_wrong"] == [])
        check("0 triggers from Phase 1 (correct ticks produce no triggers)",
              r["triggers"] == [])
        # Phase 1 has no contradiction detection — verify no rows were written
        cur.execute("SELECT COUNT(*) FROM hiring_contradictions WHERE attempt_id = %s", (aid,))
        c_count = cur.fetchone()[0]
        check("0 contradiction rows from Phase 1 (polished liar detected in Phase 2, not Phase 1)",
              c_count == 0, f"got {c_count}")

        # ── Test 4: Not-sure on critical ──────────────────────────────────────
        print("\nTest 4: 'not_sure' on critical A2-Q13 — Phase 1")
        cid = _make_candidate(cur, "__TEST_NotSure__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers, overrides={"A2-Q13": "not_sure"})
        _insert(cur, aid, "D1", _correct_d1())
        conn.commit()

        r = auto_grade(aid)
        check("A2-Q13 in not_sure_critical", "A2-Q13" in r["summary"]["not_sure_critical"])
        check("not_sure_critical trigger fired",
              any(t["type"] == "not_sure_critical" for t in r["triggers"]))
        check("score_a < 60 (not_sure counts as not correct)", r["summary"]["score_a"] < 60)

        # ── Test 5: D1 wrong order ────────────────────────────────────────────
        print("\nTest 5: D1 wrong order (phone first) — Phase 1")
        cid = _make_candidate(cur, "__TEST_D1Wrong__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)
        _fill_correct_ab(cur, aid, answers)
        _insert(cur, aid, "D1", {"order": [
            "Use personal phone", "Check orders/delivery tablet", "Check low stock",
            "Refill items", "Prepare for next rush if trained",
            "Clean customer and work area", "Ask management what needs help",
        ]})
        conn.commit()

        r = auto_grade(aid)
        check("d1_priority_score = 0 (phone first)", r["summary"]["d1_priority_score"] == 0)
        check("d1_wrong_priority trigger fired",
              any(t["type"] == "d1_wrong_priority" for t in r["triggers"]))

        # ── Test 6: Schedule conflict ─────────────────────────────────────────
        print("\nTest 6: Schedule conflict — A1-Q5 + A1-Q7 both wrong — Phase 1")
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
        check("verbal_retest triggers for both schedule questions",
              sum(1 for t in r["triggers"] if t["type"] == "verbal_retest") >= 2)

        # ── Test 7: Phase 2 semantic contradiction detection ──────────────────
        print("\nTest 7: Phase 2 semantic contradiction (pre-scored rubric, no Claude API)")
        cid = _make_candidate(cur, "__TEST_Phase2__")
        candidate_ids.append(cid)
        aid = _make_attempt(cur, cid, vid)

        # Tick: A2-Q13 correct (knows hiding mistakes is wrong)
        # Written: C-Q8 responsibility=0 (would handle quietly — contradiction!)
        _insert_with_rubric(cur, aid, "A2-Q13",
                            {"answer": "yes"},   # correct tick
                            is_correct=True,
                            responsibility=3, specificity=3, completeness=3)  # tick has no rubric

        _insert_with_rubric(cur, aid, "C-Q8",
                            {"text": "I would fix it quietly myself."},
                            is_correct=None,
                            responsibility=0, specificity=1, completeness=2)  # low responsibility!

        # Tick: A4-Q38 correct + C-Q12 responsibility=2 → should NOT flag
        _insert_with_rubric(cur, aid, "A4-Q38",
                            {"answer": "yes"},
                            is_correct=True,
                            responsibility=3, specificity=3, completeness=3)

        _insert_with_rubric(cur, aid, "C-Q12",
                            {"text": "I check stock, restock, clean, and ask management."},
                            is_correct=None,
                            responsibility=2, specificity=2, completeness=3)  # good score, no flag

        # Tick: A6-Q58 correct + C-Q16 responsibility=1, completeness=2 → should flag
        _insert_with_rubric(cur, aid, "A6-Q58",
                            {"answer": "yes"},
                            is_correct=True,
                            responsibility=3, specificity=3, completeness=3)

        _insert_with_rubric(cur, aid, "C-Q16",
                            {"text": "People have to do what is best for them."},
                            is_correct=None,
                            responsibility=1, specificity=1, completeness=2)  # low responsibility

        # Tick: A5-Q42 WRONG + C-Q11 responsibility=0 → should NOT flag as contradiction
        # (wrong tick + bad written = consistent failure, NOT a contradiction)
        _insert_with_rubric(cur, aid, "A5-Q42",
                            {"answer": "yes"},   # wrong: says gossip is ok
                            is_correct=False,
                            responsibility=0, specificity=0, completeness=0)

        _insert_with_rubric(cur, aid, "C-Q11",
                            {"text": "I would tell friends about it."},
                            is_correct=None,
                            responsibility=0, specificity=0, completeness=1)

        conn.commit()

        contradictions = detect_semantic_contradictions(aid)
        flagged_pairs = {(c["qa"], c["qb"]) for c in contradictions}

        check("A2-Q13/C-Q8 flagged (tick correct, responsibility=0 → polished liar)",
              ("A2-Q13", "C-Q8") in flagged_pairs)
        check("A6-Q58/C-Q16 flagged (tick correct, responsibility=1)",
              ("A6-Q58", "C-Q16") in flagged_pairs)
        check("A4-Q38/C-Q12 NOT flagged (tick correct, responsibility=2 → no contradiction)",
              ("A4-Q38", "C-Q12") not in flagged_pairs)
        check("A5-Q42/C-Q11 NOT flagged (tick wrong + bad written = consistent failure, not contradiction)",
              ("A5-Q42", "C-Q11") not in flagged_pairs)
        check("ai_flagged=TRUE on all Phase 2 rows",
              all(c.get("severity") for c in contradictions))

    finally:
        _cleanup(cur, candidate_ids)
        conn.commit()
        cur.close()
        conn.close()

    print(f"\n{'='*55}")
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    print(f"{'='*55}")
    return FAIL == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
