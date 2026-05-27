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


def _parse_json_list(text: str) -> list:
    """Extract JSON array from Claude response, handling optional markdown fences."""
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        logger.warning("Could not parse AI response as JSON list: %.200s", text)
        return []


def _parse_json(text: str) -> dict:
    """Extract JSON from Claude's response, handling optional markdown fences."""
    # Strip markdown code block if present
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    # Find outermost { } boundaries
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
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

_PDF_PAYMENT_SYSTEM = (
    "You are a payment verification assistant. Read a bank transfer PDF document and extract details. "
    "Return only valid JSON:\n"
    '{"amount": <number or null>, "currency": "<string or null>", '
    '"to_account": "<destination account number digits only or null>", '
    '"seller": "<seller/merchant name exactly as shown or null>"}\n'
    "Rules: amount is a plain number (e.g. 138.60). "
    "to_account: digits only, no spaces or dashes. If partially visible (e.g. ***1234) extract only the visible digits. "
    "seller: the merchant/payee name field if present. Set each to null if not found."
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
    '  Payment: {"type": "payment", "amount": <number or null>, "currency": "<string or null>", "to_account": "<destination account number digits only or null>", "seller": "<seller/merchant name exactly as shown or null>"}\n'
    '  Order:   {"type": "order", "items": [{"item": "<product name>", "qty": <integer>}]}\n'
    '  Other:   {"type": "other"}\n'
    "For payments: extract to_account (digits only, no spaces/dashes; if partially visible e.g. ***1234 extract only visible digits 1234) "
    "AND seller name (the merchant/seller field if this is a QR/PayWay receipt). Set each to null if not present. "
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
    """Read payment amount, destination account, and seller from a PDF bank document."""
    if not config.ANTHROPIC_API_KEY:
        return {"amount": None, "currency": None, "to_account": None, "seller": None}
    try:
        resp = await _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=256,
            system=[{"type": "text", "text": _PDF_PAYMENT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": _encode(pdf_bytes)}},
                    {"type": "text", "text": "Extract the payment details from this document."},
                ],
            }],
        )
        return _parse_json(resp.content[0].text) or {"amount": None, "currency": None, "to_account": None, "seller": None}
    except Exception as exc:
        logger.error("PDF payment reading failed: %s", exc)
        return {"amount": None, "currency": None, "to_account": None, "seller": None}


_PRICE_LIST_SYSTEM = (
    "You extract product prices from supplier price lists, catalogs, invoices, and promotional images.\n"
    "Text may be in English, Khmer, French, Thai, or mixed. Always translate product names to English.\n"
    "Return ONLY valid JSON:\n"
    '{"valid_date": "YYYY-MM-DD or null", "currency": "USD", '
    '"items": [{"product": "English name", "price": 1.50, "unit": "kg/case/bottle/piece/etc", "notes": ""}]}\n'
    "Rules:\n"
    "- product: English, specific (e.g. 'Cream cheese Philadelphia 1kg', 'Tiger draft beer keg 20L')\n"
    "- price: plain number in the listed currency (if range, use lower; note range in notes)\n"
    "- unit: what the price covers — kg, g, piece, bottle, case, box, pack, roll, etc.\n"
    "- notes: promo conditions, minimum order, discount %, out of stock, or empty string\n"
    "- If case and unit price both shown: use unit price, put case price in notes\n"
    "- Skip items with no visible price\n"
    "- Include ALL products — aim for completeness, up to 200 items\n"
    'If nothing readable: {"valid_date": null, "currency": "USD", "items": []}'
)


async def extract_price_list_image(image_bytes: bytes) -> dict:
    """Extract price items from a supplier price list photo."""
    try:
        resp = await _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            system=[{"type": "text", "text": _PRICE_LIST_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _encode(image_bytes)}},
                    {"type": "text", "text": "Extract all products and prices from this supplier price list."},
                ],
            }],
        )
        return _parse_json(resp.content[0].text) or {"valid_date": None, "currency": "USD", "items": []}
    except Exception as exc:
        logger.error("Price list image extraction failed: %s", exc)
        return {"valid_date": None, "currency": "USD", "items": [], "error": str(exc)}


async def extract_price_list_pdf(pdf_bytes: bytes) -> dict:
    """Extract price items from a supplier price list PDF."""
    try:
        resp = await _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            system=[{"type": "text", "text": _PRICE_LIST_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": _encode(pdf_bytes)}},
                    {"type": "text", "text": "Extract ALL products and prices from this price list. Include every item with a visible price."},
                ],
            }],
        )
        return _parse_json(resp.content[0].text) or {"valid_date": None, "currency": "USD", "items": []}
    except Exception as exc:
        logger.error("Price list PDF extraction failed: %s", exc)
        return {"valid_date": None, "currency": "USD", "items": [], "error": str(exc)}


GM_PROPOSALS_MODEL = "claude-opus-4-7"
GM_REPLY_MODEL     = "claude-haiku-4-5-20251001"

_GM_PROPOSALS_SYSTEM = (
    "You are the GM Manager AI for a bakery in Phnom Penh, Cambodia. "
    "You analyze months of staff operational messages and generate actionable proposals for the owner.\n\n"
    "Two types of proposals:\n"
    "1. CORRECTION — recurring problems that need a re-education message\n"
    "2. RECOGNITION — positive behaviors that deserve acknowledgement and a point award\n\n"
    "Staff culture: Khmer-speaking team, mix of experience levels. Tone always warm and encouraging, never shaming. "
    "The bakery monitors: stock checks, cleanliness, mistakes, waste, and accidents.\n\n"
    "Return ONLY a valid JSON array, no other text."
)

_GM_PROPOSALS_USER = """Here are {n} operational concerns from the bakery's Stock Checks group:

{concerns}

Also note: this bakery rewards staff for transparency — staff who proactively report problems (even their own mistakes) should be recognized.

Instructions:
1. Group the CORRECTION concerns by root cause. Aim for 3-8 meaningful groups. Do not make groups too granular.
2. Identify any RECOGNITION opportunities — patterns of good reporting behavior worth acknowledging.
3. For each group, draft the message the GM will eventually send.

Return a JSON array where each item is:
{{
  "proposal_type": "correction" or "recognition",
  "group_name": "Short descriptive name (5 words max)",
  "concern_ids": [list of concern ID integers in this group],
  "root_cause": "Why this keeps happening or why this deserves recognition — 1-2 sentences",
  "solution_text": "The message to send staff. Friendly, practical, 2-4 sentences. Start with 'Dear team,' or 'Dear [name],' as appropriate.",
  "recipients": "group" or "individual",
  "staff_names": ["Name1", "Name2"],
  "concern_type": "mistake" or "waste" or "low_stock" or "mixed",
  "points": 0 (correction) or 1 (recognition)
}}"""


async def generate_proposals(concerns: list[dict]) -> list[dict]:
    """Cluster concerns into groups and generate re-education or recognition proposals."""
    if not config.ANTHROPIC_API_KEY:
        return []

    lines = []
    for c in concerns[:150]:
        desc = (c.get("description") or "")[:150]
        lines.append("#%d [%s] %s: %s" % (c["id"], c.get("concern_type", "?"),
                                           c.get("sender_name", "?"), desc))
    concerns_text = "\n".join(lines)

    try:
        resp = await _get_client().messages.create(
            model=GM_PROPOSALS_MODEL,
            max_tokens=4000,
            system=[{"type": "text", "text": _GM_PROPOSALS_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user",
                       "content": _GM_PROPOSALS_USER.format(n=len(concerns),
                                                             concerns=concerns_text)}],
        )
        return _parse_json_list(resp.content[0].text)
    except Exception as exc:
        logger.error("Proposal generation failed: %s", exc)
        return []


_GM_REFINE_SYSTEM = (
    "You are the GM Manager AI for a bakery in Phnom Penh, Cambodia. "
    "You are refining an operational proposal based on the owner's feedback. "
    "Keep the same proposal_type and overall intent, but rewrite solution_text to incorporate the owner's context. "
    "Tone: warm, encouraging, never shaming. Suitable for Khmer staff. "
    "Return ONLY the updated solution_text — no labels, no JSON, just the message."
)


async def refine_proposal_with_ai(proposal: dict, feedback: str) -> str:
    """Rewrite a proposal's solution_text using owner feedback. Returns new solution text."""
    prompt = (
        "Proposal type: %s\n"
        "Group: %s\n"
        "Root cause: %s\n"
        "Current solution:\n%s\n\n"
        "Owner's feedback/additional context:\n%s\n\n"
        "Rewrite the solution incorporating this feedback."
    ) % (proposal.get("proposal_type", "correction"), proposal.get("group_name", ""),
         proposal.get("root_cause", ""), proposal.get("solution_text", ""), feedback)
    try:
        resp = await _get_client().messages.create(
            model=GM_PROPOSALS_MODEL,
            max_tokens=500,
            system=_GM_REFINE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        logger.error("Proposal refine failed: %s", exc)
        return proposal.get("solution_text", "")


_GM_REPLY_SYSTEM = (
    "You are the GM Manager AI for a bakery in Phnom Penh, Cambodia. "
    "You post occasional messages in staff group chats based on approved operational policies. "
    "Your tone is warm, direct, and encouraging — never robotic or preachy. "
    "Write naturally, as a real manager who noticed something specific. "
    "2-3 sentences max. English unless strongly contextual Khmer is needed."
)


async def gm_compose_reply(solution_intent: str, trigger_text: str,
                           sender_name: str, chat_title: str) -> str:
    """Compose a fresh, contextual GM group reply using an approved solution as policy.
    Uses Haiku — cheap per call, called at delivery time."""
    prompt = (
        "Approved policy: %s\n\n"
        "What just happened in '%s':\n"
        "%s posted: %s\n\n"
        "Write a short natural response for this specific moment. "
        "Don't repeat the policy word-for-word — phrase it freshly."
    ) % (solution_intent, chat_title, sender_name, trigger_text)
    try:
        resp = await _get_client().messages.create(
            model=GM_REPLY_MODEL,
            max_tokens=200,
            system=_GM_REPLY_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        logger.error("GM reply composition failed: %s", exc)
        return solution_intent


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
