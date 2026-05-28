import sys
sys.path.insert(0, '/root/TWBshop')
from secrets import DATABASE_URL
import psycopg2

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    INSERT INTO hiring_candidates
        (name, candidate_type, score_a, score_b, written_pct, overall_pct, classification, hired, notes)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    RETURNING id
""", ('Lina', 'staff', 58, 22, 88, 94, 'develop',  True,
      'Met Solina. Right hand, trusted, assistant-manager track. Strong honesty + customer + team thinking. Rough English. Gaps: C-Q4 blank (self-improvement), C-Q5 incomplete on costly mistakes.'))
candidate_id = cur.fetchone()[0]

points = [
(1,  'trust_foundation',
 "Your test shows that you understand honesty, responsibility, apology, teamwork, customers, and training. That is why I trust you more than normal staff.",
 "តេស្តរបស់បងបង្ហាញថាបងយល់ពីភាពស្មោះត្រង់ ទំនួលខុសត្រូវ ការសុំទោស ការងារជាក្រុម អតិថិជន និងការបង្ហាត់បុគ្គលិក។ នោះហើយជាមូលហេតុដែលខ្ញុំទុកចិត្តបងច្រើនជាងបុគ្គលិកធម្មតា។"),
(2,  'growth_required',
 "Being trusted is not the same as being finished. A trusted person must keep growing, because more trust means more responsibility.",
 "ការត្រូវបានទុកចិត្ត មិនមែនមានន័យថាបងរួចរាល់គ្រប់យ៉ាងហើយទេ។ មនុស្សដែលត្រូវបានទុកចិត្ត ត្រូវបន្តរីកចម្រើន ព្រោះទំនុកចិត្តកាន់តែច្រើន មានន័យថាទំនួលខុសត្រូវកាន់តែច្រើន។"),
(3,  'next_level',
 "You are not only here to work correctly by yourself. Your next level is to help other people work correctly too.",
 "បងមិនមែននៅទីនេះដើម្បីធ្វើការត្រឹមត្រូវដោយខ្លួនឯងប៉ុណ្ណោះទេ។ ជំហានបន្ទាប់របស់បង គឺជួយឲ្យមនុស្សផ្សេងទៀតធ្វើការឲ្យបានត្រឹមត្រូវដែរ។"),
(4,  'right_hand_role',
 "A right hand must not only help when asked. A right hand must see problems early, organize people, and stop small problems before they become big.",
 "ដៃស្តាំមិនត្រឹមតែជួយពេលគេសុំទេ។ ដៃស្តាំត្រូវមើលឃើញបញ្ហាតូចៗតាំងពីដំបូង រៀបចំមនុស្ស និងបញ្ឈប់បញ្ហាតូចៗ មុនវាក្លាយជាបញ្ហាធំ។"),
(5,  'mistake_culture',
 "You understand that hiding mistakes is wrong. Now you must make sure others understand it too. If someone hides a mistake, the bigger problem is broken trust.",
 "បងយល់ថាការលាក់កំហុសគឺខុស។ ឥឡូវនេះ បងត្រូវធានាថាអ្នកផ្សេងក៏យល់ដូចគ្នាដែរ។ បើនរណាម្នាក់លាក់កំហុស បញ្ហាធំជាងគឺការបាត់បង់ទំនុកចិត្ត។"),
(6,  'reporting_quality',
 "When a mistake happens, a stronger habit is: what happened, why it happened, what was fixed, and how to prevent it next time.",
 "ពេលមានកំហុស ទម្លាប់ខ្លាំងជាងនេះគឺ៖ អ្វីកើតឡើង, ហេតុអ្វីវាកើតឡើង, បានកែអ្វីខ្លះ, និងការពារយ៉ាងដូចម្តេចកុំឲ្យកើតឡើងម្តងទៀត។"),
(7,  'apology_culture',
 "You understand apology well. Keep teaching that apology is not weakness. At work, saying sorry means we put the customer, the team, and the business before ego.",
 "បងយល់ល្អអំពីការសុំទោស។ ត្រូវបន្តបង្រៀនថាការសុំទោសមិនមែនជាភាពខ្សោយទេ។ នៅកន្លែងធ្វើការ ការសុំទោសមានន័យថាយើងដាក់អតិថិជន ក្រុមការងារ និងអាជីវកម្ម មុន ego របស់ខ្លួនឯង។"),
(8,  'customer_thinking',
 "You understand customers are important because customers come back when they feel good. Now teach staff that every small action affects whether customers come back.",
 "បងយល់ថាអតិថិជនសំខាន់ ព្រោះអតិថិជននឹងត្រឡប់មកវិញ បើគាត់មានអារម្មណ៍ល្អ។ ឥឡូវនេះ ជំហានបន្ទាប់គឺបង្រៀនបុគ្គលិកថា សកម្មភាពតូចៗទាំងអស់ ប៉ះពាល់ថាអតិថិជននឹងត្រឡប់មកវិញឬអត់។"),
(9,  'service_definition',
 "Service is not only smiling. Service means clean area, correct order, fast checking, calm voice, respectful words, and fixing problems quickly.",
 "សេវាកម្មមិនមែនត្រឹមតែញញឹមទេ។ សេវាកម្មមានន័យថាកន្លែងស្អាត, order ត្រឹមត្រូវ, ពិនិត្យឲ្យលឿន, សំឡេងស្ងប់ស្ងាត់, ពាក្យសមរម្យ, និងកែបញ្ហាឲ្យលឿន។"),
(10, 'quiet_time_system',
 "Quiet time must become a system, not random work. During quiet time, staff should check orders, delivery tablets, stock, refills, cleanliness, prep, and ask what else needs help.",
 "ម៉ោងស្ងាត់ត្រូវក្លាយជាប្រព័ន្ធ មិនមែនធ្វើការចៃដន្យទេ។ ពេលម៉ោងស្ងាត់ បុគ្គលិកគួរតែពិនិត្យ order, delivery tablet, stock, refill, អនាម័យ, prep, និងសួរថាមានអ្វីត្រូវជួយបន្ថែមទៀត។"),
(11, 'checklist_habit',
 "A right hand must create checklists, not only remember things in the head. If something is important, write it down, check it, and make sure another person can follow it too.",
 "ដៃស្តាំត្រូវបង្កើត checklist មិនមែនចាំតែអ្វីៗនៅក្នុងក្បាលទេ។ បើរឿងណាសំខាន់ ត្រូវកត់វា ពិនិត្យវា ហើយធានាថាមនុស្សម្នាក់ទៀតក៏អាចធ្វើតាមបានដែរ។"),
(12, 'backup_training',
 "You wrote that senior staff should train backups. That is very good. Now I want to see real backups, not only good words.",
 "បងបានសរសេរថា staff ចាស់គួរបង្ហាត់មនុស្ស backup។ នោះល្អខ្លាំង។ ឥឡូវនេះ ខ្ញុំចង់ឃើញ backup ពិតប្រាកដ មិនមែនត្រឹមតែពាក្យល្អទេ។"),
(13, 'training_method',
 "Training does not mean showing one time. Training means explain, show, watch them do it, correct them, test them again, and make sure they can do it without you.",
 "ការបង្ហាត់មិនមែនបង្ហាញម្តងហើយចប់ទេ។ ការបង្ហាត់មានន័យថា ពន្យល់ បង្ហាញ មើលគេធ្វើ កែតម្រូវគេ សាកល្បងម្តងទៀត ហើយធានាថាគេអាចធ្វើបានដោយគ្មានបងនៅក្បែរ។"),
(14, 'team_resilience',
 "If only you know how to do something, the team is still weak. The team becomes stronger when 2 or 3 people can cover the same important task.",
 "បើមានតែបងម្នាក់ដែលចេះធ្វើអ្វីមួយ ក្រុមនៅតែខ្សោយ។ ក្រុមកាន់តែរឹងមាំ នៅពេលមានមនុស្ស ២ ឬ ៣ នាក់អាចជួយគ្នាកាន់ការងារសំខាន់ដូចគ្នាបាន។"),
(15, 'kind_not_soft',
 "You must be kind, but not too soft. Helping staff is good. Protecting bad habits is not good.",
 "បងត្រូវមានចិត្តល្អ ប៉ុន្តែមិនត្រូវទន់ពេកទេ។ ការជួយបុគ្គលិកគឺល្អ។ ប៉ុន្តែការពារទម្លាប់អាក្រក់គឺមិនល្អទេ។"),
(16, 'lazy_correction',
 "If a staff member is friendly but lazy, friendship cannot be stronger than the team. A leader must correct lazy behavior early, calmly, and fairly.",
 "បើបុគ្គលិកម្នាក់រួសរាយ ប៉ុន្តែខ្ជិល មិត្តភាពមិនអាចខ្លាំងជាងក្រុមការងារបានទេ។ អ្នកដឹកនាំត្រូវកែអាកប្បកិរិយាខ្ជិល តាំងពីដំបូង ដោយស្ងប់ស្ងាត់ និងយុត្តិធម៌។"),
(17, 'early_reporting',
 "Do not wait until I see the problem. If you see a pattern, report it early and explain what you already tried to fix.",
 "កុំរង់ចាំរហូតដល់ខ្ញុំឃើញបញ្ហា។ បើបងឃើញបញ្ហាដដែលៗ ត្រូវរាយការណ៍មុន ហើយពន្យល់ថាបងបានព្យាយាមកែអ្វីខ្លះរួចហើយ។"),
(18, 'clear_reporting',
 "Reporting should be clear, not emotional. A good report says: who, what, when, why, how bad, what was done, and what should happen next.",
 "ការរាយការណ៍ត្រូវច្បាស់ មិនមែនតាមអារម្មណ៍ទេ។ របាយការណ៍ល្អត្រូវមាន៖ នរណា, អ្វី, ពេលណា, ហេតុអ្វី, ធ្ងន់ប៉ុណ្ណា, បានធ្វើអ្វីហើយ, និងបន្ទាប់គួរធ្វើអ្វី។"),
(19, 'words_carry_weight',
 "Because you are trusted, your words carry weight. That means you must be extra careful, extra fair, and extra clear.",
 "ព្រោះបងត្រូវបានទុកចិត្ត ពាក្យរបស់បងមានទម្ងន់។ នោះមានន័យថាបងត្រូវប្រុងប្រយ័ត្នជាងមុន យុត្តិធម៌ជាងមុន និងច្បាស់ជាងមុន។"),
(20, 'earn_respect_not_like',
 "Do not become the person staff only like because you are nice. Become the person staff respect because you are fair, honest, clear, and serious about standards.",
 "កុំក្លាយជាមនុស្សដែលបុគ្គលិកចូលចិត្តតែព្រោះបងចិត្តល្អ។ ត្រូវក្លាយជាមនុស្សដែលបុគ្គលិកគោរព ព្រោះបងយុត្តិធម៌ ស្មោះត្រង់ ច្បាស់លាស់ និងម៉ឺងម៉ាត់លើស្តង់ដារ។"),
(21, 'schedule_transparency',
 "Your family schedule or personal responsibilities must always be clear early. It is not wrong to have family responsibility. It is wrong to make the team guess.",
 "កាលវិភាគគ្រួសារ ឬទំនួលខុសត្រូវផ្ទាល់ខ្លួនរបស់បង ត្រូវតែប្រាប់ឲ្យច្បាស់តាំងពីដំបូង។ ការមានទំនួលខុសត្រូវគ្រួសារ មិនមែនខុសទេ។ អ្វីដែលខុសគឺធ្វើឲ្យក្រុមត្រូវទាយ ឬមិនដឹងច្បាស់។"),
(22, 'flexibility_clarity',
 "If you say you are flexible, then explain clearly what is truly flexible and what is not. Clear information helps management plan correctly.",
 "បើបងនិយាយថាបង flexible ត្រូវពន្យល់ឲ្យច្បាស់ថាអ្វីដែលពិតជាអាចបត់បែនបាន និងអ្វីដែលមិនអាចបត់បែនបាន។ ព័ត៌មានច្បាស់ជួយឲ្យអ្នកគ្រប់គ្រងរៀបចំផែនការបានត្រឹមត្រូវ។"),
(23, 'system_owner',
 "I want you to grow from trusted helper into system owner. A trusted helper helps today. A system owner makes tomorrow easier too.",
 "ខ្ញុំចង់ឲ្យបងរីកចម្រើនពីអ្នកជួយដែលគេទុកចិត្ត ទៅជាអ្នកកាន់ប្រព័ន្ធ។ អ្នកជួយដែលគេទុកចិត្ត ជួយសម្រាប់ថ្ងៃនេះ។ អ្នកកាន់ប្រព័ន្ធ ធ្វើឲ្យថ្ងៃស្អែកកាន់តែងាយស្រួលផងដែរ។"),
(24, 'thirty_day_goals',
 "For the next 30 days: train 2 backup staff for important tasks, run a stock and refill checklist, and report mistakes with prevention steps.",
 "ក្នុងរយៈពេល ៣០ ថ្ងៃបន្ទាប់ ខ្ញុំចង់ឃើញបងកាន់រឿងច្បាស់ៗ៖ បង្ហាត់ backup staff ២ នាក់សម្រាប់ការងារសំខាន់ៗ, ប្រើ stock/refill checklist, និងរាយការណ៍កំហុសជាមួយវិធីការពារ។"),
(25, 'sharpen_up',
 "You are valuable here, but I want you to become sharper. More structure, more follow-up, more written checks, and more training will make you much stronger.",
 "បងមានតម្លៃនៅទីនេះ ប៉ុន្តែខ្ញុំចង់ឲ្យបងកាន់តែច្បាស់ និង sharp ជាងមុន។ ការរៀបចំច្រើនជាងមុន ការតាមដានច្រើនជាងមុន ការពិនិត្យជាលាយលក្ខណ៍អក្សរ និងការបង្ហាត់ច្រើនជាងមុន នឹងធ្វើឲ្យបងកាន់តែខ្លាំង។"),
(26, 'trust_your_system',
 "I trust you, but I do not want to trust only your good heart. I want to trust your system, your follow-up, your training, and your ability to make the team stronger.",
 "ខ្ញុំទុកចិត្តបង ប៉ុន្តែខ្ញុំមិនចង់ទុកចិត្តតែចិត្តល្អរបស់បងប៉ុណ្ណោះទេ។ ខ្ញុំចង់ទុកចិត្តប្រព័ន្ធរបស់បង ការតាមដានរបស់បង ការបង្ហាត់របស់បង និងសមត្ថភាពរបស់បងក្នុងការធ្វើឲ្យក្រុមកាន់តែរឹងមាំ។"),
(27, 'final_encouragement',
 "If you do this, you will not only be my right hand. You will become someone who can help build stronger staff and a stronger workplace.",
 "បើបងធ្វើបាន បងនឹងមិនមែនត្រឹមតែជាដៃស្តាំរបស់ខ្ញុំទេ។ បងនឹងក្លាយជាមនុស្សដែលអាចជួយបង្កើតបុគ្គលិកខ្លាំងជាងមុន និងកន្លែងធ្វើការរឹងមាំជាងមុន។"),
]

for pt in points:
    cur.execute("""
        INSERT INTO hiring_feedback_templates
            (candidate_id, candidate_name, topic, point_number, english_text, khmer_text, score_range, is_generic)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (candidate_id, 'Lina', pt[1], pt[0], pt[2], pt[3], 'high', False))

conn.commit()
cur.execute("SELECT COUNT(*) FROM hiring_feedback_templates WHERE candidate_name = 'Lina'")
print('Points stored for Lina:', cur.fetchone()[0])
cur.execute("SELECT id, name, overall_pct, classification FROM hiring_candidates WHERE name = 'Lina'")
print('Candidate:', cur.fetchone())
conn.close()
