"""Go-live grace (owner, Jun 16): a shift that STARTED before we flipped attendance_live must be exempt
from no-show/late penalties — the staff couldn't have checked in (the system wasn't live). The grace is
keyed on an `attendance_live_at` stamp set by /golive; with no stamp it's fully inert (pre-go-live AND
the normal steady state), and it self-expires after the first day (later shifts all start after it)."""
from gm_bot import bot


def test_golive_grace_keys_on_the_stamp(monkeypatch):
    live_iso = bot._shift_start_dt("2026-07-01", 600).isoformat()   # went live at 10:00

    # no stamp -> inert (the normal state): nothing is ever graced
    monkeypatch.setattr(bot, "gm_get_state", lambda k: None)
    assert bot._golive_grace(bot._shift_start_dt("2026-07-01", 360)) is False

    # stamp present: a shift that began BEFORE the flip is graced; one that began after is not
    monkeypatch.setattr(bot, "gm_get_state",
                        lambda k: live_iso if k == "attendance_live_at" else None)
    assert bot._golive_grace(bot._shift_start_dt("2026-07-01", 360)) is True    # 6:00 < 10:00 -> graced
    assert bot._golive_grace(bot._shift_start_dt("2026-07-01", 600)) is False   # 10:00 == live -> not before
    assert bot._golive_grace(bot._shift_start_dt("2026-07-01", 840)) is False   # 14:00 > 10:00 -> normal
    # next day: every shift starts well after the stamp -> grace never triggers (self-expires)
    assert bot._golive_grace(bot._shift_start_dt("2026-07-02", 360)) is False


def test_golive_grace_bad_stamp_is_safe(monkeypatch):
    monkeypatch.setattr(bot, "gm_get_state", lambda k: "not-a-date")
    assert bot._golive_grace(bot._shift_start_dt("2026-07-01", 360)) is False


def test_shift_start_dt():
    d = bot._shift_start_dt("2026-07-01", 360)   # 06:00
    assert d.hour == 6 and d.minute == 0 and d.date().isoformat() == "2026-07-01"
    assert d.tzinfo is not None                  # PP-tz aware (so comparisons never crash)


def test_on_shift_now_picks_only_the_running_shift(monkeypatch):
    """_on_shift_now (used by /broadcast + /golivestatus) returns only staff whose window covers NOW."""
    from gm_bot import attendance_ui as ui
    now = bot._shift_start_dt("2026-07-01", 600)          # pretend it's 10:00 today
    monkeypatch.setattr(bot, "_now_pp", lambda: now)
    on = {"id": 1, "canonical_name": "On", "call_name": "On", "org": "TWB"}
    off = {"id": 2, "canonical_name": "Off", "call_name": "Off", "org": "TWB"}
    delis = {"id": 3, "canonical_name": "Del", "call_name": "Del", "org": "DELIS"}
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [on, off, delis])
    monkeypatch.setattr(ui, "_day_context", lambda days: {})

    def _resolve(p, iso, ctx=None):
        if p["id"] == 1 and iso == "2026-07-01":         # On works 08:00–17:00 today → covers 10:00
            return {"working": True, "start_min": 480, "end_min": 1020}
        return {"working": False}                        # Off is away; Del is filtered by org anyway

    monkeypatch.setattr(ui, "resolve_day", _resolve)
    res = bot._on_shift_now()
    ids = [s["id"] for s, *_ in res]
    assert ids == [1]                                    # only the running TWB shift; Off + Delis excluded
    assert res[0][1] == "2026-07-01" and res[0][2] == 480   # carries shift_date + start for the session lookup
