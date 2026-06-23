"""Settle shadow (platform step 3) — proves: (1) the UNCAPPED core.settle call the hook makes equals
live's gm_bot.ot.settle_shift on every input (so a correct settle never false-alarms); (2) compare_settle
records agree/mismatch on the money split; (3) record_settle_info logs an unmodeled payback-slot as
non-alarming; (4) shadow_settle is gated-off-noop, isolated (never raises into live), and routes
normal→compare vs payback-slot→info. Real staging DB for the recorder tests; cleaned up."""
import core.shadow_hook as sh
import core.shadow as csh
from core.settle import settle_shift as core_settle
from gm_bot.ot import settle_shift as live_settle
from core.shadow import compare_settle, record_settle_info, comparison_stats
from shared.database import _db

ORG = "test_settle"
STAFF = {"id": 1, "call_name": "X", "canonical_name": "X"}


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM shadow_comparisons WHERE org_id=%s", (ORG,))


def test_core_settle_uncapped_matches_live():
    """The hook calls core.settle UNCAPPED → it must equal live's gm_bot.ot.settle_shift (ot_banked,
    pb_cleared) on every input, else the shadow would flag correct settles. Drift-guard."""
    for worked, normal, pb in [(540, 540, 0), (600, 540, 0), (700, 540, 120), (540, 540, 300),
                               (800, 480, 1000), (0, 540, 0), (540, 600, 50), (900, 540, 200)]:
        l_ot, l_pb, _ = live_settle(worked, normal, pb)
        c = core_settle(worked, normal, pb, bank_min=0, bank_cap_min=10 ** 9)
        assert (c["ot_banked"], c["pb_cleared"]) == (l_ot, l_pb), (worked, normal, pb, c, (l_ot, l_pb))


def test_compare_settle_agree_and_mismatch():
    _clean()
    try:
        same = {"worked": 600, "ot_banked": 60, "pb_cleared": 0}
        assert compare_settle(ORG, 1, same, dict(same)) is True
        assert compare_settle(ORG, 1, {"worked": 600, "ot_banked": 60, "pb_cleared": 0},
                              {"worked": 600, "ot_banked": 0, "pb_cleared": 60}) is False   # split differs
        s = comparison_stats(ORG)
        assert (s["total"], s["agree"], s["mismatch"]) == (2, 1, 1)
    finally:
        _clean()


def test_record_settle_info_never_alarms():
    _clean()
    try:
        record_settle_info(ORG, 1, {"worked": 120, "reason": "payback slot"}, "ext-worked not modeled")
        s = comparison_stats(ORG)
        assert s["total"] == 1 and s["mismatch"] == 0   # informational → counted, never a false alarm
    finally:
        _clean()


def test_shadow_settle_gated_off_is_noop(monkeypatch):
    monkeypatch.setattr(sh, "shadow_enabled", lambda: False)
    rec = []
    monkeypatch.setattr(csh, "compare_settle", lambda *a, **k: rec.append(a) or True)
    sh.shadow_settle(STAFF, "2026-06-23", 540, 0, "redefine", 600, 60, 0)
    assert rec == []                                   # OFF → core never invoked, nothing recorded


def test_shadow_settle_never_raises_into_live(monkeypatch):
    monkeypatch.setattr(sh, "shadow_enabled", lambda: True)
    monkeypatch.setattr(csh, "compare_settle", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    sh.shadow_settle(STAFF, "2026-06-23", 540, 0, "redefine", 600, 60, 0)   # must NOT raise


def test_shadow_settle_routes_normal_vs_payback(monkeypatch):
    monkeypatch.setattr(sh, "shadow_enabled", lambda: True)
    comp, info = [], []
    monkeypatch.setattr(csh, "compare_settle", lambda *a, **k: comp.append(a) or True)
    monkeypatch.setattr(csh, "record_settle_info", lambda *a, **k: info.append(a) or None)
    sh.shadow_settle(STAFF, "2026-06-23", 540, 0, "redefine", 600, 60, 0)        # normal → compared
    assert comp and not info
    comp.clear()
    sh.shadow_settle(STAFF, "2026-06-23", 0, 120, "payback slot", 120, 0, 120)   # payback → informational
    assert info and not comp
