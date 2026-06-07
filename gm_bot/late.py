"""Late-declaration pure logic (session 28). No DB/Telegram.

Late = TIME only (never AL). Staff declare a time → reason → Supervisors heads-up; the actual
debt is measured at arrival by location (in checkin/payback). Gated behind attendance_live.
"""
from __future__ import annotations

GRACE_MIN = 5


def shift_len(ws_min: int, we_min: int) -> int:
    return (we_min - ws_min) % 1440 or 1440


def late_offsets(ws_min: int, we_min: int) -> list[int]:
    """Minutes-after-start the staff can declare, capped 2h before shift end:
    +5,10,15,20,30,45,60,75,90,120, then every 30 min."""
    cap = shift_len(ws_min, we_min) - 120
    out = [o for o in (5, 10, 15, 20, 30, 45, 60, 75, 90, 120) if o <= cap]
    t = 150
    while t <= cap:
        out.append(t)
        t += 30
    return out


def declared_minutes_late(declared_min: int, ws_min: int) -> int:
    """How late the DECLARED arrival is vs shift start (for the heads-up text)."""
    return (declared_min - ws_min) % 1440
