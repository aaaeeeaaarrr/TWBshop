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
""", ('Por','staff',60,22,93,95,'strong',True,
      'Current staff, promising, taking new responsibilities. Best quiz score seen so far. Owner: answered maybe the best.'))
candidate_id = cur.fetchone()[0]

points = [
(1,'responsibility',
 "Your test shows that you understand responsibility, honesty, customers, teamwork, and training. That is not small. Many staff can work, but not many staff understand why the work matters.",
 "តេស្តរបស់ប្អូនបង្ហាញថាប្អូនយល់ពីទំនួលខុសត្រូវ ភាពស្មោះត្រង់ អតិថិជន ការងារជាក្រុម និងការបង្ហាត់បុគ្គលិក។ នេះមិនមែនជារឿងតូចទេ។ បុគ្គលិកជាច្រើនអាចធ្វើការ ប៉ុន្តែមិនច្រើនទេដែលយល់ថាហេតុអ្វីការងារនោះសំខាន់។"),
(2,'business_thinking',
 "You answered many questions like someone who thinks from the business side, not only from the staff side. That is why I see potential in you.",
 "ប្អូនបានឆ្លើយសំណួរជាច្រើនដូចជាមនុស្សដែលគិតពីខាងអាជីវកម្ម មិនមែនគិតតែពីខាងបុគ្គលិកប៉ុណ្ណោះទេ។ នោះហើយជាមូលហេតុដែលខ្ញុំឃើញសក្តានុពលនៅក្នុងប្អូន។"),
(3,'readiness',
 "But potential is not the same as being ready. A good test answer is only the beginning. Real proof is how you act every day under pressure.",
 "ប៉ុន្តែសក្តានុពល មិនដូចគ្នានឹងការត្រៀមរួចរាល់ទេ។ ចម្លើយតេស្តល្អ គ្រាន់តែជាចំណុចចាប់ផ្តើមប៉ុណ្ណោះ។ ភស្តុតាងពិតគឺរបៀបដែលប្អូនប្រព្រឹត្តរៀងរាល់ថ្ងៃ នៅពេលមានសម្ពាធ។"),
(4,'leadership_goal',
 "I do not want you to become only good staff. I want to see if you can become someone who makes other staff better too.",
 "ខ្ញុំមិនចង់ឲ្យប្អូនក្លាយជាតែបុគ្គលិកល្អប៉ុណ្ណោះទេ។ ខ្ញុំចង់មើលថាប្អូនអាចក្លាយជាមនុស្សដែលធ្វើឲ្យបុគ្គលិកផ្សេងៗកាន់តែល្អឡើងបានដែរឬទេ។"),
(5,'next_level',
 "The next level is not just working hard. The next level is helping the shift run smoothly even when management is not standing beside you.",
 "ជំហានបន្ទាប់ មិនមែនត្រឹមតែធ្វើការខ្លាំងទេ។ ជំហានបន្ទាប់គឺជួយឲ្យវេនដំណើរការល្អ ទោះបីអ្នកគ្រប់គ្រងមិនឈរនៅក្បែរប្អូនក៏ដោយ។"),
(6,'early_problem_detection',
 "A future leader does not wait for problems to become big. A future leader sees small problems early, fixes what he can, and reports clearly.",
 "មនុស្សដែលអាចក្លាយជាអ្នកដឹកនាំនៅថ្ងៃក្រោយ មិនរង់ចាំឲ្យបញ្ហាក្លាយជាធំទេ។ មនុស្សបែបនោះមើលឃើញបញ្ហាតូចៗតាំងពីដំបូង កែអ្វីដែលអាចកែបាន ហើយរាយការណ៍ឲ្យច្បាស់។"),
(7,'quiet_time',
 "When there are no customers, quiet time is not personal time. Quiet time is when strong staff prepare the shop for the next busy time. You should check orders, delivery tablets, stock, refill items, cleanliness, and what the team needs next.",
 "ពេលគ្មានអតិថិជន ម៉ោងស្ងាត់មិនមែនជាម៉ោងផ្ទាល់ខ្លួនទេ។ ម៉ោងស្ងាត់គឺជាពេលដែលបុគ្គលិកខ្លាំងរៀបចំហាងសម្រាប់ម៉ោងរវល់បន្ទាប់។ ប្អូនគួរតែពិនិត្យ order, delivery tablet, stock, បំពេញសម្ភារៈ, សម្អាត និងមើលថាក្រុមត្រូវការអ្វីបន្ទាប់។"),
(8,'delivery_accuracy',
 "One responsibility I want you to grow in is delivery and order accuracy. A missing item is not a small mistake. It affects the customer, the shop, the driver, and the team. Good staff pack orders. Strong staff build a habit that prevents missing items.",
 "ទំនួលខុសត្រូវមួយដែលខ្ញុំចង់ឲ្យប្អូនរីកចម្រើន គឺភាពត្រឹមត្រូវនៃ delivery និង order។ អីវ៉ាន់ខ្វះមួយ មិនមែនជាកំហុសតូចទេ។ វាប៉ះពាល់អតិថិជន ហាង អ្នកដឹក និងក្រុមការងារ។ បុគ្គលិកល្អវេចខ្ចប់ order។ បុគ្គលិកខ្លាំងបង្កើតទម្លាប់ដែលការពារកុំឲ្យមានអីវ៉ាន់ខ្វះ។"),
(9,'training_responsibility',
 "Another responsibility is training. You wrote that staff should train others and the team should become stronger. That answer was good. Now I want to see if you can actually train one person until they can do the task correctly without you.",
 "ទំនួលខុសត្រូវមួយទៀតគឺការបង្ហាត់បុគ្គលិក។ ប្អូនបានសរសេរថាបុគ្គលិកគួរបង្ហាត់គ្នា ហើយក្រុមគួរតែកាន់តែរឹងមាំ។ ចម្លើយនោះល្អ។ ឥឡូវនេះ ខ្ញុំចង់ឃើញថាប្អូនអាចបង្ហាត់មនុស្សម្នាក់ឲ្យធ្វើការងារមួយបានត្រឹមត្រូវ ដោយមិនចាំបាច់មានប្អូននៅក្បែរទេ។"),
(10,'training_method',
 "Training does not mean only showing once. Training means explain, show, watch them do it, correct them, and check again later. If they still cannot do it, then the training is not finished.",
 "ការបង្ហាត់មិនមែនមានន័យថាបង្ហាញម្តងហើយចប់ទេ។ ការបង្ហាត់មានន័យថា ពន្យល់ បង្ហាញ មើលគេធ្វើ កែគេ ហើយពិនិត្យម្តងទៀតនៅពេលក្រោយ។ បើគេនៅតែមិនអាចធ្វើបាន នោះមានន័យថាការបង្ហាត់មិនទាន់ចប់ទេ។"),
(11,'leadership_character',
 "A leader must not only be friendly. A leader must be fair, calm, clear, and brave enough to correct wrong behavior. If your friend is lazy, your job is not to protect laziness. Your job is to help the person improve and protect the team.",
 "អ្នកដឹកនាំមិនអាចមានតែភាពរួសរាយប៉ុណ្ណោះទេ។ អ្នកដឹកនាំត្រូវតែយុត្តិធម៌ ស្ងប់ស្ងាត់ ច្បាស់លាស់ និងក្លាហានគ្រប់គ្រាន់ក្នុងការកែអាកប្បកិរិយាខុស។ បើមិត្តរបស់ប្អូនខ្ជិល ការងាររបស់ប្អូនមិនមែនការពារភាពខ្ជិលនោះទេ។ ការងាររបស់ប្អូនគឺជួយឲ្យមនុស្សនោះកែលម្អ និងការពារក្រុមការងារ។"),
(12,'honesty_over_friendship',
 "If a staff member hides a mistake and asks you not to tell management, you must not follow that. Friendship cannot be stronger than honesty. We can fix a mistake, but broken trust is much harder to repair.",
 "បើបុគ្គលិកម្នាក់លាក់កំហុស ហើយសុំឲ្យប្អូនកុំប្រាប់អ្នកគ្រប់គ្រង ប្អូនមិនត្រូវធ្វើតាមនោះទេ។ មិត្តភាពមិនអាចខ្លាំងជាងភាពស្មោះត្រង់បានទេ។ យើងអាចកែកំហុសបាន ប៉ុន្តែទំនុកចិត្តដែលបាត់បង់ហើយ គឺពិបាកកែត្រឡប់មកវិញណាស់។"),
(13,'reporting_quality',
 "When you report a problem, do not report only the story. A strong report should include: what happened, why it happened, what was done, and how to prevent it next time. This is how staff become responsible operators, not just workers.",
 "ពេលប្អូនរាយការណ៍បញ្ហា កុំរាយការណ៍តែរឿងរ៉ាវប៉ុណ្ណោះ។ របាយការណ៍ខ្លាំងគួរតែមាន៖ អ្វីកើតឡើង, ហេតុអ្វីវាកើតឡើង, បានធ្វើអ្វីដើម្បីកែ, និងការពារយ៉ាងដូចម្តេចកុំឲ្យកើតម្តងទៀត។ នេះជារបៀបដែលបុគ្គលិកក្លាយជាអ្នកដំណើរការការងារដែលមានទំនួលខុសត្រូវ មិនមែនគ្រាន់តែជាអ្នកធ្វើការទេ។"),
(14,'customer_handling',
 "Customer problems must be handled with calmness. Even if the mistake is not yours, the customer still needs help, not excuses. The correct habit is: listen, apologize for the problem, check quickly, fix what can be fixed, and inform management if needed.",
 "បញ្ហាអតិថិជនត្រូវដោះស្រាយដោយភាពស្ងប់ស្ងាត់។ ទោះបីកំហុសមិនមែនជារបស់ប្អូនក៏ដោយ អតិថិជនត្រូវការជំនួយ មិនមែនលេសទេ។ ទម្លាប់ត្រឹមត្រូវគឺ៖ ស្តាប់ សុំទោសចំពោះបញ្ហា ពិនិត្យឲ្យលឿន កែអ្វីដែលអាចកែបាន ហើយប្រាប់អ្នកគ្រប់គ្រងប្រសិនបើចាំបាច់។"),
(15,'systems_thinking',
 "Your answer about making the workplace run smoothly without you was one of your strongest answers. That is real systems thinking. Now you must prove it by making tasks clear, training backups, and not keeping knowledge only in your own head.",
 "ចម្លើយរបស់ប្អូនអំពីការធ្វើឲ្យកន្លែងធ្វើការដំណើរការល្អ ទោះបីគ្មានប្អូន ក៏ជាចម្លើយខ្លាំងបំផុតមួយរបស់ប្អូន។ នោះគឺជាការគិតបែបប្រព័ន្ធពិតប្រាកដ។ ឥឡូវនេះ ប្អូនត្រូវបង្ហាញវាឲ្យឃើញ ដោយធ្វើឲ្យការងារច្បាស់ បង្ហាត់អ្នក backup ហើយមិនរក្សាចំណេះដឹងទុកតែក្នុងក្បាលប្អូនម្នាក់ឯងទេ។"),
(16,'reliability_in_small_things',
 "If you want more responsibility, you must become reliable in small things first. Small things are: being on time, checking orders, refilling items, cleaning without being told, reporting early, and finishing tasks fully. People who cannot control small things cannot be trusted with big things.",
 "បើប្អូនចង់បានទំនួលខុសត្រូវច្រើនជាងមុន ប្អូនត្រូវក្លាយជាមនុស្សអាចទុកចិត្តបានលើរឿងតូចៗជាមុន។ រឿងតូចៗគឺ៖ មកទាន់ម៉ោង, ពិនិត្យ order, បំពេញសម្ភារៈ, សម្អាតដោយមិនចាំបាច់មានគេប្រាប់, រាយការណ៍មុន, និងធ្វើការងារឲ្យចប់ពេញលេញ។ មនុស្សដែលគ្រប់គ្រងរឿងតូចៗមិនបាន មិនអាចឲ្យទុកចិត្តលើរឿងធំៗបានទេ។"),
(17,'calm_leadership',
 "I do not want drama leadership. I want calm leadership: clear words, fair correction, no gossip, no ego, and no showing off. A strong person does not need to act powerful. A strong person makes the team better.",
 "ខ្ញុំមិនចង់បានការដឹកនាំដែលបង្ក drama ទេ។ ខ្ញុំចង់បានការដឹកនាំស្ងប់ស្ងាត់៖ និយាយច្បាស់ កែតម្រូវដោយយុត្តិធម៌ គ្មាននិយាយដើមគ្នា គ្មាន ego និងគ្មានការបង្ហាញខ្លួនឲ្យលើសពេក។ មនុស្សខ្លាំងមិនចាំបាច់ធ្វើអាកប្បកិរិយាដូចមានអំណាចទេ។ មនុស្សខ្លាំងធ្វើឲ្យក្រុមកាន់តែល្អឡើង។"),
(18,'30_day_growth',
 "For the next 30 days, I want to see you grow in a clear way. Choose one area you can own: delivery and order checking, quiet-time checklist, stock and refill checking, or training one junior staff. Do not try to own everything at once. Own one thing properly first.",
 "ក្នុងរយៈពេល ៣០ ថ្ងៃបន្ទាប់ ខ្ញុំចង់ឃើញប្អូនរីកចម្រើនយ៉ាងច្បាស់។ ជ្រើសរើសផ្នែកមួយដែលប្អូនអាចទទួលខុសត្រូវ៖ ពិនិត្យ delivery និង order, checklist ម៉ោងស្ងាត់, ពិនិត្យ stock និង refill, ឬបង្ហាត់បុគ្គលិកថ្មីម្នាក់។ កុំព្យាយាមកាន់គ្រប់យ៉ាងក្នុងពេលតែមួយ។ ត្រូវកាន់រឿងមួយឲ្យបានត្រឹមត្រូវជាមុនសិន។"),
(19,'team_improvement_goal',
 "Your goal is not only to impress management. Your goal is to make the shift stronger, cleaner, faster, and less dependent on one person. If the team becomes better because of you, then you are truly growing.",
 "គោលដៅរបស់ប្អូន មិនមែនត្រឹមតែធ្វើឲ្យអ្នកគ្រប់គ្រងពេញចិត្តទេ។ គោលដៅរបស់ប្អូនគឺធ្វើឲ្យវេនកាន់តែរឹងមាំ ស្អាត លឿន និងមិនពឹងផ្អែកលើមនុស្សម្នាក់ពេក។ បើក្រុមកាន់តែល្អឡើងដោយសារប្អូន នោះមានន័យថាប្អូនកំពុងរីកចម្រើនពិតប្រាកដ។"),
(20,'final_encouragement',
 "I am happy with your test, but now I want real proof in daily work. Keep your good attitude, but add more structure, follow-up, and responsibility. If you do this, you will not just be good staff. You can become someone important for the team.",
 "ខ្ញុំពេញចិត្តនឹងតេស្តរបស់ប្អូន ប៉ុន្តែឥឡូវនេះ ខ្ញុំចង់ឃើញភស្តុតាងពិតក្នុងការងាររៀងរាល់ថ្ងៃ។ រក្សាអាកប្បកិរិយាល្អរបស់ប្អូន ប៉ុន្តែបន្ថែមការរៀបចំ ការតាមដាន និងទំនួលខុសត្រូវឲ្យច្រើនជាងមុន។ បើប្អូនធ្វើបាន ប្អូននឹងមិនមែនត្រឹមតែជាបុគ្គលិកល្អទេ។ ប្អូនអាចក្លាយជាមនុស្សសំខាន់សម្រាប់ក្រុមបាន។"),
]

for pt in points:
    cur.execute("""
        INSERT INTO hiring_feedback_templates
            (candidate_id, candidate_name, topic, point_number, english_text, khmer_text, score_range, is_generic)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (candidate_id, 'Por', pt[1], pt[0], pt[2], pt[3], 'high', False))

conn.commit()
cur.execute("SELECT COUNT(*) FROM hiring_feedback_templates WHERE candidate_name = 'Por'")
print('Points stored for Por:', cur.fetchone()[0])
cur.execute("SELECT id, name, overall_pct, classification FROM hiring_candidates WHERE name = 'Por'")
print('Candidate:', cur.fetchone())
conn.close()
