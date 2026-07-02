"""
One-time import: Phan Piseth (Seth) attendance reliability review.
Source: ops_messages DB (Supervisors TWB group + Stock Checks group messages).

Run once on server: python3 run_import_seth_assessment.py
Safe to re-run: checks for existing candidate/assessment before inserting.

Requires migration 2026_05_28_part_e_and_ops_assessment.sql to be run first
(adds ops_messages + attendance_review to CHECK constraints).
"""
import json
import sys
sys.path.insert(0, '/root/TWBshop')
from shared.database import raw_connect
import psycopg2


CANDIDATE = {
    "name": "Phan Piseth",
    "candidate_type": "existing_staff",
    "notes": (
        "Day-shift service staff. Alias: Seth (used in all group chats). "
        "Self-introduced in Stock Checks group 2026-05-27: 'Hello Sir, My name Phan Piseth, call me Seth'. "
        "NOTE: Not the same person as Piseth Vinal (Hikaru, night bakery) or 'Mr Pisey' (SAM-side kitchen). "
        "Three separate people — never merge these records."
    ),
}

ASSESSMENT = {
    "subject_status_at_assessment": "existing_staff",
    "assessment_source": "ops_messages",
    "assessment_context": "attendance_review",
    "assessor_name": "ops_messages_review (Supervisors TWB + Stock Checks, 2026-03 to 2026-05)",
    "human_review_confidence": "high",
    "notes": json.dumps({
        "review_period": "2026-03-01 to 2026-05-27",
        "data_sources": [
            "Supervisors TWB group (chat_id=-4980513319): reports from Lina So, Bart KimHeng, Por/Bruce, Rath Phal, Met Solina",
            "Stock Checks group (chat_id=-1003952029131): Seth's own messages, Por reporting",
        ],
        "pattern_summary": (
            "Repeated lateness across March–May 2026 with rotating excuses. "
            "Multiple supervisors independently reporting. "
            "Full no-show on 2026-05-27 citing exams. "
            "Payback hours logged at least 4 times in 2 months. "
            "Pattern is not isolated incidents — it is recurring attendance unreliability."
        ),
        "known_context": (
            "Seth joined and is assigned day-shift service. "
            "Supervisors Por (Bruce), Lina, Met Solina, Bart, Rath have all reported him. "
            "No prior formal accountability conversation documented."
        ),
        "import_version": "v1.0",
    }),
}

FINDINGS = [
    {
        "source_type": "observation",
        "source_ref": "supervisors_group_2026-03",
        "answer_summary": (
            "Mar 11: late 30 minutes, reason 'busy at mom's house'. "
            "Reported by supervisor in Supervisors TWB group."
        ),
        "trait_detected": "punctuality_gap",
        "severity": "risk_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "schedule_reliability",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": (
            "Personal-errand reason for lateness. Supervisor logged it. "
            "Alone, this would be a minor incident. Pattern context makes it one data point in a trend."
        ),
        "english_text": (
            "Being late because of personal errands shows the job is not the first priority on that day. "
            "Every late arrival adds pressure to the team and management."
        ),
        "khmer_text": (
            "ការមកយឺតដោយសារធ្វើការផ្ទាល់ខ្លួនបង្ហាញថា ការងារមិនមែនជាអ្វីដំបូងក្នុងថ្ងៃនោះ។ "
            "រាល់ការមកយឺត បន្ថែមសម្ពាធដល់ក្រុម និងការគ្រប់គ្រង។"
        ),
    },
    {
        "source_type": "observation",
        "source_ref": "supervisors_group_2026-04-to-05",
        "answer_summary": (
            "Apr 25: paid back 1hr, reported by Por. "
            "Apr 27: asked for 4pm start (cannot come on time). "
            "May 3: paid back 2hrs, Por reporting. "
            "May 12: late 1hr. "
            "Payback pattern also noted Mar 15 and Mar 20."
        ),
        "trait_detected": "payback_pattern",
        "severity": "risk_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "schedule_reliability",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": (
            "At least 4 confirmed payback instances across March–May 2026. "
            "Por (Bruce) is the primary reporter. "
            "Payback itself means management already accepted the lateness — but the frequency is the issue. "
            "This is not occasional; it is a pattern within the first months on the job."
        ),
        "english_text": (
            "Paying back hours is not a solution if the late arrivals keep happening. "
            "Management cannot keep adjusting the schedule around one person's recurring attendance issues."
        ),
        "khmer_text": (
            "ការបំពេញម៉ោងវិញមិនមែនជាដំណោះស្រាយ បើការមកយឺតនៅតែបន្ត។ "
            "ការគ្រប់គ្រងមិនអាចបន្តកែតម្រូវកាលវិភាគសម្រាប់អ្នកម្នាក់ដែលមានបញ្ហាវត្តមានជាប់រហូតបានទេ។"
        ),
    },
    {
        "source_type": "observation",
        "source_ref": "supervisors_group_multi",
        "answer_summary": (
            "At least 5 different supervisors/managers have reported or noted Seth's attendance: "
            "Lina So, Bart KimHeng, Por/Bruce, Rath Phal, Met Solina. "
            "Reporting spans the full period March–May 2026."
        ),
        "trait_detected": "multi_supervisor_reporting",
        "severity": "risk_high",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "schedule_reliability",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": (
            "Multi-supervisor independent reporting is the strongest signal here. "
            "This is not one supervisor being strict — multiple people across the team have noted it. "
            "When attendance problems are visible to the whole management layer, they become a team morale issue, "
            "not just a schedule issue."
        ),
        "english_text": (
            "When multiple supervisors are all reporting the same attendance problem independently, "
            "it is no longer a personal matter — it is a team issue that needs a formal response."
        ),
        "khmer_text": (
            "នៅពេលដែលអ្នកគ្រប់គ្រងជាច្រើននាក់ រាយការណ៍ពីបញ្ហាវត្តមានដូចគ្នាដោយឯករាជ្យ "
            "វាលែងជារឿងផ្ទាល់ខ្លួនទៀតហើយ — វាជាបញ្ហារបស់ក្រុម ដែលត្រូវការការឆ្លើយតបផ្លូវការ។"
        ),
    },
    {
        "source_type": "observation",
        "source_ref": "supervisors_group_2026-05-27",
        "answer_summary": (
            "2026-05-27: Full no-show. "
            "Met Solina reported: 'Mr Piseth ask permission again today he can't come to work because have exams.' "
            "Key word: 'again' — supervisor already treats this as a recurring pattern."
        ),
        "trait_detected": "no_show_exam_claim",
        "severity": "risk_high",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "schedule_reliability",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": (
            "Full shift no-show on 2026-05-27. Excuse: exams. "
            "Supervisor's use of 'again' confirms the team already sees this as habitual. "
            "Exam dates are knowable in advance — if Seth is studying, he should have disclosed his schedule "
            "and arranged cover days in advance, not called in the same day. "
            "This is the most serious single incident: full no-show + same-day notice + part of a pattern."
        ),
        "english_text": (
            "Exam dates are known in advance. A full no-show on the day with same-day notice is not acceptable. "
            "The right way is to give the exam date to management at least a week before and arrange cover."
        ),
        "khmer_text": (
            "ថ្ងៃប្រឡងអាចដឹងជាស្រេចទុកជាមុន។ ការមិនមកធ្វើការទាំងស្រុង ហើយប្រាប់ថ្ងៃតែមួយ មិនអាចទទួលយកបានទេ។ "
            "វិធីត្រឹមត្រូវគឺ ប្រាប់ការគ្រប់គ្រងពីថ្ងៃប្រឡង យ៉ាងហោចណាស់មួយសប្ដាហ៍មុន ហើយរកនរណាម្នាក់ចូលជំនួស។"
        ),
    },
    {
        "source_type": "observation",
        "source_ref": "rotating_excuse_pattern",
        "answer_summary": (
            "Different excuses across incidents: 'busy at mom's house' (Mar 11), "
            "no reason given (Mar 15, 20 paybacks), 'can't come on time' (Apr 27), "
            "'exams' (May 27). No single consistent reason."
        ),
        "trait_detected": "rotating_excuse_pattern",
        "severity": "risk_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "honesty_logic",
        "contradiction_score": 1,
        "confidence": "medium",
        "interpretation": (
            "The variety of excuses across incidents is itself a signal. "
            "A genuine scheduling conflict would have a consistent cause (school schedule, second job, transport). "
            "Rotating reasons suggest the excuse is post-hoc, not a real structural constraint. "
            "Confidence medium because each individual excuse cannot be confirmed as false — "
            "only the pattern as a whole is suspicious."
        ),
        "english_text": (
            "Different excuses every time is a pattern. "
            "If there is a real reason, name it clearly once, and management can help plan around it. "
            "A different story each time makes it hard to trust the reason."
        ),
        "khmer_text": (
            "ហេតុផលផ្សេងគ្នារាល់ពេល គឺជារូបភាពមួយ។ "
            "បើមានហេតុផលពិត ត្រូវប្រាប់ឲ្យច្បាស់ម្ដង ហើយការគ្រប់គ្រងអាចជួយដោះស្រាយបាន។ "
            "រឿងផ្លាស់ប្ដូររាល់ពេល ធ្វើឲ្យពិបាកជឿ។"
        ),
    },
    {
        "source_type": "observation",
        "source_ref": "accountability_gap",
        "answer_summary": (
            "No documented formal accountability conversation with Seth about his attendance pattern as of 2026-05-27. "
            "Management has been absorbing the incidents without a structured response."
        ),
        "trait_detected": "management_response_gap",
        "severity": "gap_high",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "schedule_reliability",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": (
            "ACTION REQUIRED: A formal one-on-one conversation is needed. "
            "Frame it as pattern, not punishment: show the specific dates, show the payback log, "
            "name the no-show, explain the team impact. "
            "Ask Seth to explain what is actually causing this. "
            "If it is school schedule: negotiate a fixed schedule accommodation and confirm in writing. "
            "If there is no real reason: set a clear standard with a defined consequence for the next incident. "
            "Do this before assuming the worst — but do not delay past the next payback or no-show."
        ),
        "english_text": (
            "You need to hear from Seth directly about what is causing this pattern. "
            "Give him a chance to explain. Then set a clear agreement: specific dates, specific expectations, "
            "specific consequence if it continues. Put it in writing."
        ),
        "khmer_text": (
            "អ្នកត្រូវស្ដាប់ Seth ផ្ទាល់ ថាហេតុអ្វីបណ្ដាលឲ្យមានរូបភាពនេះ។ "
            "ផ្ដល់ឱកាសសម្រាប់គាត់ពន្យល់។ បន្ទាប់មកកំណត់ការព្រមព្រៀងច្បាស់លាស់: "
            "ថ្ងៃច្បាស់លាស់ ការរំពឹងច្បាស់លាស់ និងផលវិបាកច្បាស់លាស់ បើបន្ត។ "
            "ត្រូវសរសេរជាលាយលក្ខណ៍អក្សរ។"
        ),
    },
]


# ── Import ────────────────────────────────────────────────────────────────────

def run():
    conn = raw_connect()
    cur = conn.cursor()
    try:
        # 1. Find or create candidate (match by name AND alias hint in notes)
        cur.execute(
            "SELECT id FROM hiring_candidates WHERE name = %s",
            (CANDIDATE["name"],)
        )
        row = cur.fetchone()
        if row:
            candidate_id = row[0]
            print(f"Found existing candidate: id={candidate_id} name={CANDIDATE['name']}")
        else:
            cur.execute("""
                INSERT INTO hiring_candidates (name, candidate_type, notes)
                VALUES (%s, %s, %s) RETURNING id
            """, (CANDIDATE["name"], CANDIDATE["candidate_type"], CANDIDATE["notes"]))
            candidate_id = cur.fetchone()[0]
            print(f"Created candidate: id={candidate_id} name={CANDIDATE['name']}")

        # 2. Idempotent guard
        cur.execute("""
            SELECT id FROM hiring_assessments
            WHERE candidate_id = %s
              AND assessment_source = %s
              AND assessment_context = %s
            LIMIT 1
        """, (candidate_id, ASSESSMENT["assessment_source"], ASSESSMENT["assessment_context"]))
        existing = cur.fetchone()
        if existing:
            print(f"Assessment already exists: id={existing[0]} — skipping.")
            print("Delete it first if you want to re-import.")
            conn.rollback()
            return

        # 3. Create assessment
        cur.execute("""
            INSERT INTO hiring_assessments
                (candidate_id, subject_status_at_assessment, assessment_source,
                 assessment_context, quiz_attempt_id, assessor_name,
                 human_review_confidence, notes)
            VALUES (%s, %s, %s, %s, NULL, %s, %s, %s)
            RETURNING id
        """, (
            candidate_id,
            ASSESSMENT["subject_status_at_assessment"],
            ASSESSMENT["assessment_source"],
            ASSESSMENT["assessment_context"],
            ASSESSMENT["assessor_name"],
            ASSESSMENT["human_review_confidence"],
            ASSESSMENT["notes"],
        ))
        assessment_id = cur.fetchone()[0]
        print(f"Created assessment: id={assessment_id}")

        # 4. Insert findings
        for i, f in enumerate(FINDINGS, 1):
            cur.execute("""
                INSERT INTO hiring_feedback_points
                    (candidate_id, assessment_id, source_type, source_ref,
                     answer_summary, trait_detected, severity,
                     staff_level_expectation, principle_tag,
                     contradiction_score, confidence, interpretation,
                     english_text, khmer_text,
                     point_number, evidence_status, generated_by, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                candidate_id, assessment_id,
                f["source_type"], f["source_ref"],
                f["answer_summary"], f["trait_detected"], f["severity"],
                f["staff_level_expectation"], f["principle_tag"],
                f["contradiction_score"], f["confidence"], f["interpretation"],
                f["english_text"], f["khmer_text"],
                i, "linked", "ops_messages_review", "v1.0",
            ))
            print(f"  Finding {i:02d}: {f['source_ref']:<40} {f['severity']}")

        conn.commit()
        print(
            f"\nDone. 1 assessment + {len(FINDINGS)} findings imported for {CANDIDATE['name']} (Seth)."
        )
        print(f"assessment_id={assessment_id}  candidate_id={candidate_id}")

    except Exception as e:
        conn.rollback()
        print(f"ERROR — rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
