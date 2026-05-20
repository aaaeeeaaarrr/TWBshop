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

_STAFF_MSG_SYSTEM = (
    "You monitor bakery staff communications for issues needing management attention. "
    "Flag: safety concerns, customer complaints, conflicts, significant frustration, policy violations. "
    "Do not flag: normal coordination, friendly chat, routine updates. "
    'Return only valid JSON: {"action": "none/alert/urgent", "flag": true/false, "reason": "brief reason or empty string"}'
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
