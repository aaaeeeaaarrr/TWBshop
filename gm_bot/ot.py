"""Give-OT / time-bank pure logic (session 28). No DB/Telegram.

Seniors GRANT OT → owner approves → hours bank (cap 14h, no money) → staff takes buyback rest at
the shop's SAFEST (most-surplus) times. NOW-OT = present staff (consent + location/senior proof);
FUTURE-OT = accept → scheduled work slot. Accepted = commitment.
"""
from __future__ import annotations

BANK_CAP_MIN = 14 * 60   # 14 hours


def cap_room(current_bank_min: int) -> int:
    """Minutes of OT still grantable before the 14h cap."""
    return max(0, BANK_CAP_MIN - current_bank_min)


def grant_fits(current_bank_min: int, grant_min: int) -> bool:
    return grant_min <= cap_room(current_bank_min)


def duration_options(current_bank_min: int) -> list[int]:
    """30min→6h in 30-min steps, capped to remaining bank room."""
    room = cap_room(current_bank_min)
    return [m for m in range(30, 361, 30) if m <= room]
