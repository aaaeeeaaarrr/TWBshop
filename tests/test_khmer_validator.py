"""
Khmer validator proof tests — all strings as explicit Unicode escapes.
repr() is printed before every test so the exact bytes are visible in output.

Run: python3 -m pytest tests/test_khmer_validator.py -v -s
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hire_bot.khmer_validator import validate_khmer

# ── Broken strings — MUST REJECT ─────────────────────────────────────────────
# All written as explicit Unicode escapes to guarantee the exact bytes.

REJECT_CASES = [
    # (label, explicit-unicode string)

    # Original 8 cases
    ("coeng_single_space",          "ខ្ ដុំ"),
    # ខ្ ញុំ  — COENG + space

    ("vowel_u_double_space",        "ប៉ុ  ន្តែ"),
    # ប៉ុ  ន្តែ — VOWEL U + 2 spaces + consonant

    ("anusvara_multi_space",        "ចំ     ពោះ"),
    # ចំ     ពោះ — ANUSVARA + 5 spaces + consonant

    ("anusvara_single_space",       "ចាំ បាច់"),
    # ចាំ បាច់ — ANUSVARA + single space + consonant

    ("anusvara_space_ng",           "ទាំ ងពីរ"),
    # ទាំ ងពីរ — ANUSVARA + space + consonant

    ("khmer_multi_space_khmer",     "នៅទី     នេះ"),
    # នៅទី     នេះ — 5 spaces inside Khmer

    ("khmer_multi_space_latin",     "សូមផ្ញើ   CV"),
    # សូមផ្ញើ   CV — 3 spaces before Latin

    ("khmer_multi_space_and_split", "ប្អូនមិន   ចាំ បាច់"),
    # ប្អូនមិន   ចាំ បាច់ — multi-space + anusvara split

    # New cases: box/dash artifacts
    ("box_dash_inside_khmer",       "ប្អូនបាន──ដោះស្រាយ"),
    # ប្អូនបាន──ដោះស្រាយ — U+2500 box-drawing inside Khmer

    ("em_dash_artifact",            "ចំ—ពោះ"),
    # ចំ—ពោះ — EM DASH (U+2014) between Khmer words

    # New cases: Latin adjacent to Khmer
    ("latin_fragment_adjacent",     "កំហុសtterrupt នោះ"),
    # កំហុសtterrupt នោះ — Latin directly after Khmer

    ("path_artifact_adjacent",      "ស្ថិតស្ថេរ។i/claude-code"),
    # ស្ថិតស្ថេរ។i/claude-code — Latin after Khmer punctuation

    # COENG followed by dash or Latin
    ("coeng_box_dash",              "ខ្─ញុំ"),
    # ខ្─ញុំ — COENG + box-drawing dash

    ("coeng_latin",                 "ខ្nញុំ"),
    # ខ្nញុំ — COENG + Latin letter
]

# ── Clean strings — MUST PASS ─────────────────────────────────────────────────
PASS_CASES = [
    ("agreement_line",
     "បើប្អូនយល់ព្រម"
     "ចំពោះចំណុចតាំង"
     "ពីរ ហើយត្រៀមខ្ល"
     "ួនធ្វើតាម យើងស្"
     "វាគមន៍ឲ្យប្អូន"
     "ចូលរួមជាមួយយើង។"),
    # បើប្អូនយល់ព្រមចំពោះចំណុចទាំងពីរ ហើយត្រៀមខ្លួនធ្វើតាម យើងស្វាគមន៍ឲ្យប្អូនចូលរួមជាមួយយើង។

    ("btn_agree",   "ខ្ញុំយល់ព្រម"),
    # ខ្ញុំយល់ព្រម

    ("clean_sentence",
     "ប៉ុន្តែប្អូនគួ"
     "ររាយការណ៍ផងដែរ។"),
    # ប៉ុន្តែប្អូនគួររាយការណ៍ផងដែរ។

    ("khmer_with_cv_approved",
     "សូមផ្ញើ CV ឬប្រវត្"
     "តិការងាររបស់ប្"
     "អូន។"),
    # សូមផ្ញើ CV ឬប្រវត្តិការងាររបស់ប្អូន។  (CV with proper spacing = allowed)

    ("btn_question", "ខ្ញុំមានសំណួរ"),
    # ខ្ញុំមានសំណួរ
]


@pytest.mark.parametrize("label,text", REJECT_CASES)
def test_must_reject(label, text):
    print(f"\n  [{label}] repr: {repr(text)}", file=sys.stderr)
    result = validate_khmer(text)
    assert not result["passed"], (
        f"[{label}] SHOULD HAVE REJECTED but passed.\n"
        f"  repr: {repr(text)}\n"
        f"  violations: {result['violations']}"
    )


@pytest.mark.parametrize("label,text", PASS_CASES)
def test_must_pass(label, text):
    print(f"\n  [{label}] repr: {repr(text)}", file=sys.stderr)
    result = validate_khmer(text)
    assert result["passed"], (
        f"[{label}] SHOULD HAVE PASSED but was rejected.\n"
        f"  repr: {repr(text)}\n"
        f"  violations: {result['violations']}"
    )
