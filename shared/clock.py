"""Phnom-Penh wall-clock helpers.

The server runs UTC; the shop is UTC+7. Use these wherever a CALENDAR DATE or "now" must reflect
the shop's day. A naive `date.today()` / `datetime.now()` is the WRONG day for the 7 hours each
night that PNH is already in tomorrow (00:00–07:00 PNH = 17:00–24:00 UTC) — e.g. a B2B order placed
at 1am PNH computed "tomorrow" off by one. (gm_bot has its own PP helpers `_today()`/`_now_pp()`;
these exist for b2b and any future shared use.)
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

PP_TZ = ZoneInfo("Asia/Phnom_Penh")


def pp_now() -> datetime:
    """Timezone-aware 'now' in Phnom-Penh."""
    return datetime.now(PP_TZ)


def pp_today() -> date:
    """Today's calendar date in Phnom-Penh (NOT the server's UTC date)."""
    return datetime.now(PP_TZ).date()
