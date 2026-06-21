"""core.shadow_hook — the SAFE bridge. Proves: gated off = no-op (never touches the core); never raises
into the live flow (isolation); when on, records a comparison and normalizes the live 'ontime' vocab."""
import core.shadow_hook as sh
import core.attendance as catt
import core.shadow as csh

STAFF = {"id": 1, "work_start": "21:00", "work_end": "06:00", "call_name": "X"}


def test_disabled_is_noop(monkeypatch):
    calls = []
    monkeypatch.setattr(sh, "shadow_enabled", lambda: False)
    monkeypatch.setattr(catt, "check_in", lambda *a, **k: calls.append(1) or {})
    sh.shadow_checkin(STAFF, None, "late", 5, 0)
    assert calls == []                       # OFF → the core is never even invoked


def test_never_raises_into_live(monkeypatch):
    monkeypatch.setattr(sh, "shadow_enabled", lambda: True)
    monkeypatch.setattr(catt, "check_in", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("core broke")))
    # must NOT raise — a shadow failure can never break a live check-in
    sh.shadow_checkin(STAFF, None, "late", 5, 0)


def test_enabled_records_and_normalizes(monkeypatch):
    monkeypatch.setattr(sh, "shadow_enabled", lambda: True)
    monkeypatch.setattr(catt, "check_in",
                        lambda *a, **k: {"bound": True, "state": "on_time", "minutes_late": 0, "minutes_early": 0})
    rec = []
    monkeypatch.setattr(csh, "compare_checkin", lambda *a, **k: rec.append(a) or True)
    sh.shadow_checkin(STAFF, None, "ontime", 0, 0)   # live vocab 'ontime'
    assert rec, "compare_checkin must be called when shadow is on"
    assert rec[0][2] == "on_time"                     # 'ontime' normalized → 'on_time' (no false mismatch)
