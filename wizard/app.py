"""wizard.app — Stage 1 READ-ONLY config viewer (Flask). Shows a tenant's effective config with every knob
badged LIVE/SHADOW/PLANNED, plus the catalog of possibilities + integrations. No writes, no secrets in the
page; binds to localhost (reach via SSH tunnel). The brain (rules/config) stays server-side — this only
renders views. Editing + auth + multi-tenant are later stages.
"""
from html import escape

from flask import Flask

from core.tenant_config import get_config
from wizard.status import status_for, LEGEND, summary
from wizard import catalog

_BADGE_CSS = {"LIVE": "#b3261e", "SHADOW": "#1a73e8", "PLANNED": "#6b7280"}


def _badge(status: str) -> str:
    return ('<span style="background:%s;color:#fff;border-radius:4px;padding:1px 6px;font-size:11px;'
            'margin-left:8px">%s</span>' % (_BADGE_CSS.get(status, "#6b7280"), status))


def _render_node(node, path: str) -> str:
    """Recursively render a config subtree as a nested list; each leaf carries its cut-over badge."""
    if isinstance(node, dict):
        rows = []
        for k, v in node.items():
            child = "%s.%s" % (path, k) if path else k
            if isinstance(v, dict):
                rows.append("<li><b>%s</b>%s<ul>%s</ul></li>"
                            % (escape(str(k)), _badge(status_for(child)), _render_node(v, child)))
            else:
                rows.append("<li>%s%s &nbsp;→&nbsp; <code>%s</code></li>"
                            % (escape(str(k)), _badge(status_for(child)), escape(_fmt(v))))
        return "".join(rows)
    return "<li><code>%s</code></li>" % escape(_fmt(node))


def _fmt(v) -> str:
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) if v else "(none)"
    return str(v)


def _render_catalog() -> str:
    rows = []
    for name, c in catalog.CATEGORIES.items():
        tag = _badge("LIVE") if c["live"] else _badge("PLANNED")
        ints = " · ".join(escape(i) for i in c["integrations"])
        rows.append("<li><b>%s</b>%s<br><span style='color:#444'>%s</span>"
                    "<br><small style='color:#777'>integrations: %s</small></li>"
                    % (escape(name), tag, escape(c["blurb"]), ints))
    pkgs = "".join("<li><b>%s</b> → %s</li>" % (escape(p), escape(", ".join(cats)))
                   for p, cats in catalog.PACKAGES.items())
    ai = "".join("<li><b>%s</b> — %s</li>" % (escape(k), escape(v)) for k, v in catalog.AI_POWER.items())
    bonus = "".join("<li>%s</li>" % escape(b) for b in catalog.BONUSES)
    return ("<h3>Categories &amp; integrations (possibilities)</h3><ul>%s</ul>"
            "<h3>Packages</h3><ul>%s</ul><h3>Computer / AI Power</h3><ul>%s</ul>"
            "<h3>Bonuses</h3><ul>%s</ul>" % ("".join(rows), pkgs, ai, bonus))


def render_page(org_id: str = "twb") -> str:
    cfg = get_config(org_id)
    legend = " &nbsp; ".join("%s <small style='color:#555'>%s</small>" % (_badge(k), escape(v))
                             for k, v in LEGEND.items())
    s = summary()
    return ("<!doctype html><html><head><meta charset='utf-8'><title>Wizard — %s config</title>"
            "<style>body{font-family:system-ui,Arial;margin:24px;max-width:980px;color:#111}"
            "ul{list-style:none;padding-left:18px}li{margin:3px 0}code{background:#f3f4f6;padding:1px 5px;"
            "border-radius:4px}h1{font-size:20px}h2,h3{margin-top:22px}.box{border:1px solid #e5e7eb;"
            "border-radius:8px;padding:14px 18px;margin:14px 0}</style></head><body>"
            "<h1>🧩 Wizard — tenant <code>%s</code> · config viewer "
            "<small style='color:#888'>(read-only)</small></h1>"
            "<div class='box'><b>Legend:</b> %s<br><small style='color:#777'>cut-over map: %d LIVE · "
            "%d SHADOW · %d PLANNED prefixes</small></div>"
            "<h2>Current config (what's set for this tenant)</h2><div class='box'><ul>%s</ul></div>"
            "<h2>The menu</h2><div class='box'>%s</div>"
            "<p><small style='color:#999'>Server-side • read-only • localhost. Editing, the cut-over "
            "controls, and per-customer logins come in later stages.</small></p>"
            "</body></html>"
            % (escape(org_id), escape(org_id), legend, s["LIVE"], s["SHADOW"], s["PLANNED"],
               _render_node(cfg, ""), _render_catalog()))


def create_app(org_id: str = "twb") -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_page(org_id)

    @app.get("/healthz")
    def healthz():
        return "ok"

    return app


app = create_app()
