import sys
sys.path.insert(0, '/root/TWBshop')
from shared.database import raw_connect
import psycopg2
import json

conn = raw_connect()
cur = conn.cursor()

cur.execute("""
    SELECT id, quiz_version_id, part, section, display_order,
           question_text_en, question_text_km, answer_type,
           options, correct_answer, trait_tags, severity_if_wrong,
           requires_verbal_retest
    FROM hiring_quiz_questions
    ORDER BY part, display_order
""")
rows = cur.fetchall()


def s(v):
    if v is None:
        return 'NULL'
    return "'" + str(v).replace("'", "''") + "'"


def j(v):
    if v is None:
        return 'NULL'
    return "'" + json.dumps(v).replace("'", "''") + "'::jsonb"


def arr(v):
    if not v:
        return 'NULL'
    return "ARRAY[" + ",".join("'" + x.replace("'", "''") + "'" for x in v) + "]"


lines = [
    "-- Seed: 2026_05_28_load_final_v3_quiz_questions.sql",
    "-- 111 questions from 'Candidate Staff Interview Test - Final Edited v3'",
    "-- Safe to re-run: uses INSERT ... ON CONFLICT (id) DO UPDATE",
    "-- Requires hiring_quiz_versions row with version_name='Final v3' to exist first.",
    "",
    "INSERT INTO hiring_quiz_questions",
    "    (id, quiz_version_id, part, section, display_order,",
    "     question_text_en, question_text_km, answer_type,",
    "     options, correct_answer, trait_tags, severity_if_wrong,",
    "     requires_verbal_retest, active)",
    "VALUES",
]

parts = []
for row in rows:
    qid, vid, part, section, order_, en, km, atype, opts, correct, tags, sev, verbal = row
    parts.append(
        "    (" +
        s(qid) + ", " +
        str(vid) + ", " +
        s(part) + ", " +
        s(section) + ", " +
        str(order_) + ", " +
        s(en) + ", " +
        s(km) + ", " +
        s(atype) + ", " +
        j(opts) + ", " +
        j(correct) + ", " +
        arr(tags) + ", " +
        s(sev) + ", " +
        str(verbal).upper() + ", " +
        "TRUE)"
    )

lines.append(",\n".join(parts))
lines.append("ON CONFLICT (id) DO UPDATE SET")
lines.append("    question_text_en       = EXCLUDED.question_text_en,")
lines.append("    question_text_km       = EXCLUDED.question_text_km,")
lines.append("    correct_answer         = EXCLUDED.correct_answer,")
lines.append("    trait_tags             = EXCLUDED.trait_tags,")
lines.append("    severity_if_wrong      = EXCLUDED.severity_if_wrong,")
lines.append("    requires_verbal_retest = EXCLUDED.requires_verbal_retest,")
lines.append("    active                 = EXCLUDED.active;")

output = "\n".join(lines)
path = "/root/TWBshop/migrations/2026_05_28_load_final_v3_quiz_questions.sql"
with open(path, "w") as f:
    f.write(output)

print(f"Written: {len(rows)} questions, {len(output):,} bytes → {path}")
cur.close()
conn.close()
