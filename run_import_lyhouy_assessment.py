"""
One-time import: Yorng Lyhouy hiring screen assessment.
Paper test 2026-05-26 + Lina post-test interview observation.
13 findings from ChatGPT review + 1 owner/Lina observation.

Run once: python3 run_import_lyhouy_assessment.py
Idempotent: checks for existing assessment before inserting.
"""
import hashlib
import json
import pathlib
import sys
sys.path.insert(0, '/root/TWBshop')
from shared.database import raw_connect
import psycopg2


def hash_file(path: str):
    """SHA-256 of a local file. Returns hex string or None if not found."""
    p = pathlib.Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def map_staff_level(expectation: str, severity: str) -> str:
    if expectation == "senior_expected":
        return "senior_expected_strength" if "strength" in severity else "senior_expected_gap"
    if expectation in (
        "entry_acceptable", "worker_acceptable", "worker_gap",
        "senior_expected_strength", "senior_expected_gap",
        "supervisor_expected_strength", "supervisor_expected_gap",
        "chef_expected_strength", "chef_expected_gap",
    ):
        return expectation
    return "entry_acceptable"


def map_source_type(source_type: str) -> str:
    mapping = {
        "legacy_paper": "legacy_paper",
        "owner_observation": "observation",
        "legacy_paper_plus_owner_observation": "legacy_paper",
        "owner_context": "legacy_paper",
        "quiz": "quiz",
        "cv": "cv",
        "observation": "observation",
        "trial": "trial",
        "draft": "draft",
    }
    return mapping.get(source_type, "legacy_paper")


def map_confidence(confidence: str) -> str:
    return "medium" if confidence == "medium_high" else confidence


# ── Candidate ─────────────────────────────────────────────────────────────────

CANDIDATE = {
    "system_name": "Lyhouy",
    "display_name": "Yorng Lyhouy",
    "candidate_type": "applicant",
    "notes": (
        "Possible alt spelling: Yong Lyhouy. Applicant. Took paper test 2026-05-26. "
        "Started work 2026-05-27, shift 1pm-10pm. "
        "Student in Digital Media Design. Prior cashier/service experience, possibly Krispy Kreme. "
        "Hired conditionally — first days under close observation."
    ),
}

# ── Assessment ────────────────────────────────────────────────────────────────

ASSESSMENT = {
    "subject_status_at_assessment": "applicant",
    "assessment_source": "legacy_paper",
    "assessment_context": "hiring_screen",
    "assessor_name": "ChatGPT review from paper photos + owner/Lina post-test interview observation",
    "human_review_confidence": "medium_high",
    "notes": json.dumps({
        "known_context": (
            "Applicant. Paper test taken 2026-05-26. Started work 2026-05-27, 1pm-10pm. "
            "Student in Digital Media Design. Prior cashier/service experience. "
            "Owner hired conditionally, watching first days closely."
        ),
        "overall_interpretation": (
            "Hireable as service/cashier trainee, not supervisor. "
            "Tick answers mostly decent but written answers are MIXED/THIN — basic service instinct, "
            "not deep operational thinking. Do not label as strong written answers. "
            "Main risk: schedule-story consistency. Availability/start-date explanation changed under "
            "questioning in Lina post-test interview. Trial must validate honesty, punctuality, "
            "phone discipline, correction reaction, and schedule stability."
        ),
        "lina_interview_note": (
            "Lina conducted post-test conversation. Sequence: agreed to feedback, offered 6am-3pm, "
            "said afternoons only (study mornings), accepted 12pm-9pm, then said can only start "
            "June 1st (hometown reason), then after longer conversation said can start tomorrow "
            "if shift is 1pm-10pm. Lina accepted. This is a higher-signal event than most paper answers."
        ),
        "source_photos": "13 photos, 2026-05-26, extracted from Yorng Lyhouy.zip",
        "import_version": "v1.0",
    }),
}

# ── Evidence (13 photos already extracted locally) ────────────────────────────

_EVIDENCE_DIR = pathlib.Path(
    r"C:\Users\Papa\Documents\Bluetooth\Staff Assessments\Yorng Lyhouy\2026-05-26 hiring screen"
)

EVIDENCE = [
    {"page": i, "file_name": f"{i:02d}_page.jpg",
     "path": str(_EVIDENCE_DIR / f"{i:02d}_page.jpg"),
     "storage_status": "local_to_pc",
     "description": f"Yorng Lyhouy paper questionnaire -- photo {i} of 13. Taken 2026-05-26."}
    for i in range(1, 14)
]

# ── Findings (14 total) ───────────────────────────────────────────────────────

FINDINGS = [
    {
        "source_type": "legacy_paper",
        "source_ref": "CandidateInfo-RoleExperience",
        "answer_summary": "Presents as service/cashier. Approx 2 years cashier/customer service experience. Currently studying Digital Media Design.",
        "trait_detected": "service_cashier_exposure",
        "severity": "strength_medium",
        "staff_level_expectation": "entry_acceptable",
        "principle_tag": "role_fit",
        "contradiction_score": 0,
        "confidence": "medium_high",
        "interpretation": "Not raw zero-experience. Has some customer/cashier exposure, but the test does not prove high maturity or independent cashier trust yet.",
        "english_text": "Your cashier/service experience is useful, but here you still need to prove accuracy, honesty, calm service, and discipline during real work.",
        "khmer_text": "បទពិសោធន៍ cashier/service របស់ប្អូនអាចប្រើបាន ប៉ុន្តែនៅទីនេះប្អូននៅត្រូវបង្ហាញភាពត្រឹមត្រូវ ភាពស្មោះត្រង់ សេវាកម្មស្ងប់ស្ងាត់ និងវិន័យក្នុងការងារពិត។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "CandidateInfo-Commitment",
        "answer_summary": "For whether she can work 1 year or more if the job is fair, she marked Maybe rather than Yes.",
        "trait_detected": "commitment_uncertainty",
        "severity": "gap_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "commitment",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "Honest but not strong. For a student applicant, Maybe often means school, family, better offer, or schedule changes may interfere.",
        "english_text": "Answering Maybe for one year is honest, but it tells us your commitment is not fully clear yet. If school, family, or another plan may affect work, you must say it early.",
        "khmer_text": "ការឆ្លើយ Maybe សម្រាប់១ឆ្នាំ គឺស្មោះត្រង់ ប៉ុន្តែវាបង្ហាញថាការប្តេជ្ញារបស់ប្អូនមិនទាន់ច្បាស់ពេញលេញ។ បើសាលា គ្រួសារ ឬផែនការផ្សេងអាចប៉ះពាល់ការងារ ត្រូវប្រាប់ឲ្យបានមុន។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "CandidateInfo-SchoolSchedule",
        "answer_summary": "Marked that school schedule does not change, but also marked she can personally choose/change school time if work needs stable schedule.",
        "trait_detected": "schedule_clarity_risk",
        "severity": "gap_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "schedule_honesty",
        "contradiction_score": 1,
        "confidence": "high",
        "interpretation": "Could be true, but needs verification. Students often overpromise schedule flexibility. This became more important because her availability story changed during offer discussion.",
        "english_text": "Your school schedule must be exact. If you say you can choose or change school time, you must explain clearly which days and hours you can truly guarantee.",
        "khmer_text": "កាលវិភាគសាលារបស់ប្អូនត្រូវតែច្បាស់។ បើប្អូននិយាយថាអាចជ្រើស ឬប្តូរម៉ោងសាលា ត្រូវពន្យល់ឲ្យច្បាស់ថាថ្ងៃណា និងម៉ោងណាដែលប្អូនអាចធានាបានពិត។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "CandidateInfo-StartLeaveDates",
        "answer_summary": "Start date and known leave details were not fully clear from the paper.",
        "trait_detected": "detail_completion_gap",
        "severity": "gap_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "completion_discipline",
        "contradiction_score": 0,
        "confidence": "medium_high",
        "interpretation": "Matches the pattern of giving incomplete operational information. Does not prove dishonesty, but creates scheduling risk.",
        "english_text": "Important work information cannot be half-filled. Start date, available hours, and leave dates must be exact because the team schedule depends on them.",
        "khmer_text": "ព័ត៌មានសំខាន់សម្រាប់ការងារ មិនអាចបំពេញតែពាក់កណ្ដាលបានទេ។ ថ្ងៃចាប់ផ្តើម ម៉ោងអាចធ្វើការ និងថ្ងៃត្រូវសុំឈប់ ត្រូវច្បាស់ ព្រោះកាលវិភាគក្រុមពឹងលើវា។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "Overall-WrittenAnswers",
        "answer_summary": "Written answers are mixed: some relevant service instinct, but many answers are thin, vague, or not fully developed.",
        "trait_detected": "written_depth_mixed",
        "severity": "gap_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "completion_discipline",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": "Do not classify her written section as strong. Shows trainability and basic instinct, not deep operational maturity.",
        "english_text": "Your written answers show some good thinking, but many are too short or not complete enough. At work, incomplete answers can become incomplete work.",
        "khmer_text": "ចម្លើយសរសេររបស់ប្អូនបង្ហាញថាមានការគិតល្អខ្លះ ប៉ុន្តែច្រើននៅខ្លីពេក ឬមិនពេញលេញគ្រប់គ្រាន់។ នៅការងារ ចម្លើយមិនពេញលេញអាចក្លាយជាការងារមិនពេញលេញ។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "CustomerProblemAnswer",
        "answer_summary": "For angry customer scenario: shows basic instinct to ask/help, but not the full sequence: calm apology, listen, check, fix, inform management, follow up.",
        "trait_detected": "customer_instinct_trainable",
        "severity": "strength_medium",
        "staff_level_expectation": "entry_acceptable",
        "principle_tag": "customer_service",
        "contradiction_score": 0,
        "confidence": "medium_high",
        "interpretation": "Useful basic service instinct, but needs a clear service-recovery formula before being trusted with difficult customers alone.",
        "english_text": "When a customer is upset, do not only ask what happened. Stay calm, apologize for the problem, check quickly, fix what can be fixed, and inform management if needed.",
        "khmer_text": "ពេលអតិថិជនមិនពេញចិត្ត កុំគ្រាន់តែសួរថាមានអ្វីកើតឡើង។ ត្រូវស្ងប់ស្ងាត់ សុំទោសចំពោះបញ្ហា ពិនិត្យឲ្យលឿន កែអ្វីដែលអាចកែបាន ហើយប្រាប់អ្នកគ្រប់គ្រងបើចាំបាច់។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "QuietTimeAnswer",
        "answer_summary": "Quiet-time answers acceptable: understands she should work, clean, help, or prepare, but no strong stock-check/prep system mindset yet.",
        "trait_detected": "quiet_time_trainable",
        "severity": "strength_medium",
        "staff_level_expectation": "entry_acceptable",
        "principle_tag": "quiet_time",
        "contradiction_score": 0,
        "confidence": "medium_high",
        "interpretation": "Trainable. Needs daily checklist behavior: orders/tablet, stock, refill, clean, prep, ask senior.",
        "english_text": "Quiet time is not waiting time. It should become a habit: check orders, check stock, refill, clean, prepare, and ask what else needs help.",
        "khmer_text": "ម៉ោងស្ងាត់មិនមែនជាម៉ោងរង់ចាំទេ។ វាត្រូវក្លាយជាទម្លាប់៖ ពិនិត្យ order, ពិនិត្យ stock, បំពេញរបស់, សម្អាត, ត្រៀមការងារ និងសួរថាមានអ្វីត្រូវជួយបន្ថែម។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "TickAnswers-Overall",
        "answer_summary": "Tick answers mostly decent: recognizes basic workplace rules — reporting mistakes, hygiene, low stock communication, helping during quiet time, transport communication.",
        "trait_detected": "basic_rule_recognition",
        "severity": "strength_medium",
        "staff_level_expectation": "entry_acceptable",
        "principle_tag": "workplace_rules",
        "contradiction_score": 0,
        "confidence": "medium_high",
        "interpretation": "She can recognize many correct workplace choices when presented as options. Real work will test whether she acts correctly without multiple-choice prompts.",
        "english_text": "Your tick answers show you understand many basic rules. Now you must prove those rules in real work, without someone giving choices.",
        "khmer_text": "ចម្លើយគូសប្រអប់របស់ប្អូនបង្ហាញថាប្អូនយល់ច្បាប់មូលដ្ឋានជាច្រើន។ ឥឡូវនេះប្អូនត្រូវបង្ហាញវាក្នុងការងារពិត ដោយគ្មាននរណាផ្តល់ជម្រើសឲ្យ។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "CV-vs-Test",
        "answer_summary": "CV presents cashier/customer service ability, but the paper test does not fully prove the same level of maturity, cash discipline, or pressure handling.",
        "trait_detected": "cv_claim_needs_trial_validation",
        "severity": "gap_low_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "experience_credibility",
        "contradiction_score": 0,
        "confidence": "medium_high",
        "interpretation": "Do not pay or trust based on CV alone. Trial should test cash accuracy, customer tone, order checking, and pressure response.",
        "english_text": "A CV can say cashier/customer service, but real work must prove cash accuracy, order accuracy, calm voice, and pressure handling.",
        "khmer_text": "CV អាចសរសេរថា cashier/customer service ប៉ុន្តែការងារពិតត្រូវបង្ហាញភាពត្រឹមត្រូវលុយ ភាពត្រឹមត្រូវ order សំឡេងស្ងប់ស្ងាត់ និងការទប់សម្ពាធ។",
    },
    {
        "source_type": "legacy_paper",
        "source_ref": "WorkAttitudeTone",
        "answer_summary": "Some wording/tone suggests directness or sharp coworker attitude rather than soft social style. May be honest self-awareness or may become teamwork friction.",
        "trait_detected": "team_tone_watch",
        "severity": "gap_low_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "team_behavior",
        "contradiction_score": 0,
        "confidence": "medium",
        "interpretation": "Do not punish directness automatically. Watch whether directness becomes rude tone, coldness, or conflict with coworkers/customers.",
        "english_text": "It is okay not to be a sweet person. But at work, direct words must still be respectful, calm, and useful to the team.",
        "khmer_text": "មិនចាំបាច់ជាមនុស្សផ្អែមពេកក៏បាន។ ប៉ុន្តែនៅការងារ ពាក្យត្រង់ៗត្រូវនៅតែមានការគោរព ស្ងប់ស្ងាត់ និងមានប្រយោជន៍សម្រាប់ក្រុម។",
    },
    # Finding 11 — corrected/strengthened version (Lina interview, full sequence)
    {
        "source_type": "owner_observation",
        "source_ref": "PostTest-LinaInterview-ScheduleStory",
        "answer_summary": (
            "After reading and agreeing to the feedback message, she was offered 6am-3pm starting tomorrow. "
            "Said she could only work afternoons because she later wants to study mornings. "
            "Accepted 12pm-9pm, then said she could only start June 1st, gave hometown reason. "
            "After longer conversation with Lina about needs/life/work, said she could start tomorrow "
            "if shift was 1pm-10pm. Lina accepted."
        ),
        "trait_detected": "schedule_story_consistency_risk",
        "severity": "risk_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "schedule_honesty",
        "contradiction_score": 2,
        "confidence": "high",
        "interpretation": (
            "This is more important than most paper answers. It does not prove malicious dishonesty, "
            "but it shows her start-date and availability story changed under questioning. "
            "Most likely risk: unstable self-reporting — she may answer based on pressure, comfort, "
            "or what sounds acceptable instead of stating the real condition clearly from the beginning. "
            "First 3 days must validate punctuality, truthfulness, correction reaction, phone discipline, "
            "and whether her schedule story stays stable."
        ),
        "english_text": "Your schedule story must be clean from the beginning. If you can start tomorrow only with a certain shift, say that directly. Changing the story later makes management lose trust.",
        "khmer_text": "រឿងកាលវិភាគរបស់ប្អូនត្រូវតែច្បាស់តាំងពីដំបូង។ បើប្អូនអាចចាប់ផ្តើមថ្ងៃស្អែកបានតែជាមួយម៉ោងជាក់លាក់មួយ ត្រូវនិយាយត្រង់ៗតាំងពីដំបូង។ ការប្តូររឿងក្រោយមកធ្វើឲ្យអ្នកគ្រប់គ្រងបាត់ទំនុកចិត្ត។",
    },
    # Finding 12 — new (pressure response signal from Lina interview)
    {
        "source_type": "owner_observation",
        "source_ref": "PostTest-LinaInterview-PressureResponse",
        "answer_summary": "During the longer Lina conversation, her answer changed from delayed start to immediate start once the shift became 1pm-10pm.",
        "trait_detected": "pressure_response_unclear",
        "severity": "gap_medium",
        "staff_level_expectation": "worker_gap",
        "principle_tag": "truthfulness_under_pressure",
        "contradiction_score": 1,
        "confidence": "high",
        "interpretation": (
            "May mean she was negotiating schedule, afraid to state her real preference, "
            "or casually giving a convenient reason. Not confirmed bad character yet, "
            "but a real trial-watch item."
        ),
        "english_text": "When management asks about schedule, answer the real condition clearly. Do not give one reason first and a different condition later.",
        "khmer_text": "ពេលអ្នកគ្រប់គ្រងសួរអំពីកាលវិភាគ ត្រូវឆ្លើយលក្ខខណ្ឌពិតឲ្យច្បាស់។ កុំឲ្យហេតុផលមួយជាមុន ហើយបន្ទាប់មកទើបនិយាយលក្ខខណ្ឌផ្សេង។",
    },
    # Finding 13 — hiring decision (owner observation)
    {
        "source_type": "owner_observation",
        "source_ref": "HiringDecision",
        "answer_summary": "Owner hired her conditionally, starting 2026-05-27, 1pm-10pm, watching first days closely.",
        "trait_detected": "trial_validation_needed",
        "severity": "gap_medium",
        "staff_level_expectation": "entry_acceptable",
        "principle_tag": "trial_followup",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": (
            "Correct decision: not immediate trust, not immediate rejection. "
            "Trial decides. Watch arrival time, phone, correction reaction, honesty, memory, "
            "order/customer accuracy, and whether schedule story stays stable."
        ),
        "english_text": "The real test is your first days at work: arrive on time, use phone correctly, accept correction, report honestly, remember instructions, and keep your schedule story stable.",
        "khmer_text": "តេស្តពិតគឺថ្ងៃដំបូងៗនៅការងារ៖ មកទាន់ម៉ោង ប្រើទូរស័ព្ទឲ្យត្រឹមត្រូវ ទទួលការកែតម្រូវ រាយការណ៍ដោយស្មោះ ចងចាំបញ្ជា និងរក្សារឿងកាលវិភាគឲ្យនៅច្បាស់ដដែល។",
    },
    # Finding 14 — overall (combined paper + observation)
    {
        "source_type": "legacy_paper_plus_owner_observation",
        "source_ref": "Overall",
        "answer_summary": "Overall: hireable service/cashier trainee, not leadership; basic rule recognition and service instinct; written answers mixed/thin; schedule-story risk requires trial validation.",
        "trait_detected": "hireable_with_conditions",
        "severity": "strength_medium",
        "staff_level_expectation": "entry_acceptable",
        "principle_tag": "hiring_decision",
        "contradiction_score": 0,
        "confidence": "high",
        "interpretation": (
            "Treat as controlled trainee. Do not overtrust CV or tick answers. "
            "If first days show punctuality, honesty, humility, and learning speed, she may become useful. "
            "If story-changing, phone, attitude, or correction resistance appears, cut early."
        ),
        "english_text": "You are hireable as a trainee, but trust must be earned in real work. Good first days can change the picture; bad habits in the first days will also tell us quickly.",
        "khmer_text": "ប្អូនអាចចូលធ្វើការជាអ្នកកំពុងរៀនបាន ប៉ុន្តែទំនុកចិត្តត្រូវរកបានពីការងារពិត។ ថ្ងៃដំបូងៗល្អអាចធ្វើឲ្យរូបភាពល្អឡើង; ទម្លាប់អាក្រក់នៅថ្ងៃដំបូងៗក៏នឹងបង្ហាញឲ្យយើងឃើញលឿនដែរ។",
    },
]


# ── Import ────────────────────────────────────────────────────────────────────

def run():
    conn = raw_connect()
    cur = conn.cursor()
    try:
        # 1. Find or create candidate
        cur.execute("SELECT id FROM hiring_candidates WHERE name = %s",
                    (CANDIDATE["system_name"],))
        row = cur.fetchone()
        if row:
            candidate_id = row[0]
            print(f"Found existing candidate: id={candidate_id}")
        else:
            cur.execute("""
                INSERT INTO hiring_candidates (name, candidate_type, notes)
                VALUES (%s, %s, %s) RETURNING id
            """, (CANDIDATE["system_name"], CANDIDATE["candidate_type"],
                  CANDIDATE["notes"]))
            candidate_id = cur.fetchone()[0]
            print(f"Created candidate: id={candidate_id} name={CANDIDATE['system_name']}")

        # 2. Idempotent guard
        cur.execute("""
            SELECT id FROM hiring_assessments
            WHERE candidate_id = %s
              AND assessment_source = %s
              AND assessment_context = %s
            LIMIT 1
        """, (candidate_id, ASSESSMENT["assessment_source"],
              ASSESSMENT["assessment_context"]))
        existing = cur.fetchone()
        if existing:
            print(f"Assessment already exists: id={existing[0]} -- skipping.")
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

        # 4. Insert evidence rows
        for ev in EVIDENCE:
            fhash = hash_file(ev["path"])
            cur.execute("""
                INSERT INTO hiring_assessment_evidence
                    (assessment_id, evidence_type, file_name, file_path_or_url,
                     page_or_photo_number, file_hash, storage_status, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                assessment_id, "photo", ev["file_name"], ev["path"],
                ev["page"], fhash, ev["storage_status"], ev["description"],
            ))
        print(f"  {len(EVIDENCE)} evidence rows inserted"
              f" ({'hashed' if hash_file(EVIDENCE[0]['path']) else 'no hash — files not on this machine'})")

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
                i, "linked", "chatgpt_visual_review_plus_owner_obs", "v1.0",
            ))
            print(f"  Finding {i:02d}: {f['source_ref']:<45} {f['severity']:<18} {staff_lvl}")

        conn.commit()
        print(f"\nDone. 1 assessment + {len(EVIDENCE)} evidence + {len(FINDINGS)} findings"
              f" for {CANDIDATE['display_name']}.")
        print(f"assessment_id={assessment_id}  candidate_id={candidate_id}")

    except Exception as e:
        conn.rollback()
        print(f"ERROR -- rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
