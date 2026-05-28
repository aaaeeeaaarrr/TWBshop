"""
Unit tests for Part E trigger evaluation and question sequencing.
All tests use _rows injection — no DB required.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hire_bot.questions import (
    evaluate_e_triggers,
    get_next_part_e_question,
    get_part_e_progress,
    PART_E_ALWAYS,
    PART_E_CONDITIONAL,
    PART_E_FINAL,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows(**answers) -> dict:
    """Build a _rows dict: keyword arg name = question_id (underscores → dashes), value = answer dict."""
    return {k.replace("_", "-"): v for k, v in answers.items()}


def triggers(rows_dict: dict) -> list[str]:
    return evaluate_e_triggers(attempt_id=0, _rows=rows_dict)


# ── E-T1: studying trigger ────────────────────────────────────────────────────

def test_e_t1_structured_yes():
    r = _rows(**{"E-A3a": {"answer": "A"}})
    assert "E-T1" in triggers(r)


def test_e_t1_structured_no():
    r = _rows(**{"E-A3a": {"answer": "B"}})
    assert "E-T1" not in triggers(r)


def test_e_t1_exam_keyword_in_e_a4():
    r = _rows(**{"E-A4": {"text": "I have an exam on June 5th"}})
    assert "E-T1" in triggers(r)


def test_e_t1_study_keyword_in_e_a4():
    r = _rows(**{"E-A4": {"text": "I attend university classes in the morning"}})
    assert "E-T1" in triggers(r)


def test_e_t1_no_study_signal():
    r = _rows(**{"E-A3a": {"answer": "B"}, "E-A4": {"text": "None"}})
    assert "E-T1" not in triggers(r)


# ── E-T2: current-job trigger ─────────────────────────────────────────────────

def test_e_t2_structured_yes():
    r = _rows(**{"E-A3b": {"answer": "A"}})
    assert "E-T2" in triggers(r)


def test_e_t2_structured_no():
    r = _rows(**{"E-A3b": {"answer": "B"}})
    assert "E-T2" not in triggers(r)


def test_e_t2_legacy_keyword():
    r = _rows(**{"E-A3": {"text": "Yes I am currently working at a cafe"}})
    assert "E-T2" in triggers(r)


def test_e_t2_legacy_no_prefix():
    # "no" at start of E-A3 blocks keyword match
    r = _rows(**{"E-A3": {"text": "no, I don't have a job"}})
    assert "E-T2" not in triggers(r)


# ── E-T3: delayed-start trigger ───────────────────────────────────────────────

def test_e_t3_structured_no():
    r = _rows(**{"E-A1a": {"answer": "B"}})
    assert "E-T3" in triggers(r)


def test_e_t3_structured_not_sure():
    r = _rows(**{"E-A1a": {"answer": "C"}})
    assert "E-T3" in triggers(r)


def test_e_t3_structured_yes_no_trigger():
    r = _rows(**{"E-A1a": {"answer": "A"}})
    assert "E-T3" not in triggers(r)


def test_e_t3_keyword_fallback():
    r = _rows(**{"E-A1": {"text": "I can start next month after my notice period"}})
    assert "E-T3" in triggers(r)


def test_e_t3_no_delay_signal():
    r = _rows(**{"E-A1a": {"answer": "A"}, "E-A1": {"text": "I can start tomorrow"}})
    assert "E-T3" not in triggers(r)


def test_e_t3_structured_overrides_no_keyword():
    # E-A1a=B triggers E-T3 even if no delay keywords in E-A1
    r = _rows(**{"E-A1a": {"answer": "B"}, "E-A1": {"text": "I will start on June 1st"}})
    assert "E-T3" in triggers(r)


# ── All triggers fire together ────────────────────────────────────────────────

def test_all_triggers():
    r = _rows(**{
        "E-A1a": {"answer": "C"},
        "E-A3a": {"answer": "A"},
        "E-A3b": {"answer": "A"},
    })
    result = triggers(r)
    assert "E-T1" in result
    assert "E-T2" in result
    assert "E-T3" in result


def test_no_triggers():
    r = _rows(**{
        "E-A1a": {"answer": "A"},
        "E-A1":  {"text": "I can start the day after tomorrow"},
        "E-A3a": {"answer": "B"},
        "E-A3b": {"answer": "B"},
        "E-A4":  {"text": "None"},
    })
    assert triggers(r) == []


# ── Sequence ordering ─────────────────────────────────────────────────────────

def test_part_e_always_starts_with_e_a1a():
    assert PART_E_ALWAYS[0] == "E-A1a"


def test_part_e_always_ends_with_e_a5():
    assert PART_E_ALWAYS[-1] == "E-A5"


def test_sequence_no_triggers():
    seq = PART_E_ALWAYS + [] + [PART_E_FINAL]
    assert seq == ["E-A1a", "E-A1", "E-A2", "E-A3a", "E-A3b", "E-A4", "E-A5", "E-Final"]


def test_sequence_all_triggers():
    seq = PART_E_ALWAYS + PART_E_CONDITIONAL + [PART_E_FINAL]
    assert seq.index("E-A5") < seq.index("E-T1")
    assert seq.index("E-A5") < seq.index("E-T2")
    assert seq.index("E-A5") < seq.index("E-T3")
    assert seq[-1] == "E-Final"


# ── get_next_part_e_question ──────────────────────────────────────────────────

def test_next_question_empty():
    assert get_next_part_e_question(set(), []) == "E-A1a"


def test_next_question_after_e_a1a():
    assert get_next_part_e_question({"E-A1a"}, []) == "E-A1"


def test_next_question_skips_answered():
    answered = {"E-A1a", "E-A1", "E-A2", "E-A3a", "E-A3b"}
    assert get_next_part_e_question(answered, []) == "E-A4"


def test_next_question_trigger_inserted():
    answered = set(PART_E_ALWAYS)
    triggered = ["E-T1"]
    assert get_next_part_e_question(answered, triggered) == "E-T1"


def test_next_question_complete():
    answered = set(PART_E_ALWAYS) | {"E-Final"}
    assert get_next_part_e_question(answered, []) is None


# ── get_part_e_progress ───────────────────────────────────────────────────────

def test_progress_first_question():
    assert get_part_e_progress("E-A1a", []) == "E 1/8"


def test_progress_with_triggers():
    # 7 always + 1 trigger + E-Final = 9 total
    assert get_part_e_progress("E-A1a", ["E-T1"]) == "E 1/9"


def test_progress_e_final_no_triggers():
    assert get_part_e_progress("E-Final", []) == "E 8/8"


def test_progress_unknown_qid():
    assert get_part_e_progress("X-UNKNOWN", []) == "E"
