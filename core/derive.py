"""core.derive — the SELF-DERIVING resolver: the core decides what a day is from its OWN state
(core_day_overrides), with no live to feed it. This is what cut-over needs (post-cut-over live is gone).

During the shadow phase the overrides can be SYNCED from live (sync_from_live); the clean platform
creates them natively (set_override) from its own approval flows. Either way resolve() folds the day's
overrides into the modifiers and runs the parity-locked core.schedule.resolve_day brain.
"""
from datetime import date

from shared.database import _db
from core.schedule import resolve_day


def set_override(org_id, staff_id, day_iso, kind, start_min=None, end_min=None, source="native") -> None:
    """Record one day modifier natively (al/sick/special/redefine/swap_off/swap_work)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_day_overrides (org_id, staff_id, day, kind, start_min, end_min, source) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (org_id, staff_id, day, kind) "
                        "DO UPDATE SET start_min=EXCLUDED.start_min, end_min=EXCLUDED.end_min, source=EXCLUDED.source",
                        (org_id, staff_id, day_iso, kind, start_min, end_min, source))


def clear_overrides(org_id, staff_id, day_iso) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM core_day_overrides WHERE org_id=%s AND staff_id=%s AND day=%s",
                        (org_id, staff_id, day_iso))


def _modifiers(org_id, staff_id, day_iso) -> dict:
    mods = {"al": False, "sick": False, "special": False, "redefine": None, "override": None}
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT kind, start_min, end_min FROM core_day_overrides "
                        "WHERE org_id=%s AND staff_id=%s AND day=%s", (org_id, staff_id, day_iso))
            for r in cur.fetchall():
                k = r["kind"]
                if k in ("al", "sick", "special"):
                    mods[k] = True
                elif k == "redefine":
                    mods["redefine"] = (r["start_min"], r["end_min"])
                elif k == "swap_off":
                    mods["override"] = "off"
                elif k == "swap_work":
                    mods["override"] = "work"
    return mods


def resolve(org_id, staff_id, day_iso, base_start_min, base_end_min, day_off_weekday) -> dict:
    """Self-derive the day from the core's OWN overrides → the parity-locked precedence. Same result as
    being fed live's resolve_day, but sourced from core state (cut-over-ready)."""
    return resolve_day(_modifiers(org_id, staff_id, day_iso), base_start_min, base_end_min,
                       day_off_weekday, date.fromisoformat(day_iso).weekday())
