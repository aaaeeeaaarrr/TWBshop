import sys
sys.path.insert(0, '/root/TWBshop')
from secrets import DATABASE_URL
import psycopg2, json

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("SELECT id FROM hiring_quiz_versions WHERE version_name = 'Final v3'")
VID = cur.fetchone()[0]

Y = json.dumps({"answer": "yes"})
N = json.dumps({"answer": "no"})
YNS = None  # options always yes/no/not_sure for Part A

def b(opts, ans):
    return json.dumps(opts), json.dumps({"answer": ans})

# ── PART A ─────────────────────────────────────────────────────────────────
# (id, part, section, order, en, km, answer_type, options, correct, traits, severity, verbal_retest)
A = [
# A1 – Time, schedule, adult responsibility
("A1-Q1","A","A1",1,
 "If my work starts at 6:00am, I should arrive around 5:55am.",
 "បើការងារចាប់ផ្តើមមៅ 6:00 ព្រឹក ខ្ញុំគួរមកប្រហែល 5:55 ព្រឹក។",
 "yes_no_not_sure",YNS,Y,["punctuality","schedule_honesty"],"minor",False),

("A1-Q2","A","A1",2,
 "If it rains, it is okay to be late without telling anyone.",
 "បើភ្លៀង អាចមកយឺតដោយមិនប្រាប់អ្នកណាក៏បាន។",
 "yes_no_not_sure",YNS,N,["punctuality","communication"],"moderate",False),

("A1-Q3","A","A1",3,
 "If my moto breaks, I should tell management before work time and find another way to come.",
 "បើម៉ូតូខូច ខ្ញុំគួរប្រាប់គ្រប់គ្រងមុនម៉ោងធ្វើការ ហើយរកវិធីផ្សេងមក។",
 "yes_no_not_sure",YNS,Y,["punctuality","communication"],"minor",False),

("A1-Q4","A","A1",4,
 "If I have a wedding, exam, family trip, health issue, family duty, or other plan, I should tell management early.",
 "បើខ្ញុំមានរៀបការ ប្រឡង ដំណើរកំសាន្ត បញ្ហាសុខភាព ការទទួលខុសត្រូវគ្រួសារ ឬផែនការផ្សេងៗ ខ្ញុំគួរប្រាប់គ្រប់គ្រងឲ្យមុន។",
 "yes_no_not_sure",YNS,Y,["schedule_honesty","communication"],"minor",False),

("A1-Q5","A","A1",5,
 "It is okay to say \"busy tomorrow\" one day before my shift.",
 "អាចនិយាយថា \"ស្អែករវល់\" មួយថ្ងៃមុនវេនបាន។",
 "yes_no_not_sure",YNS,N,["schedule_honesty","adult_responsibility"],"critical",True),

("A1-Q6","A","A1",6,
 "If school time may change soon, I should say it during interview.",
 "បើម៉ោងរៀនអាចផ្លាស់ប្តូរឆាប់ៗ ខ្ញុំគួរប្រាប់ពេលសម្ភាសន៍។",
 "yes_no_not_sure",YNS,Y,["schedule_honesty","honesty"],"moderate",False),

("A1-Q7","A","A1",7,
 "If I hide schedule problems, I am not being honest with the job.",
 "បើខ្ញុំលាក់បញ្ហាកាលវិភាគ ខ្ញុំមិនស្មោះត្រង់ជាមួយការងារទេ។",
 "yes_no_not_sure",YNS,Y,["schedule_honesty","honesty"],"critical",True),

("A1-Q8","A","A1",8,
 "If management is kind before, I should respect them more, not take advantage.",
 "បើគ្រប់គ្រងធ្លាប់ចិត្តល្អ ខ្ញុំគួរគោរពពួកគេកាន់តែច្រើន មិនមែនយកចំណេញពីពួកគេទេ។",
 "yes_no_not_sure",YNS,Y,["loyalty","adult_responsibility"],"minor",False),

("A1-Q9","A","A1",9,
 "If I use health, mother, sister, family, or other excuses too many times, people may stop trusting my words.",
 "បើខ្ញុំប្រើលេសសុខភាព ម៉ាក់ បងប្អូនស្រី គ្រួសារ ឬលេសផ្សេងៗច្រើនពេក មនុស្សអាចឈប់ជឿពាក្យខ្ញុំ។",
 "yes_no_not_sure",YNS,Y,["honesty","adult_responsibility"],"moderate",False),

("A1-Q10","A","A1",10,
 "Adult staff explain health and family responsibilities early, before the business trains them.",
 "បុគ្គលិកមានគំនិតធំ ពន្យល់បញ្ហាសុខភាព និងការទទួលខុសត្រូវគ្រួសារឲ្យមុន មុនពេលអាជីវកម្មបង្រៀនពួកគេ។",
 "yes_no_not_sure",YNS,Y,["adult_responsibility","communication"],"minor",False),

# A2 – Honesty, mistakes, asking
("A2-Q11","A","A2",11,
 "If I break something, I should report it.",
 "បើខ្ញុំបំបែកអ្វីមួយ ខ្ញុំគួររាយការណ៍។",
 "yes_no_not_sure",YNS,Y,["honesty","mistake_reporting"],"moderate",False),

("A2-Q12","A","A2",12,
 "If I make a mistake, I should hide it if no one saw.",
 "បើខ្ញុំធ្វើកំហុស ខ្ញុំគួរលាក់វាបើគ្មាននរណាឃើញ។",
 "yes_no_not_sure",YNS,N,["honesty","mistake_reporting"],"critical",False),

("A2-Q13","A","A2",13,
 "Hiding a mistake is worse than making an honest mistake.",
 "ការលាក់កំហុស អាក្រក់ជាងការធ្វើកំហុសដោយស្មោះត្រង់។",
 "yes_no_not_sure",YNS,Y,["honesty","mistake_reporting"],"critical",True),

("A2-Q14","A","A2",14,
 "Helping someone hide a mistake makes me part of the mistake.",
 "ការជួយនរណាម្នាក់លាក់កំហុស ធ្វើឲ្យខ្ញុំក្លាយជាផ្នែកនៃកំហុសនោះ។",
 "yes_no_not_sure",YNS,Y,["honesty","team_responsibility"],"moderate",False),

("A2-Q15","A","A2",15,
 "If I do not know how to do something, I should ask.",
 "បើខ្ញុំមិនដឹងធ្វើអ្វីមួយ ខ្ញុំគួរសួរ។",
 "yes_no_not_sure",YNS,Y,["asking","learning"],"minor",False),

("A2-Q16","A","A2",16,
 "Guessing is better than asking because asking looks weak.",
 "ការទាយល្អជាងការសួរ ព្រោះការសួរមើលទៅខ្សោយ។",
 "yes_no_not_sure",YNS,N,["asking","ego_management"],"moderate",False),

("A2-Q17","A","A2",17,
 "Asking many times is better than making expensive mistakes.",
 "សួរច្រើនដង ល្អជាងធ្វើកំហុសថ្លៃ។",
 "yes_no_not_sure",YNS,Y,["asking","learning"],"minor",False),

("A2-Q18","A","A2",18,
 "If I find food that smells strange, looks strange, or has unclear date, I should ask before using it.",
 "បើខ្ញុំឃើញម្ហូបក្លិនចម្លែក មើលចម្លែក ឬថ្ងៃមិនច្បាស់ ខ្ញុំគួរសួរមុនប្រើ។",
 "yes_no_not_sure",YNS,Y,["food_safety","asking"],"moderate",False),

("A2-Q19","A","A2",19,
 "If I touch money, personal phone, trash, raw food, or my face, I may need to wash hands before touching food.",
 "បើខ្ញុំប៉ះលុយ ទូរស័ព្ទផ្ទាល់ខ្លួន សំរាម ម្ហូបឆៅ ឬមុខខ្លួន ខ្ញុំប្រហែលត្រូវលាងដៃមុនប៉ះម្ហូប។",
 "yes_no_not_sure",YNS,Y,["food_safety","hygiene"],"moderate",False),

("A2-Q20","A","A2",20,
 "Food that falls on the floor can be sold if it looks clean.",
 "ម្ហូបធ្លាក់លើដី អាចលក់បានបើមើលទៅស្អាត។",
 "yes_no_not_sure",YNS,N,["food_safety"],"critical",True),

# A3 – Apology, pride, customers
("A3-Q21","A","A3",21,
 "Saying sorry can be the adult thing to do.",
 "ការនិយាយសុំទោស អាចជារឿងដែលមនុស្សធំគួរធ្វើ។",
 "yes_no_not_sure",YNS,Y,["apology","adult_responsibility"],"minor",False),

("A3-Q22","A","A3",22,
 "Saying sorry always means I am a bad person.",
 "ការនិយាយសុំទោស តែងតែមានន័យថាខ្ញុំជាមនុស្សអាក្រក់។",
 "yes_no_not_sure",YNS,N,["apology","ego_management"],"moderate",False),

("A3-Q23","A","A3",23,
 "If a customer is unhappy, I can say sorry for the problem even if I did not personally make the mistake.",
 "បើអតិថិជនមិនសប្បាយ ខ្ញុំអាចសុំទោសចំពោះបញ្ហា ទោះខ្ញុំមិនមែនជាអ្នកធ្វើកំហុសផ្ទាល់ក៏ដោយ។",
 "yes_no_not_sure",YNS,Y,["apology","customer_service"],"minor",False),

("A3-Q24","A","A3",24,
 "It is more important to fix the problem than protect my pride.",
 "ការដោះស្រាយបញ្ហា សំខាន់ជាងការពារអំនួតខ្លួន។",
 "yes_no_not_sure",YNS,Y,["ego_management","customer_service"],"moderate",False),

("A3-Q25","A","A3",25,
 "If I was not wrong, I should never help fix the problem.",
 "បើខ្ញុំមិនខុស ខ្ញុំមិនគួរជួយដោះស្រាយបញ្ហាឡើយ។",
 "yes_no_not_sure",YNS,N,["ego_management","teamwork"],"moderate",False),

("A3-Q26","A","A3",26,
 "Customers notice clean clothes, clean face, calm voice, and respectful words.",
 "អតិថិជនសង្កេតឃើញសម្លៀកបំពាក់ស្អាត មុខស្អាត សំឡេងស្ងប់ និងពាក្យគោរព។",
 "yes_no_not_sure",YNS,Y,["customer_service","hygiene"],"minor",False),

("A3-Q27","A","A3",27,
 "If a customer is angry, I should become angry too.",
 "បើអតិថិជនខឹង ខ្ញុំគួរខឹងតបវិញ។",
 "yes_no_not_sure",YNS,N,["customer_service","calm"],"moderate",False),

("A3-Q28","A","A3",28,
 "If I cannot solve a customer problem, I should call management.",
 "បើខ្ញុំដោះស្រាយបញ្ហាអតិថិជនមិនបាន ខ្ញុំគួរហៅគ្រប់គ្រង។",
 "yes_no_not_sure",YNS,Y,["customer_service","escalation"],"minor",False),

("A3-Q29","A","A3",29,
 "If I do not understand English, I should politely ask another staff to help.",
 "បើខ្ញុំមិនយល់អង់គ្លេស ខ្ញុំគួរសុំឲ្យបុគ្គលិកផ្សេងជួយដោយសុភាព។",
 "yes_no_not_sure",YNS,Y,["teamwork","customer_service"],"minor",False),

("A3-Q30","A","A3",30,
 "A customer complaint can help us see a problem.",
 "ពាក្យបណ្ដឹងរបស់អតិថិជន អាចជួយឲ្យយើងឃើញបញ្ហា។",
 "yes_no_not_sure",YNS,Y,["customer_service","learning"],"minor",False),

# A4 – Teamwork, personal phone, quiet time
("A4-Q31","A","A4",31,
 "If one staff works and another staff relaxes, the team becomes bad.",
 "បើបុគ្គលិកម្នាក់ធ្វើការ ហើយម្នាក់ទៀតសម្រាក ក្រុមនឹងអាក្រក់។",
 "yes_no_not_sure",YNS,Y,["teamwork","fairness"],"minor",False),

("A4-Q32","A","A4",32,
 "If my work is done, I should ask how to help.",
 "បើការងារខ្ញុំរួច ខ្ញុំគួរសួរថាអាចជួយអ្វីបាន។",
 "yes_no_not_sure",YNS,Y,["teamwork","proactive"],"minor",False),

("A4-Q33","A","A4",33,
 "Quiet time is for cleaning, stock check, refill, preparation, and learning.",
 "ម៉ោងស្ងាត់ គឺសម្រាប់សម្អាត ពិនិត្យស្តុក បំពេញរបស់ រៀបចំ និងរៀន។",
 "yes_no_not_sure",YNS,Y,["quiet_time","proactive"],"minor",False),

("A4-Q34","A","A4",34,
 "Quiet time is personal phone time.",
 "ម៉ោងស្ងាត់ គឺម៉ោងលេងទូរស័ព្ទផ្ទាល់ខ្លួន។",
 "yes_no_not_sure",YNS,N,["phone_discipline","quiet_time"],"critical",False),

("A4-Q35","A","A4",35,
 "If my station is quiet, I can hide in the bakery room or back area.",
 "បើកន្លែងខ្ញុំស្ងាត់ ខ្ញុំអាចទៅលាក់នៅបន្ទប់នំ ឬខាងក្រោយបាន។",
 "yes_no_not_sure",YNS,N,["quiet_time","proactive"],"moderate",False),

("A4-Q36","A","A4",36,
 "I should copy good habits, not bad habits.",
 "ខ្ញុំគួរចម្លងទម្លាប់ល្អ មិនមែនទម្លាប់អាក្រក់។",
 "yes_no_not_sure",YNS,Y,["learning","team_culture"],"minor",False),

("A4-Q37","A","A4",37,
 "Friendly staff can still be bad staff if they are lazy or dishonest.",
 "បុគ្គលិករួសរាយ ក៏អាចជាបុគ្គលិកមិនល្អបាន បើខ្ជិល ឬមិនស្មោះត្រង់។",
 "yes_no_not_sure",YNS,Y,["honesty","teamwork"],"minor",False),

("A4-Q38","A","A4",38,
 "Good staff work even when management is not watching.",
 "បុគ្គលិកល្អ ធ្វើការទោះគ្រប់គ្រងមិនមើលក៏ដោយ។",
 "yes_no_not_sure",YNS,Y,["honesty","self_discipline"],"critical",True),

("A4-Q39","A","A4",39,
 "If stock is almost finished, I should tell someone before it is empty.",
 "បើស្តុកជិតអស់ ខ្ញុំគួរប្រាប់នរណាម្នាក់មុនវាអស់។",
 "yes_no_not_sure",YNS,Y,["proactive","stock_management"],"minor",False),

("A4-Q40","A","A4",40,
 "Wrong packing or missing items can lose customers.",
 "វេចខ្ចប់ខុស ឬខ្វះរបស់ អាចធ្វើឲ្យបាត់អតិថិជន។",
 "yes_no_not_sure",YNS,Y,["accuracy","customer_service"],"moderate",False),

# A5 – Talking, gossip, team problems
("A5-Q41","A","A5",41,
 "If I have a work problem, I should tell management early.",
 "បើខ្ញុំមានបញ្ហាការងារ ខ្ញុំគួរប្រាប់គ្រប់គ្រងឲ្យមុន។",
 "yes_no_not_sure",YNS,Y,["communication","escalation"],"moderate",False),

("A5-Q42","A","A5",42,
 "If I have a work problem, I should complain to other staff first.",
 "បើខ្ញុំមានបញ្ហាការងារ ខ្ញុំគួរត្អូញត្អែរជាមួយបុគ្គលិកផ្សេងមុន។",
 "yes_no_not_sure",YNS,N,["gossip","communication"],"critical",True),

("A5-Q43","A","A5",43,
 "Bad talk can make the team weak.",
 "ការនិយាយអាក្រក់ អាចធ្វើឲ្យក្រុមខ្សោយ។",
 "yes_no_not_sure",YNS,Y,["gossip","team_culture"],"moderate",False),

("A5-Q44","A","A5",44,
 "If I am unhappy, I should quiet-quit and make other staff feel bad too.",
 "បើខ្ញុំមិនសប្បាយ ខ្ញុំគួរធ្វើការដោយមិនខំ ហើយធ្វើឲ្យអ្នកផ្សេងមានអារម្មណ៍អាក្រក់ដែរ។",
 "yes_no_not_sure",YNS,N,["team_culture","adult_responsibility"],"critical",False),

("A5-Q45","A","A5",45,
 "If the team feeling is bad, someone must tell management early.",
 "បើអារម្មណ៍ក្រុមមិនល្អ ត្រូវមាននរណាម្នាក់ប្រាប់គ្រប់គ្រងឲ្យមុន។",
 "yes_no_not_sure",YNS,Y,["team_culture","communication"],"minor",False),

("A5-Q46","A","A5",46,
 "If I see two staff having a problem, I should ignore it forever.",
 "បើខ្ញុំឃើញបុគ្គលិកពីរនាក់មានបញ្ហា ខ្ញុំគួរមិនអើពើរហូត។",
 "yes_no_not_sure",YNS,N,["team_culture","leadership"],"moderate",False),

("A5-Q47","A","A5",47,
 "A small team problem should be discussed early before it grows.",
 "បញ្ហាក្រុមតូច គួរត្រូវបាននិយាយឲ្យមុន មុនពេលវាធំឡើង។",
 "yes_no_not_sure",YNS,Y,["team_culture","communication"],"minor",False),

("A5-Q48","A","A5",48,
 "Respectful staff do not poison the team.",
 "បុគ្គលិកដែលគោរព មិនបំពុលក្រុមទេ។",
 "yes_no_not_sure",YNS,Y,["team_culture","gossip"],"minor",False),

("A5-Q49","A","A5",49,
 "When another staff leaves or moves, good staff see a chance to step up, learn more, and help train new staff.",
 "ពេលបុគ្គលិកផ្សេងចាកចេញ ឬប្តូរកន្លែង បុគ្គលិកល្អមើលឃើញថាវាជាឱកាសឈានឡើង រៀនបន្ថែម និងជួយបង្រៀនបុគ្គលិកថ្មី។",
 "yes_no_not_sure",YNS,Y,["leadership","training","proactive"],"minor",False),

("A5-Q50","A","A5",50,
 "Good staff can make the team stronger even if they are not supervisor yet.",
 "បុគ្គលិកល្អ អាចធ្វើឲ្យក្រុមរឹងមាំឡើង ទោះមិនទាន់ជាប្រធានក្រុមក៏ដោយ។",
 "yes_no_not_sure",YNS,Y,["leadership","teamwork"],"minor",False),

# A6 – Resignation, loyalty, future leadership
("A6-Q51","A","A6",51,
 "Training new staff costs time and money.",
 "ការបណ្តុះបណ្តាលបុគ្គលិកថ្មី ចំណាយពេល និងប្រាក់។",
 "yes_no_not_sure",YNS,Y,["training","loyalty"],"critical",True),

("A6-Q52","A","A6",52,
 "This job is only for a few weeks if I feel bored.",
 "ការងារនេះធ្វើតែប៉ុន្មានសប្ដាហ៍ បើខ្ញុំអផ្សក។",
 "yes_no_not_sure",YNS,N,["loyalty","commitment"],"moderate",False),

("A6-Q53","A","A6",53,
 "If I want to resign, I should talk early and give the real reason.",
 "បើខ្ញុំចង់លាឈប់ ខ្ញុំគួរនិយាយឲ្យមុន ហើយប្រាប់ហេតុផលពិត។",
 "yes_no_not_sure",YNS,Y,["honesty","adult_responsibility"],"minor",False),

("A6-Q54","A","A6",54,
 "If I want to resign, I should first ask if the problem can be fixed.",
 "បើខ្ញុំចង់លាឈប់ ខ្ញុំគួរសួរមុនថាបញ្ហាអាចដោះស្រាយបានទេ។",
 "yes_no_not_sure",YNS,Y,["adult_responsibility","communication"],"minor",False),

("A6-Q55","A","A6",55,
 "If school time is the problem, I can ask if another shift is possible.",
 "បើម៉ោងរៀនជាបញ្ហា ខ្ញុំអាចសួរថាវេនផ្សេងអាចបានទេ។",
 "yes_no_not_sure",YNS,Y,["schedule_honesty","communication"],"minor",False),

("A6-Q56","A","A6",56,
 "If I say \"health problem\" or \"my family told me to stop,\" I should be honest and explain the real problem early.",
 "បើខ្ញុំនិយាយថា \"បញ្ហាសុខភាព\" ឬ \"គ្រួសារប្រាប់ឲ្យឈប់\" ខ្ញុំគួរតែស្មោះត្រង់ ហើយពន្យល់បញ្ហាពិតឲ្យមុន។",
 "yes_no_not_sure",YNS,Y,["honesty","adult_responsibility"],"moderate",False),

("A6-Q57","A","A6",57,
 "Fake excuses about health or family are okay if I feel shy to say the truth.",
 "លេសក្លែងក្លាយអំពីសុខភាព ឬគ្រួសារ អាចប្រើបាន បើខ្ញុំខ្មាស់នឹងនិយាយការពិត។",
 "yes_no_not_sure",YNS,N,["honesty","adult_responsibility"],"critical",False),

("A6-Q58","A","A6",58,
 "If I leave suddenly, other staff may suffer more work.",
 "បើខ្ញុំចាកចេញភ្លាមៗ បុគ្គលិកផ្សេងអាចទទួលការងារច្រើនជាងមុន។",
 "yes_no_not_sure",YNS,Y,["loyalty","team_responsibility"],"critical",True),

("A6-Q59","A","A6",59,
 "Good staff help train 2 or 3 backup people when possible.",
 "បុគ្គលិកល្អ ជួយបង្រៀនអ្នកបម្រុង 2 ឬ 3 នាក់ បើអាចធ្វើបាន។",
 "yes_no_not_sure",YNS,Y,["training","leadership"],"minor",False),

("A6-Q60","A","A6",60,
 "A good future leader trains others so the team is not weak when one person is absent or leaves.",
 "អ្នកដឹកនាំល្អ សម្រាប់អនាគត បង្រៀនអ្នកផ្សេង ដើម្បីក្រុមមិនខ្សោយ ពេលមនុស្សម្នាក់អវត្តមាន ឬចាកចេញ។",
 "yes_no_not_sure",YNS,Y,["training","leadership","systems_thinking"],"minor",False),
]

# ── PART B ─────────────────────────────────────────────────────────────────
def bq(n, en, km, opts, ans, traits, sev, vr=False):
    opts_j, ans_j = b(opts, ans)
    return (f"B-Q{n}","B","B",n,en,km,"single_choice",opts_j,ans_j,traits,sev,vr)

B = [
bq(1,
"Your shift starts at 6:00am. Heavy rain starts at 5:35am. What should you do?",
"វេនអ្នកចាប់ផ្តើមមៅ 6:00 ព្រឹក។ ភ្លៀងខ្លាំងម៉ោង 5:35 ព្រឹក។ អ្នកគួរធ្វើអ្វី?",
{"A":"Wait until rain stops.","B":"Come late and say rain was heavy.",
 "C":"Wear raincoat, leave early, and tell management early if there is real trouble.",
 "D":"Sleep more because raining is not your fault."},"C",
["punctuality","communication"],"moderate"),

bq(2,
"Your moto breaks 30 minutes before work. What should you do first?",
"ម៉ូតូខូច 30 នាទីមុនធ្វើការ។ អ្នកគួរធ្វើអ្វីមុន?",
{"A":"Wait until management calls.","B":"Tell management before work time and find another way to come.",
 "C":"Stay home and fix it slowly.","D":"Tell another staff only."},"B",
["punctuality","communication"],"moderate"),

bq(3,
"You have school next month. Your school time may change. What should you do during interview?",
"ខែក្រោយអ្នកមានសាលា។ ម៉ោងរៀនអាចផ្លាស់ប្តូរ។ ពេលសម្ភាសន៍គួរធ្វើអ្វី?",
{"A":"Hide it so you get the job.","B":"Tell management clearly.",
 "C":"Say 'no problem' even if not true.","D":"Wait until after salary is agreed."},"B",
["schedule_honesty","honesty"],"critical"),

bq(4,
"A customer is unhappy because food is late. You did not cook the food. What should you say?",
"អតិថិជនមិនសប្បាយ ព្រោះម្ហូបយឺត។ អ្នកមិនមែនជាអ្នកចម្អិន។ អ្នកគួរនិយាយអ្វី?",
{"A":"'Not my mistake.'","B":"'Why are you angry?'",
 "C":"'Sorry, I will check for you now.'","D":"Ignore the customer."},"C",
["apology","customer_service"],"moderate"),

bq(5,
"Management corrects your mistake. You feel embarrassed. What should you do?",
"គ្រប់គ្រងកែតម្រូវកំហុសអ្នក។ អ្នកមានអារម្មណ៍ខ្មាស។ អ្នកគួរធ្វើអ្វី?",
{"A":"Argue to protect your pride.","B":"Listen, say sorry if needed, and fix it.",
 "C":"Talk badly later.","D":"Stop working hard."},"B",
["ego_management","apology"],"moderate"),

bq(6,
"A staff refuses to apologize because they say 'I was not wrong.' What is the best lesson?",
"បុគ្គលិកម្នាក់មិនព្រមសុំទោស ព្រោះនិយាយថា 'ខ្ញុំមិនខុស'។ មេរៀនល្អបំផុតគឺអ្វី?",
{"A":"Never say sorry if you are not wrong.",
 "B":"At work, sorry can mean sorry for the problem. We fix first, ego later.",
 "C":"Hide from the customer.","D":"Fight until people understand you are right."},"B",
["apology","ego_management","customer_service"],"moderate"),

bq(7,
"You forgot one item in a delivery order. What should you do?",
"អ្នកភ្លេចរបស់មួយក្នុងការបញ្ជាទិញដឹកជញ្ជូន។ អ្នកគួរធ្វើអ្វី?",
{"A":"Say nothing unless customer complains.","B":"Tell management fast and help fix it.",
 "C":"Blame another staff.","D":"Delete the message."},"B",
["honesty","accuracy","mistake_reporting"],"moderate"),

bq(8,
"You broke something. No one saw. What should you do?",
"អ្នកបំបែកអ្វីមួយ។ គ្មាននរណាឃើញ។ អ្នកគួរធ្វើអ្វី?",
{"A":"Hide it.","B":"Report it and say sorry.",
 "C":"Wait until someone finds it.","D":"Throw it away quietly."},"B",
["honesty","mistake_reporting"],"critical"),

bq(9,
"A senior staff tells you 'Do not tell management.' What should you do?",
"បុគ្គលិកជាន់ខ្ពស់និយាយថា 'កុំប្រាប់គ្រប់គ្រង'។ អ្នកគួរធ្វើអ្វី?",
{"A":"Help hide it.","B":"Stay quiet because senior staff said so.",
 "C":"Report honestly because hiding is wrong.","D":"Ask for money to stay quiet."},"C",
["honesty","leadership"],"critical"),

bq(10,
"Your station is quiet. Another staff is busy. What should you do?",
"កន្លែងអ្នកស្ងាត់។ បុគ្គលិកផ្សេងរវល់។ អ្នកគួរធ្វើអ្វី?",
{"A":"Use personal phone.","B":"Offer help but keep your own station ready.",
 "C":"Watch them work.","D":"Hide in the back."},"B",
["teamwork","quiet_time","proactive"],"moderate"),

bq(11,
"There are no customers for 10 minutes. What should you do?",
"មិនមានអតិថិជន 10 នាទី។ អ្នកគួរធ្វើអ្វី?",
{"A":"Check personal phone.","B":"Sit and wait.",
 "C":"Clean, refill, check stock, prepare, or ask what to do.","D":"Walk outside."},"C",
["quiet_time","proactive"],"moderate"),

bq(12,
"You see a staff always late but not punished yet. What should you do?",
"អ្នកឃើញបុគ្គលិកម្នាក់មកយឺតជារឿយៗ តែមិនទាន់ត្រូវពិន័យ។ អ្នកគួរធ្វើអ្វី?",
{"A":"Copy them.","B":"Be late sometimes too.",
 "C":"Follow the good example, not the bad example.","D":"Complain to customers."},"C",
["team_culture","self_discipline"],"moderate"),

bq(13,
"You want to resign because you feel unhappy with the team. What is best?",
"អ្នកចង់លាឈប់ ព្រោះមិនសប្បាយជាមួយក្រុម។ អ្វីល្អបំផុត?",
{"A":"Say fake reason and leave.","B":"Quiet-quit until management lets you go.",
 "C":"Talk to management early and explain the real problem.",
 "D":"Make other staff resign too."},"C",
["honesty","adult_responsibility","communication"],"moderate"),

bq(14,
"You have school problem. What should you try before resigning?",
"អ្នកមានបញ្ហាសាលា។ មុនលាឈប់ អ្នកគួរសាកល្បងអ្វី?",
{"A":"Ask if shift change is possible.","B":"Say nothing and stop coming.",
 "C":"Say health problem.","D":"Tell other staff only."},"A",
["schedule_honesty","communication"],"moderate"),

bq(15,
"You feel your health is not good, or your family says they need you to stop working. What is a mature answer?",
"អ្នកមានអារម្មណ៍ថាសុខភាពមិនល្អ ឬគ្រួសារនិយាយថាត្រូវការឲ្យអ្នកឈប់ធ្វើការ។ ចម្លើយដែលមានគំនិតធំគឺអ្វី?",
{"A":"'I resign.' No more explanation.",
 "B":"Explain honestly what health issue affects work and what schedule you can or cannot do.",
 "C":"Use health as an easy excuse.","D":"Quiet-quit."},"B",
["honesty","adult_responsibility"],"moderate"),

bq(16,
"A staff says 'My health makes this shift difficult.' What should a sensible staff or supervisor ask first?",
"បុគ្គលិកម្នាក់និយាយថា 'សុខភាពខ្ញុំធ្វើឲ្យវេននេះពិបាក'។ បុគ្គលិក ឬប្រធានក្រុមមានគំនិតគួរសួរអ្វីមុន?",
{"A":"Accept immediately and tell owner days later.",
 "B":"Ask what health problem affects work, ask if leave or shift change can help, then tell management same day if serious.",
 "C":"Ignore.","D":"Tell other staff first."},"B",
["leadership","communication","escalation"],"moderate"),

bq(17,
"One experienced staff leaves or moves to another shift. New staff arrive. What should good staff do?",
"បុគ្គលិកមានបទពិសោធន៍ម្នាក់ចាកចេញ ឬប្តូរទៅវេនផ្សេង។ បុគ្គលិកថ្មីចូលមក។ បុគ្គលិកល្អគួរធ្វើអ្វី?",
{"A":"Complain that there will be more work.",
 "B":"Step up, help train the new staff, and keep the team strong.",
 "C":"Hide knowledge so they stay important.","D":"Wait for management to do everything."},"B",
["leadership","training","teamwork"],"moderate"),

bq(18,
"If any staff needs to resign, what is the adult way?",
"បើថ្ងៃណាមួយបុគ្គលិកណាម្នាក់ត្រូវចាកចេញ វិធីមនុស្សធំគឺអ្វី?",
{"A":"Leave as fast as possible.",
 "B":"Give a long time notice, explain honestly, help train replacement during those months, and leave the team stronger if possible.",
 "C":"Say 'my feeling not good' and stop caring.",
 "D":"Tell other staff to leave too."},"B",
["adult_responsibility","loyalty","training"],"moderate"),

bq(19,
"You touched raw chicken. Now you need to touch bread. What first?",
"អ្នកប៉ះមាន់ឆៅ។ ឥឡូវត្រូវប៉ះនំប័ង។ ត្រូវធ្វើអ្វីមុន?",
{"A":"Wipe hands on apron.","B":"Wash hands and change gloves/tools if needed.",
 "C":"Touch bread quickly.","D":"Use same gloves."},"B",
["food_safety","hygiene"],"critical"),

bq(20,
"Important item is almost finished before busy time. What should you do?",
"របស់សំខាន់ជិតអស់មុនម៉ោងរវល់។ អ្នកគួរធ្វើអ្វី?",
{"A":"Wait until empty.","B":"Tell management or prepare more if trained.",
 "C":"Hide it.","D":"Use another item without permission."},"B",
["proactive","stock_management"],"moderate"),

bq(21,
"Customer leaves cash on table. You are not sure if tip or forgotten money. What should you do?",
"អតិថិជនទុកលុយលើតុ។ អ្នកមិនប្រាកដថាជា Tip ឬលុយភ្លេច។ អ្នកគួរធ្វើអ្វី?",
{"A":"Keep it.","B":"Tell cashier or management and follow shop rule.",
 "C":"Split with staff.","D":"Hide it."},"B",
["honesty","loyalty"],"critical"),

bq(22,
"Your friend asks for free food or discount. What should you do?",
"មិត្តរបស់អ្នកសុំអាហារឥតគិតថ្លៃ ឬបញ្ចុះតម្លៃ។ អ្នកគួរធ្វើអ្វី?",
{"A":"Give discount because friend.","B":"Give small free food.",
 "C":"Follow shop rule and ask management if not sure.",
 "D":"Put it as waste."},"C",
["honesty","loyalty"],"critical"),
]

# ── PART C ─────────────────────────────────────────────────────────────────
def cq(n, en, km, rubric, traits, sev):
    return (f"C-Q{n}","C","C",n,en,km,"free_text",None,
            json.dumps({"rubric": rubric}),traits,sev,False)

C = [
cq(1,"Write your last 2 jobs. What was your position? How long? Why did you stop?",
   "សរសេរការងារ 2 កន្លែងចុងក្រោយ។ តំណែងអ្វី? ធ្វើបានប៉ុន្មាន? ហេតុអ្វីឈប់?",
   "Check: date precision (day/month/year vs vague), job stability, honest reason for leaving, red flags (very short stays, 'new experience' reason)",
   ["work_history","honesty"],"moderate"),

cq(2,"What 3 things did you do every day in your last job?",
   "នៅការងារចុងក្រោយ អ្នកធ្វើអ្វី 3 យ៉ាងរៀងរាល់ថ្ងៃ?",
   "Check: real tasks vs vague answers. Specific = honest. 'Help customers, clean, prepare' = ok. Blank or 'everything' = weak.",
   ["work_history","specificity"],"minor"),

cq(3,"What mistake did you make before at work? What did you learn?",
   "អ្នកធ្លាប់ធ្វើកំហុសអ្វីនៅការងារ? អ្នកបានរៀនអ្វី?",
   "Check: willingness to admit a real mistake (not 'I never made mistakes'). Learning must be specific, not just 'I will not do it again'.",
   ["honesty","learning","self_awareness"],"moderate"),

cq(4,"If your old manager was here, what would they say you need to improve?",
   "បើអ្នកគ្រប់គ្រងចាស់នៅទីនេះ គាត់នឹងនិយាយថាអ្នកត្រូវកែលម្អអ្វី?",
   "CRITICAL: Blank = major gap (Lina got this wrong). A good answer shows self-awareness. 'Nothing' or blank = dangerous. Real answer: speed, communication, attention to detail, etc.",
   ["self_awareness","honesty"],"critical"),

cq(5,"If you make a mistake that costs money, what should you do?",
   "បើអ្នកធ្វើកំហុសដែលចំណាយលុយ អ្នកគួរធ្វើអ្វី?",
   "Check: full cycle = report → apologize → understand why → fix → prevent. 'Pay money' alone is not enough. Must include reporting and prevention.",
   ["mistake_reporting","adult_responsibility"],"moderate"),

cq(6,"Why is saying sorry sometimes strong, not weak?",
   "ហេតុអ្វីការសុំទោសពេលខ្លះជារឿងរឹងមាំ មិនមែនខ្សោយ?",
   "Check: understands apology = putting customer/team before ego. Not just 'it shows respect'. Must show reasoning.",
   ["apology","ego_management"],"moderate"),

cq(7,"What is more important: protecting your pride or fixing the problem? Why?",
   "អ្វីសំខាន់ជាង: ការពារអំនួតខ្លួន ឬដោះស្រាយបញ្ហា? ហេតុអ្វី?",
   "Check: clearly says fixing the problem. Reason must show customer/team impact, not just 'rules say so'.",
   ["ego_management","customer_service"],"minor"),

cq(8,"If your friend at work asks you to hide a mistake, what should you do?",
   "បើមិត្តរួមការងារសុំឲ្យអ្នកលាក់កំហុស អ្នកគួរធ្វើអ្វី?",
   "Check: refuses to hide + reports. Must not say 'talk to friend first then decide'. Strong answer: report regardless of friendship.",
   ["honesty","loyalty"],"critical"),

cq(9,"If one staff is lazy but friendly with you, what should you do?",
   "បើបុគ្គលិកម្នាក់ខ្ជិល តែរួសរាយជាមួយអ្នក អ្នកគួរធ្វើអ្វី?",
   "Check: does not protect laziness. Must show: address behavior or report. 'Nothing because friend' = red flag.",
   ["leadership","honesty","team_culture"],"moderate"),

cq(10,"If the team feeling is bad, what should good staff do?",
   "បើអារម្មណ៍ក្រុមមិនល្អ បុគ្គលិកល្អគួរធ្វើអ្វី?",
   "Check: does not spread bad feeling. Must include: talk to right person early, find root cause. 'Ignore' = red flag.",
   ["team_culture","leadership","communication"],"moderate"),

cq(11,"If you have a problem with another staff, what should you do?",
   "បើអ្នកមានបញ្ហាជាមួយបុគ្គលិកផ្សេង អ្នកគួរធ្វើអ្វី?",
   "Check: does not gossip to others first. Must talk to the person directly OR escalate to supervisor. Not 'tell everyone'.",
   ["communication","gossip"],"moderate"),

cq(12,"What should you do when there are no customers?",
   "ពេលគ្មានអតិថិជន អ្នកគួរធ្វើអ្វី?",
   "CRITICAL: Must say: clean, check stock, refill, prepare, ask what to help. 'Wait' or 'rest' = wrong. 'Find customers' = wrong (supervisor got this).",
   ["quiet_time","proactive"],"critical"),

cq(13,"If you want to resign, what is the respectful way?",
   "បើអ្នកចង់លាឈប់ វិធីគោរពគឺអ្វី?",
   "Check: give early notice, real reason, help train replacement. 'Just leave' or 'say health problem' = wrong.",
   ["adult_responsibility","loyalty"],"moderate"),

cq(14,"If your problem is school time, what should you ask before resigning?",
   "បើបញ្ហារបស់អ្នកគឺម៉ោងរៀន មុនលាឈប់អ្នកគួរសួរអ្វី?",
   "Check: must say 'ask if shift change is possible'. Not 'just resign'.",
   ["schedule_honesty","communication"],"minor"),

cq(15,"If your problem is health or family responsibility, how should you explain honestly?",
   "បើបញ្ហារបស់អ្នកគឺសុខភាព ឬការទទួលខុសត្រូវគ្រួសារ តើអ្នកគួរពន្យល់ដោយស្មោះយ៉ាងដូចម្តេច?",
   "Check: specific about what the real issue is and what schedule/capacity they actually have. Not vague.",
   ["honesty","communication"],"moderate"),

cq(16,"Why is sudden resignation bad for other staff?",
   "ហេតុអ្វីការលាឈប់ភ្លាមៗ អាក្រក់សម្រាប់បុគ្គលិកផ្សេង?",
   "Check: understands impact on team (more work, stress, no backup). Must mention team, not only about management.",
   ["team_responsibility","loyalty"],"minor"),

cq(17,"If a team member has a problem or wants to leave, what questions should a good senior staff ask before the problem grows?",
   "បើសមាជិកក្រុមមានបញ្ហា ឬចង់ចាកចេញ បុគ្គលិកជាន់ខ្ពស់ល្អគួរសួរអ្វីមុនពេលបញ្ហាធំឡើង?",
   "Check: asks what the real problem is, whether fix is possible, gives time and support. Shows leadership thinking.",
   ["leadership","communication","team_culture"],"moderate"),

cq(18,"When new staff join because someone left or moved, what should good staff do to make the team stronger?",
   "ពេលបុគ្គលិកថ្មីចូលមក ព្រោះមានអ្នកចាកចេញ ឬប្តូរកន្លែង បុគ្គលិកល្អគួរធ្វើអ្វីដើម្បីឲ្យក្រុមរឹងមាំឡើង?",
   "Check: must include training the new person and stepping up, not complaining.",
   ["leadership","training","teamwork"],"minor"),

cq(19,"If you become senior staff one day, how will you train 2 or 3 backup people and make people around you stronger?",
   "បើថ្ងៃណាមួយអ្នកក្លាយជាបុគ្គលិកជាន់ខ្ពស់ អ្នកនឹងបង្រៀនអ្នកបម្រុង 2 ឬ 3 នាក់ និងធ្វើឲ្យមនុស្សជុំវិញអ្នករឹងមាំយ៉ាងដូចម្តេច?",
   "Check: specific method. 'Show them what to do' is thin. Strong = explain, show, watch, correct, test again.",
   ["leadership","training","systems_thinking"],"moderate"),

cq(20,"If you need to resign, how can you make the workplace better and stronger than when you first joined?",
   "បើថ្ងៃណាមួយអ្នកត្រូវលាឈប់ តើអ្នកអាចធ្វើឲ្យកន្លែងធ្វើការល្អជាងមុន និងរឹងមាំជាងមុន យ៉ាងដូចម្តេច?",
   "GOLD: Por's best answer. Strong answer shows systems thinking: train backups, document, leave systems that run without you.",
   ["systems_thinking","leadership","loyalty"],"moderate"),

cq(21,"What makes customers come back again?",
   "អ្វីធ្វើឲ្យអតិថិជនត្រឡប់មកវិញ?",
   "Check: must go beyond 'good food'. Include: consistency, staff attitude, cleanliness, speed, trust. Depth of answer = customer thinking level.",
   ["customer_service","business_thinking"],"moderate"),

cq(22,"What should staff never do in front of customers?",
   "អ្វីដែលបុគ្គលិកមិនគួរធ្វើនៅមុខអតិថិជន?",
   "Check: phone, argue, eat, gossip, yell, ignore. Must list specific behaviors, not just 'bad things'.",
   ["customer_service","professionalism"],"minor"),

cq(23,"If customer is angry, what should you do first?",
   "បើអតិថិជនខឹង អ្នកគួរធ្វើអ្វីមុន?",
   "Check: stay calm → listen → apologize for problem → check/fix → escalate if needed. Must include staying calm first.",
   ["customer_service","calm","apology"],"moderate"),

cq(24,"Why should kitchen, bakery, and cleaning staff also care about customers?",
   "ហេតុអ្វីបុគ្គលិកផ្ទះបាយ នំប័ង និងសម្អាត ក៏ត្រូវខ្វល់អតិថិជនដែរ?",
   "Check: must connect back-of-house work to customer experience. Food quality, cleanliness, timing all affect customer. Norin's best answer was about this.",
   ["customer_service","business_thinking","food_safety"],"moderate"),
]

# ── PART D ─────────────────────────────────────────────────────────────────
D = [
("D1","D","D1",1,
 "Quiet time: There are no customers for 10 minutes. Rank 1–7 in order (1 = do first): Check orders/delivery tablet | Clean customer and work area | Check low stock | Refill bags, tissue, cups, boxes, labels, cutlery | Use personal phone | Ask management or senior staff what needs help | Prepare items for next rush if trained.",
 "ម៉ោងស្ងាត់: គ្មានអតិថិជន 10 នាទី។ លំដាប់ 1–7 (1 = ធ្វើមុន)។",
 "ranking",None,
 json.dumps({"correct_order":["Check orders/delivery tablet","Check low stock","Refill items","Prepare for next rush if trained","Clean customer and work area","Ask management what needs help","Use personal phone"],
             "note":"Orders/tablet MUST be first. Personal phone LAST or never. Cleaning before tablet = wrong. This question caught Touch Sreykeu (D1 wrong)."}),
 ["quiet_time","proactive","priority_thinking"],"critical",False),

("D2","D","D2",2,
 "Find the problems: A staff starts at 6:00am. Arrives 6:04am. Says rain was heavy. Did not message because 'only 4 minutes.' Later uses personal phone in back while another staff packs delivery. One order misses an item. He says 'I was not trained.' Write 5 problems.",
 "រកបញ្ហា 5 ក្នុងករណីនេះ។",
 "free_text",None,
 json.dumps({"rubric":"Expected: (1) Late without communicating, (2) Excuse instead of plan, (3) Phone during work, (4) Not helping with delivery, (5) Blaming training for missing item. Strong answer catches all 5. Weak = only 2-3."}),
 ["problem_detection","accountability","honesty"],"moderate",False),

("D3","D","D3",3,
 "Step-up and training problem: One experienced staff leaves. New staff arrive. Some old staff complain about more work. One good staff sees a chance to step up and train new staff. Write 3 problems and 3 good solutions.",
 "សរសេរបញ្ហា 3 និងដំណោះស្រាយ 3 ក្នុងស្ថានការណ៍នេះ។",
 "free_text",None,
 json.dumps({"rubric":"Problems: morale drop, knowledge gap, workload imbalance. Solutions: step-up mindset, structured training, management communication. Vague = weak. Specific = strong."}),
 ["leadership","training","systems_thinking"],"moderate",False),

("D4","D","D4",4,
 "Rewrite 5 bad answers: (1) 'If customer angry, not my fault.' (2) 'If I make mistake, I try not do again.' (3) 'I resign because health / my mother told me to stop.' (4) 'No customers, I wait.' (5) 'I left last job because new experience.'",
 "ធ្វើឲ្យចម្លើយអាក្រក់ទាំង 5 នេះល្អជាងមុន។",
 "rewrite",None,
 json.dumps({"rubric":"Each rewrite must show: correct attitude + specific action. Just making it polite is not enough. Strong rewrite = shows real understanding."}),
 ["apology","mistake_reporting","honesty","quiet_time","work_history"],"moderate",False),

("D-Final","D","Final",5,
 "What have you learned from this test? Explain properly. Write the rules, habits, or ideas you think are important for this job. Also explain how good staff make the team stronger and help train backup people.",
 "អ្នកបានរៀនអ្វីខ្លះពីតេស្តនេះ? សូមពន្យល់ឲ្យច្បាស់។",
 "free_text",None,
 json.dumps({"rubric":"MOST IMPORTANT QUESTION. Check: depth of reflection vs just listing rules. Strong = shows they internalized why each rule exists. Weak = copy of rules without understanding. Time taken matters: very fast answer = did not read properly."}),
 ["self_awareness","systems_thinking","learning","leadership"],"critical",False),
]

all_questions = A + B + C + D

inserted = 0
for q in all_questions:
    cur.execute("""
        INSERT INTO hiring_quiz_questions
        (id, quiz_version_id, part, section, display_order, question_text_en, question_text_km,
         answer_type, options, correct_answer, trait_tags, severity_if_wrong, requires_verbal_retest)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO NOTHING
    """, (q[0], VID, q[1], q[2], q[3], q[4], q[5], q[6],
          q[7],   # options (already json string or None)
          q[8],   # correct_answer (already json string)
          q[9],   # trait_tags (list)
          q[10],  # severity_if_wrong
          q[11])) # requires_verbal_retest
    inserted += 1

conn.commit()

cur.execute("SELECT COUNT(*) FROM hiring_quiz_questions")
total = cur.fetchone()[0]
cur.execute("SELECT part, COUNT(*) FROM hiring_quiz_questions GROUP BY part ORDER BY part")
by_part = cur.fetchall()
cur.execute("SELECT id FROM hiring_quiz_questions WHERE requires_verbal_retest = TRUE ORDER BY id")
verbal = [r[0] for r in cur.fetchall()]

print(f"Total questions: {total} (inserted {inserted})")
for part, cnt in by_part:
    print(f"  Part {part}: {cnt}")
print(f"Verbal retest flags ({len(verbal)}): {verbal}")
conn.close()
print("Done.")
