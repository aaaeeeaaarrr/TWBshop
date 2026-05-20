"""Photo receiving, storage, and AI analysis."""

import os
import logging
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
from shared.database import save_photo_submission

logger = logging.getLogger(__name__)

# file_id awaiting type confirmation: {user_id: file_id}
_pending_photos: dict[int, str] = {}

_TYPE_LABELS = {
    "workstation": "Workstation cleaning",
    "fridge": "Fridge display",
    "stock_sheet": "Stock sheet",
}


async def analyze_photo(image_bytes: bytes, photo_type: str) -> dict:
    if not getattr(config, "ANTHROPIC_API_KEY", None):
        return {"status": "pending", "notes": "manual review required (API key not configured)"}

    from shared.ai_client import analyze_stock_sheet, analyze_compliance_photo

    if photo_type == "stock_sheet":
        return await analyze_stock_sheet(image_bytes)
    return await analyze_compliance_photo(image_bytes, photo_type)


def _save_photo_file(image_bytes: bytes, user_id: int, photo_type: str) -> str:
    os.makedirs(config.PHOTO_STORAGE_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{photo_type}_{user_id}_{timestamp}.jpg"
    path = os.path.join(config.PHOTO_STORAGE_DIR, filename)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path


async def _notify_staff(bot, photo_type: str, staff_name: str, result: dict) -> None:
    """Send actionable AI results to the staff group."""
    today = date.today().isoformat()

    if photo_type == "stock_sheet":
        items = result.get("items")
        if items:
            lines = [f"Stock sheet from {staff_name} ({today}):"]
            for item in items:
                unit = item.get("unit", "")
                lines.append(f"  • {item['name']}: {item['quantity']}{' ' + unit if unit else ''}")
            if result.get("notes"):
                lines.append(f"\nNotes: {result['notes']}")
        else:
            notes = result.get("notes", "manual review required")
            lines = [f"Stock sheet from {staff_name} ({today}) — {notes}"]
        await bot.send_message(config.STAFF_GROUP_ID, "\n".join(lines))

    elif photo_type in ("workstation", "fridge"):
        if result.get("passed") is False:
            label = _TYPE_LABELS[photo_type]
            issues = result.get("issues", [])
            lines = [f"{label} issues — {staff_name}:"]
            lines.extend(f"  • {issue}" for issue in issues)
            if result.get("notes"):
                lines.append(f"Notes: {result['notes']}")
            await bot.send_message(config.STAFF_GROUP_ID, "\n".join(lines))
        # passed=True or passed=None → no staff group alert needed


async def handle_incoming_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive a photo; ask staff to label it, reject non-staff."""
    user_id = update.effective_user.id

    if config.STAFF_USER_IDS and user_id not in config.STAFF_USER_IDS:
        await update.message.reply_text(
            "Thanks, but I can only accept photos from staff members."
        )
        return

    file_id = update.message.photo[-1].file_id
    _pending_photos[user_id] = file_id

    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"photo:{key}")]
        for key, label in _TYPE_LABELS.items()
    ]
    await update.message.reply_text(
        "Photo received. What type of photo is this?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_photo_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the type button pressed after a staff photo is submitted."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    photo_type = query.data.split(":", 1)[1]

    file_id = _pending_photos.pop(user_id, None)
    if not file_id:
        await query.edit_message_text("No pending photo found. Please send the photo again.")
        return

    # Download, save to disk, record in DB
    file = await context.bot.get_file(file_id)
    image_bytes = bytes(await file.download_as_bytearray())
    file_path = _save_photo_file(image_bytes, user_id, photo_type)

    staff_name = config.STAFF_NAMES.get(user_id, str(user_id))
    save_photo_submission(user_id, staff_name, photo_type, file_path)

    label = _TYPE_LABELS.get(photo_type, photo_type)
    await query.edit_message_text(f"{label} photo saved. Analysing...")

    # Analyse and notify staff group with results
    result = await analyze_photo(image_bytes, photo_type)
    logger.info("Photo analysis result for %s: %s", file_path, result)

    await _notify_staff(context.bot, photo_type, staff_name, result)

    # Update the submitter's message to confirm completion
    passed = result.get("passed")
    if passed is True:
        status = "passed"
    elif passed is False:
        status = "issues found — staff group notified"
    else:
        status = "saved"
    await query.edit_message_text(f"{label} photo {status}. Thank you!")
