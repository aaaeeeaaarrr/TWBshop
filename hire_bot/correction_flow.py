"""
Correction acceptance flow:
- Sends targeted message to applicant (English first, Khmer if validated)
- Shows [I agree] / [I have a question] buttons
- If critical_hold: asks open understanding check after agreement
- Opus classifies the open-check answer
- Records correction_responses row
- Notifies owner of outcome
"""

import json
import logging
import psycopg2
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)

# Buttons stacked — English button / Khmer button
AGREE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("I agree",          callback_data="correction:agree")],
    [InlineKeyboardButton("ខ្ញុំយល់ព្រម",       callback_data="correction:agree_km")],
    [InlineKeyboardButton("I have a question", callback_data="correction:question")],
    [InlineKeyboardButton("ខ្ញុំមានសំណួរ",       callback_data="correction:question_km")],
])

# Open understanding check (fires when critical_hold = True)
OPEN_CHECK_EN = (
    "Before we continue, please write one sentence: "
    "if you make a mistake and nobody sees it, what do you do first?"
)
OPEN_CHECK_KH = (
    "មុនពេលយើងបន្ត សូមសរសេរមួយប្រយោគ៖ "
    "បើប្អូនធ្វើខុស ហើយគ្មាននរណាឃើញ "
    "ប្អូននឹងធ្វើអ្វីជាដំបូង?"
)

# Resistance response (English + Khmer, no argument)
RESIST_EN = (
    "We understand you have solved the problem. "
    "But our standard is clear: mistakes must be reported, even when they are fixed. "
    "If you are not comfortable with that, this role may not be the right fit right now."
)
RESIST_KH = (
    "យើងយល់ថា ប្អូនបានដោះស្រាយបញ្ហា។ "
    "ប៉ុន្តែស្តង់ដាររបស់យើងច្បាស់៖ "
    "កំហុសត្រូវតែរាយការណ៍ ទោះបីបានដោះស្រាយរួចហើយក៏ដោយ។ "
    "បើប្អូនមិនស្រួលចិត្តជាមួយចំណុចនេះទេ "
    "ប្រហែលតំណែងនេះមិនទាន់ស័ក្តិសមសម្រាប់ប្អូននៅពេលនេះ។"
)

# Classification prompts (used in Opus second call)
_CLASSIFICATION_SYSTEM = """\
Classify a job applicant's response to a workplace standard correction.
Return ONLY valid JSON, no markdown.

Available primary classifications:
- correction_understood: names the correct action AND explains why
- correction_parroted: repeats correct words but no reasoning
- conditional_reporting: introduces a threshold (small/big, important/minor) not in our standard
- correction_understanding_failed: fundamentally misreads the standard
- hiding_standard_not_accepted: defends original hiding behavior
- correction_unclear: ambiguous, off-topic, or too vague
- correction_deflected: blames the test, the question, or external context
- correction_understood_with_qualifier: correct action + reasonable real-world nuance

Output schema:
{
  "primary": "...",
  "secondary": ["...", "..."],
  "reasoning": "one sentence",
  "severity": "low|medium|high",
  "recommendation_update": "proceed_to_verbal_retest|reject_unless_owner_override|one_more_probe|proceed_with_note"
}
"""


def _db():
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)


def _get_targeted_message_id_for_attempt(attempt_id: int) -> int | None:
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id FROM hiring_targeted_messages
            WHERE attempt_id = %s ORDER BY created_at DESC LIMIT 1
        """, (attempt_id,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close(); conn.close()


def _get_critical_hold_for_attempt(attempt_id: int) -> bool:
    """critical_hold = True when the assessment found at least one critical signal."""
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT critical_signal_count FROM hiring_ai_assessments
            WHERE attempt_id = %s AND output_valid = TRUE
            ORDER BY created_at DESC LIMIT 1
        """, (attempt_id,))
        row = cur.fetchone()
        return bool(row and row[0] and row[0] > 0)
    finally:
        cur.close(); conn.close()


async def send_targeted_message(
    bot,
    chat_id: int,
    targeted_message_id: int,
    critical_hold: bool = False,
) -> None:
    """
    Send targeted message to applicant.
    Uses validated Khmer if available; English-only otherwise.
    Auto-send is ALWAYS blocked for Khmer — checked by khmer_validated column.
    """
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT english_text, khmer_text, khmer_validated, points_json
            FROM hiring_targeted_messages WHERE id = %s
        """, (targeted_message_id,))
        row = cur.fetchone()
    finally:
        cur.close(); conn.close()

    if not row:
        logger.error("targeted_message %s not found", targeted_message_id)
        return

    english_text, khmer_text, khmer_validated, points_json = row

    # Build message: English text always; Khmer only if validated
    message_parts = [english_text]
    if khmer_validated and khmer_text:
        message_parts.append("\n──\n\n" + khmer_text)
    else:
        message_parts.append("\n\n<i>(Khmer translation pending manual approval)</i>")

    # Parse points for the agreement footer
    points = json.loads(points_json) if points_json else []
    n = len(points)
    if n > 1:
        agree_en = f"If you agree with all {n} points and are ready to follow them, you are welcome to join us."
        agree_kh = f"បើប្អូនយល់ព្រមចំពោះចំណុចទាំង{n} ហើយត្រៀមខ្លួនធ្វើតាម យើងស្វាគមន៍ឲ្យប្អូនចូលរួមជាមួយយើង។"
    else:
        agree_en = "If you agree with this and are ready to follow it, you are welcome to join us."
        agree_kh = "បើប្អូនយល់ព្រម ហើយត្រៀមខ្លួនធ្វើតាម យើងស្វាគមន៍ឲ្យប្អូនចូលរួមជាមួយយើង។"

    message_parts.append(f"\n\n{agree_en}\n{agree_kh}")

    await bot.send_message(
        chat_id,
        "".join(message_parts),
        parse_mode=ParseMode.HTML,
        reply_markup=AGREE_KEYBOARD,
    )

    logger.info("targeted_message %s sent to chat %s", targeted_message_id, chat_id)


async def handle_correction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle [I agree] / [I have a question] button taps from targeted message."""
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id

    attempt_id          = context.user_data.get("attempt_id")
    targeted_message_id = context.user_data.get("correction_message_id")
    is_critical_hold    = context.user_data.get("correction_critical_hold", False)

    # DB fallback — survive bot restarts
    if attempt_id and not targeted_message_id:
        targeted_message_id = _get_targeted_message_id_for_attempt(attempt_id)
        context.user_data["correction_message_id"] = targeted_message_id
    if attempt_id and not is_critical_hold:
        is_critical_hold = _get_critical_hold_for_attempt(attempt_id)
        context.user_data["correction_critical_hold"] = is_critical_hold

    if data in ("correction:agree", "correction:agree_km"):
        if is_critical_hold:
            # Ask the open understanding check before proceeding
            context.user_data["awaiting_open_check"] = True
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(
                chat_id,
                f"{OPEN_CHECK_EN}\n\n{OPEN_CHECK_KH}",
            )
        else:
            # Low-risk: record agreement, notify owner, proceed
            _store_correction_response(
                attempt_id=attempt_id,
                targeted_message_id=targeted_message_id,
                button_tapped="agree",
                open_check_answer=None,
                classification_primary="correction_understood",
                classification_reasoning="Button agreement only (no critical hold)",
                severity="low",
                recommendation_update="proceed_to_verbal_retest",
            )
            await query.edit_message_reply_markup(reply_markup=None)
            await _notify_owner_correction(
                context.bot, attempt_id, "agree_button",
                None, "correction_understood", "low", "proceed_to_verbal_retest"
            )

    elif data in ("correction:question", "correction:question_km"):
        context.user_data["awaiting_correction_question"] = True
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id,
            "Please send your question. We will answer once, then ask for your decision.\n\n"
            "សូមផ្ញើសំណួររបស់ប្អូន។ យើងនឹងឆ្លើយម្ដង បន្ទាប់មកសូមធ្វើការសម្រេចចិត្ត។"
        )


async def handle_open_check_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    targeted_message_id: int,
    attempt_id: int,
) -> dict:
    """
    Process the open understanding check answer. Opus classifies it.
    Returns the classification dict so the caller can trigger offer approval on Path A.
    """
    answer_text = (update.message.text or "").strip()
    if not answer_text:
        return {}

    context.user_data["awaiting_open_check"] = False

    classification = await _classify_correction_response(answer_text)

    primary = classification.get("primary", "correction_unclear")
    severity = classification.get("severity", "medium")
    rec_update = classification.get("recommendation_update", "reject_unless_owner_override")
    reasoning = classification.get("reasoning", "")

    _store_correction_response(
        attempt_id=attempt_id,
        targeted_message_id=targeted_message_id,
        button_tapped="agree_then_open_check",
        open_check_answer=answer_text,
        classification_primary=primary,
        classification_reasoning=reasoning,
        severity=severity,
        recommendation_update=rec_update,
        secondary=classification.get("secondary", []),
    )

    await _notify_owner_correction(
        context.bot, attempt_id, answer_text,
        reasoning, primary, severity, rec_update
    )

    if primary in ("correction_understood", "correction_understood_with_qualifier"):
        await context.bot.send_message(
            update.effective_chat.id,
            "Thank you. We will be in touch.\n\n"
            "អរគុណ។ យើងនឹងទំនាក់ទំនងប្អូនក្នុងពេលឆាប់ៗ។"
        )
    elif primary == "one_more_probe":
        await context.bot.send_message(
            update.effective_chat.id,
            "Can you explain why you would do that?\n\n"
            "តើប្អូនអាចពន្យល់ ហេតុអ្វី?"
        )
    else:
        # Resistance / failed — standard response, no argument
        await context.bot.send_message(
            update.effective_chat.id,
            f"{RESIST_EN}\n\n{RESIST_KH}"
        )

    return classification


async def _classify_correction_response(answer_text: str) -> dict:
    """Second Opus call: classify the applicant's open-check answer."""
    try:
        from shared.ai_client import _get_client
        from hire_bot.assessment_runner import ASSESSMENT_MODEL

        client = _get_client()
        resp = await client.messages.create(
            model=ASSESSMENT_MODEL,
            max_tokens=256,
            system=_CLASSIFICATION_SYSTEM,
            messages=[{"role": "user", "content": f"Applicant's answer: {answer_text}"}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(l for l in raw.split("\n") if not l.strip().startswith("```"))
        return json.loads(raw)
    except Exception as e:
        logger.error("_classify_correction_response failed: %s", e)
        return {
            "primary": "correction_unclear",
            "secondary": [],
            "reasoning": f"Classification error: {e}",
            "severity": "medium",
            "recommendation_update": "reject_unless_owner_override",
        }


def _store_correction_response(
    attempt_id: int | None,
    targeted_message_id: int | None,
    button_tapped: str | None,
    open_check_answer: str | None,
    classification_primary: str,
    classification_reasoning: str,
    severity: str,
    recommendation_update: str,
    secondary: list | None = None,
) -> None:
    conn = _db(); cur = conn.cursor()
    try:
        # Idempotency: one response per attempt
        cur.execute(
            "SELECT id FROM hiring_correction_responses WHERE attempt_id = %s LIMIT 1",
            (attempt_id,)
        )
        if cur.fetchone():
            logger.info("_store_correction_response: already stored for attempt %s — skipping", attempt_id)
            conn.close()
            return

        cur.execute("""
            INSERT INTO hiring_correction_responses
                (attempt_id, targeted_message_id, button_tapped,
                 open_check_question, open_check_answer,
                 classification_primary, classification_secondary,
                 classification_reasoning, severity, recommendation_update,
                 classified_by, created_at)
            VALUES (%s,%s,%s, %s,%s, %s,%s, %s,%s,%s, 'opus', now())
        """, (
            attempt_id, targeted_message_id, button_tapped,
            OPEN_CHECK_EN, open_check_answer,
            classification_primary,
            secondary or [],
            classification_reasoning,
            severity,
            recommendation_update,
        ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close(); conn.close()


async def _notify_owner_correction(
    bot, attempt_id, answer_or_button, reasoning,
    primary, severity, recommendation_update,
) -> None:
    import html as _html
    icon = "✅" if "proceed" in recommendation_update else "⚠️"
    lines = [
        f"{icon} <b>Correction response received</b>",
        f"Attempt #{attempt_id}",
        f"Classification: <b>{_html.escape(primary)}</b> (severity: {severity})",
        f"Response: <i>{_html.escape(str(answer_or_button)[:300])}</i>",
        f"Reasoning: {_html.escape(reasoning or '')}",
        f"Recommendation update: {_html.escape(recommendation_update)}",
    ]
    if "reject" in recommendation_update:
        lines.append("\n<b>No offer should be sent. Override required to proceed.</b>")
    try:
        await bot.send_message(
            config.OWNER_TELEGRAM_ID,
            "\n".join(lines),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("_notify_owner_correction failed: %s", e)
