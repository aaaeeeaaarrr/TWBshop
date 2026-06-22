"""adapters.web — the web channel. Proves an HTTP request drives the SAME brain as Telegram/replay
(channel-agnosticism, second real adapter), with clean HTTP status mapping. No DB (config in body)."""
from adapters import web


def test_web_verdict_same_brain():
    body = {"when": "2026-06-20T23:12:00+00:00", "start_dt": "2026-06-20T23:00:00+00:00", "config": {}}
    status, res = web.handle_request("POST", "/verdict", body)
    assert status == 200
    assert res == {"ok": True, "state": "late", "minutes_late": 12, "minutes_early": 0}   # 06:12 PP → late 12


def test_web_http_semantics():
    assert web.handle_request("GET", "/verdict", {})[0] == 405                  # wrong method
    assert web.handle_request("POST", "/nonsense", {"config": {}})[0] == 400    # unknown command
    bad = web.handle_request("POST", "/verdict", {"when": "not-a-date", "start_dt": "x", "config": {}})
    assert bad[0] == 400 and "bad datetime" in bad[1]["error"]                  # bad input
