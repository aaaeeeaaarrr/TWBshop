"""W3 #5 foundation — the standalone builder-monitor sweep (scripts/builder_monitor.py).

Guards:
  • DRIFT — the lean re-implemented dedupe helpers are byte-identical to the gm_bot.bot originals
    (`_watchdog_delta` / `_sentinel_new_alarms`), so the two copies can't silently diverge.
  • READ-ONLY — a DRY-RUN (default) persists NOTHING (no sink write, no state write, no Monitor send).
  • ROUTING — with --send, a NEW alarm is persisted to the sink AND DM'd to the Monitor, and the dedupe
    state is advanced so a repeat sweep is silent.
INERT: the module is additive, not scheduled/deployed; the gm bot keeps its own jobs until the owner cuts over.
"""
import scripts.builder_monitor as bm


# ── drift-guard parity vs the gm_bot.bot originals ───────────────────────────────
def test_watchdog_delta_parity():
    from gm_bot.bot import _watchdog_delta
    for prev, probs in [(None, []), ("[]", ["a"]), ('["a","b"]', ["b", "c"]), ('["x"]', []), ("corrupt", ["a"])]:
        assert bm.watchdog_delta(prev, probs) == _watchdog_delta(prev, probs), (prev, probs)


def test_sentinel_new_parity():
    """Identical dedupe RESULT on every VALID state (the only state either side ever writes — both json.dumps).
    The standalone additionally hardens a corrupt prev (returns 'none seen') where the gm original would raise;
    that path is unreachable in practice, so it's an intentional superset, not drift."""
    from gm_bot.bot import _sentinel_new_alarms
    found = [{"flow": "f1", "key": "k1", "severity": "warn", "detail": "d1"},
             {"flow": "f2", "key": "k2", "severity": "critical", "detail": "d2"}]
    for prev in [None, "[]", '["f1:k1"]', '["f1:k1","f2:k2"]']:
        assert bm.sentinel_new(found, prev) == _sentinel_new_alarms(found, prev), prev
    assert bm.sentinel_new(found, "corrupt")[0] == found          # standalone survives a corrupt prev


# ── read-only dry-run + routing ─────────────────────────────────────────────────
def _canned(monkeypatch, audit, sentinel, prev=""):
    monkeypatch.setattr(bm, "sweep_org", lambda org: {"audit": audit, "sentinel": sentinel})
    monkeypatch.setattr(bm, "all_orgs", lambda: ["twb"])
    import shared.database as sd
    monkeypatch.setattr(sd, "gm_get_state", lambda k: prev)


def test_dryrun_persists_nothing(monkeypatch):
    _canned(monkeypatch, ["problem-1"], [{"flow": "f", "key": "k", "severity": "warn", "detail": "d"}])
    import shared.database as sd
    import gm_bot.alarms as al
    import shared.monitor_notify as mn
    monkeypatch.setattr(sd, "gm_set_state", lambda *a, **k: (_ for _ in ()).throw(AssertionError("state write in dry-run")))
    monkeypatch.setattr(al, "log_alarm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sink write in dry-run")))
    monkeypatch.setattr(mn, "notify_monitor", lambda *a, **k: (_ for _ in ()).throw(AssertionError("send in dry-run")))
    assert bm.run(send=False, only_org="twb") == 2       # 1 audit + 1 sentinel are NEW (but nothing persisted)


def test_send_routes_and_advances_state(monkeypatch):
    _canned(monkeypatch, ["problem-1"], [{"flow": "f", "key": "k", "severity": "critical", "detail": "d"}])
    import shared.database as sd
    import gm_bot.alarms as al
    import shared.monitor_notify as mn
    sent, logged, saved = [], [], []
    monkeypatch.setattr(mn, "notify_monitor", lambda body: sent.append(body) or True)
    monkeypatch.setattr(al, "log_alarm", lambda kind, body, severity="warn": logged.append((kind, severity)) or 1)
    monkeypatch.setattr(al, "mark_delivered", lambda aid: None)
    monkeypatch.setattr(sd, "gm_set_state", lambda k, v: saved.append((k, v)))
    n = bm.run(send=True, only_org="twb")
    assert n == 2
    assert len(logged) == 2 and len(sent) == 2                    # both new alarms persisted + sent
    assert {k for k, _v in saved} == {"bmon_audit_twb", "bmon_sentinel_twb"}   # dedupe state advanced


def test_dedupe_suppresses_repeat(monkeypatch):
    # prior state already contains this exact audit problem → not new
    _canned(monkeypatch, ["problem-1"], [], prev='["problem-1"]')
    assert bm.run(send=False, only_org="twb") == 0


def test_all_orgs_returns_list_and_fallback(monkeypatch):
    orgs = bm.all_orgs()
    assert isinstance(orgs, list) and orgs and all(isinstance(o, str) for o in orgs)   # real orgs from the table
    import shared.database as sd
    monkeypatch.setattr(sd, "_db", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    assert bm.all_orgs() == ["twb"]                                                     # unreachable → safe fallback
