"""
Khmer validator — proof tests.
All 8 broken strings must REJECT. All 3 clean strings must PASS.
Run: python3 -m pytest tests/test_khmer_validator.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hire_bot.khmer_validator import validate_khmer

# ── MUST REJECT ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,description", [
    ("ខ្ ញុំ",                          "COENG split by single space"),
    ("ប៉ុ  ន្តែ",                        "VOWEL U split by double space"),
    ("ចំ     ពោះ",                       "multi-space inside word"),
    ("ចាំ បាច់",                         "ANUSVARA + single space + consonant"),
    ("ទាំ ងពីរ",                         "ANUSVARA + single space + consonant"),
    ("នៅទី     នេះ",                     "multi-space inside Khmer"),
    ("សូមផ្ញើ   CV ឬប្រវត្តិការងារ",    "multi-space between Khmer and Latin"),
    ("ប្អូនមិន   ចាំ បាច់",              "multi-space + ANUSVARA split"),
])
def test_must_reject(text, description):
    result = validate_khmer(text)
    assert not result["passed"], (
        f"SHOULD HAVE REJECTED '{description}' but passed.\n"
        f"Text: {repr(text)}\nViolations: {result['violations']}"
    )

# ── MUST PASS ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,description", [
    ("យើងស្វាគមន៍ឲ្យប្អូនចូលរួមជាមួយយើង។",  "clean agreement line"),
    ("ខ្ញុំយល់ព្រម",                            "clean button label"),
    ("ប៉ុន្តែប្អូនគួររាយការណ៍ផងដែរ។",          "clean sentence no spaces"),
])
def test_must_pass(text, description):
    result = validate_khmer(text)
    assert result["passed"], (
        f"SHOULD HAVE PASSED '{description}' but was rejected.\n"
        f"Text: {repr(text)}\nViolations: {result['violations']}"
    )
