"""
Full assessment pipeline — called after complete_session() in hire_bot/bot.py.

Steps:
  1. collect_assessment_package()
  2. run_phase1_auto_grade()          (existing scorer.py)
  3. detect_rule_contradictions()     (existing scorer.py)
  4. detect_partial_answers()         (assessment_package.py)
  5. detect_critical_signal_hits()    (assessment_package.py)
  6. run_final_hiring_assessment()    (Opus via assessment_runner.py)
  7. validate_model_json()
  8. store_assessment()
  9. run_khmer_rewrite() — separate pass, blocked until validator passes
  10. store_targeted_message()
  11. notify_owner_assessment() — English only
"""

import logging
import json

logger = logging.getLogger(__name__)


async def run_full_assessment(
    bot,
    attempt_id: int,
    session_id: int | None = None,
) -> dict | None:
    """
    Entry point: run the full assessment pipeline for a completed quiz.
    Returns assessment dict or None on failure.
    Assessment failure does not crash the quiz completion — errors are logged.
    """
    try:
        from hire_bot.assessment_package import collect_assessment_package
        from hire_bot.assessment_runner import (
            run_final_hiring_assessment,
            run_khmer_rewrite,
            store_assessment,
            validate_assessment_json,
        )
        from hire_bot.assessment_notify import (
            notify_owner_assessment,
            store_targeted_message,
            store_khmer_on_message,
        )

        logger.info("Assessment pipeline started for attempt %s", attempt_id)

        # Step 1: collect evidence
        package = collect_assessment_package(attempt_id)
        intake_id = package.get("intake", {}).get("intake_id")
        candidate_id = package["candidate"]["candidate_id"]

        # Step 2+3: existing rule-based scoring already stores scores on attempt
        # (auto_grade runs inside complete_session — nothing to do here)

        # Step 4-5: additional detectors already run inside collect_assessment_package

        # Step 6: Opus assessment (English targeted message, no Khmer yet)
        assessment = await run_final_hiring_assessment(package)

        # Step 7+8: validate + store
        is_valid, errors = validate_assessment_json(assessment)
        if not is_valid:
            logger.error("Assessment JSON invalid: %s", errors)
            return None

        assessment_id = store_assessment(package, assessment, attempt_id, intake_id)
        logger.info("Assessment stored, id=%s", assessment_id)

        # Step 9: Khmer rewrite — separate Opus call, results validated
        points = assessment.get("targeted_message_points", [])
        points_with_khmer = await run_khmer_rewrite(points)

        # Step 10: store targeted message (Khmer field NULL if not validated)
        english_text = "\n\n──\n\n".join(pt["english"] for pt in points)
        msg_id = store_targeted_message(
            assessment_id=assessment_id,
            attempt_id=attempt_id,
            candidate_id=candidate_id,
            points=points_with_khmer,
            english_text=english_text,
        )

        all_khmer_passed = store_khmer_on_message(msg_id, points_with_khmer)
        if not all_khmer_passed:
            logger.warning(
                "Khmer validation failed on %d points — "
                "targeted message stored English-only, Khmer pending manual approval",
                sum(1 for pt in points_with_khmer if pt.get("khmer_status") != "passed")
            )

        # Step 11: notify owner (English only)
        await notify_owner_assessment(
            bot=bot,
            assessment=assessment,
            package=package,
            assessment_id=assessment_id,
            targeted_message_id=msg_id,
        )

        logger.info("Assessment pipeline complete for attempt %s", attempt_id)
        return assessment

    except Exception as e:
        logger.error("run_full_assessment failed for attempt %s: %s", attempt_id, e, exc_info=True)
        # Fail silently — quiz completion must not be blocked by assessment failure. The failure itself is a
        # BUILDER/system concern (degraded machinery + a raw error) → route to the MONITOR bot, NOT the client
        # hire bot (client/builder separation law, 2026-06-30).
        try:
            import asyncio
            from shared.monitor_notify import notify_monitor
            await asyncio.to_thread(
                notify_monitor,
                "⚠️ Assessment pipeline failed for attempt #%s.\nError: %s\nRaw scores still in DB."
                % (attempt_id, str(e)[:300]))
        except Exception:
            pass
        return None
