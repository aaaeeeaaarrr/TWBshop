"""
Owner notifications from assessment layer.
English only — Khmer field on targeted messages stays NULL until validator passes.
Idempotent: stores sent_at on assessment row to prevent duplicate notifications.
"""

import html
import json
import logging
import psycopg2

import config

logger = logging.getLogger(__name__)

_PAY_RULES = {
    9:  {"base": 160, "bonus": 15, "food_riel": 4500},
    10: {"base": 170, "bonus": 15, "food_riel": 5000},
    11: {"base": 190, "bonus": 20, "food_riel": 5500},
    12: {"base": 210, "bonus": 20, "food_riel": 6000},
}


def _db():
    from shared.database import raw_connect
    return raw_connect()


def _esc(v) -> str:
    return html.escape(str(v)) if v else ""


def _offer_display(suggested_offer: dict) -> str:
    h = suggested_offer.get("hours_per_day", 9)
    base = suggested_offer.get("recommended_base_salary", 0)
    bonus = suggested_offer.get("bonus", 0)
    food = suggested_offer.get("food_allowance_daily_riel", 0)
    rule = _PAY_RULES.get(h, {})
    lines = [
        f"{h}h/day | ${base} base + ${bonus} bonus + {food:,} riel food/day",
        f"Acceptable range: ${suggested_offer.get('acceptable_range', [base, base])[0]}"
        f"–${suggested_offer.get('acceptable_range', [base, base])[1]}",
        f"Do not exceed ${suggested_offer.get('do_not_exceed_without_owner_review', base)}"
        f" without owner review",
        f"Reason: {_esc(suggested_offer.get('reasoning', ''))}",
    ]
    if suggested_offer.get("note"):
        lines.append(f"Note: {_esc(suggested_offer['note'])}")
    return "\n".join(lines)


async def notify_owner_assessment(
    bot,
    assessment: dict,
    package: dict,
    assessment_id: int,
    targeted_message_id: int | None,
) -> None:
    """
    Send owner a structured assessment summary in English.
    Khmer targeted message is NOT auto-sent — owner must approve separately.
    Idempotent: checks if notification already sent for this assessment_id.
    """
    # Idempotency check
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute(
            "SELECT quiz_owner_notified_at FROM hiring_quiz_attempts WHERE id = %s",
            (package.get("attempt_id"),)
        )
        row = cur.fetchone()
        if row and row[0]:
            logger.info("Assessment notification already sent for attempt %s", package.get("attempt_id"))
            return
    finally:
        cur.close(); conn.close()

    cand = package.get("candidate", {})
    intake = package.get("intake", {})
    quiz_attempt = package.get("quiz_attempt", {})
    scores = package.get("mechanical_scores", {})

    username = cand.get("telegram_username")
    user_id  = cand.get("telegram_user_id")
    name     = cand.get("name", "Unknown")

    if username:
        user_ref = f"@{_esc(username)}"
    elif user_id:
        user_ref = f'<a href="tg://user?id={user_id}">{_esc(name)}</a>'
    else:
        user_ref = _esc(name)

    rec = assessment.get("overall_recommendation", "unknown")
    conf = assessment.get("confidence", 0)
    icon = "✅" if rec in ("hire", "trial") else ("⚠️" if "hold" in rec else "❌")

    abandoned = quiz_attempt.get("abandoned_at_question_id")
    abandoned_str = f" — abandoned at {_esc(str(abandoned))}" if abandoned else ""
    resume_str = f" (resumed {quiz_attempt.get('resume_count', 0)}×)" if quiz_attempt.get("resume_count") else ""

    # Scores line
    score_line = ""
    if scores:
        a   = scores.get("score_a",    scores.get("a_pct",   "?"))
        b   = scores.get("score_b",    scores.get("b_pct",   "?"))
        w   = scores.get("written_pct", "?")
        ov  = scores.get("overall_pct", scores.get("overall", "?"))
        score_line = f"\n📊 <b>Scores:</b> A={a}% B={b}% Written={w}% Overall={ov}%"

    # Critical signals
    crit_lines = ""
    for hit in assessment.get("critical_signal_hits", [])[:4]:
        crit_lines += (
            f"\n  ⚠ {_esc(hit.get('signal',''))} "
            f"[{', '.join(hit.get('evidence_refs', []))}]\n"
            f'  Raw: "{_esc(hit.get("raw_quote", ""))}"'
        )

    # Positive signals
    pos_lines = ""
    for f in assessment.get("evidence_based_findings", []):
        if f.get("finding_type") == "positive":
            pos_lines += f"\n  ✓ {_esc(f.get('description',''))} [{', '.join(f.get('evidence_refs', []))}]"

    # Required before offer
    required = assessment.get("required_before_offer", [])
    req_str = "\n".join(f"  {i+1}. {_esc(r)}" for i, r in enumerate(required))

    # Watchlist
    watch_lines = "\n".join(
        f"  • {_esc(w.get('watch', ''))}"
        for w in assessment.get("trial_watchlist_with_behaviors", [])[:3]
    )

    # Offer
    offer_str = _offer_display(assessment.get("suggested_offer", {}))

    lines = [
        f"{icon} <b>Assessment: {_esc(rec.replace('_', ' ').title())}</b> — {user_ref}",
        f"Candidate: {_esc(name)} | Position: {_esc(cand.get('position') or '?')}",
        f"Attempt #{package.get('attempt_id')}{resume_str}{abandoned_str}",
        f"Confidence: {conf:.0%}",
        score_line,
        "",
        f"<b>Who is this person?</b>",
        _esc(assessment.get("who_is_this_person", "")),
        "",
    ]

    if assessment.get("score_vs_judgment_note"):
        lines += [
            "<b>Score vs judgment:</b>",
            _esc(assessment["score_vs_judgment_note"]),
            "",
        ]

    if crit_lines:
        lines += ["<b>Critical signals:</b>" + crit_lines, ""]

    if pos_lines:
        lines += ["<b>Positives:</b>" + pos_lines, ""]

    if req_str:
        lines += ["<b>Required before offer:</b>", req_str, ""]

    lines += ["<b>Suggested offer:</b>", offer_str, ""]

    if watch_lines:
        lines += ["<b>First 3 days — watch:</b>", watch_lines, ""]

    if targeted_message_id:
        lines.append(f"<b>Targeted message ready — approve to send (message_id={targeted_message_id})</b>")
    else:
        lines.append("<i>Targeted message not yet generated.</i>")

    try:
        await bot.send_message(
            config.OWNER_TELEGRAM_ID,
            "\n".join(lines),
            parse_mode="HTML",
        )
        # Mark as notified
        conn = _db(); cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE hiring_quiz_attempts
                SET quiz_owner_notified_at = now(), quiz_owner_notified_outcome = %s
                WHERE id = %s
            """, (rec, package.get("attempt_id")))
            conn.commit()
        finally:
            cur.close(); conn.close()
    except Exception as e:
        logger.error("notify_owner_assessment failed: %s", e)


def store_targeted_message(
    assessment_id: int,
    attempt_id: int,
    candidate_id: int,
    points: list[dict],
    english_text: str,
) -> int:
    """Store the English targeted message. Khmer is NULL until validated."""
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO hiring_targeted_messages
                (candidate_id, assessment_id, attempt_id,
                 message_type, points_json, english_text,
                 khmer_text, khmer_validated, khmer_validation_status,
                 owner_approved, created_at)
            VALUES (%s,%s,%s, 'applicant_correction', %s, %s,
                    NULL, FALSE, 'pending', FALSE, now())
            RETURNING id
        """, (
            candidate_id, assessment_id, attempt_id,
            json.dumps(points, ensure_ascii=False),
            english_text,
        ))
        msg_id = cur.fetchone()[0]
        conn.commit()
        return msg_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close(); conn.close()


def store_khmer_on_message(targeted_message_id: int, points_with_khmer: list[dict]) -> bool:
    """
    Store validated Khmer on an existing targeted_message row.
    Returns True only if ALL points passed Khmer validation.
    """
    all_passed = all(pt.get("khmer_status") == "passed" for pt in points_with_khmer)
    status = "passed" if all_passed else "validation_failed"
    khmer_text = None
    if all_passed:
        khmer_text = "\n\n──\n\n".join(pt.get("khmer", "") or "" for pt in points_with_khmer)

    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE hiring_targeted_messages
            SET khmer_text = %s,
                khmer_validated = %s,
                khmer_validation_status = %s,
                points_json = %s
            WHERE id = %s
        """, (
            khmer_text,
            all_passed,
            status,
            json.dumps(points_with_khmer, ensure_ascii=False),
            targeted_message_id,
        ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close(); conn.close()
    return all_passed
