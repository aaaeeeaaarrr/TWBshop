"""Photo receiving, storage, and analyze_photo() stub."""

import os
import logging
from datetime import datetime
from telegram import Update

import config

logger = logging.getLogger(__name__)


def analyze_photo(image_bytes: bytes, photo_type: str) -> dict:
    # Placeholder: will connect to Claude API later
    # photo_type: "workstation" | "fridge" | "stock_sheet"
    return {"status": "pending", "notes": "manual review required"}


def _save_photo(image_bytes: bytes, user_id: int, photo_type: str) -> str:
    os.makedirs(config.PHOTO_STORAGE_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{photo_type}_{user_id}_{timestamp}.jpg"
    path = os.path.join(config.PHOTO_STORAGE_DIR, filename)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path


async def handle_photo(update: Update, context, photo_type: str = "general") -> None:
    photo = update.message.photo[-1]  # largest available size
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    path = _save_photo(bytes(image_bytes), update.effective_user.id, photo_type)
    result = analyze_photo(bytes(image_bytes), photo_type)

    logger.info("Photo saved: %s | analysis: %s", path, result)
    await update.message.reply_text(
        f"Photo received ({photo_type}). It has been stored for review."
    )
