"""
Offer flow — gated by all required conditions.

Conditions that must ALL be true before offer is sent:
1. Assessment complete (hiring_ai_assessments row exists)
2. Targeted message sent and owner-approved
3. Correction response classified as correction_understood (or with_qualifier)
4. Verbal retest passed (owner taps [Approve trial] in private bot chat)
5. E-T2 last working day clarified (if applicable)
6. Owner explicit approval

For non-critical cases (no critical_hold), conditions 3-5 are relaxed.

No salary discussion before all gates pass.
Actual offer recorded in hiring_offers (separate from applicant current salary).
"""

import json
import logging
import psycopg2
from datetime import date
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config

logger = logging.getLogger(__name__)

_PAY_RULES = {
    9:  {"base": 160, "bonus": 15, "food_riel": 4500},
    10: {"base": 170, "bonus": 15, "food_riel": 5000},
    11: {"base": 190, "bonus": 20, "food_riel": 5500},
    12: {"base": 210, "bonus": 20, "food_riel": 6000},
}
INTERNAL_RIEL_TO_USD = 4000  # 4,000 riel = $1

OWNER_APPROVE_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ Approve trial — send offer", callback_data="offer:owner_approve")],
    [InlineKeyboardButton("❌ Reject — close",             callback_data="offer:owner_reject")],
    [InlineKeyboardButton("⏸ Hold — need more info",       callback_data="offer:owner_hold")],
])


def _db():
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)


def check_offer_gates(attempt_id: int) -> dict:
    """
    Return which gates are open/closed for this attempt.
    All must be True for offer to proceed.
    """
    conn = _db(); cur = conn.cursor()
    try:
        # Assessment exists and is valid
        cur.execute("""
            SELECT id, recommendation, output_valid
            FROM hiring_ai_assessments WHERE attempt_id = %s
            ORDER BY created_at DESC LIMIT 1
        """, (attempt_id,))
        assessment_row = cur.fetchone()

        # Targeted message sent
        cur.execute("""
            SELECT id, owner_approved, sent_at
            FROM hiring_targeted_messages WHERE attempt_id = %s
            ORDER BY created_at DESC LIMIT 1
        """, (attempt_id,))
        msg_row = cur.fetchone()

        # Correction response
        cur.execute("""
            SELECT classification_primary, recommendation_update
            FROM hiring_correction_responses WHERE attempt_id = %s
            ORDER BY created_at DESC LIMIT 1
        """, (attempt_id,))
        corr_row = cur.fetchone()

        # Owner approval stored on attempt
        cur.execute("""
            SELECT quiz_owner_notified_outcome, attempt_status
            FROM hiring_quiz_attempts WHERE id = %s
        """, (attempt_id,))
        attempt_row = cur.fetchone()

    finally:
        cur.close(); conn.close()

    gates = {
        "assessment_exists":    bool(assessment_row and assessment_row[2]),
        "message_approved":     bool(msg_row and msg_row[1]),
        "message_sent":         bool(msg_row and msg_row[2]),
        "correction_accepted":  bool(corr_row and corr_row[0] in (
                                    "correction_understood",
                                    "correction_understood_with_qualifier")),
        "owner_approved":       bool(attempt_row and attempt_row[0] == "owner_approved_trial"),
        "recommendation":       assessment_row[1] if assessment_row else None,
    }
    gates["all_gates_open"] = all([
        gates["assessment_exists"],
        gates["message_approved"],
        gates["correction_accepted"],
        gates["owner_approved"],
    ])
    return gates


async def request_owner_approval(
    bot,
    attempt_id: int,
    assessment_id: int,
    candidate_name: str,
    suggested_offer: dict,
    correction_classification: str,
    open_check_answer: str | None,
) -> None:
    """
    Ask owner to explicitly approve trial + offer before anything is sent.
    Stores context in DB for when owner taps the button.
    """
    import html
    h = suggested_offer.get("hours_per_day", 9)
    base = suggested_offer.get("recommended_base_salary", 0)
    bonus = suggested_offer.get("bonus", 0)
    food = suggested_offer.get("food_allowance_daily_riel", 0)

    open_check_str = ""
    if open_check_answer:
        open_check_str = f'\nOpen check: "<i>{html.escape(open_check_answer[:200])}</i>"'
        open_check_str += f"\nClassification: {html.escape(correction_classification)}"

    lines = [
        f"<b>Trial approval required — {html.escape(candidate_name)}</b>",
        f"Attempt #{attempt_id}",
        open_check_str,
        "",
        f"Suggested offer: {h}h/day | ${base} base + ${bonus} bonus + {food:,} riel food/day",
        f"Range: ${suggested_offer.get('acceptable_range', [base, base])[0]}"
        f"–${suggested_offer.get('acceptable_range', [base, base])[1]}",
        "",
        "Please approve or reject:",
    ]
    try:
        await bot.send_message(
            config.OWNER_TELEGRAM_ID,
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=OWNER_APPROVE_KB,
        )
        # Store pending approval
        conn = _db(); cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE hiring_quiz_attempts
                SET quiz_owner_notified_outcome = 'pending_approval'
                WHERE id = %s
            """, (attempt_id,))
            conn.commit()
        finally:
            cur.close(); conn.close()
    except Exception as e:
        logger.error("request_owner_approval failed: %s", e)


async def send_offer_to_applicant(
    bot,
    chat_id: int,
    suggested_offer: dict,
    start_date: date | None,
    candidate_id: int,
    intake_id: int | None,
    attempt_id: int,
    assessment_id: int | None,
    reason: str,
) -> int:
    """
    Send the offer message and create hiring_offers row.
    Called only after all gates are confirmed open.
    Returns offer_id.
    """
    h     = suggested_offer.get("hours_per_day", 9)
    base  = suggested_offer.get("recommended_base_salary", 0)
    bonus = suggested_offer.get("bonus", 0)
    food  = suggested_offer.get("food_allowance_daily_riel", 0)
    start_str = start_date.strftime("%A %d %B") if start_date else "[to be confirmed]"
    food_usd = food / INTERNAL_RIEL_TO_USD

    message = (
        f"Here is our offer:\n\n"
        f"{h}-hour shift\n"
        f"${base} base salary + ${bonus} bonus + food allowance ({food:,} riel/day ≈ ${food_usd:.2f})\n"
        f"Start date: {start_str}\n\n"
        f"Is this okay with you?\n\n"
        f"───\n\n"
        f"នេះជាការផ្ដល់ជូនរបស់យើង:\n\n"
        f"ម៉ោង {h} ក្នុងមួយថ្ងៃ\n"
        f"ប្រាក់ខែ ${base} + ប្រាក់រង្វាន់ ${bonus} + "
        f"ប្រាក់អាហារ {food:,} រៀល/ថ្ងៃ\n"
        f"ថ្ងៃចាប់ផ្ដើម: {start_str}\n\n"
        f"ប្អូនយល់ព្រមទេ?"
    )

    accept_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes, I accept / ខ្ញុំយល់ព្រម", callback_data="offer:accept")],
        [InlineKeyboardButton("I have a question / ខ្ញុំមានសំណួរ", callback_data="offer:question")],
    ])

    await bot.send_message(chat_id, message, reply_markup=accept_kb)

    # Record offer
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO hiring_offers
                (candidate_id, intake_id, attempt_id, assessment_id,
                 base_salary, bonus, food_allowance_daily_riel,
                 hours_per_day, total_monthly_display,
                 start_date, offer_status, reason_for_offer,
                 created_by, proposed_at)
            VALUES (%s,%s,%s,%s, %s,%s,%s, %s,%s, %s,'proposed',%s,'system',now())
            RETURNING id
        """, (
            candidate_id, intake_id, attempt_id, assessment_id,
            base, bonus, food,
            h, base + bonus,
            start_date,
            reason,
        ))
        offer_id = cur.fetchone()[0]
        conn.commit()
        return offer_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close(); conn.close()


async def mark_offer_accepted(offer_id: int, attempt_id: int) -> None:
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE hiring_offers
            SET offer_status = 'accepted', accepted_at = now()
            WHERE id = %s
        """, (offer_id,))
        cur.execute("""
            UPDATE hiring_quiz_attempts
            SET attempt_status = 'offer_accepted'
            WHERE id = %s
        """, (attempt_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close(); conn.close()
