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


_B2B_ORDER_IMAGE_SYSTEM = (
    "You extract a bakery order from a photo or scanned document (order sheet, table, handwritten "
    "list, chat screenshot). Return only valid JSON:\n"
    '{"items": [{"item": "<product name>", "qty": <integer>}]}\n'
    "Rules:\n"
    "- Extract readable product names only — ignore item codes like PP-FOOD-BK-2503; if a row has "
    "a code column and a description column, use the description.\n"
    "- Look for quantities in columns named Qty, Quantity, Pcs, or similar; qty must be a positive "
    "integer.\n"
    'If no order items are readable, return {"items": []}'
)


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


GM_PROPOSALS_MODEL = "claude-opus-4-8"
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


async def generate_proposals(concerns: list[dict],
                             approved_proposals: list[dict] | None = None) -> list[dict]:
    """Cluster concerns into groups and generate re-education or recognition proposals.

    approved_proposals: previously approved decisions — injected as context so the AI
    avoids re-proposing settled matters and builds on existing knowledge.
    """
    if not config.ANTHROPIC_API_KEY:
        return []

    lines = []
    for c in concerns[:150]:
        desc = (c.get("description") or "")[:150]
        lines.append("#%d [%s] %s: %s" % (c["id"], c.get("concern_type", "?"),
                                           c.get("sender_name", "?"), desc))
    concerns_text = "\n".join(lines)

    # Option 3: inject approved proposals as learned context
    approved_context = ""
    if approved_proposals:
        ap_lines = []
        for p in approved_proposals:
            ap_lines.append("• [%s] %s — %s" % (
                p.get("proposal_type", "correction"),
                p.get("group_name", ""),
                (p.get("solution_text") or "")[:120],
            ))
        approved_context = (
            "\n\nAll previously approved decisions (owner has settled these — never expire):\n"
            + "\n".join(ap_lines)
            + "\n\nDo NOT re-propose any of the above. Use them to understand tone, priorities, "
            "and what the owner considers resolved. Build on them if new concerns relate."
        )

    try:
        resp = await _get_client().messages.create(
            model=GM_PROPOSALS_MODEL,
            max_tokens=4000,
            system=[{"type": "text", "text": _GM_PROPOSALS_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user",
                       "content": _GM_PROPOSALS_USER.format(
                           n=len(concerns), concerns=concerns_text
                       ) + approved_context}],
        )
        return _parse_json_list(resp.content[0].text)
    except Exception as exc:
        logger.error("Proposal generation failed: %s", exc)
        return []


_GM_REFINE_SYSTEM = (
    "You are the GM Manager AI for a bakery in Phnom Penh, Cambodia. "
    "You are refining an operational proposal based on the owner's accumulated feedback. "
    "Keep the same proposal_type and overall intent. Tone: warm, encouraging, never shaming.\n\n"
    "Return ONLY valid JSON:\n"
    '{"solution_text": "the rewritten message", "conflict": null}\n'
    "OR if the new note directly contradicts an earlier note:\n"
    '{"solution_text": "best guess incorporating new note", '
    '"conflict": "Old note said X. New note says Y. Which should I use?"}\n'
    "conflict should be null unless there is a genuine factual contradiction — not just an update or addition."
)


async def refine_proposal_with_ai(proposal: dict, feedback: str,
                                   refinement_history: list[dict] | None = None) -> dict:
    """Rewrite a proposal using owner feedback, stacking all previous notes.

    Returns {"solution_text": "...", "conflict": "description or None"}.
    """
    history_text = ""
    if refinement_history:
        lines = []
        for i, h in enumerate(refinement_history, 1):
            at = h.get("at", "")[:10]
            lines.append("%d. [%s] %s" % (i, at, h.get("note", "")))
        history_text = "\n\nAll previous refinement notes (oldest first):\n" + "\n".join(lines)

    prompt = (
        "Proposal type: %s\n"
        "Group: %s\n"
        "Root cause: %s\n"
        "Current solution:\n%s%s\n\n"
        "New feedback from owner:\n%s\n\n"
        "Rewrite the solution incorporating all context above. "
        "Check if the new feedback contradicts any previous note."
    ) % (proposal.get("proposal_type", "correction"), proposal.get("group_name", ""),
         proposal.get("root_cause", ""), proposal.get("solution_text", ""),
         history_text, feedback)
    try:
        resp = await _get_client().messages.create(
            model=GM_PROPOSALS_MODEL,
            max_tokens=600,
            system=_GM_REFINE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _parse_json(resp.content[0].text)
        if not result.get("solution_text"):
            return {"solution_text": proposal.get("solution_text", ""), "conflict": None}
        return {"solution_text": result["solution_text"], "conflict": result.get("conflict")}
    except Exception as exc:
        logger.error("Proposal refine failed: %s", exc)
        return {"solution_text": proposal.get("solution_text", ""), "conflict": None}


_GM_RESOLVE_SYSTEM = (
    "You are the GM Manager AI for a bakery in Phnom Penh, Cambodia. "
    "You are finalising a proposal rewrite after the owner resolved a conflict between notes. "
    "Tone: warm, encouraging, never shaming. Suitable for Khmer staff. "
    "Return ONLY the final solution_text — no labels, no JSON, just the message."
)


async def refine_proposal_resolve_conflict(proposal: dict, feedback: str,
                                            refinement_history: list[dict] | None,
                                            conflict_desc: str, resolution: str) -> str:
    """Called after owner resolves a conflict. Returns final solution_text string."""
    history_text = ""
    if refinement_history:
        lines = []
        for i, h in enumerate(refinement_history, 1):
            at = h.get("at", "")[:10]
            lines.append("%d. [%s] %s" % (i, at, h.get("note", "")))
        history_text = "\n\nAll previous notes:\n" + "\n".join(lines)

    resolution_labels = {
        "new": "Apply the new note; discard the conflicting old note.",
        "old": "Keep the old note; ignore the new feedback for the conflicting point.",
        "merge": "Both are valid — find a way to incorporate both.",
    }
    resolution_text = resolution_labels.get(resolution, resolution)

    prompt = (
        "Proposal type: %s\n"
        "Group: %s\n"
        "Root cause: %s\n"
        "Current solution:\n%s%s\n\n"
        "New feedback:\n%s\n\n"
        "Conflict that was identified:\n%s\n\n"
        "Owner's resolution: %s\n\n"
        "Write the final solution_text applying this resolution."
    ) % (proposal.get("proposal_type", "correction"), proposal.get("group_name", ""),
         proposal.get("root_cause", ""), proposal.get("solution_text", ""),
         history_text, feedback, conflict_desc, resolution_text)
    try:
        resp = await _get_client().messages.create(
            model=GM_PROPOSALS_MODEL,
            max_tokens=500,
            system=_GM_RESOLVE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        logger.error("Proposal conflict resolve failed: %s", exc)
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


# Meaning-based concern detection — one short staff message, called live per message.
# Haiku: cheap and fast. Replaces the keyword waste/mistake scan in gm_bot/analyzer.py.
GM_CONCERN_MODEL = "claude-haiku-4-5-20251001"

_GM_CONCERN_SYSTEM = (
    "You read ONE staff message from a bakery/restaurant operations group in Phnom Penh "
    "and decide whether it reports an OPERATIONAL CONCERN the manager should see.\n\n"
    "Concern types:\n"
    "- waste: food or product thrown away, spoiled, expired, binned, gone off, unsellable.\n"
    "- mistake: an error or accident happened — dropped/broke something, burnt a batch, "
    "wrong order, spill, damage, something went wrong.\n"
    "- low_stock: an item is running out, finished, or needs buying/ordering soon.\n\n"
    "Judge MEANING, not keywords:\n"
    "- 'no waste today', 'nothing spoiled', 'we didn't break anything', 'all good' = NOT a concern.\n"
    "- 'the tray slipped and 6 cakes fell on the floor' = mistake, even with no obvious keyword.\n"
    "- 'we had to bin a whole batch of croissants' = waste.\n"
    "- Questions, greetings, schedules, normal coordination, plain photo captions, "
    "thanks, or routine 'done' updates = NOT a concern.\n"
    "- A staff member honestly reporting THEIR OWN mistake IS a concern — flag it "
    "(the bakery rewards transparency separately; your job is only to surface it).\n"
    "- Negations and reports that a problem did NOT happen are NOT concerns.\n\n"
    "Severity: 'info' for routine or minor; 'warning' for notable loss, repeat issue, or "
    "money lost; 'critical' for safety risk or large loss.\n\n"
    'Return ONLY valid JSON: {"is_concern": true|false, '
    '"concern_type": "waste"|"mistake"|"low_stock"|null, '
    '"severity": "info"|"warning"|"critical", "summary": "<one short clause>"}'
)


async def detect_concern_semantic(text: str) -> dict:
    """Meaning-based concern detection for one staff message (Haiku).

    Returns {is_concern, concern_type, severity, summary}. On API error returns
    {"is_concern": False, "_error": True} so the caller can fall back to the
    keyword scan and never silently drop a concern during an outage.
    """
    try:
        resp = await _get_client().messages.create(
            model=GM_CONCERN_MODEL,
            max_tokens=150,
            system=[{"type": "text", "text": _GM_CONCERN_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text[:1500]}],
        )
        result = _parse_json(resp.content[0].text)
        ctype = result.get("concern_type")
        if ctype not in ("waste", "mistake", "low_stock"):
            ctype = None
        sev = result.get("severity")
        if sev not in ("info", "warning", "critical"):
            sev = "info"
        return {
            "is_concern":   bool(result.get("is_concern", False)),
            "concern_type": ctype,
            "severity":     sev,
            "summary":      str(result.get("summary", "")),
        }
    except Exception as exc:
        logger.error("detect_concern_semantic failed: %s", exc)
        return {"is_concern": False, "_error": True}


# Lateness / pay-back detection — Haiku, live per supervisor/management message.
GM_LATENESS_MODEL = "claude-haiku-4-5-20251001"

_GM_LATENESS_SYSTEM = (
    "You read ONE message from a bakery's supervisor/management Telegram group in "
    "Phnom Penh. A senior may be reporting that a team member was LATE, ABSENT, or "
    "did NOT show up — and may mention a day that person will PAY BACK the missed time.\n"
    "Judge meaning (English + Khmer), not keywords.\n"
    "- is_lateness_report: true ONLY if it reports a specific person being late/absent/"
    "no-show. Normal chat, schedules, approvals, or planned annual leave = false.\n"
    "- late_person: the reported person's name as written, or null.\n"
    "- payback_day: the day/time they will make up the missed hours IF stated "
    "('tomorrow', 'Friday', 'the 5th', 'next week'...), else null.\n"
    'Return ONLY JSON: {"is_lateness_report": true|false, "late_person": "<name>"|null, '
    '"payback_day": "<day>"|null, "confidence": 0.0-1.0}'
)

_GM_PAYBACK_SYSTEM = (
    "A bakery manager asked when a late staff member will PAY BACK their missed time. "
    "Read the reply and extract the pay-back day if one is given (English or Khmer).\n"
    'Return ONLY JSON: {"has_payback_day": true|false, "payback_day": "<day>"|null}'
)


async def detect_lateness_report(text: str) -> dict:
    """Detect a lateness/absence report and extract the late person + any pay-back day.
    Returns {is_lateness_report, late_person, payback_day, confidence}. On error returns
    is_lateness_report False with _error=True so the caller can skip (no false cases)."""
    try:
        resp = await _get_client().messages.create(
            model=GM_LATENESS_MODEL,
            max_tokens=150,
            system=[{"type": "text", "text": _GM_LATENESS_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text[:1500]}],
        )
        result = _parse_json(resp.content[0].text)
        return {
            "is_lateness_report": bool(result.get("is_lateness_report", False)),
            "late_person":        result.get("late_person"),
            "payback_day":        result.get("payback_day"),
            "confidence":         float(result.get("confidence", 0.0)),
        }
    except Exception as exc:
        logger.error("detect_lateness_report failed: %s", exc)
        return {"is_lateness_report": False, "_error": True}


async def extract_payback_day(text: str) -> dict:
    """Extract a pay-back day from a reply. Returns {has_payback_day, payback_day}.
    On error returns has_payback_day False (case stays open) — fails safe."""
    try:
        resp = await _get_client().messages.create(
            model=GM_LATENESS_MODEL,
            max_tokens=80,
            system=[{"type": "text", "text": _GM_PAYBACK_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text[:800]}],
        )
        result = _parse_json(resp.content[0].text)
        return {
            "has_payback_day": bool(result.get("has_payback_day", False)),
            "payback_day":     result.get("payback_day"),
        }
    except Exception as exc:
        logger.error("extract_payback_day failed: %s", exc)
        return {"has_payback_day": False, "payback_day": None}


# Daily-report fallback parser — Sonnet. Only runs when the free regex parser fails
# on a report-shaped message (≤2/day). AI READS the fields; recompute() (the money
# math) stays deterministic. Also surfaces any non-standard labels so we can learn them.
GM_FINANCE_FALLBACK_MODEL = "claude-sonnet-4-6"  # == config.CLAUDE_MODEL

_GM_FINANCE_EXTRACT_SYSTEM = (
    "You read ONE daily cash-up report from a bakery in Phnom Penh (English/Khmer, "
    "handwritten-style typing, odd labels). Extract the canonical fields you can find.\n"
    "Canonical fields (all USD numbers, no symbols):\n"
    "  cash_on_hand  = starting float\n"
    "  cash_income   = cash sales\n"
    "  aba_income    = bank-app (ABA) sales\n"
    "  total_sales   = revenue (cash+ABA)\n"
    "  cash_expense  = cash paid out\n"
    "  aba_expense   = bank paid out\n"
    "  stated_total  = the 'Total'/expected drawer staff wrote\n"
    "  cash_count    = physically counted cash\n"
    "  over          = surplus stated\n"
    "  lost          = shortfall stated\n"
    "Also list, in `aliases`, every non-obvious label you mapped (the exact label text "
    "the staff used + the canonical field) so the system can learn it.\n"
    'Return ONLY JSON: {"fields": {"<canonical>": <number>, ...}, '
    '"aliases": [{"field": "<canonical>", "label": "<exact label text>"}], '
    '"stated_date": "YYYY-MM-DD"|null}\n'
    "Omit fields not present. Numbers only (e.g. 612.5), never strings."
)


async def extract_daily_report_ai(text: str) -> dict:
    """Sonnet fallback when the deterministic parser under-reads a report.
    Returns {fields: {canonical: number}, aliases: [{field,label}], stated_date}.
    On error returns empty fields so the caller simply skips (no bad data stored)."""
    if not config.ANTHROPIC_API_KEY:
        return {"fields": {}, "aliases": []}
    try:
        resp = await _get_client().messages.create(
            model=GM_FINANCE_FALLBACK_MODEL,
            max_tokens=500,
            system=[{"type": "text", "text": _GM_FINANCE_EXTRACT_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text[:2000]}],
        )
        result = _parse_json(resp.content[0].text)
        fields = result.get("fields") or {}
        # Keep only numeric values
        clean = {}
        for k, v in fields.items():
            try:
                clean[k] = float(v)
            except (TypeError, ValueError):
                continue
        return {
            "fields": clean,
            "aliases": result.get("aliases") or [],
            "stated_date": result.get("stated_date"),
        }
    except Exception as exc:
        logger.error("extract_daily_report_ai failed: %s", exc)
        return {"fields": {}, "aliases": []}


# Weekly attendance/AL digest — Opus (cross-week reasoning), owner-facing, scheduled.
GM_ATTENDANCE_DIGEST_MODEL = GM_PROPOSALS_MODEL  # claude-opus-4-8

_GM_ATTENDANCE_DIGEST_SYSTEM = (
    "You are the GM of a bakery in Phnom Penh. Write a SHORT weekly attendance digest "
    "for the OWNER (English). Cover: who was late or absent and how often, pay-back time "
    "owed or still unanswered, any worsening patterns, and 1-3 concrete suggestions. "
    "Be factual and concise — bullet points, no fluff, no shaming. If the data is thin, "
    "say so briefly. Do not invent anything beyond the data given."
)


async def generate_attendance_digest(lateness_cases: list[dict],
                                     attendance_concerns: list[dict]) -> str:
    """Opus weekly digest of lateness/pay-back + attendance concerns. Returns text
    (empty string on error so the job simply skips that week)."""
    if not config.ANTHROPIC_API_KEY:
        return ""
    lines = ["Lateness / pay-back cases this week:"]
    if lateness_cases:
        for c in lateness_cases:
            lines.append(
                "- %s | late: %s | status: %s | payback: %s | reported by: %s" % (
                    str(c.get("created_at"))[:10], c.get("late_person") or "?",
                    c.get("status") or "?", c.get("payback_day") or "(none)",
                    c.get("reporter_name") or "?"))
    else:
        lines.append("- (none)")
    lines.append("\nOther attendance/staffing notes this week:")
    if attendance_concerns:
        for c in attendance_concerns:
            lines.append("- %s" % (c.get("description") or "")[:160])
    else:
        lines.append("- (none)")
    try:
        resp = await _get_client().messages.create(
            model=GM_ATTENDANCE_DIGEST_MODEL,
            max_tokens=900,
            system=[{"type": "text", "text": _GM_ATTENDANCE_DIGEST_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": "\n".join(lines)}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        logger.error("generate_attendance_digest failed: %s", exc)
        return ""


REASON_CATEGORIES = ["transport", "family", "health", "oversleep", "weather", "other"]
_CATEGORIZE_SYSTEM = (
    "Classify each staff lateness/absence reason into EXACTLY ONE category from this fixed list: "
    "transport, family, health, oversleep, weather, other. Reasons may be in Khmer or English. "
    "transport = traffic/moto/bus/bridge/car; family = child/parent/spouse/family matter; "
    "health = own sickness/doctor/injury; oversleep = slept in / alarm; weather = rain/flood/storm; "
    "other = anything else or unclear. Return ONLY a JSON array of category strings — same length and "
    "order as the numbered input, nothing else."
)


async def categorize_reasons(reasons: list[str]) -> list[str]:
    """Haiku (cheap, batched = one call for many): label each free-text reason into a fixed category.
    Brain then aggregates these labels into exact trends. Analysis-time, never at confession time.
    Falls back to all 'other' with no key / on error so the pipeline never breaks. Always returns a
    list the same length as `reasons`."""
    if not reasons:
        return []
    if not config.ANTHROPIC_API_KEY:
        return ["other"] * len(reasons)
    import json as _json
    numbered = "\n".join("%d. %s" % (i + 1, (r or "").strip()) for i, r in enumerate(reasons))
    try:
        resp = await _get_client().messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=600,
            system=[{"type": "text", "text": _CATEGORIZE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": numbered}],
        )
        txt = resp.content[0].text.strip()
        arr = _json.loads(txt[txt.index("["):txt.rindex("]") + 1])
        out = [(c if c in REASON_CATEGORIES else "other") for c in arr]
    except Exception as exc:
        logger.error("categorize_reasons failed: %s", exc)
        out = []
    if len(out) < len(reasons):
        out += ["other"] * (len(reasons) - len(out))
    return out[:len(reasons)]


_GM_WEEK_NARRATE_SYSTEM = (
    "You are the GM of a bakery in Phnom Penh writing to the OWNER (English). You are given EXACT "
    "figures and pattern flags that were already computed by code — treat every number as final: do "
    "NOT recount, re-derive, or change any figure, and never invent one. Your only job is JUDGMENT "
    "over the staff's verbatim reasons and the flagged patterns: in 2-4 short sentences, say what the "
    "week's reasons suggest, which flagged patterns actually matter, and at most TWO concrete, kind "
    "suggestions. No bullet lists, no restating the numbers back, no shaming. If the reasons are thin, "
    "say so in one line."
)


async def narrate_attendance_week(facts_summary: str, reasons_block: str) -> str:
    """Opus 4.8 narrative for the split weekly digest: the Brain already computed the exact facts +
    pattern flags (passed in `facts_summary`); Opus only reads the verbatim REASONS and writes the
    human insight. Returns '' on no key/error (the digest still sends the Brain facts)."""
    if not config.ANTHROPIC_API_KEY:
        return ""
    user = ("Computed facts + flags (final — do not recount):\n%s\n\n"
            "Staff's verbatim reasons this week:\n%s" % (facts_summary, reasons_block or "(none)"))
    try:
        resp = await _get_client().messages.create(
            model=GM_ATTENDANCE_DIGEST_MODEL,
            max_tokens=400,
            system=[{"type": "text", "text": _GM_WEEK_NARRATE_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        logger.error("narrate_attendance_week failed: %s", exc)
        return ""


# Stock-sheet reading — Haiku classifies (cheap pre-filter), Sonnet extracts counts.
GM_STOCK_CLASSIFY_MODEL = "claude-haiku-4-5-20251001"

_STOCK_CLASSIFY_SYSTEM = (
    "You see one photo from a bakery's stock group. Decide if it is a STOCK-COUNT "
    "INVENTORY SHEET — a printed/handwritten form or table listing many ingredient/"
    "supply items down the side with quantity/count columns. It is NOT a stock sheet if "
    "it's a food plate, a fridge/display, a cleaning/workstation photo, a receipt, or a "
    "person. Return ONLY JSON: {\"is_stock_sheet\": true|false}"
)

_STOCK_READ_SYSTEM = (
    "You read a bakery STOCK-COUNT SHEET. It lists items down the side with a minimum "
    "column and one or more dated count columns. Read the CURRENT count for each item — "
    "the RIGHTMOST/most-recent filled count column. Map each row to the closest name in "
    "the provided canonical item list; ignore rows you cannot map. A blank/empty count "
    "means 0. Numbers may be decimals.\n"
    "Return ONLY JSON: {\"is_stock_sheet\": true|false, "
    "\"counts\": [{\"item\": \"<canonical name>\", \"count\": <number>}]}"
)


async def classify_stock_photo(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Cheap Haiku gate: is this photo a stock-count sheet? {is_stock_sheet: bool}.
    Fails closed (False) so a misread never triggers an expensive read."""
    try:
        resp = await _get_client().messages.create(
            model=GM_STOCK_CLASSIFY_MODEL,
            max_tokens=30,
            system=[{"type": "text", "text": _STOCK_CLASSIFY_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": _encode(image_bytes)}},
                {"type": "text", "text": "Is this a stock-count sheet?"},
            ]}],
        )
        return {"is_stock_sheet": bool(_parse_json(resp.content[0].text).get("is_stock_sheet", False))}
    except Exception as exc:
        logger.error("classify_stock_photo failed: %s", exc)
        return {"is_stock_sheet": False}


async def read_stock_sheet(image_bytes: bytes, canonical_items: list[str],
                           mime_type: str = "image/jpeg") -> dict:
    """Sonnet: read the latest count per item from a stock sheet, mapped to our
    canonical names. Returns {is_stock_sheet, counts:[{item, count}]}. Empty on error."""
    items_str = "\n".join("- " + i for i in canonical_items)
    try:
        resp = await _get_client().messages.create(
            model=GM_FINANCE_FALLBACK_MODEL,   # claude-sonnet-4-6
            max_tokens=1500,
            system=[{"type": "text", "text": _STOCK_READ_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": _encode(image_bytes)}},
                {"type": "text", "text": "Canonical items:\n%s\n\nRead the current counts." % items_str},
            ]}],
        )
        result = _parse_json(resp.content[0].text)
        counts = []
        for c in result.get("counts", []):
            try:
                counts.append({"item": str(c["item"]), "count": float(c["count"])})
            except (KeyError, TypeError, ValueError):
                continue
        return {"is_stock_sheet": bool(result.get("is_stock_sheet", False)), "counts": counts}
    except Exception as exc:
        logger.error("read_stock_sheet failed: %s", exc)
        return {"is_stock_sheet": False, "counts": []}


# Leave / time-off detection — Haiku, live per supervisor/management message.
_GM_LEAVE_SYSTEM = (
    "You read ONE message from a bakery's supervisor/management Telegram group in "
    "Phnom Penh. Someone may be announcing or requesting TIME OFF for a staff member — "
    "annual leave (AL), a plain day off, sick leave, or 'want off'. Judge meaning "
    "(English + Khmer), not keywords. Lateness or 'on the way' is NOT a leave request.\n"
    "- is_leave_request: true only if it announces/requests time off or an absence.\n"
    "- person: whose leave (name as written), or null if it's the sender themself.\n"
    "- leave_type: 'al' if they explicitly say annual leave/AL; 'sick' if sick/not well/"
    "unwell; 'off' if just day off / want off / not coming with NO type given; "
    "'unspecified' if unclear.\n"
    "- said_al: true ONLY if the words 'AL' or 'annual leave' actually appear.\n"
    "- dates: the day(s) of leave as written ('tomorrow','5th','next Mon'), or null.\n"
    "- reason: stated reason, or null.\n"
    'Return ONLY JSON: {"is_leave_request": true|false, "person": "<name>"|null, '
    '"leave_type": "al"|"sick"|"off"|"unspecified", "said_al": true|false, '
    '"dates": "<text>"|null, "reason": "<text>"|null, "confidence": 0.0-1.0}'
)


async def detect_leave_request(text: str) -> dict:
    """Detect a time-off / leave announcement and extract its fields (Haiku).
    Returns is_leave_request + person/leave_type/said_al/dates/reason/confidence.
    On error returns is_leave_request False with _error so the caller skips."""
    try:
        resp = await _get_client().messages.create(
            model=GM_LATENESS_MODEL,
            max_tokens=200,
            system=[{"type": "text", "text": _GM_LEAVE_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text[:1500]}],
        )
        result = _parse_json(resp.content[0].text)
        lt = result.get("leave_type")
        if lt not in ("al", "sick", "off", "unspecified"):
            lt = "unspecified"
        return {
            "is_leave_request": bool(result.get("is_leave_request", False)),
            "person":     result.get("person"),
            "leave_type": lt,
            "said_al":    bool(result.get("said_al", False)),
            "dates":      result.get("dates"),
            "reason":     result.get("reason"),
            "confidence": float(result.get("confidence", 0.0)),
        }
    except Exception as exc:
        logger.error("detect_leave_request failed: %s", exc)
        return {"is_leave_request": False, "_error": True}


async def assess_receipt_photo(image_bytes: bytes,
                               past_examples: list[dict] | None = None,
                               vendor_rules: list[dict] | None = None) -> dict:
    """Check if a receipt/expense photo in TWB REPORT is clear enough to record.
    Returns {"is_receipt": bool, "is_clear": bool, "issues": list[str], "vendor": str}

    past_examples: list of {"question": str, "answer": str} from previous clarifications
    in the same group — injected as few-shot context so the AI learns handwriting patterns.
    vendor_rules: list of {"vendor","mode","rule"} — per-vendor format knowledge
    ("Atlas: totals handwritten in riel"); same single call, just smarter prompt.
    """
    vendor_text = ""
    if vendor_rules:
        lines = ["- %s: %s" % (v["vendor"], v.get("rule") or "known vendor")
                 for v in vendor_rules if v.get("mode") != "skip" and v.get("rule")]
        if lines:
            vendor_text = ("\n\nKnown vendor formats (apply these when the receipt matches):\n"
                           + "\n".join(lines) + "\n")
    examples_text = ""
    if past_examples:
        lines = []
        for ex in past_examples:
            q = ex.get("question", "")
            a = ex.get("answer", "")
            if q and a:
                lines.append(f'  Q: "{q}"\n  A: "{a}"')
        if lines:
            examples_text = (
                "\n\nPast clarifications from this same group (use these to recognise "
                "handwriting style and naming conventions):\n"
                + "\n".join(lines) + "\n"
            )

    prompt = (
        "Look at this photo.\n\n"
        "First: is this a receipt, invoice, expense list, or payment document? "
        "(handwritten or printed — both are normal. Not a product photo, menu, or unrelated image)\n\n"
        "If yes, check ONLY these two things:\n"
        "1. Can you read the TOTAL AMOUNT? (USD or Khmer Riel ៛ — both valid. Missing vendor name, "
        "date, phone number, or blank columns are NOT a problem — ignore those.)\n"
        "2. Can you read WHAT WAS BOUGHT? (items, descriptions, or quantities — at least roughly)\n\n"
        "Also: is this handwritten?\n\n"
        "is_clear = true if BOTH total amount AND items are readable enough to record.\n"
        "Only flag something in issues if it is genuinely unreadable (too blurry, too dark, cut off, "
        "or handwriting completely illegible). Do NOT flag: missing vendor, missing date, blank columns, "
        "crossed-out entries, 2-digit year formats.\n"
        + vendor_text + examples_text +
        "\nAlso classify doc_type:\n"
        "- 'expense_sheet': the shop's printed 'Expense list' form on a clipboard — handwritten "
        "item lines with totals near the bottom labelled 'Day Cash Expense', 'Night Cash Expense', "
        "'ABA Expense'. Extract those three numbers into fields (null when blank).\n"
        "- 'pos_screen': a computer monitor showing SambaPOS reports. Extract into fields: "
        "pos_kind ('work_period' if it shows a Work Period Report, 'summary' if a Summary Report, "
        "else 'other') and grand_total (the GRAND TOTAL line; for summary screens use the Total "
        "line; null if not visible).\n"
        "- 'receipt': any supplier receipt/invoice/payment document. It may be a PRE-PRINTED FORM "
        "listing many product OPTIONS (e.g. a gas shop pre-prints Gas 12kg/15kg/48kg) — ONLY the "
        "line(s) with a HANDWRITTEN quantity/price were ACTUALLY bought; ignore blank printed options. "
        "Extract into fields: receipt_vendor (business name printed at the top), receipt_total (the "
        "final total as a plain number — usually handwritten at the bottom), receipt_currency ('USD' "
        "or 'KHR'; if BOTH are shown use the USD figure, since a supplier's Riel rate may differ from 4000).\n"
        "- 'other': anything else.\n"
        "\nRespond ONLY with JSON:\n"
        '{"is_receipt": true/false, "is_clear": true/false, "is_handwritten": true/false, '
        '"issues": ["short problem description"], "readable_partial": "any amounts/text you CAN read", '
        '"vendor": "vendor/company name if visible, else empty string", '
        '"doc_type": "expense_sheet|pos_screen|receipt|other", '
        '"fields": {"day_cash_expense": null, "night_cash_expense": null, "aba_expense": null, '
        '"pos_kind": null, "grand_total": null, "receipt_vendor": null, "receipt_total": null, '
        '"receipt_currency": null}}\n\n'
        "issues must be short (5 words max each). If is_clear is true, issues must be []. "
        "fields: only fill keys relevant to the doc_type; numbers as plain numbers, no $ or commas."
    )
    try:
        resp = await _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _encode(image_bytes)}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        result = _parse_json(resp.content[0].text)
        return {
            "is_receipt":       bool(result.get("is_receipt", False)),
            "is_clear":         bool(result.get("is_clear", True)),
            "is_handwritten":   bool(result.get("is_handwritten", False)),
            "issues":           result.get("issues", []),
            "readable_partial": result.get("readable_partial", ""),
            "vendor":           (result.get("vendor") or "").strip(),
            "doc_type":         (result.get("doc_type") or "other").strip(),
            "fields":           result.get("fields") or {},
        }
    except Exception as exc:
        logger.error("assess_receipt_photo failed: %s", exc)
        return {"is_receipt": False, "is_clear": True, "issues": [], "vendor": "",
                "doc_type": "other", "fields": {}}


# Bounded short-context judgment (one question + one reply) — Sonnet is the right tier.
CALLOUT_PRIVATE_MODEL = "claude-sonnet-4-6"   # warm private nudge
CALLOUT_GROUP_MODEL = "claude-opus-4-8"       # the unnamed group wink (highest-stakes 100 words)


async def generate_callout(dossier: str, call_name: str, channel: str) -> str:
    """Craft a bilingual (EN + KH) attendance call-out. channel='private' (Sonnet, warm, names them
    once) or 'group' (Opus, NEVER names, unmistakable to the person, light to everyone else)."""
    model = CALLOUT_PRIVATE_MODEL if channel == "private" else CALLOUT_GROUP_MODEL
    if channel == "private":
        sys = ("You are the GM of a Phnom Penh bakery. Write a SHORT, warm private message to a staff "
               "member about a lateness pattern. Address them by call-name ONCE at the start, not again. "
               "Kind, not scolding — 'we noticed, let's fix it together'. Mention the pattern lightly. "
               "Output English then Khmer underneath. No threats.")
    else:
        sys = ("You are the GM of a Phnom Penh bakery. Write a SHORT group message that NEVER names "
               "anyone, is light/friendly to everyone, but unmistakable to the one person it's about — "
               "a wink that says 'we track patterns and we're watching, kindly'. Output English then "
               "Khmer underneath. No names, no shame.")
    try:
        resp = await _get_client().messages.create(
            model=model, max_tokens=300, system=sys,
            messages=[{"role": "user", "content":
                       "Pattern: %s\nCall name (private only): %s" % (dossier, call_name)}])
        return resp.content[0].text.strip()
    except Exception as exc:
        logger.error("generate_callout failed: %s", exc)
        return ""


MEDICAL_PAPER_MODEL = "claude-opus-4-8"   # rare, high-judgment (undated papers, part-duty advice)


async def read_medical_paper(image_bytes: bytes) -> dict:
    """Read a staff sick-leave document → advise the owner. NEVER decides — owner taps.
    Returns {is_medical, hospital, doctor, patient_name, doc_date, rest_days|null,
             contagious, part_duty_possible, suggested_jobs, confidence, reasoning}.
    Used only when a staff with an open sick case sends a photo (rare → Opus is justified)."""
    prompt = (
        "This is a photo a bakery staff member sent as sick-leave proof. Read it and ADVISE the "
        "owner (you never decide). Extract:\n"
        "- is_medical: is this a genuine clinic/hospital/doctor document? (true/false)\n"
        "- hospital, doctor, patient_name, doc_date (strings; empty if absent)\n"
        "- rest_days: integer ONLY if the paper states a rest period, else null\n"
        "- contagious: true if the condition is likely contagious (fever/flu/infection) — then NO "
        "come-in suggestion\n"
        "- part_duty_possible: true if they could do light work (e.g. leg injury → seated; hand "
        "injury → one-hand) — false for contagious/serious\n"
        "- suggested_jobs: short e.g. 'seated cashier/prep' or 'one-hand cashier' or ''\n"
        "- confidence: 0..1; reasoning: one short line (treatment + likely days)\n"
        "Respond ONLY JSON with exactly those keys."
    )
    try:
        resp = await _get_client().messages.create(
            model=MEDICAL_PAPER_MODEL, max_tokens=400,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": _encode(image_bytes)}},
                {"type": "text", "text": prompt}]}])
        r = _parse_json(resp.content[0].text)
        return {
            "is_medical": bool(r.get("is_medical", False)),
            "hospital": r.get("hospital", ""), "doctor": r.get("doctor", ""),
            "patient_name": r.get("patient_name", ""), "doc_date": r.get("doc_date", ""),
            "rest_days": r.get("rest_days"),
            "contagious": bool(r.get("contagious", False)),
            "part_duty_possible": bool(r.get("part_duty_possible", False)),
            "suggested_jobs": r.get("suggested_jobs", ""),
            "confidence": r.get("confidence", 0), "reasoning": r.get("reasoning", ""),
        }
    except Exception as exc:
        logger.error("read_medical_paper failed: %s", exc)
        return {"is_medical": False, "rest_days": None, "contagious": False,
                "part_duty_possible": False, "_error": True}


CLARIFICATION_JUDGE_MODEL = "claude-sonnet-4-6"

_CLARIFY_JUDGE_SYSTEM = (
    "You are the GM of a bakery in Phnom Penh. The GM asked a staff member to clarify "
    "or correct something, and they replied. Decide ONLY whether their reply genuinely "
    "addresses the question.\n"
    "- report_math: the GM showed a cash-drawer arithmetic error. A good reply explains the "
    "cause (miscount, a missed expense, a typo) or commits to fixing/recounting. A bad reply "
    "ignores it, is evasive, blames vaguely, or makes no sense.\n"
    "- receipt_clarity: the GM asked what an unclear receipt says. A good reply gives the "
    "readable amount/items asked for. A bad reply is unrelated or still unclear.\n"
    "- cash_lost: the GM flagged the drawer short by more than $2 and asked why. A good "
    "reply gives a plausible cause (miscount, unrecorded expense, wrong change, FX) or "
    "says they recounted/will recount. A bad reply ignores it or is evasive.\n"
    "- leave_clarify: the GM asked whether a time-off is annual leave (AL) or another "
    "kind, and/or which day(s). A good reply states the leave type and/or the date(s). "
    "A bad reply is unrelated or still leaves it unclear.\n"
    "Be fair, not pedantic: a plausible, on-topic explanation counts as resolved. "
    "Only flag replies that truly fail to address the question.\n"
    'Return ONLY JSON: {"resolved": true|false, "reason": "<short>"}'
)


async def judge_clarification_answer(question: str, answer: str, topic: str) -> dict:
    """Decide if a staff reply resolves a GM clarification. Returns {'resolved': bool, 'reason': str}.
    Fails open (resolved=True) so AI outages never spam the owner."""
    prompt = (
        f"Topic: {topic}\n\n"
        f"GM asked:\n{question}\n\n"
        f"Staff replied:\n{answer}\n\n"
        "Does the reply genuinely address the question? Return the JSON."
    )
    try:
        resp = await _get_client().messages.create(
            model=CLARIFICATION_JUDGE_MODEL,
            max_tokens=150,
            system=_CLARIFY_JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _parse_json(resp.content[0].text)
        return {
            "resolved": bool(result.get("resolved", True)),
            "reason": str(result.get("reason", "")),
        }
    except Exception as exc:
        logger.error("judge_clarification_answer failed: %s", exc)
        return {"resolved": True, "reason": "judge unavailable"}


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


# ── Intake funnel — Haiku classifier/extractor (text-only, no images) ────────
# Max 2 cheap calls per applicant: intent check + CV extraction.
# No analysis of photos/files before TEST_UNLOCKED — store only.

INTAKE_HAIKU_MODEL            = "claude-haiku-4-5-20251001"
INTAKE_INTENT_PROMPT_VERSION  = "v1"
INTAKE_CV_PROMPT_VERSION      = "v1"
INTAKE_DEFLECTION_PROMPT_VERSION = "v1"

_INTENT_SYSTEM = """\
You classify the intent of someone who just messaged a bakery's hiring chatbot.
The bot greeted them and asked them to leave their CV to apply.
Their reply follows.

Return ONLY valid JSON — no explanation, no markdown:
{
  "intent": "applying" | "clear_refusal" | "wrong_number" | "confused",
  "confidence": 0.0-1.0,
  "language": "en" | "km" | "mixed" | "unknown",
  "reason_code": "short_string"
}

Rules (read carefully):
- "I have no job" / "ខ្ញុំគ្មានការងារ" = applying (unemployed, looking for work)
- "I don't want a job" / "not interested" = clear_refusal
- "wrong number" / "wrong chat" / "who is this" = wrong_number
- "hi" / "hello" / single emoji / "?" / very short greeting = confused
- Any mention of wanting to work, asking about the job, or describing experience = applying
- If confidence < 0.75 for clear_refusal or wrong_number, use confused instead
- Never use keyword matching; read full meaning and context
"""

_CV_EXTRACT_SYSTEM = """\
You extract work history from a job applicant's message at a bakery.
The person was asked to leave their CV or describe their work experience.

Return ONLY valid JSON — no explanation, no markdown:
{
  "has_work_history": true | false,
  "name": "string or null",
  "position_interest": "string or null",
  "previous_jobs": ["description..."],
  "years_experience": "string or null",
  "skills": ["skill..."],
  "availability_clues": "string or null"
}

has_work_history = true if the text contains ANY of: name, job history, skills, experience, position interest.
has_work_history = false if the text is only: greetings, questions, refusals, random text, or unrelated content.
Be generous — "hi im dara work coffee 2 year" counts as has_work_history = true.
"""

_DEFLECTION_SYSTEM = """\
Someone is applying for a job at a bakery. They were asked for their CV or work history multiple times.
Here are their recent replies (oldest first).

Classify their situation:
- struggling: trying to apply but does not know what to write or how
- refusing: clearly not interested or not serious
- has_usable_content: actually gave work history in a non-standard or messy format

Return ONLY valid JSON — no explanation, no markdown:
{
  "status": "struggling" | "refusing" | "has_usable_content",
  "confidence": 0.0-1.0
}
"""


async def classify_intake_intent(text: str) -> dict:
    """
    Classify the first reply from a job applicant.
    Returns: {intent, confidence, language, reason_code}
    On error returns intent=confused so the bot re-prompts rather than closes.
    """
    try:
        resp = await _get_client().messages.create(
            model=INTAKE_HAIKU_MODEL,
            max_tokens=128,
            system=_INTENT_SYSTEM,
            messages=[{"role": "user", "content": text[:1000]}],
        )
        result = _parse_json(resp.content[0].text)
        return {
            "intent":      result.get("intent", "confused"),
            "confidence":  float(result.get("confidence", 0.5)),
            "language":    result.get("language", "unknown"),
            "reason_code": result.get("reason_code", ""),
        }
    except Exception as exc:
        logger.error("classify_intake_intent failed: %s", exc)
        return {"intent": "confused", "confidence": 0.0, "language": "unknown",
                "reason_code": "error"}


async def extract_cv_content(text: str) -> dict:
    """
    Extract work history fields from applicant text.
    Returns: {has_work_history, name, position_interest, previous_jobs, years_experience, skills, availability_clues}
    On error returns has_work_history=False so the deflection counter increments normally.
    """
    try:
        resp = await _get_client().messages.create(
            model=INTAKE_HAIKU_MODEL,
            max_tokens=256,
            system=_CV_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": text[:2000]}],
        )
        result = _parse_json(resp.content[0].text)
        return {
            "has_work_history":    bool(result.get("has_work_history", False)),
            "name":                result.get("name"),
            "position_interest":   result.get("position_interest"),
            "previous_jobs":       result.get("previous_jobs", []),
            "years_experience":    result.get("years_experience"),
            "skills":              result.get("skills", []),
            "availability_clues":  result.get("availability_clues"),
        }
    except Exception as exc:
        logger.error("extract_cv_content failed: %s", exc)
        return {"has_work_history": False, "name": None, "position_interest": None,
                "previous_jobs": [], "years_experience": None, "skills": [],
                "availability_clues": None}


async def check_deflection_intent(messages: list[str]) -> dict:
    """
    After 3+ deflections, determine if applicant is struggling, refusing, or gave usable content.
    Returns: {status, confidence}
    On error returns status=struggling so the bot gives one more chance.
    """
    try:
        combined = "\n---\n".join(m[:500] for m in messages[-5:])
        resp = await _get_client().messages.create(
            model=INTAKE_HAIKU_MODEL,
            max_tokens=64,
            system=_DEFLECTION_SYSTEM,
            messages=[{"role": "user", "content": combined}],
        )
        result = _parse_json(resp.content[0].text)
        return {
            "status":     result.get("status", "struggling"),
            "confidence": float(result.get("confidence", 0.5)),
        }
    except Exception as exc:
        logger.error("check_deflection_intent failed: %s", exc)
        return {"status": "struggling", "confidence": 0.0}
