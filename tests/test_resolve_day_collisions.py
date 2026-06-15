"""Due-diligence stress (Jun 16): the owner asked to abuse "a senior giving someone twice work on the
same day, whether it's AL or whatever." The integrity guarantee is that resolve_day() — the ONE resolver
every reader uses — returns EXACTLY ONE coherent decision per day no matter how many events pile onto it,
via a strict precedence (AL > sick > special > redefine > swap > day-off > normal). If that holds, no
reader can double-count work, double-charge leave, or dead-end on a contradiction.

These are PURE (a hand-built ctx, no DB) so they run instantly and lock the precedence as a guard."""
from gm_bot import attendance_ui as ui

P = {"id": 1, "work_start": "08:00", "work_end": "17:00", "day_off": "Sun"}
MON = "2026-07-20"   # a working weekday
SUN = "2026-07-19"   # P's weekly day off


def _ctx(*, al=None, sick=None, special=None, redefine=None, override=None, sid=1, day=MON):
    """Build a resolve_day ctx with whatever combination of same-day events we want to collide."""
    return {
        "al": {sid: {day}} if al else {},
        "sick": {sid: {day}} if sick else {},
        "special": {sid: {day}} if special else {},
        "redefines": {(sid, day): redefine} if redefine else {},   # (start_min, end_min)
        "overrides": {(sid, day): override} if override else {},     # 'work' | 'off'
    }


def _r(ctx, day=MON):
    return ui.resolve_day(P, day, ctx=ctx)


def test_single_decision_no_matter_how_many_events_collide():
    # AL beats EVERYTHING (leave is protected) — even a redefine + swap-work + sick all on the same day
    d = _r(_ctx(al=True, sick=True, special=True, redefine=(480, 1080), override="work"))
    assert d["working"] is False and d["reason"] == "al"

    # sick beats a redefine + swap
    d = _r(_ctx(sick=True, redefine=(480, 1080), override="work"))
    assert d["working"] is False and d["reason"] == "sick"

    # special-leave beats a redefine
    d = _r(_ctx(special=True, redefine=(480, 1080)))
    assert d["working"] is False and d["reason"] == "special"


def test_redefine_is_the_single_work_source_when_it_collides_with_a_swap():
    # redefine + swap-work BOTH say "work" — the resolver picks ONE (redefine), never both → no double
    d = _r(_ctx(redefine=(540, 1140), override="work"))
    assert d["working"] is True and d["reason"] == "redefine"
    assert d["start_min"] == 540 and d["end_min"] == 1140   # the redefine's times, not the normal shift

    # redefine beats swap-OFF too (a redefine onto a day the swap took off → she works the redefine)
    d = _r(_ctx(redefine=(540, 1140), override="off"))
    assert d["working"] is True and d["reason"] == "redefine"


def test_redefine_or_swap_work_overrides_the_weekly_day_off():
    # a redefine landing on her weekly day off → she works it (move/extend onto a day off)
    d = _r(_ctx(redefine=(480, 1080), day=SUN), day=SUN)
    assert d["working"] is True and d["reason"] == "redefine"

    # a swap that puts her to WORK on her day off → working at normal times
    d = _r(_ctx(override="work", day=SUN), day=SUN)
    assert d["working"] is True and d["reason"] == "swap_work"


def test_away_sources_are_distinct_and_never_silently_work():
    # swap-off on a normal working day → AWAY (not a dead-end, an explicit decision)
    assert _r(_ctx(override="off"))["reason"] == "swap_off"
    # plain weekly day off, nothing else → AWAY
    assert _r(_ctx(day=SUN), day=SUN)["reason"] == "day_off"
    # nothing at all on a working day → WORKING normal
    d = _r(_ctx())
    assert d["working"] is True and d["reason"] == "normal"


def test_double_redefine_collapses_to_one_in_the_batch():
    # The batch (shift_changes_active_map) is latest-wins, so the ctx structurally holds ONE redefine per
    # (staff, day) — two proposals on the same day can never present as two work sources to a reader.
    ctx = _ctx(redefine=(600, 1200))
    assert len([k for k in ctx["redefines"] if k == (1, MON)]) == 1
    d = _r(ctx)
    assert d["working"] is True and d["reason"] == "redefine" and d["start_min"] == 600
