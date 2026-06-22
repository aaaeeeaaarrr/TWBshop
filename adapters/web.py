"""adapters.web — a WEB channel for the platform (the "web?" option in the onboarding wizard). Maps an
HTTP request to a neutral core.channel command and renders JSON. No web framework needed for the mapping
(the spine does the work); serve() is a thin optional stdlib server. Proves channel-agnosticism with a
SECOND real adapter — same brain as the Telegram hook + the replay.
"""
import json
from datetime import datetime

from core.channel import handle


def handle_request(method: str, path: str, body: dict, org_id: str = "twb"):
    """HTTP → neutral command. POST /<command> with a JSON body (ISO datetime strings auto-parsed). Pass
    `config` in the body to skip the per-tenant DB load (tests/stateless callers). Returns
    (status_code, response_dict)."""
    if method.upper() != "POST":
        return 405, {"ok": False, "error": "use POST /<command>"}
    command = path.strip("/").split("/")[0]
    params = dict(body or {})
    config = params.pop("config", None)
    org = params.pop("org_id", org_id)
    for k in ("when", "start_dt"):                       # web sends ISO strings; the brain wants datetimes
        if isinstance(params.get(k), str):
            try:
                params[k] = datetime.fromisoformat(params[k])
            except ValueError:
                return 400, {"ok": False, "error": "bad datetime: %s" % k}
    res = handle(org, command, params, config=config)
    return (200 if res.get("ok") else 400), res


def serve(host: str = "0.0.0.0", port: int = 8080):  # pragma: no cover - optional runner
    """Thin stdlib HTTP server (no dependency). For a real deployment swap in any WSGI/ASGI host — the
    mapping (handle_request) is what matters; this just wires it to sockets."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                body = {}
            status, res = handle_request("POST", self.path, body)
            payload = json.dumps(res, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

    HTTPServer((host, port), _H).serve_forever()
