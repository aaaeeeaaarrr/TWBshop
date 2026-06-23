"""wizard.app — the config viewer/editor (Flask). TWO views off one engine:
  • ADMIN  ('/')          — you: every knob badged LIVE/SHADOW/PLANNED, raw values, the catalog. Internal.
  • CUSTOMER ('/customer') — the product: their own config in plain English (an explanation next to
                             everything, what True/False means, if-conditions spelled out), edited in a
                             DRAFT with Apply / Cancel — play freely, nothing changes until Apply. Only the
                             safe SHADOW knobs are editable; LIVE ones are shown locked (changed via the
                             cut-over step); other modules show as locked upsell. No internal badges leak.

SECURITY (CLAUDE.md ▶▶ PRODUCT SECURITY & IP): brain server-side, rendered views only, 127.0.0.1 + tunnel,
read-only except an explicit Apply that writes ONLY whitelisted SHADOW knobs (type/range/enum validated
server-side), no secrets in any page. Auth + per-customer scoping + CSRF land in W3 (with public access).
"""
from html import escape

from flask import Flask, request, redirect

from core.tenant_config import get_config, set_config
from wizard.status import status_for, LEGEND, summary
from wizard import catalog, schema

_BADGE_CSS = {"LIVE": "#b3261e", "SHADOW": "#1a73e8", "PLANNED": "#6b7280"}
_CSS = ("body{font-family:system-ui,Arial;margin:24px;max-width:920px;color:#111;line-height:1.4}"
        "code{background:#f3f4f6;padding:1px 5px;border-radius:4px}h1{font-size:20px}h2,h3{margin-top:24px}"
        ".box{border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;margin:14px 0}"
        ".fld{margin:14px 0;padding-bottom:12px;border-bottom:1px solid #f0f0f0}"
        ".fld label{font-size:15px}.help{color:#444;font-size:13px;margin:3px 0}"
        ".hint{color:#666;font-size:12px;background:#f8fafc;border-left:3px solid #c7d2fe;padding:5px 9px;margin-top:4px}"
        ".lock{color:#9333ea;font-size:12px;margin-left:8px}.actions{margin-top:20px}"
        "button{background:#1a73e8;color:#fff;border:0;border-radius:7px;padding:9px 18px;font-size:15px;cursor:pointer}"
        ".btn{display:inline-block;margin-left:10px;padding:9px 16px;border:1px solid #ccc;border-radius:7px;"
        "color:#333;text-decoration:none}.saved{background:#dcfce7;border:1px solid #86efac;padding:8px 14px;"
        "border-radius:8px;margin:10px 0}input[type=number]{width:90px;padding:4px}select{padding:4px}"
        "ul{padding-left:18px}.nav a{margin-right:14px}.note{color:#777;font-size:12px}")


def _badge(status: str) -> str:
    return ('<span style="background:%s;color:#fff;border-radius:4px;padding:1px 6px;font-size:11px;'
            'margin-left:8px">%s</span>' % (_BADGE_CSS.get(status, "#6b7280"), status))


def _page(title: str, body: str) -> str:
    return ("<!doctype html><html><head><meta charset='utf-8'><title>%s</title><style>%s</style></head>"
            "<body>%s</body></html>" % (escape(title), _CSS, body))


def _get_path(cfg: dict, dotted: str):
    cur = cfg
    for k in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _set_path(d: dict, dotted: str, value) -> None:
    keys = dotted.split(".")
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def _fmt(v) -> str:
    return ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)


# ── ADMIN view (internal: badges + raw) ──────────────────────────────────────
def _render_node(node, path: str) -> str:
    if isinstance(node, dict):
        out = []
        for k, v in node.items():
            child = "%s.%s" % (path, k) if path else k
            if isinstance(v, dict):
                out.append("<li><b>%s</b>%s<ul>%s</ul></li>"
                           % (escape(str(k)), _badge(status_for(child)), _render_node(v, child)))
            else:
                out.append("<li>%s%s &nbsp;→&nbsp; <code>%s</code></li>"
                           % (escape(str(k)), _badge(status_for(child)), escape(_fmt(v))))
        return "".join(out)
    return "<li><code>%s</code></li>" % escape(_fmt(node))


def _render_catalog() -> str:
    rows = "".join("<li><b>%s</b>%s<br><span style='color:#444'>%s</span>"
                   "<br><small style='color:#777'>integrations: %s</small></li>"
                   % (escape(n), _badge("LIVE") if c["live"] else _badge("PLANNED"),
                      escape(c["blurb"]), " · ".join(escape(i) for i in c["integrations"]))
                   for n, c in catalog.CATEGORIES.items())
    pkgs = "".join("<li><b>%s</b> → %s</li>" % (escape(p), escape(", ".join(cs)))
                   for p, cs in catalog.PACKAGES.items())
    ai = "".join("<li><b>%s</b> — %s</li>" % (escape(k), escape(v)) for k, v in catalog.AI_POWER.items())
    return ("<h3>Categories &amp; integrations</h3><ul>%s</ul><h3>Packages</h3><ul>%s</ul>"
            "<h3>Computer / AI Power</h3><ul>%s</ul>" % (rows, pkgs, ai))


def render_page(org_id: str = "twb") -> str:
    cfg = get_config(org_id)
    legend = " &nbsp; ".join("%s <small style='color:#555'>%s</small>" % (_badge(k), escape(v))
                             for k, v in LEGEND.items())
    s = summary()
    body = ("<div class='nav'><b>Admin</b> · <a href='/customer'>see the customer view →</a></div>"
            "<h1>🧩 Wizard · tenant <code>%s</code> · admin <small style='color:#888'>(internal — badges, read-only)</small></h1>"
            "<div class='box'><b>Legend:</b> %s<br><small style='color:#777'>cut-over map: %d LIVE · %d SHADOW · "
            "%d PLANNED prefixes</small></div>"
            "<h2>Effective config</h2><div class='box'><ul>%s</ul></div>"
            "<h2>The menu</h2><div class='box'>%s</div>"
            % (escape(org_id), legend, s["LIVE"], s["SHADOW"], s["PLANNED"], _render_node(cfg, ""), _render_catalog()))
    return _page("Wizard — admin", body)


# ── CUSTOMER view (the product: friendly + editable draft) ────────────────────
def _field_input(path: str, desc: dict, value, editable: bool) -> str:
    t = desc["type"]
    dis = "" if editable else "disabled"
    if t == "bool":
        ctrl = '<input type="checkbox" name="%s" %s %s>' % (escape(path), "checked" if value else "", dis)
        hint = ('<div class="hint"><b>On:</b> %s<br><b>Off:</b> %s</div>'
                % (escape(desc.get("true", "")), escape(desc.get("false", ""))))
    elif t == "int":
        ctrl = ('<input type="number" name="%s" value="%s" min="%s" max="%s" %s> <small>%s</small>'
                % (escape(path), int(value or 0), desc.get("min", 0), desc.get("max", 99999), dis,
                   escape(desc.get("unit", ""))))
        hint = ""
    elif t == "enum":
        opts = "".join('<option value="%s" %s>%s</option>'
                       % (escape(str(v)), "selected" if str(value) == str(v) else "", escape(lbl))
                       for v, lbl, _h in desc["options"])
        ctrl = '<select name="%s" %s>%s</select>' % (escape(path), dis, opts)
        hint = '<div class="hint">%s</div>' % "<br>".join("<b>%s:</b> %s" % (escape(lbl), escape(h))
                                                          for _v, lbl, h in desc["options"])
    else:
        ctrl, hint = escape(str(value)), ""
    lock = "" if editable else ' <span class="lock">🔒 managed via your operations team</span>'
    return ('<div class="fld"><label><b>%s</b>%s</label><div>%s</div><div class="help">%s</div>%s</div>'
            % (escape(desc["label"]), lock, ctrl, escape(desc["help"]), hint))


def _render_approvals(cfg: dict) -> str:
    """Show the Annual-leave approval row fully explained (incl. the if-conditions), read-only — it's the
    real, live example; note the same controls apply to the other request types."""
    rows = []
    for field in schema.APPROVAL_FIELDS:
        path = "categories.attendance.approvals.al.%s" % field
        desc = schema.describe(path)
        val = _get_path(cfg, path)
        rows.append(_field_input(path, desc, val, editable=False))
    others = ", ".join(v for k, v in schema.APPROVAL_KINDS.items() if k != "al")
    return ("<p class='note'>These approval controls (shown for <b>Annual leave</b>) apply the same way to: "
            "%s.</p>%s" % (escape(others), "".join(rows)))


def _render_locked_modules(cfg: dict) -> str:
    rows = []
    for name, c in catalog.CATEGORIES.items():
        if c["live"]:
            continue
        pkgs = [p for p, cs in catalog.PACKAGES.items() if name in cs]
        rows.append("<li>🔒 <b>%s</b> — %s <br><small class='note'>available in: %s · integrations: %s</small></li>"
                    % (escape(name), escape(c["blurb"]), escape(", ".join(pkgs) or "—"),
                       escape(" · ".join(c["integrations"]))))
    return "<ul>%s</ul>" % "".join(rows)


def render_customer(org_id: str = "twb", saved: bool = False) -> str:
    cfg = get_config(org_id)
    sections = []
    for glabel, paths in schema.ATTENDANCE_GROUPS:
        flds = []
        for path in paths:
            desc = schema.describe(path)
            if not desc:
                continue
            flds.append(_field_input(path, desc, _get_path(cfg, path), editable=(status_for(path) == "SHADOW")))
        sections.append("<h3>%s</h3>%s" % (escape(glabel), "".join(flds)))
    form = ('<form method="post" action="/customer/apply">%s'
            '<div class="actions"><button type="submit">✓ Apply changes</button>'
            '<a href="/customer" class="btn">✗ Cancel changes</a></div></form>'
            % "".join(sections))
    saved_banner = '<div class="saved">✓ Your changes were applied.</div>' if saved else ""
    body = ("<div class='nav'><a href='/'>← admin</a></div>"
            "<h1>⚙️ Configure your Attendance system</h1>"
            "<p class='note'>Play with anything — <b>nothing changes until you press “Apply changes”.</b> "
            "“Cancel” throws away your edits.</p>%s"
            "<div class='box'>%s</div>"
            "<h2>Approvals</h2><div class='box'>%s</div>"
            "<h2>Add more to your system</h2><div class='box'>%s</div>"
            % (saved_banner, form, _render_approvals(cfg), _render_locked_modules(cfg)))
    return _page("Configure — your system", body)


def apply_changes(org_id: str, form) -> dict:
    """Commit ONLY whitelisted SHADOW knobs from the customer form, validated server-side (type/range/enum).
    Anything LIVE/PLANNED or unknown is ignored — a customer can never write a live or arbitrary key."""
    over: dict = {}
    for _glabel, paths in schema.ATTENDANCE_GROUPS:
        for path in paths:
            if status_for(path) != "SHADOW":          # safety: only safe shadow knobs are writable
                continue
            desc = schema.describe(path)
            if not desc:
                continue
            t = desc["type"]
            if t == "bool":
                _set_path(over, path, path in form)    # checkbox present ⇒ True
            elif t == "int":
                try:
                    v = int(form.get(path, ""))
                except (TypeError, ValueError):
                    continue
                v = max(desc.get("min", v), min(desc.get("max", v), v))   # clamp to sane range
                _set_path(over, path, v)
            elif t == "enum":
                v = form.get(path)
                if v in [opt[0] for opt in desc["options"]]:             # reject unknown options
                    _set_path(over, path, v)
    if over:
        set_config(org_id, over)
    return over


def create_app(org_id: str = "twb") -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_page(org_id)

    @app.get("/customer")
    def customer():
        return render_customer(org_id, saved=request.args.get("saved") == "1")

    @app.post("/customer/apply")
    def customer_apply():
        apply_changes(org_id, request.form)
        return redirect("/customer?saved=1")

    @app.get("/healthz")
    def healthz():
        return "ok"

    return app


app = create_app()
