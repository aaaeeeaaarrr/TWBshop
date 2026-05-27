"""
Reads supplier price list files (PDFs and photos) from pricelists/ and extracts
product prices into the supplier_price_items DB table using Claude Haiku vision.

Re-runnable — already-processed files are skipped.
"""
import asyncio
import logging
import os
import re
import subprocess
import sys
import tempfile
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


def _compress_pdf(file_path: str) -> bytes | None:
    """Compress PDF via Ghostscript /screen preset (72 DPI). Returns bytes or None on failure."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        result = subprocess.run(
            [
                "gs", "-dNOPAUSE", "-dBATCH", "-dSAFER",
                "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/screen",
                f"-sOutputFile={tmp_path}", file_path,
            ],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            return None
        with open(tmp_path, "rb") as f:
            return f.read()
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _pdf_to_page_images(file_path: str, dpi: int = 100) -> list[bytes]:
    """Convert each PDF page to a JPEG using pdftoppm. Returns list of image bytes."""
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        result = subprocess.run(
            ["pdftoppm", "-jpeg", "-r", str(dpi), file_path, os.path.join(tmp_dir, "page")],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            return []
        pages = sorted(
            os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir) if f.endswith(".jpg")
        )
        images = []
        for p in pages:
            with open(p, "rb") as f:
                images.append(f.read())
        return images
    except Exception:
        return []
    finally:
        if tmp_dir:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _normalize_date(date_str: str | None) -> str | None:
    """Normalize partial dates to YYYY-MM-DD. Returns None if unparseable."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    if re.match(r"^\d{4}-\d{2}$", date_str):
        return date_str + "-01"
    if re.match(r"^\d{4}$", date_str):
        return date_str + "-01-01"
    return None


async def _process_file(supplier: str, file_path: str) -> int:
    fname = os.path.basename(file_path)
    ext = os.path.splitext(fname)[1].lower()
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    price_date = _date_from_filename(fname)

    try:
        if ext in SUPPORTED_IMAGE_EXTS:
            with open(file_path, "rb") as f:
                data = f.read()
            result = await extract_price_list_image(data)
        elif ext in SUPPORTED_DOC_EXTS:
            if size_mb > MAX_FILE_MB:
                logger.info("  Compressing (%.1fMB): %s", size_mb, fname)
                compressed = _compress_pdf(file_path)
                compressed_mb = len(compressed) / (1024 * 1024) if compressed else 0
                if compressed and compressed_mb < size_mb and compressed_mb <= MAX_FILE_MB:
                    logger.info("  Compressed %.1fMB → %.1fMB: %s", size_mb, compressed_mb, fname)
                    data = compressed
                    result = await extract_price_list_pdf(data)
                else:
                    # Compression didn't help — convert each page to JPEG and merge results
                    logger.info("  Compress unhelpful (%.1fMB) — splitting into pages: %s", compressed_mb or size_mb, fname)
                    pages = _pdf_to_page_images(file_path)
                    if not pages:
                        logger.info("  SKIP page conversion failed: %s", fname)
                        mark_supplier_file_processed(file_path, 0, "too_large")
                        return 0
                    logger.info("  Processing %d pages: %s", len(pages), fname)
                    all_items = []
                    result_date = None
                    for i, page_data in enumerate(pages):
                        page_result = await extract_price_list_image(page_data)
                        await asyncio.sleep(API_DELAY)
                        if not page_result.get("error"):
                            all_items.extend(page_result.get("items", []))
                            if not result_date:
                                result_date = page_result.get("valid_date")
                    valid_date = _normalize_date(result_date) or _normalize_date(price_date)
                    saved = save_supplier_price_items(supplier, all_items, file_path, valid_date)
                    mark_supplier_file_processed(file_path, saved)
                    logger.info("  %s — %d items across %d pages (date: %s)", fname, saved, len(pages), valid_date or "unknown")
                    return saved
            else:
                with open(file_path, "rb") as f:
                    data = f.read()
                result = await extract_price_list_pdf(data)
        else:
            mark_supplier_file_processed(file_path, 0, "unsupported")
            return 0

        if result.get("error"):
            logger.warning("  AI error %s: %s", fname, result["error"][:120])
            mark_supplier_file_processed(file_path, 0, "ai_error")
            return 0

        items = result.get("items", [])
        valid_date = _normalize_date(result.get("valid_date")) or _normalize_date(price_date)
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
