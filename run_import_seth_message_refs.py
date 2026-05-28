"""
One-time import: link specific ops_messages rows to Seth's assessment findings.
Adds hiring_assessment_message_refs rows with chat_id, message_id, sender, text.

Run AFTER the v2 migration (which creates the hiring_assessment_message_refs table).
Safe to re-run: ON CONFLICT DO NOTHING.
"""
import sys
sys.path.insert(0, '/root/TWBshop')
from secrets import DATABASE_URL
import psycopg2

ASSESSMENT_ID = 5
SUPERVISORS_CHAT_ID = -4980513319
STOCK_CHECKS_CHAT_ID = -1003952029131

# finding_id → point_number mapping (from hiring_feedback_points, assessment_id=5)
FINDING_IDS = {
    1: 90,   # punctuality_gap
    2: 91,   # payback_pattern
    3: 92,   # multi_supervisor_reporting
    4: 93,   # no_show_exam_claim
    5: 94,   # rotating_excuse_pattern
    6: 95,   # management_response_gap
}

# Each ref: (finding_point, chat_id, message_id, confidence, notes)
# message_id here = ops_messages.id (not Telegram message_id — we store the DB id)
# Confirmed from ops_messages query 2026-05-28
MESSAGE_REFS = [
    # Finding 1 — punctuality_gap (Mar 11)
    # id=792213: SAM PHARM reports "Mr pisey" late 30mn, busy at mom's house
    # "pisey" = Phan Piseth/Seth in this context (matches known Mar 11 incident)
    (1, SUPERVISORS_CHAT_ID, 792213, "likely",
     "SAM PHARM: 'Mr pisey late 30mn because he was busy with his family at his mom house'. "
     "Content matches known Mar 11 incident. 'pisey' = Seth (Phan Piseth); "
     "marked likely not confirmed because SAM PHARM also reports SAM-side Mr Pisey."),

    # Finding 1 — punctuality_gap (May 12)
    # id=792273: Rath Phal reports "Mr Piseth asked permission for come late 1h"
    (1, SUPERVISORS_CHAT_ID, 792273, "confirmed",
     "Rath Phal: 'Mr Piseth asked permission for come late 1h'. Unambiguous — full name."),

    # Finding 2 — payback_pattern (Mar 13)
    # id=792215: SAM PHARM: "And Mr Sith he payback 1h already"
    # "Sith" = likely Seth typo; content matches payback pattern
    (2, SUPERVISORS_CHAT_ID, 792215, "likely",
     "SAM PHARM: 'Mr Sith he payback 1h already'. 'Sith' is likely a typo for Seth."),

    # Finding 2 — payback_pattern (Apr 25)
    # id=792256: Bart KimHeng: "inform piseth he pay back 1hour already"
    (2, SUPERVISORS_CHAT_ID, 792256, "confirmed",
     "Bart KimHeng: 'inform piseth he pay back 1hour already'. Clear payback log."),

    # Finding 2 — payback_pattern (Apr 27: asking for 4pm start)
    # id=792258: Lina So: "Mr Piseth can't come on time he ask to come at 4pm"
    (2, SUPERVISORS_CHAT_ID, 792258, "confirmed",
     "Lina So: 'Mr Piseth can't come on time he ask to come at 4pm.' Same-day 4pm request."),

    # Finding 2 — payback_pattern (May 3)
    # id=792264: por Khmer Bruce PP: "piseth has paid back 2hrs"
    (2, SUPERVISORS_CHAT_ID, 792264, "confirmed",
     "por Khmer Bruce PP: 'piseth has paid back 2hrs'. Por is the primary payback reporter."),

    # Finding 3 — multi_supervisor_reporting (no single message — link to May 27 general context)
    # id=792886: Met Solina: "Mr Piseth ask permission again today" — word 'again' is key
    (3, SUPERVISORS_CHAT_ID, 792886, "confirmed",
     "Met Solina: 'Mr Piseth ask permission again today he can't come to work because have exams.' "
     "Word 'again' is the key signal — supervisor treats this as an established pattern. "
     "Multi-supervisor evidence: Lina So (792258), Bart KimHeng (792256), "
     "Por/Bruce (792264), Rath Phal (792273), Met Solina (this message)."),

    # Finding 4 — no_show_exam_claim (May 27)
    # id=792886: Met Solina full no-show report
    (4, SUPERVISORS_CHAT_ID, 792886, "confirmed",
     "Met Solina: 'Mr Piseth ask permission again today he can't come to work because have exams.' "
     "Full no-show on May 27. Same-day notice. Exam date was knowable in advance."),

    # Finding 4 — corroboration: Seth's own May 27 introduction in Stock Checks
    # id=792905: Seth 🫵: "Hello Sir,My name Phan Piseth ,call me Seth"
    (4, STOCK_CHECKS_CHAT_ID, 792905, "confirmed",
     "Seth 🫵: 'Hello Sir,My name Phan Piseth ,call me Seth.' "
     "Entity confirmation: Phan Piseth = Seth in Stock Checks. "
     "Same day as no-show (May 27) — posted on Stock Checks while absent from work."),

    # Finding 5 — rotating_excuse_pattern (link key messages showing different excuses)
    # Mar 11: mom's house (792213), Apr 27: can't come on time (792258), May 27: exams (792886)
    (5, SUPERVISORS_CHAT_ID, 792213, "likely",
     "Excuse 1 (Mar 11): 'busy with family at mom house'. Different from later excuses."),

    (5, SUPERVISORS_CHAT_ID, 792258, "confirmed",
     "Excuse 2 (Apr 27): 'can't come on time' — no specific reason given, just requesting 4pm."),

    (5, SUPERVISORS_CHAT_ID, 792886, "confirmed",
     "Excuse 3 (May 27): 'have exams' — third distinct reason across three months."),
]


def run():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        inserted = 0
        skipped = 0
        for finding_point, chat_id, msg_id, confidence, notes in MESSAGE_REFS:
            finding_id = FINDING_IDS.get(finding_point)
            cur.execute("""
                INSERT INTO hiring_assessment_message_refs
                    (assessment_id, finding_id, chat_id, ops_message_row_id, confidence, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (assessment_id, finding_id, chat_id, ops_message_row_id) DO NOTHING
            """, (ASSESSMENT_ID, finding_id, chat_id, msg_id, confidence, notes))
            if cur.rowcount:
                inserted += 1
                print(f"  + finding={finding_point} msg_id={msg_id} ({confidence})")
            else:
                skipped += 1

        conn.commit()
        print(f"\nDone. {inserted} refs inserted, {skipped} already existed.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR — rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
