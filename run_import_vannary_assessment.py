"""
One-time import: Hong Vannary legacy paper leadership audit.
14 findings from ChatGPT visual review of uploaded paper photos.

Run once on server: python3 run_import_vannary_assessment.py
Safe to re-run: checks for existing candidate/assessment before inserting.
"""
import json
import sys
sys.path.insert(0, '/root/TWBshop')
from shared.database import raw_connect
import psycopg2

# ── Mapping helpers ───────────────────────────────────────────────────────────

def hash_file(path: str):
    """SHA-256 of a local file. Returns hex string or None if file not found."""
    import hashlib
    import pathlib
    p = pathlib.Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def map_staff_level(expectation: str, severity: str) -> str:
    """
    ChatGPT uses 'senior_expected' as a shorthand.
    DB CHECK needs the strength/gap suffix derived from severity.
    'worker_acceptable' is already in the enum and passes through.
    """
    if expectation == "senior_expected":
        return "senior_expected_strength" if "strength" in severity else "senior_expected_gap"
    if expectation in (
        "entry_acceptable", "worker_acceptable", "worker_gap",
        "senior_expected_strength", "senior_expected_gap",
        "supervisor_expected_strength", "supervisor_expected_gap",
        "chef_expected_strength", "chef_expected_gap",
    ):
        return expectation
    return "worker_acceptable"  # safe fallback


def map_confidence(confidence: str) -> str:
    """Per-finding confidence only has low/medium/high; map medium_high → medium."""
    return "medium" if confidence == "medium_high" else confidence


def map_source_type(source_type: str) -> str:
    """Map ChatGPT source types to DB enum."""
    mapping = {
        "owner_context": "legacy_paper",
        "legacy_paper": "legacy_paper",
        "quiz": "quiz",
        "cv": "cv",
        "observation": "observation",
        "trial": "trial",
        "draft": "draft",
    }
    return mapping.get(source_type, "legacy_paper")


# ── Assessment data ───────────────────────────────────────────────────────────

CANDIDATE = {
    "system_name": "Vannary",
    "display_name": "Hong Vannary",
    "candidate_type": "existing_staff",
    "notes": (
        "Existing senior kitchen staff / chef. Previously assistant chef years ago. "
        "Joined around 4 years ago. Owner developed her internally into chef. "
        "Telegram aliases: 'Hong Vannary', 'Hong Vanary'."
    ),
}

ASSESSMENT = {
    "subject_status_at_assessment": "senior_staff",
    "assessment_source": "legacy_paper",
    "assessment_context": "leadership_audit",
    "assessor_name": "ChatGPT visual review from uploaded paper photos",
    "human_review_confidence": "medium_high",
    "notes": json.dumps({
        "known_context": (
            "Existing senior kitchen staff / chef. Previously assistant chef years ago. "
            "Joined around 4 years ago. Owner built her into chef internally."
        ),
        "overall_interpretation": (
            "Strong loyalty, work attitude, operational understanding, and customer/product awareness. "
            "Not a new-applicant profile. Main gap is not honesty or willingness; main gap is "
            "senior-level leadership method: structured training, checking, correcting, and building backups."
        ),
        "source_photos": "Uploaded to ChatGPT — filenames to be added when available.",
        "import_version": "v1.0",
    }),
}

# Evidence rows for this assessment.
# When you know the actual filenames:
#   - Update evidence row #1 to photo #1 (file_name, file_path_or_url, storage_status, page_or_photo_number=1)
#   - Insert extra rows for photos #2, #3, etc.
#   - hash_file(path) computes SHA-256 automatically if the file is on this machine
# Never leave file_name=None alongside rows that have real file names.
EVIDENCE = [
    {
        "evidence_type": "photo",
        "file_name": None,          # ← fill in: e.g. "IMG_1234.jpg"
        "file_path_or_url": None,   # ← fill in: local path or cloud URL
        "page_or_photo_number": None,
        "storage_status": "chatgpt_only",
        "description": (
            "Paper questionnaire photos uploaded to ChatGPT for visual review. "
            "Not saved elsewhere. Update this row to photo #1 when filenames are known; "
            "insert additional rows for photos #2, #3, etc."
        ),
    },
]

FINDINGS = [
    {
        "source_type": "owner_context",
        "source_ref": "owner_statement",
        "answer_summary": "Owner reports she was previously assistant chef and was built internally into current chef over around 4 years.",
        "trait_detected": "internal_growth_loyalty",
        "severity": "strength_high",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "leadership_potential",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "High-value internal-growth case. Her value should be judged differently from an applicant; she already proved retention and development.",
        "english_text": "You are not being judged like a new applicant. You have already grown inside this workplace, so the next step is becoming stronger at leading and training others.",
        "khmer_text": "អ្នកមិនត្រូវបានវាយតម្លៃដូចបេក្ខជនថ្មីទេ។ អ្នកបានរីកចម្រើននៅក្នុងកន្លែងការងារនេះរួចហើយ ដូច្នេះជំហានបន្ទាប់គឺត្រូវខ្លាំងជាងមុនក្នុងការដឹកនាំ និងបង្រៀនអ្នកដទៃ។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "CandidateInfo",
        "answer_summary": "Marked bakery experience, no other job, willing to work harder for higher job/pay, English speaking and reading medium, not studying.",
        "trait_detected": "availability_and_growth_readiness",
        "severity": "strength_medium",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "schedule_clarity",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "Stable availability and no school conflict. For existing senior staff, this supports deeper training responsibility.",
        "english_text": "Your availability is stable, so management can expect more from you than from someone who is still unstable with school or outside work.",
        "khmer_text": "ពេលវេលារបស់អ្នកមានស្ថិរភាព ដូច្នេះគ្រប់គ្រងអាចរំពឹងពីអ្នកបានច្រើនជាងមនុស្សដែលនៅមានបញ្ហាសាលា ឬការងារខាងក្រៅ។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "A2-Q13",
        "answer_summary": "For 'Hiding a mistake is worse than making an honest mistake,' she appears to mark No.",
        "trait_detected": "honesty_concept_gap",
        "severity": "risk_critical",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "honesty_logic",
        "contradiction_score": 2,
        "confidence": "medium_high",
        "interpretation": (
            "PENDING VERBAL RETEST — do not treat as confirmed dishonesty. "
            "The paper tick appears to show No, but handwriting/position was ambiguous. "
            "A senior staff member must understand that hiding destroys trust faster than the original mistake. "
            'Retest question: "This question says: Hiding a mistake is worse than making an honest mistake. '
            "On your paper it looks like you answered No. Maybe you misunderstood. "
            'Tell me in your own words: if you make a mistake and nobody sees it, what should you do first, and why?". '
            "If she answers correctly in person, downgrade to gap_medium. If she defends hiding, escalate."
        ),
        "english_text": "A mistake can usually be fixed. Hiding a mistake damages trust, and trust is much harder to repair.",
        "khmer_text": "កំហុសភាគច្រើនអាចកែបាន។ ប៉ុន្តែការលាក់កំហុសធ្វើឲ្យបាត់ទំនុកចិត្ត ហើយទំនុកចិត្តកែវិញពិបាកជាងកំហុសដើម។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "A4-Q38",
        "answer_summary": "For 'Good staff work even when management is not watching,' her tick appears unclear / possibly Not Sure.",
        "trait_detected": "self_management_standard",
        "severity": "gap_medium",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "quiet_time_work_ethic",
        "contradiction_score": 1,
        "confidence": "low",
        "interpretation": "If truly Not Sure, this is a senior-level concern. A chef must work correctly without being watched and must make others do the same. Confidence low — tick position unclear from photo.",
        "english_text": "Senior staff must work correctly even when nobody is watching, and must teach younger staff to do the same.",
        "khmer_text": "បុគ្គលិកចាស់ ឬអ្នកដឹកនាំ ត្រូវធ្វើការឲ្យត្រឹមត្រូវ ទោះគ្មាននរណាមើលក៏ដោយ ហើយត្រូវបង្រៀនបុគ្គលិកក្មេងឲ្យធ្វើដូចគ្នា។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "C-Q3",
        "answer_summary": "She wrote that she sometimes forgot a small thing for customer/app order and learned to double-check.",
        "trait_detected": "self_correction",
        "severity": "strength_high",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "honesty_logic",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "Good sign: admits a concrete mistake and names the correction habit (double-checking). Consistent with someone developing honest self-awareness.",
        "english_text": "This is the right way to learn from mistakes: name the mistake, fix the system, and double-check next time.",
        "khmer_text": "នេះជាវិធីត្រឹមត្រូវក្នុងការរៀនពីកំហុស៖ ប្រាប់កំហុសឲ្យច្បាស់ កែប្រព័ន្ធការងារ ហើយពិនិត្យម្ដងទៀតនៅពេលក្រោយ។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "C-Q12",
        "answer_summary": "For quiet time, she wrote to clean, check products, do something useful, and help the team.",
        "trait_detected": "quiet_time_productivity",
        "severity": "strength_high",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "quiet_time_work_ethic",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "Good senior habit: quiet time is preparation, checking, cleaning, and team support — not waiting.",
        "english_text": "Quiet time is not rest time. It is the time to clean, check stock, prepare, and help the team before the next rush.",
        "khmer_text": "ពេលស្ងាត់មិនមែនជាពេលសម្រាកទេ។ វាជាពេលសម្អាត ពិនិត្យស្តុក រៀបចំ និងជួយក្រុម មុនពេលរវល់មកវិញ។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "C-Q21",
        "answer_summary": "She wrote customers come back because of service, good food, good pastry, and bread.",
        "trait_detected": "customer_product_awareness",
        "severity": "strength_high",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "customer_instinct",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "Connects repeat customers to service and product quality, not only friendliness. Practical and correct.",
        "english_text": "Customers come back because service and product quality stay consistent. Food, pastry, bread, and attitude all matter together.",
        "khmer_text": "អតិថិជនត្រឡប់មកវិញ ព្រោះសេវាកម្ម និងគុណភាពផលិតផលនៅតែស្ថិរភាព។ ម្ហូប នំ ប៉័ង និងអាកប្បកិរិយា សុទ្ធតែសំខាន់ជាមួយគ្នា។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "D1",
        "answer_summary": "Ranked: ask management/senior first, cleaning second, refill third, prepare fourth, low stock fifth, check orders/tablet last.",
        "trait_detected": "priority_order_gap",
        "severity": "gap_medium",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "quiet_time_work_ethic",
        "contradiction_score": 0,
        "confidence": "medium_high",
        "interpretation": "Not terrible, but wrong for senior staff. Orders/tablet and stock must come before asking management. A chef should know and act, not ask first.",
        "english_text": "As senior staff, do not only ask what to do first. First check live orders, low stock, preparation, and customer-impact items, then ask if anything else needs help.",
        "khmer_text": "ក្នុងនាមជាបុគ្គលិកចាស់ កុំគ្រាន់តែសួរថាត្រូវធ្វើអ្វីមុនគេ។ មុនគេត្រូវពិនិត្យអ័រឌឺ ស្តុកជិតអស់ ការរៀបចំ និងអ្វីដែលប៉ះពាល់អតិថិជន បន្ទាប់មកសួរថាមានអ្វីផ្សេងត្រូវជួយទៀត។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "D2",
        "answer_summary": "Identified: late arrival, no message, leaving another staff packing alone, needed to check before delivery, find customer solution, report to group after.",
        "trait_detected": "operational_problem_detection",
        "severity": "strength_high",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "completion_discipline",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "Strong answer. Sees multiple operational failures, not only one obvious mistake. Good chain-of-mistakes thinking.",
        "english_text": "Good answer: you saw several problems, not only the missing item. Senior staff must see the whole chain of mistakes.",
        "khmer_text": "ចម្លើយល្អ៖ អ្នកបានឃើញបញ្ហាច្រើន មិនមែនតែរបស់ខ្វះមួយទេ។ បុគ្គលិកចាស់ត្រូវមើលឃើញខ្សែសង្វាក់កំហុសទាំងមូល។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "D3",
        "answer_summary": "For training new staff after experienced staff leave: wrote general ideas — no worry, learn from job, positive thinking, try your best, follow rules, follow good staff/good advice.",
        "trait_detected": "training_method_gap",
        "severity": "gap_medium",
        "staff_level_expectation": "senior_expected",  # → senior_expected_gap via map_staff_level
        "principle_tag": "training_method",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": (
            "Worker-level answer: correct attitude, not senior-level method. "
            "Her answer (positive thinking, follow rules, try your best) is acceptable "
            "for a normal worker but is the core training-method gap for someone at chef/senior level. "
            "Missing: explain, show, watch them do it, correct mistakes, test again, build backups. "
            "This is the most important growth target."
        ),
        "english_text": "For senior staff, 'try your best' is not enough. Training means explain, show, watch them do it, correct mistakes, test again, and build backups.",
        "khmer_text": "សម្រាប់បុគ្គលិកចាស់ ពាក្យថា «ខំប្រឹងឲ្យអស់ពីសមត្ថភាព» មិនគ្រប់គ្រាន់ទេ។ ការបង្រៀនមានន័យថា ពន្យល់ បង្ហាញ មើលគេធ្វើ កែកំហុស សាកល្បងម្ដងទៀត និងបង្កើតអ្នកជំនួស។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "D4-NoCustomers",
        "answer_summary": "For bad answer 'No customers, I wait,' she wrote something about asking customer to wait while checking — does not answer the quiet-time problem.",
        "trait_detected": "question_focus_gap",
        "severity": "gap_low_medium",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "quiet_time_work_ethic",
        "contradiction_score": 2,
        "confidence": "medium_high",
        "interpretation": "She understands quiet time elsewhere (C-Q12 strong), so this looks like comprehension slip on the question, not a belief problem.",
        "english_text": "Read the exact question carefully. If there are no customers, the answer is clean, refill, check stock, prepare, and ask what else needs help.",
        "khmer_text": "ត្រូវអានសំណួរឲ្យច្បាស់។ បើគ្មានអតិថិជន ចម្លើយគឺ សម្អាត បំពេញរបស់ ពិនិត្យស្តុក រៀបចំ និងសួរថាមានអ្វីត្រូវជួយទៀត។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "D4-Mistake",
        "answer_summary": "For 'If I make mistake, I try not do again,' she improved it to saying sorry to management and not making more mistakes.",
        "trait_detected": "mistake_repair_partial",
        "severity": "gap_low_medium",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "honesty_logic",
        "contradiction_score": 0,
        "confidence": "medium_high",
        "interpretation": "Direction is correct but incomplete. Senior staff should add root cause and prevention: why it happened, what changed, who needs to know.",
        "english_text": "After a mistake, sorry is only the start. A senior person must explain why it happened, fix the cause, and make sure the same mistake does not repeat.",
        "khmer_text": "បន្ទាប់ពីធ្វើខុស ការសុំទោសគឺជាការចាប់ផ្តើមប៉ុណ្ណោះ។ មនុស្សចាស់ត្រូវពន្យល់ថាហេតុអ្វីបានកើតឡើង កែហេតុដើម និងធានាថាកំហុសដដែលមិនកើតឡើងម្ដងទៀត។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "FinalQuestion",
        "answer_summary": "She wrote the test reminded her, gave more experience, taught good management/leadership, helping younger staff, working together, good service, food, pastry, and making the boss happy.",
        "trait_detected": "leadership_potential_owner_alignment",
        "severity": "strength_high",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "leadership_potential",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "Strong loyalty and desire to grow. 'Making the boss happy' is loyalty, not dishonesty — but needs to mature toward system stability and trained staff who work correctly without the boss present.",
        "english_text": "Good staff do not only make the boss happy. Good senior staff build a team and system that work correctly even when the boss is not there.",
        "khmer_text": "បុគ្គលិកល្អមិនមែនគ្រាន់តែធ្វើឲ្យថៅកែពេញចិត្តទេ។ បុគ្គលិកចាស់ល្អ ត្រូវបង្កើតក្រុម និងប្រព័ន្ធការងារ ដែលដំណើរការត្រឹមត្រូវ ទោះថៅកែមិននៅក៏ដោយ។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "Overall",
        "answer_summary": "Tick answers mostly correct, written answers show loyalty, effort, customer/product awareness, operational sense; senior leadership answers often general.",
        "trait_detected": "senior_development_profile",
        "severity": "strength_medium",
        "staff_level_expectation": "senior_expected",
        "principle_tag": "leadership_potential",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "Not a pass/fail case. Best use: retraining plan — turn reliable chef into structured trainer and backup-builder.",
        "english_text": "Your next growth is not only cooking or working hard. It is training people, checking systems, correcting early, and making the kitchen stronger without depending only on you.",
        "khmer_text": "ការរីកចម្រើនបន្ទាប់របស់អ្នក មិនមែនតែចម្អិន ឬខំធ្វើការទេ។ ការរីកចម្រើនបន្ទាប់គឺបង្រៀនមនុស្ស ពិនិត្យប្រព័ន្ធ កែកំហុសឲ្យបានលឿន និងធ្វើឲ្យផ្ទះបាយខ្លាំងឡើង ដោយមិនពឹងតែលើអ្នកម្នាក់ឯង។",
    },
]


# ── Import ────────────────────────────────────────────────────────────────────

def run():
    conn = raw_connect()
    cur = conn.cursor()
    try:
        # 1. Find or create candidate
        cur.execute("SELECT id FROM hiring_candidates WHERE name = %s", (CANDIDATE["system_name"],))
        row = cur.fetchone()
        if row:
            candidate_id = row[0]
            print(f"Found existing candidate: id={candidate_id} name={CANDIDATE['system_name']}")
        else:
            cur.execute("""
                INSERT INTO hiring_candidates (name, candidate_type, notes)
                VALUES (%s, %s, %s) RETURNING id
            """, (CANDIDATE["system_name"], CANDIDATE["candidate_type"], CANDIDATE["notes"]))
            candidate_id = cur.fetchone()[0]
            print(f"Created candidate: id={candidate_id} name={CANDIDATE['system_name']}")

        # 2. Check for existing assessment (idempotent guard)
        cur.execute("""
            SELECT id FROM hiring_assessments
            WHERE candidate_id = %s
              AND assessment_source = %s
              AND assessment_context = %s
            LIMIT 1
        """, (candidate_id, ASSESSMENT["assessment_source"], ASSESSMENT["assessment_context"]))
        existing = cur.fetchone()
        if existing:
            print(f"Assessment already exists: id={existing[0]} — skipping to avoid duplicates.")
            print("Delete it first if you want to re-import.")
            conn.rollback()
            return

        # 3. Create assessment event
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

        # 4. Insert evidence rows
        for ev in EVIDENCE:
            fhash = hash_file(ev["file_path_or_url"]) if ev.get("file_path_or_url") else None
            cur.execute("""
                INSERT INTO hiring_assessment_evidence
                    (assessment_id, evidence_type, file_name, file_path_or_url,
                     page_or_photo_number, description, file_hash, storage_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                assessment_id, ev["evidence_type"], ev["file_name"],
                ev.get("file_path_or_url"), ev.get("page_or_photo_number"),
                ev["description"], fhash, ev["storage_status"],
            ))
        print(f"  {len(EVIDENCE)} evidence row(s) inserted")

        # 5. Insert findings
        for i, f in enumerate(FINDINGS, 1):
            staff_lvl = map_staff_level(f["staff_level_expectation"], f["severity"])
            source_t = map_source_type(f["source_type"])
            conf = map_confidence(f["confidence"])
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
                candidate_id, assessment_id, source_t, f["source_ref"],
                f["answer_summary"], f["trait_detected"], f["severity"],
                staff_lvl, f["principle_tag"],
                f["contradiction_score"], conf, f["interpretation"],
                f["english_text"], f["khmer_text"],
                i, "linked", "chatgpt_visual_review", "v1.0",
            ))
            print(f"  Finding {i:02d}: {f['source_ref']:<20} {f['severity']:<18} {staff_lvl}")

        conn.commit()
        print(f"\nDone. 1 assessment + {len(FINDINGS)} findings imported for {CANDIDATE['system_name']}.")
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
