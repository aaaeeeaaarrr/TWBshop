"""
Curated follow-up questions for the hiring bot.

Each trigger type maps to a fixed bilingual follow-up question.
The bot NEVER freestyles live questions — only these approved ones.

Trigger types (set by scorer.auto_grade):
  verbal_retest          — candidate got a critical tick question wrong
  not_sure_critical      — candidate was "not sure" on a critical question
  d1_wrong_priority      — tablet/orders was not placed first in D1 ranking
  current_job_conflict   — candidate has a current job (resignation/last-day question)
  schedule_unclear       — school/other commitment needs exact confirmation
  start_date_missing     — candidate left start date blank
  commitment_maybe       — candidate answered "maybe" on 1-year commitment
  incomplete_answer      — a Part C question had low completeness score
  contradiction_flag     — tick vs written contradiction detected (human confirms first)
"""

from typing import Optional


# ── Follow-up question definitions ──────────────────────────────────────────
# Each entry: (question_en, question_km, callback_prefix)
# callback_prefix is used as the follow-up answer callback data root.

FOLLOWUP_QUESTIONS: dict[str, dict] = {

    "A1-Q5": {
        "en": (
            "You answered that it is okay to say 'busy tomorrow' one day before your shift.\n"
            "In our shop, that is not acceptable — we need at least 3 days notice for any planned absence.\n"
            "If you already had a plan, why would you only tell us one day before?"
        ),
        "km": (
            "ប្អូនឆ្លើយថា អាចប្រាប់ 'ស្អែករវល់' មួយថ្ងៃមុនវេន។\n"
            "នៅហាងយើង វាមិនអាចទទួលយកបានទេ — យើងត្រូវការការជូនដំណឹងយ៉ាងហោចណាស់ ៣ ថ្ងៃ។\n"
            "បើប្អូនមានផែនការរួចហើយ ហេតុអ្វីប្រាប់តែមួយថ្ងៃ?"
        ),
        "callback": "followup_a1q5",
    },

    "A1-Q7": {
        "en": (
            "You ticked that hiding your schedule from management is not dishonest.\n"
            "We believe schedule honesty is part of job honesty.\n"
            "If your school hours or other job changes, what is the right thing to do?"
        ),
        "km": (
            "ប្អូនធីកថា លាក់ម៉ោងកាលវិភាគពីគ្រប់គ្រង មិនមែនជាការភូតភរទេ។\n"
            "យើងជឿថា ការប្រាប់ម៉ោងច្បាស់លាស់ គឺជាផ្នែកមួយនៃភាពស្មោះត្រង់។\n"
            "បើម៉ោងរៀន ឬការងារផ្សេងផ្លាស់ប្តូរ ប្អូនគួរធ្វើអ្វី?"
        ),
        "callback": "followup_a1q7",
    },

    "A2-Q13": {
        "en": (
            "You answered that hiding a mistake is NOT worse than making an honest mistake.\n"
            "We see it the other way: the mistake itself can be fixed; hiding it cannot be undone.\n"
            "What would you do if you made a mistake and no one saw it?"
        ),
        "km": (
            "ប្អូនឆ្លើយថា ការលាក់កំហុស មិនអាក្រក់ជាងការធ្វើកំហុសដោយស្មោះត្រង់ទេ។\n"
            "យើងគិតខុស — កំហុសអាចជួសជុលបាន ការលាក់ មិនអាចលប់ចោលបាន។\n"
            "បើប្អូនធ្វើខុស ហើយគ្មាននរណាឃើញ ប្អូននឹងធ្វើអ្វី?"
        ),
        "callback": "followup_a2q13",
    },

    "A2-Q20": {
        "en": (
            "You ticked that food dropped on the floor can still be sold if it looks clean.\n"
            "This is a food safety rule — floor food is never sold, no exceptions.\n"
            "Do you understand and agree with this rule?"
        ),
        "km": (
            "ប្អូនធីកថា អាហារធ្លាក់លើឥដ្ឋ អាចលក់បានបើមើលទៅស្អាត។\n"
            "នេះជាច្បាប់អនាម័យ — អាហារធ្លាក់លើឥដ្ឋ មិនដែលលក់ គ្មានករណីលើកលែងទេ។\n"
            "ប្អូនយល់ ហើយព្រមទទួលយកច្បាប់នេះទេ?"
        ),
        "callback": "followup_a2q20",
    },

    "A4-Q38": {
        "en": (
            "You ticked that good staff do NOT need to work hard when management is not watching.\n"
            "We hire people who work the same whether or not anyone is looking.\n"
            "What does a productive hour at work look like for you when you are alone?"
        ),
        "km": (
            "ប្អូនធីកថា បុគ្គលិកល្អ មិនចាំបាច់ខំប្រឹងធ្វើការ ពេលគ្រប់គ្រងមិននៅទេ។\n"
            "យើងជ្រើសរើសមនុស្សដែលធ្វើការដូចគ្នា មិនថាមាននរណាមើលឬអត់។\n"
            "ម៉ោងមួយដ៏ផ្លែផ្កាមើលទៅយ៉ាងណា សម្រាប់ប្អូន ពេលធ្វើការម្នាក់ឯង?"
        ),
        "callback": "followup_a4q38",
    },

    "A5-Q42": {
        "en": (
            "You ticked that complaining to coworkers about the shop or manager is acceptable.\n"
            "We ask staff to bring concerns directly to management — not to other staff.\n"
            "If something at work bothers you, what is the right first step?"
        ),
        "km": (
            "ប្អូនធីកថា ការប្តឹងទៅកាន់សហការីអំពីហាងឬអ្នកគ្រប់គ្រង គឺអាចទទួលយកបាន។\n"
            "យើងស្នើបុគ្គលិកនាំបញ្ហាដោយផ្ទាល់ទៅគ្រប់គ្រង — មិនទៅសហការីទេ។\n"
            "បើអ្វីមួយនៅកន្លែងធ្វើការធ្វើឱ្យប្អូនរំខាន ជំហានទីមួយដ៏ត្រឹមត្រូវគឺអ្វី?"
        ),
        "callback": "followup_a5q42",
    },

    "A6-Q51": {
        "en": (
            "You ticked that training new staff does NOT cost the business time and money.\n"
            "In practice, when we train someone, a senior staff member spends hours with them.\n"
            "If you leave suddenly after we invest in training you, what happens to that cost?"
        ),
        "km": (
            "ប្អូនធីកថា ការបណ្តុះបណ្តាលបុគ្គលិកថ្មី មិនចំណាយពេលវេលា និងលុយរបស់អាជីវកម្មទេ។\n"
            "ក្នុងការអនុវត្ត ពេលយើងបណ្តុះបណ្តាលនរណាម្នាក់ បុគ្គលិកជំនាញចំណាយម៉ោងច្រើនជាមួយពួកគេ។\n"
            "បើប្អូនចាកចេញភ្លាមៗ ក្រោយយើងបណ្តុះបណ្តាលប្អូនរួចហើយ តម្លៃនោះទៅណា?"
        ),
        "callback": "followup_a6q51",
    },

    "A6-Q58": {
        "en": (
            "You ticked that sudden resignation does NOT cause other staff more work.\n"
            "When one person leaves without notice, the team must cover their shifts immediately.\n"
            "If you needed to leave this job, how much notice would you give and why?"
        ),
        "km": (
            "ប្អូនធីកថា ការលាออកភ្លាមៗ មិនធ្វើឱ្យសហការីដទៃធ្វើការកាន់តែច្រើនទេ។\n"
            "ពេលម្នាក់ចាកចេញដោយគ្មានការជូនដំណឹង ក្រុមការងារត្រូវការគ្របដណ្តប់វេនភ្លាម។\n"
            "បើប្អូនត្រូវចាកចេញពីការងារនេះ ប្អូននឹងជូនដំណឹងប៉ុន្មានថ្ងៃ ហើយហេតុអ្វី?"
        ),
        "callback": "followup_a6q58",
    },

    "d1_wrong_priority": {
        "en": (
            "In your priority ranking, you did not put customer orders and the tablet first.\n"
            "In our shop: orders and tablet always come first — before cleaning, before anything else.\n"
            "Can you explain what your thinking was when you chose your order?"
        ),
        "km": (
            "ក្នុងចំណាត់ថ្នាក់អាទិភាព ប្អូនមិនដាក់ការបញ្ជាទិញអតិថិជន និងថេប្លេតជាដំបូងទេ។\n"
            "នៅហាងយើង ការបញ្ជាទិញ និងថេប្លេតតែងតែមកដំបូង — មុនការសម្អាត មុនអ្វីៗដទៃ។\n"
            "ប្អូនអាចពន្យល់ពីអ្វីដែលប្អូនគិត ពេលជ្រើសរើសចំណាត់ថ្នាក់?"
        ),
        "callback": "followup_d1_priority",
    },

    "current_job_conflict": {
        "en": (
            "You currently have another job.\n"
            "Before we can confirm a start date, we need to understand:\n"
            "Are you planning to leave that job? If yes, what is your last day? "
            "If no, can you work both without affecting your performance here?"
        ),
        "km": (
            "ប្អូនបច្ចុប្បន្នមានការងារផ្សេង។\n"
            "មុនយើងបញ្ជាក់ថ្ងៃចាប់ផ្តើម យើងត្រូវការដឹង:\n"
            "ប្អូនមានផែនការចាកចេញពីការងារនោះទេ? បើបាទ/ចាស ថ្ងៃចុងក្រោយរបស់ប្អូននៅពេលណា? "
            "បើទេ ប្អូនអាចធ្វើការទាំងពីរដោយមិនប៉ះពាល់ដល់ការអនុវត្តនៅទីនេះទេ?"
        ),
        "callback": "followup_current_job",
    },

    "commitment_maybe": {
        "en": (
            "You answered 'maybe' when asked if you can commit to working here for 1 year.\n"
            "We invest real time training every new person — we need people who plan to stay.\n"
            "What could stop you from completing 1 year here? Please be honest."
        ),
        "km": (
            "ប្អូនឆ្លើយ 'ប្រហែល' ពេលបានសួរថា ប្អូនអាចធ្វើការនៅទីនេះ ១ ឆ្នាំបានទេ។\n"
            "យើងវិនិយោគពេលវេលាពិតប្រាកដ ក្នុងការបណ្តុះបណ្តាលនរណាម្នាក់ — យើងត្រូវការមនុស្សដែលគ្រោងស្នាក់នៅ។\n"
            "អ្វីអាចការពារប្អូនពីការបំពេញ ១ ឆ្នាំនៅទីនេះ? សូមមានភាពស្មោះត្រង់។"
        ),
        "callback": "followup_commitment",
    },

    "start_date_missing": {
        "en": (
            "You did not fill in a start date on your application.\n"
            "When exactly are you available to start — day, month, and year?\n"
            "If you are not sure yet, what is stopping you from knowing?"
        ),
        "km": (
            "ប្អូនមិនបានបំពេញថ្ងៃចាប់ផ្តើមនៅលើពាក្យស្នើសុំ។\n"
            "ប្អូនអាចចាប់ផ្តើមនៅពេលណាពិតប្រាកដ — ថ្ងៃ ខែ និងឆ្នាំ?\n"
            "បើប្អូននៅមិនច្បាស់ទៀតទេ អ្វីការពារប្អូនពីការដឹង?"
        ),
        "callback": "followup_start_date",
    },

    "incomplete_answer": {
        "en": (
            "Your answer to the previous question was incomplete — you only answered part of it.\n"
            "We need a complete answer: what happened, what you did, and how you would prevent it again.\n"
            "Please answer again with all three parts."
        ),
        "km": (
            "ចម្លើយរបស់ប្អូនចំពោះសំណួរមុន មិនពេញលេញទេ — ប្អូនឆ្លើយតែផ្នែកមួយ។\n"
            "យើងត្រូវការចម្លើយពេញលេញ: អ្វីបានកើតឡើង អ្វីដែលប្អូនបានធ្វើ និងរបៀបការពារវាម្តងទៀត។\n"
            "សូមឆ្លើយម្តងទៀតដោយមានផ្នែកទាំងបី។"
        ),
        "callback": "followup_incomplete",
    },
}


def get_followup(trigger_type: str, question_id: Optional[str] = None) -> Optional[dict]:
    """
    Returns the follow-up question dict for a given trigger.
    For verbal_retest and not_sure_critical, question_id selects the specific question.
    Returns None if no follow-up is defined for this trigger.
    """
    if trigger_type in ("verbal_retest", "not_sure_critical"):
        return FOLLOWUP_QUESTIONS.get(question_id)
    return FOLLOWUP_QUESTIONS.get(trigger_type)


MAX_FOLLOWUPS = 5

# Priority order for follow-up selection when more than MAX_FOLLOWUPS triggers fire
TRIGGER_PRIORITY = [
    "verbal_retest",        # 1st: critical honesty/value contradiction (must ask)
    "not_sure_critical",    # 2nd: uncertainty on a core value
    "current_job_conflict", # 3rd: schedule/commitment risk
    "commitment_maybe",     # 4th: unclear commitment
    "start_date_missing",   # 5th: missing start date
    "d1_wrong_priority",    # 6th: operational priority failure
    "incomplete_answer",    # 7th: completeness issue (lowest)
]


def get_followups_for_triggers(triggers: list[dict]) -> list[dict]:
    """
    Takes the triggers list from scorer.auto_grade and returns
    a deduplicated, priority-ordered list of follow-up questions — max MAX_FOLLOWUPS.

    Priority: verbal_retest > not_sure_critical > schedule/job > completeness.
    """
    seen_callbacks = set()
    prioritized: list[tuple[int, dict]] = []

    for t in triggers:
        q = get_followup(t["type"], t.get("question_id"))
        if q and q["callback"] not in seen_callbacks:
            priority = TRIGGER_PRIORITY.index(t["type"]) if t["type"] in TRIGGER_PRIORITY else 99
            prioritized.append((priority, q))
            seen_callbacks.add(q["callback"])

    prioritized.sort(key=lambda x: x[0])
    return [q for _, q in prioritized[:MAX_FOLLOWUPS]]
