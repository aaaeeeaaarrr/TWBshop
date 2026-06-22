"""core.schedule — THE schedule resolver brain (channel-agnostic). "What is this person doing on a day?"
ONE resolver so every reader (verdict · settle · no-show · audit) can't drift. Precedence, highest first:

  1. leave — approved AL / active sick / special-leave  → AWAY (PROTECTED, beats a redefine)
  2. shift redefine (senior/auto, latest-wins)          → WORKING at the moved [start,end] (beats day-off)
  3. day-off swap override ('off' away / 'work' on)
  4. weekly day-off                                      → AWAY
  5. normal schedule                                     → WORKING

Parity with gm_bot.attendance_ui.resolve_day's precedence, drift-guarded by tests/test_core_schedule.py.
PURE: the caller supplies the day's MODIFIERS — the platform derives them from its own events (shift_moved,
leave_granted…); the shadow is fed them from live. This is the brain; deriving the modifiers is the wiring.
"""


def resolve_day(modifiers: dict, base_start_min, base_end_min, day_off_weekday, weekday) -> dict:
    """modifiers: {al, sick, special: bool · redefine: (start_min, end_min) | None · override: 'off'/'work'/None}.
    Returns {working, reason, start_min, end_min}. Matches live's precedence exactly."""
    if modifiers.get("al"):
        return {"working": False, "reason": "al", "start_min": None, "end_min": None}
    if modifiers.get("sick"):
        return {"working": False, "reason": "sick", "start_min": None, "end_min": None}
    if modifiers.get("special"):
        return {"working": False, "reason": "special", "start_min": None, "end_min": None}
    rd = modifiers.get("redefine")
    if rd:
        return {"working": True, "reason": "redefine", "start_min": rd[0], "end_min": rd[1]}
    ov = modifiers.get("override")
    if ov == "off":
        return {"working": False, "reason": "swap_off", "start_min": None, "end_min": None}
    if ov == "work":
        return {"working": True, "reason": "swap_work", "start_min": base_start_min, "end_min": base_end_min}
    if day_off_weekday is not None and day_off_weekday == weekday:
        return {"working": False, "reason": "day_off", "start_min": None, "end_min": None}
    return {"working": True, "reason": "normal", "start_min": base_start_min, "end_min": base_end_min}
