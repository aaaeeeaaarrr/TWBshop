"""core (new platform) — check-in/out slice. Proves: interval-only verdicts (incl. OVERNIGHT, the case
that broke the old date-keyed model), idempotency, multi-tenant isolation, and the shadow comparator.
Real staging DB; cleaned up. PP = UTC+7."""
from datetime import datetime, timezone

import pytest

import core.db as cdb
from core.shifts import shift_window, ensure_shift, shift_for_instant
from core.attendance import check_in, check_out
from core.shadow import compare_checkin
from shared.database import _db

UTC = timezone.utc
ORG = "test_shadow"
ORG2 = "test_shadow2"


def _utc(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _setup():
    cdb.init_core_db()
    cdb.ensure_org(ORG, "Test", "Asia/Phnom_Penh")
    cdb.ensure_org(ORG2, "Test2", "Asia/Phnom_Penh")
    _clean()
    yield
    _clean()


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            for t in ("attendance_events", "shifts", "shadow_comparisons"):
                cur.execute("DELETE FROM %s WHERE org_id IN (%%s,%%s)" % t, (ORG, ORG2))


# ── pure window math (no DB) ────────────────────────────────────────────────
def test_shift_window_overnight_crosses_midnight():
    s, e = shift_window("21:00", "06:00", "2026-06-21", "Asia/Phnom_Penh")
    assert s == _utc(2026, 6, 21, 14, 0)    # 21:00 PP -> 14:00 UTC
    assert e == _utc(2026, 6, 21, 23, 0)    # 06:00 PP next day -> 23:00 UTC same UTC day. 9h interval.
    assert (e - s).total_seconds() == 9 * 3600


def test_shift_window_day_shift_same_day():
    s, e = shift_window("06:00", "15:00", "2026-06-21", "Asia/Phnom_Penh")
    assert s == _utc(2026, 6, 20, 23, 0) and e == _utc(2026, 6, 21, 8, 0)


# ── overnight binding — THE proof the date-class bug is gone by construction ─
def test_overnight_checkin_after_midnight_binds_to_prior_day_shift():
    # work 21:00-06:00; a check-in at 00:30 PP Jun 22 (17:30 UTC Jun 21) must bind to the Jun-21 shift
    r = check_in(ORG, 999001, _utc(2026, 6, 21, 17, 30), "21:00", "06:00")
    assert r["bound"] is True
    assert r["business_day"] == "2026-06-21"          # NOT Jun-22 — the overnight-correct binding
    assert r["state"] == "late"
    assert r["minutes_late"] == 210                   # 17:30 - 14:00 UTC = 3h30 late


def test_overnight_checkin_early_before_start():
    # 20:55 PP Jun 21 (13:55 UTC) = 5 min before the 21:00 start
    r = check_in(ORG, 999002, _utc(2026, 6, 21, 13, 55), "21:00", "06:00")
    assert r["bound"] and r["state"] == "early" and r["minutes_early"] == 5 and r["business_day"] == "2026-06-21"


# ── day-shift verdicts ──────────────────────────────────────────────────────
def test_day_shift_on_time_and_late():
    on = check_in(ORG, 999003, _utc(2026, 6, 20, 23, 0), "06:00", "15:00")     # exactly 06:00 PP
    assert on["state"] == "on_time" and on["minutes_late"] == 0
    late = check_in(ORG, 999004, _utc(2026, 6, 20, 23, 12), "06:00", "15:00")  # 06:12 PP
    assert late["state"] == "late" and late["minutes_late"] == 12


def test_grace_and_early_threshold_match_live():
    # within GRACE (≤5 late) / below EARLY bonus (<5 early) → on_time with 0/0, exactly like live
    assert check_in(ORG, 999010, _utc(2026, 6, 20, 23, 3), "06:00", "15:00")["state"] == "on_time"   # 3 late
    assert check_in(ORG, 999011, _utc(2026, 6, 20, 22, 57), "06:00", "15:00")["state"] == "on_time"  # 3 early
    assert check_in(ORG, 999012, _utc(2026, 6, 20, 23, 5), "06:00", "15:00")["state"] == "on_time"   # 5 late (not >5)
    r6 = check_in(ORG, 999013, _utc(2026, 6, 20, 23, 6), "06:00", "15:00")                            # 6 late
    assert r6["state"] == "late" and r6["minutes_late"] == 6
    r5e = check_in(ORG, 999014, _utc(2026, 6, 20, 22, 55), "06:00", "15:00")                          # 5 early
    assert r5e["state"] == "early" and r5e["minutes_early"] == 5


def test_seconds_are_truncated_like_live():
    # 06:05:50 PP = 5 min 50 s late → live truncates seconds → 5 late → within grace → on_time
    assert check_in(ORG, 999015, _utc(2026, 6, 20, 23, 5, 50), "06:00", "15:00")["state"] == "on_time"


# ── idempotency (one check-in per shift) ────────────────────────────────────
def test_checkin_idempotent():
    when = _utc(2026, 6, 21, 13, 55)
    first = check_in(ORG, 999005, when, "21:00", "06:00")
    again = check_in(ORG, 999005, when, "21:00", "06:00")
    assert first["duplicate"] is False and again["duplicate"] is True
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM attendance_events WHERE shift_id=%s AND type='checked_in'",
                        (first["shift_id"],))
            assert cur.fetchone()["n"] == 1            # exactly one event despite two calls


# ── multi-tenant isolation ──────────────────────────────────────────────────
def test_tenant_isolation():
    ensure_shift(ORG, 1, "2026-06-21", "21:00", "06:00")
    assert shift_for_instant(ORG, 1, _utc(2026, 6, 21, 15, 0)) is not None
    assert shift_for_instant(ORG2, 1, _utc(2026, 6, 21, 15, 0)) is None   # other tenant: nothing


# ── checkout worked-minutes ─────────────────────────────────────────────────
def test_checkout_worked_capped_at_end():
    check_in(ORG, 999006, _utc(2026, 6, 21, 14, 0), "21:00", "06:00")           # on-time 21:00
    out = check_out(ORG, 999006, _utc(2026, 6, 21, 23, 30), "21:00", "06:00")   # 06:30 PP — past 06:00 end
    assert out["bound"] and out["worked_min"] == 9 * 60   # capped at the 9h shift end, not 9h30


# ── shadow comparator ───────────────────────────────────────────────────────
def test_comparator_agree_and_mismatch():
    res = check_in(ORG, 999007, _utc(2026, 6, 21, 13, 55), "21:00", "06:00")   # early 5
    assert compare_checkin(ORG, 999007, "early", 0, 5, res) is True            # live agrees
    assert compare_checkin(ORG, 999007, "late", 30, 0, res) is False           # live differs -> recorded
