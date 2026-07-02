"""core.shifts — the shift entity: materialize a real interval + resolve which shift an instant belongs to.

This is the heart of the model: a shift is (start_dt, end_dt) absolute instants. Overnight is NOT a special
case — it's just end_dt on the next day. No code here compares calendar dates for a decision.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db

_UTC = ZoneInfo("UTC")

# The binding tolerances: how far outside [start_dt, end_dt] an instant may fall and still
# belong to the shift. Shared by shift_for_instant (the bind) and _bind_shift's
# materialization gate (core.attendance) — they MUST stay one number or a shift could be
# materialized that can't bind, or bind-searched but never materialized.
EARLY_WINDOW_MIN = 120
LATE_WINDOW_MIN = 180


def shift_window(work_start: str, work_end: str, business_day, tz: str = "Asia/Phnom_Penh"):
    """PURE (no DB): the (start_dt, end_dt) UTC instants for a shift on `business_day`. work_start/work_end
    are 'HH:MM' in the tenant's tz. If end <= start the shift crosses midnight → end_dt is the NEXT day.
    Overnight, day, and a 24h shift all fall out of this with zero special-casing."""
    z = ZoneInfo(tz)
    d = business_day if isinstance(business_day, date) else date.fromisoformat(str(business_day))
    sh, sm = (int(x) for x in str(work_start).split(":")[:2])
    eh, em = (int(x) for x in str(work_end).split(":")[:2])
    start_local = datetime(d.year, d.month, d.day, sh, sm, tzinfo=z)
    end_day = d + timedelta(days=1) if (eh, em) <= (sh, sm) else d
    end_local = datetime(end_day.year, end_day.month, end_day.day, eh, em, tzinfo=z)
    return start_local.astimezone(_UTC), end_local.astimezone(_UTC)


def ensure_shift(org_id, staff_id, business_day, work_start, work_end,
                 tz: str = "Asia/Phnom_Penh", origin: str = "regular") -> dict:
    """Materialize (or fetch) the shift instance for (org, staff, business_day). The UNIQUE
    (org_id, staff_id, start_dt) is the ATOMIC CLAIM — concurrent callers can't create a duplicate
    instance. Returns the shift row."""
    start_dt, end_dt = shift_window(work_start, work_end, business_day, tz)
    bday = business_day if isinstance(business_day, date) else date.fromisoformat(str(business_day))
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO shifts (org_id, staff_id, start_dt, end_dt, business_day, origin)
                           VALUES (%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (org_id, staff_id, start_dt)
                           DO UPDATE SET end_dt=EXCLUDED.end_dt
                           RETURNING *""",
                        (org_id, staff_id, start_dt, end_dt, bday, origin))
            return dict(cur.fetchone())


def shift_for_instant(org_id, staff_id, now_dt: datetime,
                      early_window_min: int = EARLY_WINDOW_MIN,
                      late_window_min: int = LATE_WINDOW_MIN):
    """The shift the instant `now_dt` belongs to — found by INTERVAL, not by date: the shift whose window
    [start − early_window, end + late_window] contains now, nearest start as the tie-break. This IS the
    overnight-correct binding (a 2am instant lands inside last night's 21:00→06:00 interval), by
    construction. early_window allows an early check-in; late_window allows a slightly-late check-out
    (worked minutes are still capped at end_dt by the caller — lingering banks nothing)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT * FROM shifts
                           WHERE org_id=%s AND staff_id=%s
                             AND %s >= start_dt - make_interval(mins => %s)
                             AND %s <= end_dt + make_interval(mins => %s)
                           ORDER BY abs(extract(epoch FROM (start_dt - %s))) ASC
                           LIMIT 1""",
                        (org_id, staff_id, now_dt, early_window_min, now_dt, late_window_min, now_dt))
            r = cur.fetchone()
            return dict(r) if r else None
