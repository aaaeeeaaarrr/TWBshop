"""
Khmer text validator — rejects broken spacing, artifacts, and Latin intrusions.

Rules:
  1. COENG (U+17D2 = ្) followed by space, dash, or Latin letter = always broken
  2. ANUSVARA (U+17C6 = ំ) + single space + Khmer consonant = word split
  3. VOWEL U (U+17BB = ុ) + any whitespace + Khmer consonant = word split
  4. 2+ spaces between any two Khmer characters = broken
  5. 2+ spaces between Khmer character and Latin letter = broken
  6. Box-drawing / special dash artifacts inside text = broken
  7. Latin letter directly adjacent to Khmer character (no space) = broken,
     UNLESS it is an approved standalone term (CV, Done, The Wine Bakery, etc.)

Auto-send is BLOCKED until validate_khmer() returns passed=True.
"""

import re
from typing import NamedTuple

# ── Character constants ────────────────────────────────────────────────────────
COENG    = "្"   # ្  subscript/COENG marker
ANUSVARA = "ំ"   # ំ  nasalisation mark
VOWEL_U  = "ុ"   # ុ  vowel sign U
KHMER    = r"[ក-៿]"   # all Khmer Unicode
KHMER_CONS = r"[ក-អ]" # consonants only

# Box-drawing (U+2500–U+257F) and special dashes (en, em, horiz-bar)
_BOX_DASH = r"[─-╿‒-―]"

# Approved Latin terms that may appear with proper spacing in Khmer messages.
# They are stripped before the Latin-adjacency check so they don't trigger it.
_APPROVED_LATIN: list[str] = [
    "The Wine Bakery",
    "Lucky Mart",
    "supervisor",
    "Part E",
    "CV",
    "Done",
    "OK",
]

_RULES: list[tuple[re.Pattern, str, str]] = [
    # 1. COENG + space, dash, or Latin — always broken
    (
        re.compile(rf"{COENG}[\s‒-―─-╿A-Za-z]"),
        "coeng_bad_follow",
        "COENG (្) must be immediately followed by a Khmer consonant",
    ),
    # 2. ANUSVARA + single space + Khmer consonant — word split
    (
        re.compile(rf"{ANUSVARA} {KHMER_CONS}"),
        "anusvara_space_consonant",
        "ANUSVARA (ំ) + single space + consonant — mid-word split",
    ),
    # 3. VOWEL U + whitespace + Khmer consonant — word split
    (
        re.compile(rf"{VOWEL_U}\s+{KHMER_CONS}"),
        "vowel_u_split",
        "VOWEL U (ុ) + whitespace + consonant",
    ),
    # 4. 2+ spaces between two Khmer characters
    (
        re.compile(rf"{KHMER}\s{{2,}}{KHMER}"),
        "multi_space_inside_khmer",
        "Two or more spaces between Khmer characters",
    ),
    # 5. 2+ spaces between Khmer and Latin
    (
        re.compile(rf"{KHMER}\s{{2,}}[A-Za-z]"),
        "multi_space_khmer_latin",
        "Two or more spaces between Khmer character and Latin letter",
    ),
    # 6. Box-drawing / dash artifacts — rendering junk
    (
        re.compile(_BOX_DASH),
        "box_or_dash_artifact",
        "Box-drawing character or special dash artifact in Khmer text",
    ),
]


class KhmerViolation(NamedTuple):
    rule:    str
    reason:  str
    match:   str
    pos:     int


def _strip_approved_terms(text: str) -> str:
    """Replace approved Latin terms with neutral whitespace before adjacency check."""
    result = text
    for term in sorted(_APPROVED_LATIN, key=len, reverse=True):
        result = result.replace(term, " " * len(term))
    return result


def validate_khmer(text: str) -> dict:
    """
    Returns {"passed": bool, "violations": [...]}.
    Caller must verify passed=True before storing or sending any Khmer text.
    Prints repr() of input to stderr when violations are found, to prove exact bytes.
    """
    violations: list[dict] = []

    # Rules 1-6: regex-based
    for rx, rule_id, reason in _RULES:
        for m in rx.finditer(text):
            violations.append({
                "rule":   rule_id,
                "reason": reason,
                "match":  repr(m.group(0)),
                "pos":    m.start(),
            })

    # Rule 7: Latin letter directly adjacent to Khmer (after stripping approved terms)
    stripped = _strip_approved_terms(text)
    for m in re.finditer(rf"({KHMER})([A-Za-z])|([A-Za-z])({KHMER})", stripped):
        violations.append({
            "rule":   "latin_adjacent_khmer",
            "reason": "Latin letter directly adjacent to Khmer character (unapproved term)",
            "match":  repr(m.group(0)),
            "pos":    m.start(),
        })

    if violations:
        import sys
        print(f"[khmer_validator] FAILED input repr: {repr(text)}", file=sys.stderr)

    return {"passed": len(violations) == 0, "violations": violations}
