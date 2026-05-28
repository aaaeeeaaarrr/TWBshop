import sys
sys.path.insert(0, '/root/TWBshop')
from secrets import DATABASE_URL
import psycopg2
import json

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("=" * 60)
print("QUIZ BANK AUDIT — Final Edited v3")
print("=" * 60)

# 1. Count by part
cur.execute("SELECT part, COUNT(*) FROM hiring_quiz_questions GROUP BY part ORDER BY part")
total = 0
print("\n1. Count by part:")
for part, cnt in cur.fetchall():
    print(f"   Part {part}: {cnt}")
    total += cnt
print(f"   TOTAL: {total}  (expected 111)")

# 2. Duplicate IDs
cur.execute("SELECT id, COUNT(*) FROM hiring_quiz_questions GROUP BY id HAVING COUNT(*) > 1")
dupes = cur.fetchall()
print(f"\n2. Duplicate IDs: {len(dupes)} (expected 0)")
for d in dupes:
    print("   DUPE:", d)

# 3. Missing correct answers for Part A/B and D1
cur.execute("""
    SELECT id, part, answer_type FROM hiring_quiz_questions
    WHERE correct_answer IS NULL AND part IN ('A', 'B')
""")
missing = cur.fetchall()
print(f"\n3. Part A/B with NULL correct_answer: {len(missing)} (expected 0)")
for m in missing:
    print("  ", m)

cur.execute("SELECT correct_answer FROM hiring_quiz_questions WHERE id = 'D1'")
d1 = cur.fetchone()
print(f"   D1 correct_answer: {json.dumps(d1[0]) if d1 and d1[0] else 'MISSING'}")

# 4. Missing EN or KM text
cur.execute("""
    SELECT id FROM hiring_quiz_questions
    WHERE question_text_en IS NULL OR question_text_en = ''
       OR question_text_km IS NULL OR question_text_km = ''
""")
missing_text = cur.fetchall()
print(f"\n4. Missing EN or KM text: {len(missing_text)} (expected 0)")
for m in missing_text:
    print("  ", m)

# 5. Critical questions check
critical_expected = sorted([
    'A1-Q5','A1-Q7','A2-Q12','A2-Q13','A2-Q20','A4-Q34','A4-Q38',
    'A5-Q42','A5-Q44','A6-Q51','A6-Q57','A6-Q58',
    'B-Q3','B-Q8','B-Q9','B-Q19','B-Q21','B-Q22',
    'C-Q4','C-Q8','C-Q12','D1','D-Final'
])
cur.execute("SELECT id FROM hiring_quiz_questions WHERE severity_if_wrong = 'critical' ORDER BY id")
actual_critical = [r[0] for r in cur.fetchall()]
print(f"\n5. severity=critical count: {len(actual_critical)}")
print("   ", actual_critical)
missing_crit = [q for q in critical_expected if q not in actual_critical]
extra_crit = [q for q in actual_critical if q not in critical_expected]
if missing_crit:
    print("   MISSING CRITICAL TAG:", missing_crit)
if extra_crit:
    print("   EXTRA (not in expected list):", extra_crit)
if not missing_crit and not extra_crit:
    print("   OK — matches expected list")

# 6. Verbal retest flags
retest_expected = sorted(['A1-Q5','A1-Q7','A2-Q13','A2-Q20','A4-Q38','A5-Q42','A6-Q51','A6-Q58'])
cur.execute("SELECT id FROM hiring_quiz_questions WHERE requires_verbal_retest = TRUE ORDER BY id")
actual_retest = [r[0] for r in cur.fetchall()]
print(f"\n6. requires_verbal_retest=TRUE: {len(actual_retest)}")
print("   ", actual_retest)
if actual_retest != retest_expected:
    print("   MISMATCH! Expected:", retest_expected)
else:
    print("   OK")

# 7. Trait tags coverage
cur.execute("SELECT COUNT(*) FROM hiring_quiz_questions WHERE trait_tags IS NULL OR array_length(trait_tags,1) IS NULL")
no_tags = cur.fetchone()[0]
print(f"\n7. Questions with no trait_tags: {no_tags}")
if no_tags > 0:
    cur.execute("SELECT id FROM hiring_quiz_questions WHERE trait_tags IS NULL OR array_length(trait_tags,1) IS NULL ORDER BY id")
    print("   Untagged:", [r[0] for r in cur.fetchall()])

# 8. D1 ranking expected order
cur.execute("SELECT correct_answer FROM hiring_quiz_questions WHERE id = 'D1'")
row = cur.fetchone()
if row and row[0]:
    order = row[0].get('correct_order', [])
    print(f"\n8. D1 correct_order ({len(order)} items):")
    for i, item in enumerate(order):
        print(f"   {i+1}. {item}")
    first = order[0].lower() if order else ""
    last = order[-1].lower() if order else ""
    if "order" not in first and "tablet" not in first:
        print("   WARNING: first item should be orders/tablet!")
    else:
        print("   First item OK (orders/tablet)")
    if "phone" not in last and "personal" not in last:
        print("   WARNING: last item should be personal phone!")
    else:
        print("   Last item OK (personal phone)")
else:
    print("\n8. D1 correct_order: MISSING or NULL — auto_grade will fail for D1!")

print("\n" + "=" * 60)
print("AUDIT COMPLETE")
print("=" * 60)
cur.close()
conn.close()
