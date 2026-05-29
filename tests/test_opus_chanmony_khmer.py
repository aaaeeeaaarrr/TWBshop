"""
Validator run against the Opus-produced Chanmony Khmer.
Every block below must pass the Sonnet khmer_validator.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hire_bot.khmer_validator import validate_khmer

# ── Opus-generated Chanmony targeted message blocks ──────────────────────────

POINT_1 = (
    "ប្អូនបានសរសេរថា ប្អូនបានកែការអាប់ប្រាក់ខុស មុនពេលប្រធានឃើញ។ "
    "យើងយល់ថា ប្អូនបានដោះស្រាយបញ្ហាបានឆាប់រហ័ស។ "
    "ប៉ុន្តែប្អូនគួររាយការណ៍ផងដែរ។ "
    "ការដោះស្រាយកំហុសដោយស្ងាត់ មានន័យថា "
    "យើងមិនអាចរៀន ឬការពារកំហុសនោះនៅពេលក្រោយឡើយ។ "
    "ការរាយការណ៍មិនមែនជាការទទួលទោសទេ "
    "វាគឺជារបៀបដែលធ្វើឱ្យក្រុមមានសុវត្ថិភាព និងស្ថិតស្ថេរ។"
)

POINT_2 = (
    "ប្អូនបានសរសេរថា ការពិនិត្យមើលមិត្តរួមការងារ មិនមែនជាការងាររបស់ប្អូនទេ។ "
    "នៅក្នុងផ្ទះបាយរបស់យើង ស្តង់ដារក្រុមជាការទទួលខុសត្រូវរួមគ្នា។ "
    "ប្អូនមិនចាំបាច់ត្រួតពិនិត្យអ្នកដទៃនោះទេ "
    "ប៉ុន្តែបើឃើញអ្វីដែលមិនត្រឹមត្រូវ "
    "យើងរំពឹងថា ប្អូននឹងប្រាប់ប្រធានម្តង ដោយស្ងប់ស្ងាត់។ "
    "នោះជាផ្នែកមួយនៃរបៀបធ្វើការរបស់យើងនៅទីនេះ។"
)

AGREEMENT = (
    "បើប្អូនយល់ព្រមចំពោះចំណុចទាំងពីរ ហើយត្រៀមខ្លួនធ្វើតាម "
    "យើងស្វាគមន៍ឲ្យប្អូនចូលរួមជាមួយយើង។"
)

OPEN_CHECK = (
    "មុនពេលយើងបន្ត សូមសរសេរមួយប្រយោគ៖ "
    "បើប្អូនធ្វើខុស ហើយគ្មាននរណាឃើញ "
    "ប្អូននឹងធ្វើអ្វីជាដំបូង?"
)

RESISTANCE = (
    "យើងយល់ថា ប្អូនបានដោះស្រាយបញ្ហា។ "
    "ប៉ុន្តែស្តង់ដាររបស់យើងច្បាស់៖ "
    "កំហុសត្រូវតែរាយការណ៍ ទោះបីបានដោះស្រាយរួចហើយក៏ដោយ។ "
    "បើប្អូនមិនស្រួលចិត្តជាមួយចំណុចនេះទេ "
    "ប្រហែលតំណែងនេះមិនទាន់ស័ក្តិសមសម្រាប់ប្អូននៅពេលនេះឡើយ។"
)

BTN_AGREE    = "ខ្ញុំយល់ព្រម"
BTN_QUESTION = "ខ្ញុំមានសំណួរ"


@pytest.mark.parametrize("name,text", [
    ("POINT_1",     POINT_1),
    ("POINT_2",     POINT_2),
    ("AGREEMENT",   AGREEMENT),
    ("OPEN_CHECK",  OPEN_CHECK),
    ("RESISTANCE",  RESISTANCE),
    ("BTN_AGREE",   BTN_AGREE),
    ("BTN_QUESTION", BTN_QUESTION),
])
def test_opus_chanmony_khmer_passes(name, text):
    result = validate_khmer(text)
    assert result["passed"], (
        f"{name} FAILED validator.\n"
        f"Text: {text!r}\n"
        f"Violations: {result['violations']}"
    )
