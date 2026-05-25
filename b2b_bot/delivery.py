"""Delivery cost estimation via Grab Express pricing + OSRM road distance."""

import json
import logging
import math
import urllib.request
from telegram import Update

import config
from b2b_bot.customers import is_b2b_group, get_business_name
from shared.database import update_b2b_location

logger = logging.getLogger(__name__)

_GRAB_BASE    = 0.68
_GRAB_PER_90M = 0.025


def grab_express_cost(distance_meters: float) -> float:
    """Grab Express fare: $0.68 base + $0.025 per 90m. Truncate to cents."""
    total = _GRAB_BASE + (distance_meters / 90) * _GRAB_PER_90M
    return math.floor(total * 100) / 100


def get_road_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float | None:
    """Road distance in metres via OSRM public API (free, no key needed)."""
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lng1},{lat1};{lng2},{lat2}?overview=false"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
        return data["routes"][0]["distance"]
    except Exception as e:
        logger.warning("OSRM distance lookup failed: %s", e)
        return None


async def handle_location(update: Update, context) -> None:
    """Store a customer group's location pin and calculate Grab Express delivery cost."""
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return

    loc = update.message.location
    if not loc:
        return

    if config.BAKERY_LAT == 0.0 and config.BAKERY_LNG == 0.0:
        logger.warning("Bakery coordinates not set in config — skipping delivery cost calc")
        await update.message.reply_text("📍 Location received, but bakery coordinates aren't configured yet.")
        return

    distance = get_road_distance_meters(
        config.BAKERY_LAT, config.BAKERY_LNG,
        loc.latitude, loc.longitude,
    )

    if distance is None:
        await update.message.reply_text(
            "📍 Location saved, but couldn't calculate road distance right now. Try again later."
        )
        update_b2b_location(chat_id, loc.latitude, loc.longitude, delivery_cost=0.0)
        return

    cost = grab_express_cost(distance)
    update_b2b_location(chat_id, loc.latitude, loc.longitude, delivery_cost=cost)

    business = get_business_name(chat_id) or "your business"
    km = distance / 1000
    await update.message.reply_text(
        f"📍 Location saved for {business}.\n"
        f"Road distance: {km:.1f} km\n"
        f"Grab Express estimate: ${cost:.2f}"
    )
    logger.info("Location set for %s (chat %s): %.4f,%.4f — %.0fm — $%.2f",
                business, chat_id, loc.latitude, loc.longitude, distance, cost)
