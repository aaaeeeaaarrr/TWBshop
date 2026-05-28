"""
Tests the scoring engine with three synthetic quiz attempts:
  1. Perfect candidate  — max A/B, correct D1, strong written answers
  2. Half-answer        — low completeness on written, missed 2 critical A questions
  3. Contradictory      — ticked right on A but wrote contradictory answers

Prints auto_grade and detect_contradictions output for each.
Cleans up all test data after.
"""
import sys
sys.path.insert(0, '/root/TWBshop')
from secrets import DATABASE_URL
import psycopg2
import json
from datetime import datetime, timezone

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_vid():
    cur.execute("SELECT id FROM hiring_quiz_versions WHERE version_name = 'Final v3'")
    return cur.fetchone()[0]


def load_correct_answers():
    cur.execute("""
        SELECT id, part, correct_answer, requires_verbal_retest
        FROM hiring_quiz_questions WHERE active = TRUE
    """)
    return {r[0]: {"part": r[1], "correct": r[2], "verbal": r[3]} for r in cur.fetchall()}


def make_candidate(name):
    cur.execute("""
        INSERT INTO hiring_candidates (name, candidate_type, notes)
        VALUES (%s, 'applicant', 'AUTO-GENERATED TEST DATA — safe to delete')
        RETURNING id
    """, (name,))
    return cur.fetchone()[0]


def make_attempt(cid, vid):
    cur.execute("""
        INSERT INTO hiring_quiz_attempts
            (candidate_id, quiz_version_id, started_at, completed_at, arrival_status)
        VALUES (%s, %s, NOW(), NOW(), 'on_time')
        RETURNING id
    """, (cid, vid))
    return cur.fetchone()[0]


def insert_answer(attempt_id, question_id, response, skipped=False):
    raw = json.dumps(response) if response else None
    cur.execute("""
        INSERT INTO hiring_quiz_answers (attempt_id, question_id, raw_answer, skipped)
        VALUES (%s, %s, %s, %s)
    """, (attempt_id, question_id, raw, skipped))


def cleanup(candidate_ids):
    # FK ON DELETE CASCADE handles attempts → answers → contradictions
    cur.execute(
        "DELETE FROM hiring_candidates WHERE id = ANY(%s) AND name LIKE %s",
        (candidate_ids, r'__TEST_%')
    )
    conn.commit()
    print("\nCleanup done — all test data removed.")


# ── Load data ────────────────────────────────────────────────────────────────

vid = get_vid()
answers = load_correct_answers()

# Separate questions by part
a_questions = {qid: m for qid, m in answers.items() if m["part"] == "A"}
b_questions = {qid: m for qid, m in answers.items() if m["part"] == "B"}

print("=" * 60)
print("SCORING ENGINE TEST")
print("=" * 60)

test_candidate_ids = []

# ── TEST 1: Perfect candidate ─────────────────────────────────────────────────
print("\n--- Test 1: Perfect candidate ---")
cid1 = make_candidate("__TEST_Perfect__")
test_candidate_ids.append(cid1)
aid1 = make_attempt(cid1, vid)

# Part A — all correct
for qid, meta in a_questions.items():
    correct = meta["correct"]
    if isinstance(correct, dict) and "answer" in correct:
        insert_answer(aid1, qid, {"answer": correct["answer"]})

# Part B — all correct
for qid, meta in b_questions.items():
    correct = meta["correct"]
    if isinstance(correct, dict) and "answer" in correct:
        insert_answer(aid1, qid, {"answer": correct["answer"]})

# D1 — correct order
insert_answer(aid1, "D1", {
    "order": [
        "Check orders/delivery tablet",
        "Check low stock",
        "Refill items",
        "Prepare for next rush if trained",
        "Clean customer and work area",
        "Ask management what needs help",
        "Use personal phone",
    ]
})

# Written — strong answers
insert_answer(aid1, "C-Q4", {"text": "My old manager would say I need to improve my speed during rush hour. I know I sometimes slow down when it gets busy. I am working on this by practising my station setup before peak time."})
insert_answer(aid1, "C-Q8", {"text": "I would not hide the mistake. I would tell my manager immediately, apologise to the customer, fix the order, and report what happened so we can prevent it again."})
insert_answer(aid1, "C-Q12", {"text": "During quiet time I would check stock levels, restock shelves, clean preparation areas, and ask management if there is anything else that needs to be done. Quiet time is not free time."})
insert_answer(aid1, "C-Q20", {"text": "I would write a checklist for each task so any staff member can follow it. I would train two people for each role so if I am absent the work still gets done correctly. The shop should not depend on one person."})

conn.commit()

from hire_bot.scorer import auto_grade, detect_contradictions
r1 = auto_grade(aid1)
print(f"  score_a: {r1['summary']['score_a']}/60")
print(f"  score_b: {r1['summary']['score_b']}/22")
print(f"  d1_priority_score: {r1['summary']['d1_priority_score']}/3")
print(f"  critical_wrong: {r1['summary']['critical_wrong']}")
print(f"  not_sure_critical: {r1['summary']['not_sure_critical']}")
print(f"  triggers: {[t['type'] for t in r1['triggers']]}")

c1 = detect_contradictions(aid1)
print(f"  contradictions flagged: {len(c1)}")
assert r1['summary']['score_a'] == 60, f"Expected 60, got {r1['summary']['score_a']}"
assert r1['summary']['score_b'] == 22, f"Expected 22, got {r1['summary']['score_b']}"
assert r1['summary']['d1_priority_score'] == 3
assert len(r1['summary']['critical_wrong']) == 0
print("  PASS")

# ── TEST 2: Half-answer candidate ─────────────────────────────────────────────
print("\n--- Test 2: Half-answer candidate (2 critical A wrong, low written) ---")
cid2 = make_candidate("__TEST_HalfAnswer__")
test_candidate_ids.append(cid2)
aid2 = make_attempt(cid2, vid)

for qid, meta in a_questions.items():
    correct = meta["correct"]
    if isinstance(correct, dict) and "answer" in correct:
        # Get wrong answer for A1-Q5 and A4-Q38 (two critical ones)
        if qid in ("A1-Q5", "A4-Q38"):
            wrong = "yes" if correct["answer"] == "no" else "no"
            insert_answer(aid2, qid, {"answer": wrong})
        else:
            insert_answer(aid2, qid, {"answer": correct["answer"]})

for qid, meta in b_questions.items():
    correct = meta["correct"]
    if isinstance(correct, dict) and "answer" in correct:
        insert_answer(aid2, qid, {"answer": correct["answer"]})

# D1 — wrong: puts personal phone first
insert_answer(aid2, "D1", {
    "order": [
        "Use personal phone",
        "Clean customer and work area",
        "Check orders/delivery tablet",
        "Check low stock",
        "Refill items",
        "Ask management what needs help",
        "Prepare for next rush if trained",
    ]
})

# Written — thin/incomplete answers
insert_answer(aid2, "C-Q4", {"text": "I would improve my communication."})  # vague
insert_answer(aid2, "C-Q8", {"text": "I would not hide it."})  # missing what to do
insert_answer(aid2, "C-Q12", {"text": "I would wait for customers."})  # WRONG

conn.commit()

r2 = auto_grade(aid2)
print(f"  score_a: {r2['summary']['score_a']}/60")
print(f"  score_b: {r2['summary']['score_b']}/22")
print(f"  d1_priority_score: {r2['summary']['d1_priority_score']}/3")
print(f"  critical_wrong: {r2['summary']['critical_wrong']}")
print(f"  triggers: {[t['type'] for t in r2['triggers']]}")

c2 = detect_contradictions(aid2)
print(f"  contradictions flagged: {len(c2)}")

assert "A1-Q5" in r2['summary']['critical_wrong']
assert "A4-Q38" in r2['summary']['critical_wrong']
assert r2['summary']['d1_priority_score'] == 0
trigger_types = [t['type'] for t in r2['triggers']]
assert "verbal_retest" in trigger_types
assert "d1_wrong_priority" in trigger_types
print("  PASS")

# ── TEST 3: Contradictory candidate ───────────────────────────────────────────
print("\n--- Test 3: Contradictory candidate (tick right, write contradicting) ---")
cid3 = make_candidate("__TEST_Contradictory__")
test_candidate_ids.append(cid3)
aid3 = make_attempt(cid3, vid)

# Part A — all correct ticks (looks honest)
for qid, meta in a_questions.items():
    correct = meta["correct"]
    if isinstance(correct, dict) and "answer" in correct:
        insert_answer(aid3, qid, {"answer": correct["answer"]})

# Part B — all correct
for qid, meta in b_questions.items():
    correct = meta["correct"]
    if isinstance(correct, dict) and "answer" in correct:
        insert_answer(aid3, qid, {"answer": correct["answer"]})

# D1 — correct
insert_answer(aid3, "D1", {
    "order": [
        "Check orders/delivery tablet",
        "Check low stock",
        "Refill items",
        "Prepare for next rush if trained",
        "Clean customer and work area",
        "Ask management what needs help",
        "Use personal phone",
    ]
})

# Written — contradicts ticks
insert_answer(aid3, "C-Q4", {"text": "My old manager would say I am already good enough."})  # avoids self-criticism
insert_answer(aid3, "C-Q8", {"text": "I would handle it quietly and fix it myself without bothering management."})  # hides mistake!
insert_answer(aid3, "C-Q12", {"text": "I would sit and wait or maybe check my phone."})  # contradicts A4
insert_answer(aid3, "C-Q20", {"text": "I would just make sure everyone knows their job."})  # vague

conn.commit()

r3 = auto_grade(aid3)
print(f"  score_a: {r3['summary']['score_a']}/60 (all correct ticks — looks clean)")
print(f"  score_b: {r3['summary']['score_b']}/22")
print(f"  critical_wrong: {r3['summary']['critical_wrong']} (expected empty)")
print(f"  triggers from auto_grade: {[t['type'] for t in r3['triggers']]}")

c3 = detect_contradictions(aid3)
print(f"  contradictions flagged: {len(c3)}")
for c in c3:
    print(f"    [{c['severity']}] {c['qa']} vs {c['qb']}: {c['description'][:70]}...")

# Contradictions should fire because tick-vs-written contradictions exist
# (A2-Q13 ticked correct but C-Q8 says "handle quietly" = contradiction)
assert len(c3) > 0, "Should have detected at least one contradiction for contradictory candidate"
print("  PASS")

# ── Cleanup ───────────────────────────────────────────────────────────────────
cleanup(test_candidate_ids)

print("\n" + "=" * 60)
print("ALL SCORING ENGINE TESTS PASSED")
print("=" * 60)
