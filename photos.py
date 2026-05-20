"""Photo receiving, storage, and analyze_photo() stub."""

import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
from database import save_photo_submission

logger = logging.getLogger(__name__)

# file_id awaiting type confirmation: {user_id: file_id}
_pending_photos: dict[int, str] = {}

_TYPE_LABELS = {
    "workstation": "Workstation cleaning",
    "fridge": "Fridge display",
}


def analyze_photo(image_bytes: bytes, photo_type: str) -> dict:
    # Placeholder: will connect to Claude API later
    # photo_type: "workstation" | "fridge" | "stock_sheet"
    return {"status": "pending", "notes": "manual review required"}


def _save_photo_file(image_bytes: bytes, user_id: int, photo_type: str) -> str:
    os.makedirs(config.PHOTO_STORAGE_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{photo_type}_{user_id}_{timestamp}.jpg"
    path = os.path.join(config.PHOTO_STORAGE_DIR, filename)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path


async def handle_incoming_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive a photo from any user; ask staff to label it, ignore non-staff."""
    user_id = update.effective_user.id

    if config.STAFF_USER_IDS and user_id not in config.STAFF_USER_IDS:
        await update.message.reply_text(
            "Thanks, but I can only accept photos from staff members."
        )
        return

    # Store the largest available file_id until the staff picks the type
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
    photo_type = query.data.split(":", 1)[1]  # "photo:workstation" → "workstation"

    file_id = _pending_photos.pop(user_id, None)
    if not file_id:
        await query.edit_message_text("No pending photo found. Please send the photo again.")
        return

    # Download and save
    file = await context.bot.get_file(file_id)
    image_bytes = bytes(await file.download_as_bytearray())
    file_path = _save_photo_file(image_bytes, user_id, photo_type)

    # Record in DB
    staff_name = config.STAFF_NAMES.get(user_id, str(user_id))
    save_photo_submission(user_id, staff_name, photo_type, file_path)

    # Run stub analysis
    result = analyze_photo(image_bytes, photo_type)
    logger.info("Photo saved: %s | analysis: %s", file_path, result)

    label = _TYPE_LABELS.get(photo_type, photo_type)
    await query.edit_message_text(f"{label} photo saved. Thank you!")
