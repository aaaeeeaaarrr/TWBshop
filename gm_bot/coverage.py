"""Coverage engine (session 28) — pure logic, no DB/Telegram.

Encodes the owner's requirements table (front/kitchen/bakery/bar/prep minimums by window & day,
push-high) and scores how SHORT-HANDED the shop is for a given expertise at a given time.
Powers: payback need-ranking, day-off-swap partner suggestions, the heatmap, Vannary-style
proactive recommendations. A person fills ONE station at a time; skills = where they CAN stand.
"""
from __future__ import annotations

from gm_bot.attendance import overlaps

# named windows (minutes-of-day; night wraps past midnight as 1260..1740 on the 24h+ line)
WINDOWS = [("morning", 360, 660), ("lunch", 660, 840), ("afternoon", 840, 1020),
           ("dinner", 1020, 1260), ("night", 1260, 1740)]
PREP_START, PREP_END = 600, 1140   # 10:00–19:00


def stations_for(expertise: set | list) -> set:
    """Which stations a person CAN fill from their expertise."""
    e = {x.lower() for x in (expertise or [])}
    out = set()
    if e & {"cashier", "service", "bar"}:
        out.add("front")
    if "kitchen" in e:
        out.add("kitchen")
    if "bakery" in e:
        out.add("bakery")
    if "prep" in e:
        out.add("prep")
    if "bar" in e:
        out.add("bar")
    return out


def window_target(window: str, day_abbr: str, station: str) -> int:
    """Target headcount (push-high) for a station in a window on a weekday."""
    if station == "front":
        return {"lunch": 4, "dinner": 4, "morning": 3, "afternoon": 3, "night": 1}.get(window, 0)
    if station == "kitchen":
        return {"lunch": 4, "dinner": 4, "morning": 3, "afternoon": 3}.get(window, 0)
    if station == "bakery":
        if window == "night":
            return 4 if day_abbr in ("Fri", "Sat") else 3
        return 0
    if station == "bar":
        return 1   # ≥1 always
    if station == "prep":
        return 2 if window in ("morning", "lunch", "afternoon", "dinner") else 0
    return 0


def _has_station(staff: dict, station: str) -> bool:
    return station in stations_for(staff.get("expertise") or [])


def on_duty(station: str, w_start: int, w_end: int, day_abbr: str,
            staff_list: list[dict], leave_names: set, to_min) -> int:
    """How many staff cover `station` during [w_start,w_end) on `day_abbr` —
    scheduled, not day-off, not on leave, with that station's expertise."""
    off_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    target_wd = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}[day_abbr]
    n = 0
    for s in staff_list:
        if (s.get("call_name") or s.get("canonical_name") or "").lower() in leave_names:
            continue
        if off_map.get((s.get("day_off") or "")[:3].lower()) == target_wd:
            continue
        if not _has_station(s, station):
            continue
        ws, we = to_min(s.get("work_start")), to_min(s.get("work_end"))
        if ws is None or we is None:
            continue
        if overlaps(ws, we, w_start, w_end % 1440):
            n += 1
    return n


def shortfall(station: str, window: str, w_start: int, w_end: int, day_abbr: str,
              staff_list: list[dict], leave_names: set, to_min) -> int:
    return max(0, window_target(window, day_abbr, station)
               - on_duty(station, w_start, w_end, day_abbr, staff_list, leave_names, to_min))


def slot_score(expertise: set | list, slot_start: int, slot_end: int, day_abbr: str,
               staff_list: list[dict], leave_names: set, to_min) -> int:
    """Neediness of a payback/OT slot for THIS person = the biggest shortfall, across the
    windows the slot overlaps, among the stations they can fill. Higher = book here."""
    stations = stations_for(expertise)
    best = 0
    for wname, ws, we in WINDOWS:
        if not overlaps(slot_start, slot_end % 1440, ws, we % 1440):
            continue
        for st in stations:
            best = max(best, shortfall(st, wname, ws, we, day_abbr, staff_list, leave_names, to_min))
    return best
