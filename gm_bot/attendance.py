"""
Private-DM attendance system — pure logic, no DB/AI/Telegram.

Covers the geometry + scheduling the new system needs:
  - geofence: is a shared location inside the 200m work zone?
  - availability: who is working at a given window on a given day (excluding their
    day-off and anyone on AL that day) — for the senior-approval message.
  - lateness: is the staff messaging before their shift, or after it started?
  - outside-budget: have they exceeded the 30-min-out allowance?

Times are handled as minutes-from-midnight. The CSV importer turns 'HH:MM' into these.
"""
from __future__ import annotations

import math
import re

_KHMER_RE = re.compile("[ក-៿᧠-᧿]")


def strip_khmer(text: str) -> str:
    """Return an English-only version of a bilingual message (the OWNER doesn't want Khmer; staff
    still get the full bilingual text). Handles the two house styles:
      - 'English line\\nKhmer line'  → drop the Khmer line
      - 'English · ខ្មែរ' (or ' — ', ' | ') → keep the English half."""
    if not text or not _KHMER_RE.search(text):
        return text
    out = []
    for line in text.split("\n"):
        if not _KHMER_RE.search(line):
            out.append(line)
            continue
        kept = None
        for sep in (" · ", " — ", " | "):
            if sep in line:
                left = line.split(sep, 1)[0].rstrip()
                if left and not _KHMER_RE.search(left) and re.search(r"[A-Za-z0-9]", left):
                    kept = left
                break
        if kept is not None:
            out.append(kept)
        # else: a pure-Khmer translation line → drop it
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()

# The Wine Bakery coordinates (same as the B2B bakery origin).
TWB_LAT = 11.5387774
TWB_LNG = 104.9147998
WORK_ZONE_RADIUS_M = 150      # owner session 38 (Jun 16): widened 100->150 — Por's phone couldn't
                             # check in at 100m (GPS drift). (was 200->100 in session 28; Delis TBD —
                             # staff live in the building there; revisit when Delis is integrated)
OUTSIDE_BUDGET_MIN = 30       # ⚠️ DEAD/vestigial (session 28): the 30-min outside-zone allowance
                             # belonged to the WHOLE-SHIFT tracking model that was DROPPED for
                             # check-in-only. outside_exceeded() is unused by the live design — kept
                             # only so the existing test passes. Do NOT wire mid-shift outside-tracking.


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def in_work_zone(lat: float, lng: float, radius_m: float = WORK_ZONE_RADIUS_M) -> bool:
    """True if a point is within the work zone of TWB."""
    return haversine_m(lat, lng, TWB_LAT, TWB_LNG) <= radius_m


def days_due(days: list[str], deducted: list[str], today_iso: str, reason: str | None) -> list[str]:
    """Which planned-AL days should be deducted now: the date has PASSED (day < today),
    wasn't deducted yet, and the leave isn't PH compensation (never deducted). Pure."""
    if reason and reason.upper().startswith("PH"):
        return []
    return sorted(d for d in days if d < today_iso and d not in deducted)


def to_min(hhmm) -> int | None:
    """'HH:MM' (or 'H:MM', or an int already) -> minutes from midnight. None if unparseable."""
    if hhmm is None:
        return None
    if isinstance(hhmm, (int, float)):
        return int(hhmm)
    s = str(hhmm).strip().lower().replace(" ", "")
    if not s:
        return None
    ampm = None
    if s.endswith("am") or s.endswith("pm"):
        ampm = s[-2:]; s = s[:-2]
    try:
        if ":" in s:
            h, m = s.split(":", 1); h, m = int(h), int(m)
        else:
            h, m = int(s), 0
    except ValueError:
        return None
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    return (h % 24) * 60 + (m % 60)


def remaining_shift_min(ws_min: int, shift_min: int, business_day: str, now_dt, tz: str = "Asia/Phnom_Penh") -> int:
    """Minutes from `now_dt` to the shift END — the unworked tail a leave-early staffer will miss ("pay-back
    from now"). Overnight-aware via the duration (end = start + shift_min). Clamped to [0, shift_min].
    Pure (no DB)."""
    from datetime import datetime as _dt, date as _date, timedelta as _td
    from zoneinfo import ZoneInfo
    base = _dt.combine(_date.fromisoformat(str(business_day)), _dt.min.time(), tzinfo=ZoneInfo(tz))
    end = base + _td(minutes=int(ws_min) + int(shift_min))
    return max(0, min(int(shift_min), round((end - now_dt).total_seconds() / 60.0)))


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Do two minute-ranges overlap? (handles overnight shifts where end < start)."""
    def expand(s, e):
        return [(s, e)] if e >= s else [(s, 1440), (0, e)]
    for s1, e1 in expand(a_start, a_end):
        for s2, e2 in expand(b_start, b_end):
            if s1 < e2 and s2 < e1:
                return True
    return False


def available_staff(target_start: int, target_end: int, day: str,
                    schedules: list[dict], on_al_names: set | None = None) -> list[str]:
    """Names working during [target_start, target_end) on `day`, excluding their day-off
    and anyone on AL that day. `schedules` = [{name, work_start, work_end, day_off}].
    Times are minutes-from-midnight; day/day_off compared case-insensitively."""
    on_al = {n.lower() for n in (on_al_names or set())}
    out = []
    for s in schedules:
        if (s.get("name") or "").lower() in on_al:
            continue
        if (s.get("day_off") or "").strip().lower() == (day or "").strip().lower():
            continue
        ws, we = s.get("work_start"), s.get("work_end")
        if ws is None or we is None:
            continue
        if overlaps(target_start, target_end, ws, we):
            out.append(s["name"])
    return out


def lateness_kind(now_min: int, shift_start_min: int) -> str:
    """'before_shift' if they're warning ahead of time; 'already_started' if the shift
    has begun (then the GM accepts but reminds them to warn earlier next time)."""
    return "before_shift" if now_min < shift_start_min else "already_started"


def outside_exceeded(total_out_min: float, budget: int = OUTSIDE_BUDGET_MIN) -> bool:
    """True once cumulative time outside the zone passes the allowance."""
    return total_out_min > budget
