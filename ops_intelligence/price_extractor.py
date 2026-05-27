"""
Reads supplier price list files (PDFs and photos) from pricelists/ and extracts
product prices into the supplier_price_items DB table using Claude Haiku vision.

PDF strategy:
  - PDFs with a text layer (proper formatted catalogs) → sent as PDF in one API call
  - PDFs with images only (scanned sheets, photos-as-PDF) → rendered page-by-page via PyMuPDF
  - Oversized text-layer PDFs → fall back to page-by-page images
  - No size limit issues: image-only PDFs are always split regardless of size

Re-runnable — already-processed files are skipped.
"""
import asyncio
import logging
import os
import re
import sys
sys.path.insert(0, '/root/TWBshop')

import fitz  # PyMuPDF

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
MAX_PDF_MB = 25       # above this, even text-layer PDFs fall back to page images
PAGE_DPI = 120        # render DPI for image-only PDFs — readable text, moderate token cost
PAGE_JPEG_QUALITY = 75
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
SUPPORTED_DOC_EXTS = {".pdf"}
API_DELAY = 0.4


def _date_from_filename(fname: str) -> str | None:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
    return m.group(1) if m else None


def _normalize_date(date_str: str | None) -> str | None:
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


def _pdf_has_text_layer(file_path: str) -> bool:
    """Return True if any page has embedded text (not a scanned/image-only PDF)."""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            if page.get_text().strip():
                doc.close()
                return True
        doc.close()
    except Exception:
        pass
    return False


def _pdf_to_page_images(file_path: str) -> list[bytes]:
    """Render each PDF page to a JPEG via PyMuPDF. Returns list of image bytes."""
    try:
        doc = fitz.open(file_path)
        mat = fitz.Matrix(PAGE_DPI / 72, PAGE_DPI / 72)
        images = []
        for page in doc:
            pix = page.get_pixmap(matrix=mat)
            images.append(pix.tobytes("jpeg", jpg_quality=PAGE_JPEG_QUALITY))
        doc.close()
        return images
    except Exception as exc:
        logger.error("  PyMuPDF render failed for %s: %s", os.path.basename(file_path), exc)
        return []


async def _process_pdf_as_pages(supplier: str, file_path: str, price_date: str | None) -> int:
    fname = os.path.basename(file_path)
    pages = _pdf_to_page_images(file_path)
    if not pages:
        logger.info("  SKIP render failed: %s", fname)
        mark_supplier_file_processed(file_path, 0, "error")
        return 0

    logger.info("  Extracting %d pages: %s", len(pages), fname)
    all_items = []
    result_date = None
    for page_data in pages:
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
            has_text = _pdf_has_text_layer(file_path)

            if has_text and size_mb <= MAX_PDF_MB:
                # Text layer + small enough: send as PDF for best accuracy in one call
                logger.info("  PDF (text layer, %.1fMB): %s", size_mb, fname)
                with open(file_path, "rb") as f:
                    data = f.read()
                result = await extract_price_list_pdf(data)

            else:
                # Image-only or oversized: render pages and extract each as image
                reason = "image-only" if not has_text else f"oversized {size_mb:.1f}MB"
                logger.info("  PDF (%s) → page images: %s", reason, fname)
                return await _process_pdf_as_pages(supplier, file_path, price_date)

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
