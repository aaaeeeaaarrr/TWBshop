"""Anthropic API client — Claude vision and text analysis for the bakery bot."""

import base64
import json
import logging
import re
from anthropic import AsyncAnthropic

import config

logger = logging.getLogger(__name__)

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _encode(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode()


def _parse_json(text: str) -> dict:
    """Extract JSON from Claude's response, handling optional markdown fences."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        logger.warning("Could not parse AI response as JSON: %.200s", text)
        return {}


# ---------------------------------------------------------------------------
# System prompts — cached on the first call (ephemeral cache, 5-min TTL)
# ---------------------------------------------------------------------------

_STOCK_SHEET_SYSTEM = (
    "You are a bakery inventory assistant. Extract all items and quantities "
    "from stock sheet photos. Return only valid JSON:\n"
    '{"items": [{"name": "...", "quantity": number, "unit": "pieces/kg/loaves/etc"}], '
    '"date": "YYYY-MM-DD or null", "notes": "observations or null"}\n'
    "If text is unclear, include what you can read and note what is illegible."
)

_COMPLIANCE_SYSTEM = (
    "You are a bakery quality inspector reviewing staff photo submissions. "
    "Return only valid JSON:\n"
    '{"passed": true/false, "issues": ["issue 1", ...], "notes": "brief assessment"}\n'
    "Be practical — minor imperfections are fine; flag genuine hygiene or display problems."
)

_PAYMENT_SYSTEM = (
    "You are a payment verification assistant. Read a bank transfer or payment screenshot "
    "and extract the total amount transferred. Return only valid JSON:\n"
    '{"amount": number_or_null, "currency": "string_or_null", "notes": "any observations or null"}\n'
    "If no clear transfer amount is visible, return amount as null. "
    "amount must be a plain number (e.g. 42.50), not a string."
)

_STAFF_MSG_SYSTEM = (
    "You monitor bakery staff communications for issues needing management attention. "
    "Flag: safety concerns, customer complaints, conflicts, significant frustration, policy violations. "
    "Do not flag: normal coordination, friendly chat, routine updates. "
    'Return only valid JSON: {"action": "none/alert/urgent", "flag": true/false, "reason": "brief reason or empty string"}'
)

_B2B_ORDER_TEXT_SYSTEM = (
    "You are a B2B bakery order parser. Extract all ordered items and quantities from the customer's message.\n"
    "The customer may use typos, shorthand, or informal language — match to the closest menu item.\n"
    "Return only valid JSON:\n"
    '{"items": [{"item": "<exact menu name from list>", "qty": <integer>}]}\n'
    "Rules:\n"
    "- Only use exact item names from the provided menu list\n"
    "- qty must be a positive integer\n"
    "- If an item cannot be matched to any menu item, omit it\n"
    'If nothing matches, return {"items": []}'
)

_B2B_IMAGE_CLASSIFY_SYSTEM = (
    "You analyze images sent to a bakery B2B ordering system. "
    "Decide if the image is: a payment receipt/bank transfer, a bakery order, or something else. "
    "Return only valid JSON with one of these shapes:\n"
    '  Payment: {"type": "payment", "amount": <number or null>, "currency": "<string or null>", "to_account": "<destination account number as shown, or null if not visible>"}\n'
    '  Order:   {"type": "order", "items": [{"item": "<product name>", "qty": <integer>}]}\n'
    '  Other:   {"type": "other"}\n'
    "For payments: extract the destination/recipient account number exactly as shown (digits only, no spaces or dashes). "
    "If the screenshot shows a partial number (e.g. ***1234), extract only the visible digits (1234). "
    "For orders: extract readable product names only — ignore item codes like PP-FOOD-BK-2503. "
    "If a row has a code column and a description column, use the description. "
    "Look for quantities in columns named Qty, Quantity, Pcs, or similar."
)


# ---------------------------------------------------------------------------
# Public analysis functions
# ---------------------------------------------------------------------------

async def analyze_stock_sheet(image_bytes: bytes) -> dict:
    try:
        resp = await _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1024,
            system=[{"type": "text", "text": _STOCK_SHEET_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _encode(image_bytes)}},
                    {"type": "text", "text": "Extract all inventory items from this stock sheet."},
                ],
            }],
        )
        return _parse_json(resp.content[0].text) or {
            "status": "pending", "notes": "Could not parse stock sheet — manual review required"
        }
    except Exception as exc:
        logger.error("Stock sheet analysis failed: %s", exc)
        return {"status": "error", "notes": "API error — manual review required"}


async def analyze_compliance_photo(image_bytes: bytes, photo_type: str) -> dict:
    subject = (
        "workstation cleanliness and organisation"
        if photo_type == "workstation"
        else "fridge display presentation and stock levels"
    )
    try:
        resp = await _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=512,
            system=[{"type": "text", "text": _COMPLIANCE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _encode(image_bytes)}},
                    {"type": "text", "text": f"Assess this photo for {subject}."},
                ],
            }],
        )
        return _parse_json(resp.content[0].text) or {
            "passed": None, "issues": [], "notes": "Could not assess — manual review required"
        }
    except Exception as exc:
        logger.error("Compliance photo analysis failed: %s", exc)
        return {"passed": None, "issues": [], "notes": "API error — manual review required"}


async def read_payment_amount(image_bytes: bytes) -> dict:
    """Read the transfer amount from a bank payment screenshot."""
    try:
        resp = await _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=256,
            system=[{"type": "text", "text": _PAYMENT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _encode(image_bytes)}},
                    {"type": "text", "text": "Extract the transfer amount from this payment screenshot."},
                ],
            }],
        )
        return _parse_json(resp.content[0].text) or {"amount": None, "currency": None, "notes": "Could not parse"}
    except Exception as exc:
        logger.error("Payment amount reading failed: %s", exc)
        return {"amount": None, "currency": None, "notes": "API error"}


async def parse_b2b_order_text(raw_text: str, menu_items: list[str]) -> list[dict]:
    """AI-first B2B order parser using Haiku. Returns [{item, qty}] with exact canonical menu names."""
    if not config.ANTHROPIC_API_KEY:
        return []
    menu_str = "\n".join(f"- {m}" for m in sorted(menu_items))
    try:
        resp = await _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=[{"type": "text", "text": _B2B_ORDER_TEXT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Menu:\n{menu_str}\n\nCustomer message: {raw_text}"}],
        )
        return _parse_json(resp.content[0].text).get("items", [])
    except Exception as exc:
        logger.error("B2B order text parsing failed: %s", exc)
        return []


async def interpret_unmatched_b2b_order(raw_text: str, menu_items: list[str]) -> list[dict]:
    """Kept for backwards compatibility. Calls parse_b2b_order_text."""
    return await parse_b2b_order_text(raw_text, menu_items)


async def classify_b2b_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Classify a B2B group image as payment, order, or other — and extract details in one call.

    Returns one of:
      {"type": "payment", "amount": float|None, "currency": str|None}
      {"type": "order",   "items": [{"item": str, "qty": int}]}
      {"type": "other"}
    """
    if not config.ANTHROPIC_API_KEY:
        return {"type": "other"}
    try:
        resp = await _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=400,
            system=_B2B_IMAGE_CLASSIFY_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": _encode(image_bytes)}},
                    {"type": "text", "text": "What is this image? Extract the relevant details."},
                ],
            }],
        )
        raw = resp.content[0].text
        logger.info("B2B image classify response: %s", raw)
        result = _parse_json(raw)
        return result if result.get("type") in ("payment", "order", "other") else {"type": "other"}
    except Exception as exc:
        logger.error("B2B image classification failed: %s", exc)
        return {"type": "other"}


async def extract_b2b_order_from_image(image_bytes: bytes, menu_items: list[str] = None, mime_type: str = "image/jpeg") -> list[dict]:
    """Extract item names and quantities from an order photo/document. Returns [{item, qty}]."""
    if not config.ANTHROPIC_API_KEY:
        return []
    try:
        resp = await _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=300,
            system=_B2B_ORDER_IMAGE_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": _encode(image_bytes)}},
                    {"type": "text", "text": "Extract all items and quantities from this document."},
                ],
            }],
        )
        raw = resp.content[0].text
        logger.info("B2B order image raw response: %s", raw)
        result = _parse_json(raw).get("items", [])
        logger.info("B2B order image parsed items: %s", result)
        return result
    except Exception as exc:
        logger.error("B2B order image extraction failed: %s", exc)
        return []


async def read_payment_amount_pdf(pdf_bytes: bytes) -> dict:
    """Read payment amount from a PDF bank document."""
    if not config.ANTHROPIC_API_KEY:
        return {"amount": None, "currency": None, "notes": "API not configured"}
    try:
        resp = await _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=256,
            system=[{"type": "text", "text": _PAYMENT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": _encode(pdf_bytes)}},
                    {"type": "text", "text": "Extract the transfer amount from this payment document."},
                ],
            }],
        )
        return _parse_json(resp.content[0].text) or {"amount": None, "currency": None, "notes": "Could not parse"}
    except Exception as exc:
        logger.error("PDF payment reading failed: %s", exc)
        return {"amount": None, "currency": None, "notes": "API error"}


async def check_staff_message_ai(text: str, prior_context: list) -> dict:
    try:
        resp = await _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=256,
            system=[{"type": "text", "text": _STAFF_MSG_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text}],
        )
        return _parse_json(resp.content[0].text) or {"action": "none", "flag": False, "reason": ""}
    except Exception as exc:
        logger.error("Staff message check failed: %s", exc)
        return {"action": "none", "flag": False, "reason": ""}
