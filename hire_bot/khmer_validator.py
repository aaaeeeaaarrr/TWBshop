"""
Khmer text validator — rejects broken internal spacing before any
Khmer text is auto-sent to applicants or saved as calibration.

Rules:
  1. COENG (U+17D2 = ្) + any whitespace = always broken
  2. ANUSVARA (U+17C6 = ំ) + single space + Khmer consonant = word split
  3. VOWEL SIGN U (U+17BB = ុ) + whitespace + Khmer consonant = word split
  4. 2+ spaces between any two Khmer characters = broken
  5. 2+ spaces between Khmer character and Latin letter = broken

Auto-send is BLOCKED until validate_khmer() returns passed=True.
Khmer field stays NULL/pending_manual_approval if validation fails.
"""

import re
from typing import NamedTuple


COENG    = "្"   # ្  subscript/COENG marker — ALWAYS followed immediately by consonant
ANUSVARA = "ំ"   # ំ  nasalisation mark
VOWEL_U  = "ុ"   # ុ  vowel sign U

# All Khmer Unicode characters (consonants, vowels, diacritics, punctuation)
KHMER_CHAR  = r"[ក-៿]"
# Khmer consonants only
KHMER_CONS  = r"[ក-អ]"

_RULES: list[tuple[re.Pattern, str, str]] = [
    # 1. COENG + any whitespace (even single space) — always wrong
    (
        re.compile(rf"{COENG}\s"),
        "coeng_split",
        "COENG (្) must be immediately followed by consonant — no space allowed",
    ),
    # 2. ANUSVARA + single space + Khmer consonant — word split
    (
        re.compile(rf"{ANUSVARA} {KHMER_CONS}"),
        "anusvara_space_consonant",
        "ANUSVARA (ំ) followed by space then consonant — likely mid-word split",
    ),
    # 3. VOWEL U + any whitespace + Khmer consonant — word split
    (
        re.compile(rf"{VOWEL_U}\s+{KHMER_CONS}"),
        "vowel_u_split",
        "VOWEL U (ុ) followed by whitespace then consonant",
    ),
    # 4. 2+ spaces between two Khmer characters
    (
        re.compile(rf"{KHMER_CHAR}\s{{2,}}{KHMER_CHAR}"),
        "multi_space_inside_khmer",
        "Two or more spaces between Khmer characters",
    ),
    # 5. 2+ spaces between Khmer character and Latin letter
    (
        re.compile(rf"{KHMER_CHAR}\s{{2,}}[A-Za-z]"),
        "multi_space_khmer_latin",
        "Two or more spaces between Khmer character and Latin letter",
    ),
]


class KhmerViolation(NamedTuple):
    rule:    str
    reason:  str
    match:   str
    pos:     int


def validate_khmer(text: str) -> dict:
    """
    Returns {"passed": bool, "violations": [KhmerViolation, ...]}.
    Caller must check passed=True before auto-sending any Khmer text.
    """
    violations: list[KhmerViolation] = []
    for rx, rule_id, reason in _RULES:
        for m in rx.finditer(text):
            violations.append(KhmerViolation(
                rule=rule_id,
                reason=reason,
                match=repr(m.group(0)),
                pos=m.start(),
            ))
    return {"passed": len(violations) == 0, "violations": [v._asdict() for v in violations]}
