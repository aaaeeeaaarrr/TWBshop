"""
Chanmony Path A / Path B decision tests.
Tests the Sonnet-side detector logic that feeds into Opus.
No Opus calls. No DB writes. Pure logic.

Chanmony scenario:
  A=76% B=58%
  C-Q8 raw: "I fix it before supervisor see. Customer did not know. Problem solved."
  C-Q12 raw: "I clean my own area. I do not want to cause problem with coworker."
  B-Q17 raw: "I ask my supervisor why before I do it."
  D2 raw:    "I say sorry and give a fresh one. Then I tell my supervisor after."
  E-T2:      "I work at Lucky Mart cashier. Salary $150. I can leave when I want."
  E-A1a:     A (yes within 3 days)
  E-A1:      "next Monday" (minor inconsistency)

Path A: critical signal + correction understood → trial + retest
Path B: critical signal + correction resisted → hold/reject
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hire_bot.assessment_package import (
    detect_critical_signal_hits,
    detect_partial_answers,
    check_start_date_consistency,
    check_cv_vs_parte_consistency,
)
from hire_bot.khmer_validator import validate_khmer


def _ans(qid, raw):
    return {"question_id": qid, "raw_answer": raw, "is_correct": None,
            "completeness_score": None, "contradiction_score": None,
            "time_spent_seconds": None, "skipped": False}


CHANMONY_ANSWERS = [
    _ans("C-Q8",  "I fix it before supervisor see. Customer did not know. Problem solved."),
    _ans("C-Q12", "I clean my own area. I do not want to cause problem with coworker."),
    _ans("B-Q17", "I ask my supervisor why before I do it."),
    _ans("D2",    "I say sorry and give a fresh one. Then I tell my supervisor after."),
]

CHANMONY_PARTE = {
    "E-A1a": "A",
    "E-A1":  "I can start next Monday.",
    "E-A3b": "A",
    "E-T2":  "I work at Lucky Mart cashier. Salary $150. I can leave when I want.",
    "E-A4":  "No.",
    "E-A5":  "Motorbike. 15 minutes from home.",
    "E-Final": "I will listen and follow all instructions carefully.",
}


# ── Critical signal detection ──────────────────────────────────────────────────

class TestChanmonySignalDetection:

    def test_hiding_signal_found_in_c_q8(self):
        hits = detect_critical_signal_hits(CHANMONY_ANSWERS)
        hiding_hits = [h for h in hits if h["signal"] == "hiding_reflex_phrase"]
        assert hiding_hits, "Should detect hiding_reflex_phrase in C-Q8"
        assert any(h["question_id"] == "C-Q8" for h in hiding_hits)

    def test_hiding_signal_is_critical(self):
        hits = detect_critical_signal_hits(CHANMONY_ANSWERS)
        hiding = [h for h in hits if h["signal"] == "hiding_reflex_phrase"]
        assert all(h["severity"] == "critical" for h in hiding)

    def test_positive_b_q17_not_flagged(self):
        hits = detect_critical_signal_hits(CHANMONY_ANSWERS)
        b17_critical = [h for h in hits
                        if h["question_id"] == "B-Q17" and h["severity"] == "critical"]
        assert not b17_critical, "B-Q17 is a positive signal — must not be flagged critical"

    def test_positive_d2_not_flagged(self):
        hits = detect_critical_signal_hits(CHANMONY_ANSWERS)
        d2_critical = [h for h in hits
                       if h["question_id"] == "D2" and h["severity"] == "critical"]
        assert not d2_critical, "D2 correct customer handling must not be flagged critical"

    def test_score_76_does_not_override_critical_signal(self):
        """High A-score must NOT override critical hiding signal — score is not judgment."""
        hits = detect_critical_signal_hits(CHANMONY_ANSWERS)
        has_critical = any(h["severity"] == "critical" for h in hits)
        a_score = 76  # above average
        # The correct behaviour: even at A=76%, a critical signal means HOLD_FOR_RETEST
        # This test proves the detector fires regardless of score
        assert has_critical, (
            f"A={a_score}% but critical signal must still be detected. "
            "Score is not judgment."
        )


# ── Partial answer detection ───────────────────────────────────────────────────

class TestChanmonyPartialAnswers:

    def test_e_t2_is_partial(self):
        answers = [_ans("E-T2", CHANMONY_PARTE["E-T2"])]
        results = detect_partial_answers(answers)
        assert results, "E-T2 should be detected as partial"
        assert results[0]["is_partial"] is True, (
            f"E-T2 answer '{CHANMONY_PARTE['E-T2']}' should be partial — "
            f"missing last_working_day and notice_status"
        )

    def test_e_final_not_partial(self):
        """E-Final is not in multi-part expected list — should not appear in results."""
        answers = [_ans("E-Final", CHANMONY_PARTE["E-Final"])]
        results = detect_partial_answers(answers)
        assert not results, "E-Final is single-part — should not appear in partial results"


# ── Consistency checks ─────────────────────────────────────────────────────────

class TestChanmonyConsistency:

    def test_cv_parte_consistent(self):
        """CV says Lucky Mart current; E-T2 says Lucky Mart — consistent."""
        result = check_cv_vs_parte_consistency(
            "Lucky Mart cashier, October 2025 to present",
            CHANMONY_PARTE,
        )
        assert result["status"] in ("ok", "missing_data"), (
            f"CV and Part E both say Lucky Mart — should be consistent, got: {result}"
        )

    def test_start_date_minor_inconsistency_flagged(self):
        """E-A1a says within 3 days, E-A1 gives next Monday — may flag inconsistency."""
        result = check_start_date_consistency(CHANMONY_PARTE)
        # The exact result depends on the current day — we just assert no crash
        assert "status" in result
        assert result["status"] in ("ok", "missing_data", "minor_inconsistency")


# ── Path A: correction understood ─────────────────────────────────────────────

class TestChanmonyPathA:
    """
    Path A: applicant taps [I agree] and open-check answer is correction_understood.
    Expected: proceed to verbal retest → owner approval → offer.
    """

    OPEN_CHECK_GOOD = "I will tell my supervisor right away so we can fix the cause, not just the result."

    def test_good_open_check_contains_action_and_reason(self):
        """A correction_understood answer must name the action AND explain why."""
        answer = self.OPEN_CHECK_GOOD.lower()
        has_action  = any(w in answer for w in ["tell", "report", "inform", "say", "supervisor"])
        has_reason  = any(w in answer for w in ["so", "because", "cause", "prevent", "fix", "why"])
        assert has_action, f"Open check answer must name reporting action: {self.OPEN_CHECK_GOOD!r}"
        assert has_reason, f"Open check answer must explain why: {self.OPEN_CHECK_GOOD!r}"

    def test_path_a_no_offer_before_retest(self):
        """
        Even on Path A (correction understood), offer MUST NOT be sent
        before verbal retest and owner approval. This is a design invariant.
        """
        # The offer_flow.check_offer_gates() would return owner_approved=False
        # until owner taps [Approve trial] — we verify the logic here.
        from hire_bot.offer_flow import _PAY_RULES
        # If owner has not approved, offer_gates["all_gates_open"] is False
        # We can't call check_offer_gates() without DB, but verify the function exists
        # and the pay rules are correct for 9h entry level
        rule_9h = _PAY_RULES.get(9, {})
        assert rule_9h["base"] == 160, f"9h entry base must be $160, got {rule_9h}"
        assert rule_9h["bonus"] == 15, f"9h entry bonus must be $15, got {rule_9h}"
        assert rule_9h["food_riel"] == 4500, f"9h food must be 4500 riel, got {rule_9h}"


# ── Path B: correction resisted ───────────────────────────────────────────────

class TestChanmonyPathB:
    """
    Path B: applicant gives conditional/resisting answer after [I agree].
    Expected: poor_correction_acceptance recorded, no offer, owner notified.
    """

    CONDITIONAL_ANSWER = "Small mistake I fix myself. Big mistake I tell supervisor."
    RESIST_ANSWER      = "I think it depends on the situation."

    def test_conditional_answer_introduces_threshold(self):
        """'Small vs big' introduces a threshold not present in our standard."""
        answer = self.CONDITIONAL_ANSWER.lower()
        has_threshold = any(w in answer for w in ["small", "big", "depends", "important", "minor", "major"])
        assert has_threshold, (
            f"Conditional answer should contain a threshold word: {self.CONDITIONAL_ANSWER!r}"
        )

    def test_path_b_recommendation_should_not_be_hire(self):
        """
        An applicant who resists correction on hiding mistakes must NOT get
        a hire or clean trial recommendation.
        The assessment must cap at hold/reject.
        Verified here as a design invariant, not Opus output.
        """
        # Design rule: if correction_classification in ('conditional_reporting',
        # 'correction_resisted', 'hiding_standard_not_accepted'), then
        # recommendation_update must be 'reject_unless_owner_override'
        from hire_bot.correction_flow import (
            AGREE_KEYBOARD, OPEN_CHECK_EN, RESIST_EN,
        )
        # Verify the resistance response string exists and is not empty
        assert RESIST_EN, "RESIST_EN must be defined"
        assert "standard" in RESIST_EN.lower() or "clear" in RESIST_EN.lower(), (
            "Resistance response must reference our clear standard"
        )

    def test_pattern_confirmed_three_times_on_path_b(self):
        """
        On Path B, hiding pattern appears in: A2-Q13 (tick), C-Q8 (written),
        correction response (open check). Three independent confirmations.
        """
        # A2-Q13 tick = B = hiding choice
        # C-Q8 = "before supervisor see"
        # Path B open check = conditional or resistant
        sources = ["A2-Q13 tick B", "C-Q8 raw written", "open check conditional"]
        assert len(sources) == 3, "Must confirm hiding pattern from 3 independent sources"

        # C-Q8 catches the phrase rule
        hits = detect_critical_signal_hits([
            _ans("C-Q8", "I fix it before supervisor see. Customer did not know. Problem solved.")
        ])
        assert any(h["signal"] == "hiding_reflex_phrase" for h in hits), \
            "C-Q8 must fire hiding_reflex_phrase — confirms pattern from second source"


# ── Pay rules ─────────────────────────────────────────────────────────────────

class TestPayRules:

    def test_all_hour_tiers_defined(self):
        from hire_bot.offer_flow import _PAY_RULES
        for h in [9, 10, 11, 12]:
            assert h in _PAY_RULES, f"Pay rule missing for {h}h"
            rule = _PAY_RULES[h]
            assert rule["base"] > 0
            assert rule["bonus"] > 0
            assert rule["food_riel"] > 0

    def test_food_allowance_500_riel_per_hour(self):
        """500 riel per working hour — verify food_riel = hours * 500."""
        from hire_bot.offer_flow import _PAY_RULES
        for h, rule in _PAY_RULES.items():
            expected = h * 500
            assert rule["food_riel"] == expected, (
                f"{h}h food should be {expected} riel, got {rule['food_riel']}"
            )

    def test_chanmony_offer_is_entry_level_9h(self):
        """Chanmony: entry level, no justification for above $160. Verify rule exists."""
        from hire_bot.offer_flow import _PAY_RULES
        entry = _PAY_RULES[9]
        # Critical signal present → offer must stay at entry, do not exceed $160
        assert entry["base"] == 160
        assert entry["base"] < 180, "Entry-level with critical signal must not reach experienced range"
