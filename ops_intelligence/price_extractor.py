"""
Reads supplier price list files (PDFs and photos) from pricelists/ and extracts
product prices into the supplier_price_items DB table using Claude Haiku vision.

Re-runnable — already-processed files are skipped.
"""
import asyncio
import logging
import os
import re
import sys
sys.path.insert(0, '/root/TWBshop')

import config
from shared.database import (
    init_supplier_prices_db,
    is_supplier_file_processed,
    save_supplier_price_items,
    mark_supplier_file_processed,
)
from shared.ai_client import extract_price_list_image, extract_price_list_pdf

logger = logging.getLogger(__name__)

PRICELISTS_DIR = "/root/TWBshop/pricelists"
MAX_FILE_MB = 25
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
SUPPORTED_DOC_EXTS = {".pdf"}
API_DELAY = 0.4  # seconds between API calls


def _date_from_filename(fname: str) -> str | None:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
    return m.group(1) if m else None


async def _process_file(supplier: str, file_path: str) -> int:
    fname = os.path.basename(file_path)
    ext = os.path.splitext(fname)[1].lower()
    size_mb = os.path.getsize(file_path) / (1024 * 1024)

    if size_mb > MAX_FILE_MB:
        logger.info("  SKIP too large (%.1fMB): %s", size_mb, fname)
        mark_supplier_file_processed(file_path, 0, "too_large")
        return 0

    price_date = _date_from_filename(fname)

    try:
        with open(file_path, "rb") as f:
            data = f.read()

        if ext in SUPPORTED_IMAGE_EXTS:
            result = await extract_price_list_image(data)
        elif ext in SUPPORTED_DOC_EXTS:
            result = await extract_price_list_pdf(data)
        else:
            mark_supplier_file_processed(file_path, 0, "unsupported")
            return 0

        if result.get("error"):
            logger.warning("  AI error %s: %s", fname, result["error"][:120])
            mark_supplier_file_processed(file_path, 0, "ai_error")
            return 0

        items = result.get("items", [])
        valid_date = result.get("valid_date") or price_date
        saved = save_supplier_price_items(supplier, items, file_path, valid_date)
        mark_supplier_file_processed(file_path, saved)
        logger.info("  %s — %d items (date: %s)", fname, saved, valid_date or "unknown")
        return saved

    except Exception as exc:
        logger.error("  FAILED %s: %s", fname, exc)
        mark_supplier_file_processed(file_path, 0, "error")
        return 0


async def run() -> None:
    init_supplier_prices_db()

    if not config.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set — cannot extract prices")
        return

    total_files = total_items = skipped = errors = 0

    for supplier_dir in sorted(os.listdir(PRICELISTS_DIR)):
        dir_path = os.path.join(PRICELISTS_DIR, supplier_dir)
        if not os.path.isdir(dir_path):
            continue

        all_exts = SUPPORTED_IMAGE_EXTS | SUPPORTED_DOC_EXTS
        files = sorted(
            f for f in os.listdir(dir_path)
            if os.path.splitext(f)[1].lower() in all_exts
        )
        if not files:
            continue

        new_files = [f for f in files if not is_supplier_file_processed(os.path.join(dir_path, f))]
        if not new_files:
            logger.info("Supplier: %s — all %d files already processed", supplier_dir, len(files))
            skipped += len(files)
            continue

        logger.info("Supplier: %s — %d new files", supplier_dir, len(new_files))
        for fname in new_files:
            fpath = os.path.join(dir_path, fname)
            n = await _process_file(supplier_dir, fpath)
            total_items += n
            total_files += 1
            if n == 0:
                errors += 1
            await asyncio.sleep(API_DELAY)

    logger.info(
        "Complete — %d files processed, %d items extracted, %d skipped, %d errors/empty",
        total_files, total_items, skipped, errors,
    )
