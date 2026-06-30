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


def test_body_org_id_is_rejected():
    """WEB-ADAPTER (s55): the client may NOT choose the tenant — a body org_id is rejected (cross-tenant guard)."""
    status, res = web.handle_request("POST", "/verdict",
                                     {"when": "2026-06-20T23:12:00+00:00", "start_dt": "2026-06-20T23:00:00+00:00",
                                      "config": {}, "org_id": "someone_else"})
    assert status == 403 and "org_id" in res["error"]


def test_network_body_strips_config():
    """DL-F3: the HTTP network boundary drops a client-supplied `config` (it would override the tenant's own
    verdict/leave rules). In-process callers (the tests above) still pass config to handle_request directly."""
    clean = web._sanitize_network_body({"config": {"grace_min": 999}, "when": "2026-06-20T23:00:00+00:00"})
    assert "config" not in clean and clean["when"] == "2026-06-20T23:00:00+00:00"


def test_serve_defaults_to_localhost():
    """WEB-ADAPTER (s55): serve() must default to 127.0.0.1, never 0.0.0.0, until W3 auth exists."""
    import inspect
    assert inspect.signature(web.serve).parameters["host"].default == "127.0.0.1"


def test_no_runner_wires_the_web_adapter():
    """WEB-ADAPTER (s55): adapters.web is INERT — no run_*.py may wire serve() to a socket until W3 auth
    exists. If you add a runner, add auth (server-side org_id + HTTPS + rate-limit) first, then update this."""
    import os, glob
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    offenders = []
    for f in glob.glob(os.path.join(root, "run_*.py")):
        with open(f, encoding="utf-8") as fh:
            txt = fh.read()
        if "adapters.web" in txt or "adapters import web" in txt:
            offenders.append(os.path.basename(f))
    assert not offenders, "a runner wires the web adapter without W3 auth: %s" % offenders
