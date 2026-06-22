"""core.schedule — DRIFT-GUARD parity with live's resolver (gm_bot.attendance_ui.resolve_day) across the
full precedence space. The platform carries its own resolver brain; this locks it to live so the one
decision every reader depends on can't diverge."""
from datetime import date

import core.schedule as cs
import gm_bot.attendance_ui as ui

P = {"id": 99, "work_start": "06:00", "work_end": "15:00", "day_off": "Sunday"}
WS, WE, DAY_OFF_WD = 360, 900, 6   # Sunday = weekday 6
MON, SUN = "2026-06-22", "2026-06-21"   # Monday (working) / Sunday (day off)


def _ctx(al=(), sick=(), special=(), redefines=None, overrides=None):
    return {"al": {99: set(al)}, "sick": {99: set(sick)}, "special": {99: set(special)},
            "redefines": redefines or {}, "overrides": overrides or {}}


def _mods(al=False, sick=False, special=False, redefine=None, override=None):
    return {"al": al, "sick": sick, "special": special, "redefine": redefine, "override": override}


def _cmp(day_iso, ctx, mods):
    live = ui.resolve_day(P, day_iso, ctx)
    core = cs.resolve_day(mods, WS, WE, DAY_OFF_WD, date.fromisoformat(day_iso).weekday())
    assert {k: live[k] for k in ("working", "reason", "start_min", "end_min")} == core, (day_iso, live, core)


def test_resolver_precedence_parity():
    RD = {(99, MON): (1051, 1411)}
    _cmp(MON, _ctx(), _mods())                                            # normal
    _cmp(SUN, _ctx(), _mods())                                            # weekly day-off
    _cmp(MON, _ctx(al=[MON]), _mods(al=True))                             # AL → away
    _cmp(MON, _ctx(sick=[MON]), _mods(sick=True))                         # sick → away
    _cmp(MON, _ctx(special=[MON]), _mods(special=True))                   # special → away
    _cmp(MON, _ctx(redefines=RD), _mods(redefine=(1051, 1411)))          # redefine → moved times
    _cmp(MON, _ctx(overrides={(99, MON): "off"}), _mods(override="off"))  # swap off
    _cmp(SUN, _ctx(overrides={(99, SUN): "work"}), _mods(override="work"))# swap onto a day-off


def test_resolver_precedence_order_parity():
    # leave BEATS a redefine (protected)
    _cmp(MON, _ctx(al=[MON], redefines={(99, MON): (1051, 1411)}),
         _mods(al=True, redefine=(1051, 1411)))
    # a redefine BEATS the weekly day-off (works a normally-off Sunday)
    _cmp(SUN, _ctx(redefines={(99, SUN): (1051, 1411)}), _mods(redefine=(1051, 1411)))
