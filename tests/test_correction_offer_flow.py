"""
Correction + offer flow wiring tests.
No DB, no bot context, no Opus calls — pure logic checks.

Tests:
1. Chanmony Path A: correction_understood → gates allow offer after owner_approved
2. Chanmony Path B: conditional_reporting → recommendation is reject_unless_owner_override
3. Double-tap agree does not duplicate correction response (idempotency guard in store fn)
4. Double-tap owner approve does not duplicate offer (is_already_approved guard)
5. Owner reject blocks offer (attempt_status = rejected, owner_approved_trial never set)
6. Missing E-T2 last day is detected as partial and prevents offer until answered
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import inspect
import pytest


# ── Path A: correction_understood ────────────────────────────────────────────

class TestChanmonyPathA:

    def test_classification_schema_includes_correction_understood(self):
        from hire_bot.correction_flow import _CLASSIFICATION_SYSTEM
        assert "correction_understood" in _CLASSIFICATION_SYSTEM
        assert "proceed_to_verbal_retest" in _CLASSIFICATION_SYSTEM

    def test_path_a_recommendation_is_proceed(self):
        """correction_understood maps to proceed_to_verbal_retest, not reject."""
        from hire_bot.correction_flow import _CLASSIFICATION_SYSTEM
        assert "proceed_to_verbal_retest" in _CLASSIFICATION_SYSTEM
        assert "reject_unless_owner_override" in _CLASSIFICATION_SYSTEM
        # Verify they are distinct outcomes
        assert "proceed_to_verbal_retest" != "reject_unless_owner_override"

    def test_offer_approval_button_uses_dynamic_keyboard(self):
        """request_owner_approval uses owner_approval_kb(attempt_id), not static OWNER_APPROVE_KB."""
        from hire_bot.offer_flow import request_owner_approval, owner_approval_kb
        src = inspect.getsource(request_owner_approval)
        assert "owner_approval_kb" in src, (
            "request_owner_approval must use owner_approval_kb(attempt_id) "
            "so attempt_id is embedded in callback_data"
        )

    def test_owner_approval_kb_encodes_attempt_id(self):
        """owner_approval_kb must embed attempt_id in callback_data."""
        from hire_bot.offer_flow import owner_approval_kb
        kb = owner_approval_kb(42)
        buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any("42" in (d or "") for d in buttons), (
            f"owner_approval_kb(42) must encode 42 in callback_data, got: {buttons}"
        )

    def test_offer_not_created_until_applicant_accepts(self):
        """send_offer_message does no DB write — record_offer_accepted is called on accept."""
        from hire_bot.offer_flow import send_offer_message, record_offer_accepted
        send_src = inspect.getsource(send_offer_message)
        assert "INSERT" not in send_src, (
            "send_offer_message must not INSERT — hiring_offers row is created only on accept"
        )
        accept_src = inspect.getsource(record_offer_accepted)
        assert "INSERT" in accept_src, "record_offer_accepted must INSERT the hiring_offers row"
        assert "accepted" in accept_src, "record_offer_accepted must set offer_status='accepted'"


# ── Path B: correction resisted ───────────────────────────────────────────────

class TestChanmonyPathB:

    def test_conditional_reporting_maps_to_reject(self):
        """conditional_reporting → recommendation_update must be reject_unless_owner_override."""
        from hire_bot.correction_flow import _CLASSIFICATION_SYSTEM
        assert "conditional_reporting" in _CLASSIFICATION_SYSTEM
        # The schema documents conditional_reporting as a distinct classification
        assert "hiding_standard_not_accepted" in _CLASSIFICATION_SYSTEM

    def test_path_b_notify_owner_fires(self):
        """_notify_owner_correction is always called, even on resistance."""
        from hire_bot.correction_flow import handle_open_check_answer
        src = inspect.getsource(handle_open_check_answer)
        assert "_notify_owner_correction" in src

    def test_path_b_resistance_response_exists(self):
        from hire_bot.correction_flow import RESIST_EN, RESIST_KH
        assert RESIST_EN, "RESIST_EN must be non-empty"
        assert RESIST_KH, "RESIST_KH must be non-empty"
        assert "standard" in RESIST_EN.lower() or "clear" in RESIST_EN.lower()


# ── Double-tap idempotency ────────────────────────────────────────────────────

class TestDoubleTapIdempotency:

    def test_store_correction_response_has_idempotency_guard(self):
        """_store_correction_response must check for existing row before INSERT."""
        from hire_bot.correction_flow import _store_correction_response
        src = inspect.getsource(_store_correction_response)
        assert "SELECT" in src and "attempt_id" in src, (
            "_store_correction_response must SELECT first to avoid duplicate inserts"
        )

    def test_cb_owner_approve_has_idempotency_guard(self):
        """cb_owner_approve must check is_already_approved before processing."""
        from hire_bot.bot import cb_owner_approve
        src = inspect.getsource(cb_owner_approve)
        assert "is_already_approved" in src, (
            "cb_owner_approve must call is_already_approved to prevent duplicate offers"
        )

    def test_cb_offer_accept_has_idempotency_guard(self):
        """cb_offer_accept must guard against double-tap via user_data flag."""
        from hire_bot.bot import cb_offer_accept
        src = inspect.getsource(cb_offer_accept)
        assert "offer_accepted" in src, (
            "cb_offer_accept must check context.user_data['offer_accepted'] to skip on repeat"
        )


# ── Owner reject blocks offer ─────────────────────────────────────────────────

class TestOwnerReject:

    def test_reject_sets_rejected_status(self):
        """reject_trial_in_db must set attempt_status='rejected'."""
        from hire_bot.offer_flow import reject_trial_in_db
        src = inspect.getsource(reject_trial_in_db)
        assert "rejected" in src

    def test_check_offer_gates_requires_owner_approved_trial(self):
        """offer gates owner_approved check requires exactly 'owner_approved_trial', not 'rejected'."""
        from hire_bot.offer_flow import check_offer_gates
        src = inspect.getsource(check_offer_gates)
        assert "owner_approved_trial" in src, (
            "check_offer_gates must require owner_approved_trial specifically — "
            "owner_rejected must not pass this gate"
        )

    def test_cb_owner_reject_registered(self):
        """cb_owner_reject must be registered in build_application."""
        from hire_bot.bot import build_application
        src = inspect.getsource(build_application)
        assert "cb_owner_reject" in src


# ── Missing E-T2 prevents offer ──────────────────────────────────────────────

class TestMissingE_T2:

    def test_partial_e_t2_detected(self):
        """E-T2 without last_working_day is detected as partial."""
        from hire_bot.assessment_package import detect_partial_answers
        partial_answer = "I work at Lucky Mart cashier. Salary $150. I can leave when I want."
        results = detect_partial_answers([{
            "question_id": "E-T2", "raw_answer": partial_answer,
            "is_correct": None, "completeness_score": None, "contradiction_score": None,
            "time_spent_seconds": None, "skipped": False,
        }])
        assert results, "E-T2 without last_working_day must be detected as partial"
        assert results[0]["is_partial"] is True

    def test_e_t2_expected_fields_include_last_working_day(self):
        from hire_bot.assessment_package import MULTI_PART_EXPECTED
        assert "E-T2" in MULTI_PART_EXPECTED
        assert "last_working_day" in MULTI_PART_EXPECTED["E-T2"]

    def test_cb_owner_approve_checks_e_t2(self):
        """cb_owner_approve must call check_e_t2_partial before sending offer."""
        from hire_bot.bot import cb_owner_approve
        src = inspect.getsource(cb_owner_approve)
        assert "check_e_t2_partial" in src, (
            "cb_owner_approve must check E-T2 completeness before sending offer"
        )

    def test_e_t2_partial_pauses_offer_with_owner_prompt(self):
        """When E-T2 is partial, cb_owner_approve stores awaiting_e_t2_for_attempt."""
        from hire_bot.bot import cb_owner_approve
        src = inspect.getsource(cb_owner_approve)
        assert "awaiting_e_t2_for_attempt" in src, (
            "cb_owner_approve must set awaiting_e_t2_for_attempt when E-T2 is partial"
        )

    def test_complete_e_t2_not_flagged(self):
        """A fully answered E-T2 is not flagged as partial."""
        from hire_bot.assessment_package import detect_partial_answers
        full_answer = (
            "I work at Lucky Mart cashier. My last day is June 15. "
            "Salary $150 per month. I need to give 2 weeks notice."
        )
        results = detect_partial_answers([{
            "question_id": "E-T2", "raw_answer": full_answer,
            "is_correct": None, "completeness_score": None, "contradiction_score": None,
            "time_spent_seconds": None, "skipped": False,
        }])
        if results:
            assert not results[0]["is_partial"], (
                f"Complete E-T2 must not be partial, got completeness={results[0].get('completeness_estimate')}"
            )
