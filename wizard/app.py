"""wizard.app — the config viewer/editor (Flask). TWO views off one engine:
  • ADMIN  ('/')          — you: every knob badged LIVE / SHADOW / LIVE_FIXED / PLANNED, raw values (secrets
                            masked), the cut-over dashboard, the catalog. Internal.
  • CUSTOMER ('/customer') — the product: their config in plain English (an explanation next to everything,
                            True/False + if-conditions spelled out), edited in a DRAFT with Apply / Cancel.
                            Play freely — nothing changes until Apply. EDITABLE = safe SHADOW + PLANNED knobs;
                            LIVE / LIVE_FIXED are shown locked ("live today — set at cut-over"); tokens are
                            write-only + masked. No internal badges leak.

SECURITY (CLAUDE.md ▶▶ PRODUCT SECURITY & IP): brain server-side, rendered views only, 127.0.0.1 + tunnel.
SECRETS (bot tokens etc.) live in the encrypted org-secret store, are NEVER rendered (only set ✓ / not set),
and are never written to the readable config. Apply validates server-side + writes ONLY whitelisted knobs.
Auth + CSRF + encryption-at-rest land in W3 (with public access).
"""
import re
from html import escape
from urllib.parse import quote

from flask import Flask, request, redirect

from core.tenant_config import get_config, set_config
from core.db import set_org_secret, has_org_secret
from core.onboarding_flow import (list_staff, add_staff_manual, remove_staff, get_staff, update_staff,
                                  list_groups, set_group_role, GROUP_ROLES,
                                  list_candidates, group_id_for_role)
from wizard.status import status_for, LEGEND, summary, EDITABLE
from wizard import catalog, schema

_BADGE_CSS = {"LIVE": "#b3261e", "SHADOW": "#1a73e8", "LIVE_FIXED": "#d97706", "PLANNED": "#6b7280"}
_CSS = ("body{font-family:system-ui,Arial;margin:24px;max-width:940px;color:#111;line-height:1.4}"
        "code{background:#f3f4f6;padding:1px 5px;border-radius:4px}h1{font-size:20px}h2,h3{margin-top:24px}"
        ".box{border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;margin:14px 0}"
        ".fld{margin:14px 0;padding-bottom:12px;border-bottom:1px solid #f0f0f0}.fld label{font-size:15px}"
        ".help{color:#444;font-size:13px;margin:3px 0}.hint{color:#666;font-size:12px;background:#f8fafc;"
        "border-left:3px solid #c7d2fe;padding:5px 9px;margin-top:4px}.lock{color:#9333ea;font-size:12px;"
        "margin-left:8px}.actions{margin-top:20px}button{background:#1a73e8;color:#fff;border:0;"
        "border-radius:7px;padding:9px 18px;font-size:15px;cursor:pointer}.btn{display:inline-block;"
        "margin-left:10px;padding:9px 16px;border:1px solid #ccc;border-radius:7px;color:#333;"
        "text-decoration:none}.saved{background:#dcfce7;border:1px solid #86efac;padding:8px 14px;"
        "border-radius:8px;margin:10px 0}input[type=number]{width:90px;padding:4px}input[type=text],"
        "input[type=password]{padding:4px;width:260px}select{padding:4px}ul{padding-left:18px}"
        ".nav a{margin-right:14px}.note{color:#777;font-size:12px}.set{color:#16a34a}.unset{color:#9ca3af}")


def _badge(status: str) -> str:
    return ('<span style="background:%s;color:#fff;border-radius:4px;padding:1px 6px;font-size:11px;'
            'margin-left:8px">%s</span>' % (_BADGE_CSS.get(status, "#6b7280"), status))


def _is_secret(v) -> bool:
    return isinstance(v, dict) and "__secret__" in v


def _secret_status_html(org_id: str, v: dict) -> str:
    on = has_org_secret(org_id, v["__secret__"])
    return ('🔒 secret — <span class="%s">%s</span>' % ("set" if on else "unset",
                                                        "set ✓" if on else "not set"))


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


# ── ADMIN view (internal: badges + raw, secrets masked) ──────────────────────
def _render_node(node, path: str, org_id: str) -> str:
    if _is_secret(node):
        return "<li>%s%s</li>" % (_secret_status_html(org_id, node), _badge(status_for(path)))
    if isinstance(node, dict):
        out = []
        for k, v in node.items():
            child = "%s.%s" % (path, k) if path else k
            if _is_secret(v):
                out.append("<li>%s %s%s</li>" % (escape(str(k)), _secret_status_html(org_id, v), _badge(status_for(child))))
            elif isinstance(v, dict):
                out.append("<li><b>%s</b>%s<ul>%s</ul></li>"
                           % (escape(str(k)), _badge(status_for(child)), _render_node(v, child, org_id)))
            else:
                out.append("<li>%s%s &nbsp;→&nbsp; <code>%s</code></li>"
                           % (escape(str(k)), _badge(status_for(child)), escape(_fmt(v))))
        return "".join(out)
    return "<li><code>%s</code></li>" % escape(_fmt(node))


def _render_catalog() -> str:
    rows = "".join("<li><b>%s</b>%s<br><span style='color:#444'>%s</span>"
                   "<br><small style='color:#777'>integrations: %s</small></li>"
                   % (escape(n), _badge("LIVE_FIXED") if c["live"] else _badge("PLANNED"),
                      escape(c["blurb"]), " · ".join(escape(i) for i in c["integrations"]))
                   for n, c in catalog.CATEGORIES.items())
    pkgs = "".join("<li><b>%s</b> → %s</li>" % (escape(p), escape(", ".join(cs)))
                   for p, cs in catalog.PACKAGES.items())
    ai = "".join("<li><b>%s</b> — %s</li>" % (escape(k), escape(v)) for k, v in catalog.AI_POWER.items())
    return ("<h3>Categories &amp; integrations</h3><ul>%s</ul><h3>Packages</h3><ul>%s</ul>"
            "<h3>Computer / AI Power</h3><ul>%s</ul>" % (rows, pkgs, ai))


def render_cutover(org_id: str) -> str:
    try:
        from core.shadow import build_digest
        st = build_digest(org_id)["stats"]
    except Exception:
        return "<div class='box'>Cut-over status unavailable (shadow not initialised).</div>"
    rows = []
    for kind, v in sorted(st.get("by_kind", {}).items()):
        rate = (100.0 * v["ok"] / v["n"]) if v["n"] else 0.0
        verdict = ("READY ✅" if (kind == "checkin" and st.get("ready")) else "gathering data")
        rows.append("<li><b>%s</b>: %d compared · %.0f%% agree · %s</li>" % (escape(kind), v["n"], rate, verdict))
    s = summary()
    return ("<div class='box'><b>🚦 Cut-over status</b> — the shadow running the NEW engine beside live:<ul>%s</ul>"
            "<small class='note'>Knobs: <b>%d</b> LIVE · <b>%d</b> SHADOW (proving) · <b>%d</b> LIVE-FIXED "
            "(live today, fixed rules) · <b>%d</b> PLANNED (options). A vertical cuts over only when its shadow "
            "agrees for days AND you flip it — never automatic.</small></div>"
            % ("".join(rows) or "<li>no comparisons yet</li>", s["LIVE"], s["SHADOW"], s["LIVE_FIXED"], s["PLANNED"]))


def render_page(org_id: str = "twb") -> str:
    cfg = get_config(org_id)
    legend = " &nbsp; ".join("%s <small style='color:#555'>%s</small>" % (_badge(k), escape(v))
                             for k, v in LEGEND.items())
    body = ("<div class='nav'><b>Admin</b> · <a href='/setup'>setup</a> · <a href='/customer'>customer view</a> · "
            "<a href='/staff'>staff</a> · <a href='/expertise'>expertise</a> · <a href='/groups'>groups</a> · "
            "<a href='/bot'>bot setup</a></div>"
            "<h1>🧩 Wizard · tenant <code>%s</code> · admin <small style='color:#888'>(internal — badges, read-only)</small></h1>"
            "%s<div class='box'><b>Legend:</b> %s</div>"
            "<h2>Effective config</h2><div class='box'><ul>%s</ul></div>"
            "<h2>The menu</h2><div class='box'>%s</div>"
            % (escape(org_id), render_cutover(org_id), legend, _render_node(cfg, "", org_id), _render_catalog()))
    return _page("Wizard — admin", body)


# ── CUSTOMER view (the product: friendly + editable draft) ────────────────────
def _field_input(path: str, desc: dict, value, status: str, org_id: str) -> str:
    t = desc["type"]
    editable = status in EDITABLE
    if t == "secret":
        on = _is_secret(value) and has_org_secret(org_id, value["__secret__"])
        ctrl = ('<span class="%s">%s</span> &nbsp; <input type="password" name="%s" placeholder="paste to set/replace">'
                % ("set" if on else "unset", "set ✓" if on else "not set", escape(path)))
        hint = '<div class="hint">Stored encrypted · never shown back · only the server uses it.</div>'
        return ('<div class="fld"><label><b>%s</b></label><div>%s</div><div class="help">%s</div>%s</div>'
                % (escape(desc["label"]), ctrl, escape(desc["help"]), hint))
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
    elif t == "text":
        ctrl = '<input type="text" name="%s" value="%s" %s>' % (escape(path), escape(str(value or "")), dis)
        hint = ""
    else:
        ctrl, hint = escape(str(value)), ""
    if status == "LIVE":
        note = ' <span class="lock">🔒 drives the live shop — changed at cut-over</span>'
    elif status == "LIVE_FIXED":
        note = ' <span class="lock">live today (fixed) — your change applies at cut-over</span>'
    else:
        note = ""
    return ('<div class="fld"><label><b>%s</b>%s</label><div>%s</div><div class="help">%s</div>%s</div>'
            % (escape(desc["label"]), note, ctrl, escape(desc["help"]), hint))


def _render_groups(cfg: dict, groups, org_id: str) -> str:
    out = []
    for glabel, paths in groups:
        flds = []
        for path in paths:
            desc = schema.describe(path)
            if not desc:
                continue
            flds.append(_field_input(path, desc, _get_path(cfg, path), status_for(path), org_id))
        if flds:
            out.append("<h3>%s</h3>%s" % (escape(glabel), "".join(flds)))
    return "".join(out)


def _render_approvals(cfg: dict) -> str:
    rows = []
    for field in schema.APPROVAL_FIELDS:
        path = "categories.attendance.approvals.al.%s" % field
        rows.append(_field_input(path, schema.describe(path), _get_path(cfg, path), "LIVE", "twb"))
    others = ", ".join(v for k, v in schema.APPROVAL_KINDS.items() if k != "al")
    return ("<p class='note'>These approval controls (shown for <b>Annual leave</b>, which is live today) apply "
            "the same way to: %s.</p>%s" % (escape(others), "".join(rows)))


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
    saved_banner = '<div class="saved">✓ Your changes were applied.</div>' if saved else ""
    body = ("<div class='nav'><a href='/'>← admin</a> · <a href='/setup'>setup</a> · <a href='/staff'>staff</a> · "
            "<a href='/expertise'>expertise</a> · <a href='/groups'>groups</a> · <a href='/bot'>bot setup</a></div>"
            "<h1>⚙️ Configure your system</h1>"
            "<p class='note'>Play with anything — <b>nothing changes until you press “Apply changes”.</b> "
            "“Cancel” throws away your edits. Settings marked 🔒 are live today with fixed rules (you'll set "
            "those when we switch them over). Tokens are write-only — paste to set, never shown back.</p>%s"
            "<form method='post' action='/customer/apply'>"
            "<h2>Setup &amp; staff</h2><div class='box'>"
            "<p class='note'>How your system gets set up. The easy path: we guide you to create a bot, you "
            "add it to your groups, and it <b>finds your staff for you to confirm one-by-one</b> — no typing "
            "lists. (The guided bot-creation + staff discover-confirm flow is the next build.)</p>%s</div>"
            "<h2>Attendance</h2><div class='box'>%s</div>"
            "<h2>Accountant</h2><div class='box'><p class='note'>Built; not live yet — set your preferences "
            "now, they apply when it's switched on.</p>%s</div>"
            "<h2>Connections (channels &amp; tokens)</h2><div class='box'>%s</div>"
            "<div class='actions'><button type='submit'>✓ Apply changes</button>"
            "<a href='/customer' class='btn'>✗ Cancel changes</a></div></form>"
            "<h2>Approvals</h2><div class='box'>%s</div>"
            "<h2>Add more to your system</h2><div class='box'>%s</div>"
            % (saved_banner, _render_groups(cfg, schema.ONBOARDING_GROUPS, org_id),
               _render_groups(cfg, schema.ATTENDANCE_GROUPS, org_id),
               _render_groups(cfg, schema.ACCOUNTANT_GROUPS, org_id),
               _render_groups(cfg, schema.CONNECTIONS_GROUPS, org_id), _render_approvals(cfg),
               _render_locked_modules(cfg)))
    return _page("Configure — your system", body)


def apply_changes(org_id: str, form) -> dict:
    """Commit ONLY safe knobs: SHADOW/PLANNED config values (validated) + any SECRET written (to the encrypted
    store, never the config). LIVE / LIVE_FIXED and unknown keys are ignored — a customer can't touch a live
    knob or write an arbitrary key from here."""
    cfg = get_config(org_id)
    over: dict = {}
    for _glabel, paths in (schema.ATTENDANCE_GROUPS + schema.CONNECTIONS_GROUPS + schema.ONBOARDING_GROUPS
                           + schema.ACCOUNTANT_GROUPS):
        for path in paths:
            desc = schema.describe(path)
            if not desc:
                continue
            t = desc["type"]
            if t == "secret":                                  # always allowed; write-only to the secret store
                ref = _get_path(cfg, path)
                val = form.get(path)
                if _is_secret(ref) and val:
                    set_org_secret(org_id, ref["__secret__"], val.strip())
                continue
            if status_for(path) not in EDITABLE:               # only safe shadow/planned config knobs
                continue
            if t == "bool":
                _set_path(over, path, path in form)
            elif t == "int":
                try:
                    v = int(form.get(path, ""))
                except (TypeError, ValueError):
                    continue
                _set_path(over, path, max(desc.get("min", v), min(desc.get("max", v), v)))
            elif t == "enum":
                v = form.get(path)
                if v in [opt[0] for opt in desc["options"]]:
                    _set_path(over, path, v)
            elif t == "text":
                _set_path(over, path, (form.get(path) or "").strip())
    if over:
        set_config(org_id, over)
    return over


# ── EXPERTISE editor (skills + minimum coverage + day/hour overrides) ─────────
_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _exp_cfg(org_id: str) -> dict:
    return get_config(org_id).get("categories", {}).get("attendance", {}).get("expertise", {})


def _save_exp(org_id: str, key: str, value) -> None:
    set_config(org_id, {"categories": {"attendance": {"expertise": {key: value}}}})


def _int(v, lo, hi, default=0) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def render_expertise(org_id: str) -> str:
    exp = _exp_cfg(org_id)
    roles = exp.get("roles") or []
    overrides = exp.get("coverage_overrides") or []
    role_rows = "".join(
        "<li><b>%s</b> — min <b>%d</b> at all times "
        "<form method='post' action='/expertise/role/del' style='display:inline'>"
        "<input type='hidden' name='name' value='%s'><button class='btn'>remove</button></form></li>"
        % (escape(r.get("name", "")), int(r.get("min_required", 0)), escape(r.get("name", "")))
        for r in roles) or "<li class='note'>No skills yet.</li>"
    ov_rows = "".join(
        "<li>%s: min <b>%d</b> on <b>%s</b>%s "
        "<form method='post' action='/expertise/override/del' style='display:inline'>"
        "<input type='hidden' name='idx' value='%d'><button class='btn'>remove</button></form></li>"
        % (escape(o.get("role", "")), int(o.get("min", 0)), escape(", ".join(o.get("days") or []) or "any day"),
           (" " + escape(o["hours"]) if o.get("hours") else ""), i)
        for i, o in enumerate(overrides)) or "<li class='note'>No overrides — the minimums above apply all the time.</li>"
    role_opts = "".join("<option value='%s'>%s</option>" % (escape(r["name"]), escape(r["name"])) for r in roles)
    day_boxes = " ".join("<label style='font-weight:normal'><input type='checkbox' name='days' value='%s'> %s</label>"
                         % (d, d) for d in _DAYS)
    body = (
        "<div class='nav'><a href='/'>← admin</a> · <a href='/customer'>customer</a> · <a href='/staff'>staff</a></div>"
        "<h1>🧠 Expertise &amp; coverage</h1>"
        "<p class='note'>Define each skill and how many you need WORKING at all times; add overrides to need "
        "more (or fewer) on certain days/hours. The bot can use this to approve leave only when coverage holds.</p>"
        "<div class='box'><h3>Skills &amp; minimums</h3><ul>%s</ul>"
        "<form method='post' action='/expertise/role/add'>Skill <input type='text' name='name' placeholder='e.g. baker'> "
        "&nbsp; min at all times <input type='number' name='min' value='1' min='0' max='99' style='width:70px'> "
        "<button type='submit'>+ add skill</button></form></div>"
        "<div class='box'><h3>Coverage overrides (need more/fewer at special times)</h3><ul>%s</ul>"
        "<form method='post' action='/expertise/override/add'>Skill <select name='role'>%s</select> "
        "&nbsp; min <input type='number' name='min' value='1' min='0' max='99' style='width:70px'> "
        "&nbsp; days: %s &nbsp; hours <input type='text' name='hours' placeholder='06:00-12:00 (optional)'> "
        "<button type='submit'>+ add override</button></form></div>"
        % (role_rows, ov_rows, role_opts or "<option value=''>(add a skill first)</option>", day_boxes))
    return _page("Expertise & coverage", body)


# ── STAFF editor (the platform roster — discover-confirm feeds it; this is the manual/edit view) ──
def _hhmm(v):
    v = (v or "").strip()
    return v if re.fullmatch(r"[0-2]?\d:[0-5]\d", v) else None


def _windows_from_form(form) -> list:
    w = []
    s, e = _hhmm(form.get("work_start")), _hhmm(form.get("work_end"))
    if s and e:
        w.append({"start": s, "end": e})
    ss, se = _hhmm(form.get("split_start")), _hhmm(form.get("split_end"))
    if ss and se:
        w.append({"start": ss, "end": se})
    return w


def _windows_str(windows) -> str:
    return " + ".join("%s–%s" % (w.get("start", "?"), w.get("end", "?")) for w in (windows or [])) or "—"


def _parse_staff_line(line: str) -> dict | None:
    """One bulk-import line → a staff dict. Format: 'Name, role, HH:MM-HH:MM, skill1;skill2' (only name
    required; the rest optional). Lenient."""
    parts = [p.strip() for p in line.split(",")]
    name = (parts[0] if parts else "")[:60]
    if not name:
        return None
    role = (parts[1][:40] or None) if len(parts) > 1 and parts[1] else None
    windows = []
    if len(parts) > 2 and "-" in parts[2]:
        a, b = (x.strip() for x in parts[2].split("-", 1))
        if _hhmm(a) and _hhmm(b):
            windows = [{"start": a, "end": b}]
    skills = [s.strip()[:30] for s in parts[3].split(";") if s.strip()] if len(parts) > 3 and parts[3] else []
    return {"name": name, "role": role, "shift_windows": windows, "expertises": skills}


def render_staff(org_id: str) -> str:
    staff = list_staff(org_id)
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
        "<td><a href='/staff/edit/%d' class='btn'>edit</a> "
        "<form method='post' action='/staff/del' style='display:inline'>"
        "<input type='hidden' name='staff_id' value='%d'><button class='btn'>remove</button></form></td></tr>"
        % (escape(s.get("name", "")), escape(s.get("role") or ""), "senior" if s.get("is_senior") else "",
           escape(", ".join(s.get("expertises") or [])), escape(_windows_str(s.get("shift_windows"))),
           s["staff_id"], s["staff_id"])
        for s in staff) or "<tr><td colspan='6' class='note'>No staff yet.</td></tr>"
    body = (
        "<div class='nav'><a href='/'>← admin</a> · <a href='/customer'>customer</a> · <a href='/expertise'>expertise</a></div>"
        "<h1>👥 Staff</h1>"
        "<p class='note'>Your platform roster. The bot's <b>discover-confirm</b> fills this from your group; you "
        "can also add/edit by hand here. (TWB's existing live staff migrate here at cut-over.) Overnight is fine "
        "— a window like 21:00→06:00 is one shift; add a second window for a split shift.</p>"
        "<div class='box'><table style='width:100%%;border-collapse:collapse' cellpadding='6'>"
        "<tr style='text-align:left;border-bottom:1px solid #eee'><th>Name</th><th>Role</th><th></th>"
        "<th>Skills</th><th>Hours</th><th></th></tr>%s</table></div>"
        "<div class='box'><h3>Add a staffer</h3><form method='post' action='/staff/add'>"
        "Name <input type='text' name='name' placeholder='full name'> "
        "Call-name <input type='text' name='call_name' style='width:120px'> "
        "Role <input type='text' name='role' style='width:120px'> "
        "<label style='font-weight:normal'><input type='checkbox' name='is_senior'> senior</label><br><br>"
        "Skills (comma-separated) <input type='text' name='expertises' placeholder='baker, cashier'><br><br>"
        "Shift <input type='time' name='work_start'> to <input type='time' name='work_end'> "
        "&nbsp; split (optional) <input type='time' name='split_start'> to <input type='time' name='split_end'>"
        "<br><br><button type='submit'>+ add staffer</button></form></div>"
        "<div class='box'><h3>Bulk import</h3>"
        "<p class='note'>One staffer per line: <code>Name, role, 21:00-06:00, baker;cashier</code> "
        "(role / hours / skills optional). Overnight + skills supported.</p>"
        "<form method='post' action='/staff/import'>"
        "<textarea name='bulk' rows='5' style='width:100%%'></textarea><br>"
        "<button type='submit'>Import</button></form></div>"
        % rows)
    return _page("Staff", body)


def render_staff_edit(org_id: str, staff_id: int) -> str:
    s = get_staff(org_id, staff_id)
    if not s:
        return _page("Edit staff", "<div class='nav'><a href='/staff'>← staff</a></div><p>Not found.</p>")
    w = s.get("shift_windows") or []
    w0, w1 = (w[0] if len(w) > 0 else {}), (w[1] if len(w) > 1 else {})
    body = (
        "<div class='nav'><a href='/staff'>← staff</a></div><h1>✏️ Edit %s</h1>"
        "<div class='box'><form method='post' action='/staff/update'>"
        "<input type='hidden' name='staff_id' value='%d'>"
        "Name <input type='text' name='name' value='%s'> "
        "Call-name <input type='text' name='call_name' value='%s' style='width:120px'> "
        "Role <input type='text' name='role' value='%s' style='width:120px'> "
        "<label style='font-weight:normal'><input type='checkbox' name='is_senior' %s> senior</label><br><br>"
        "Skills (comma-separated) <input type='text' name='expertises' value='%s'><br><br>"
        "Shift <input type='time' name='work_start' value='%s'> to <input type='time' name='work_end' value='%s'> "
        "&nbsp; split <input type='time' name='split_start' value='%s'> to <input type='time' name='split_end' value='%s'>"
        "<br><br><button type='submit'>Save</button> <a href='/staff' class='btn'>Cancel</a></form></div>"
        % (escape(s.get("name", "")), s["staff_id"], escape(s.get("name", "")), escape(s.get("call_name") or ""),
           escape(s.get("role") or ""), "checked" if s.get("is_senior") else "",
           escape(", ".join(s.get("expertises") or [])), escape(w0.get("start", "")), escape(w0.get("end", "")),
           escape(w1.get("start", "")), escape(w1.get("end", ""))))
    return _page("Edit staff", body)


# ── SETUP checklist — the "where am I" view that ties onboarding together ─────
def render_setup(org_id: str) -> str:
    cfg = get_config(org_id)
    bot_user = cfg.get("connections", {}).get("telegram", {}).get("bot_username")
    staff_grp = group_id_for_role(org_id, "staff")
    staff, pending = list_staff(org_id), list_candidates(org_id)

    def step(done, label, link, hint):
        return ("<li style='margin:8px 0'>%s <a href='%s'><b>%s</b></a> — <span class='note'>%s</span></li>"
                % ("✅" if done else "⬜", link, escape(label), escape(hint)))

    steps = "".join([
        step(bool(bot_user), "Connect your bot", "/bot",
             ("@%s connected" % bot_user) if bot_user else "create + verify your bot in BotFather"),
        step(bool(staff_grp), "Tag your staff group", "/groups",
             "done" if staff_grp else "add the bot to your groups, then tag the staff one"),
        step(len(staff) > 0, "Add your staff", "/staff",
             (("%d added" % len(staff)) + ((", %d to confirm" % len(pending)) if pending else ""))
             if (staff or pending) else "discover-confirm from the group, or add by hand"),
        step(True, "Set your rules", "/customer", "attendance · leave · OT · approvals — tweak anytime"),
    ])
    done_n = sum([bool(bot_user), bool(staff_grp), len(staff) > 0, True])
    body = (
        "<div class='nav'><a href='/'>← admin</a> · <a href='/customer'>customer</a> · <a href='/bot'>bot</a> · "
        "<a href='/groups'>groups</a> · <a href='/staff'>staff</a> · <a href='/expertise'>expertise</a></div>"
        "<h1>🚀 Setup — %d of 4 done</h1>"
        "<p class='note'>Work through these in any order. The bot does the heavy lifting — you just confirm.</p>"
        "<div class='box'><ul style='list-style:none;padding-left:0;line-height:1.8'>%s</ul></div>"
        "<p class='note'>New here? <a href='/templates'>Start from a template</a> to pre-fill typical "
        "skills + rules.</p>"
        % (done_n, steps))
    return _page("Setup", body)


def render_templates(org_id: str) -> str:
    from wizard.templates import TEMPLATES
    cur = get_config(org_id).get("onboarding", {}).get("industry_template") or ""
    cards = "".join(
        "<li style='margin:10px 0'><b>%s</b>%s — <span class='note'>%s</span> "
        "<form method='post' action='/templates/apply' style='display:inline'>"
        "<input type='hidden' name='name' value='%s'><button class='btn'>Apply</button></form></li>"
        % (escape(t["label"]), " ✅ (current)" if name == cur else "", escape(t["blurb"]), name)
        for name, t in TEMPLATES.items())
    flash = ("<div class='saved'>✅ Template applied — tweak anything in the other screens.</div>"
             if request.args.get("applied") else "")
    body = (
        "<div class='nav'><a href='/setup'>← setup</a> · <a href='/customer'>customer</a> · "
        "<a href='/expertise'>expertise</a></div>"
        "<h1>🧩 Starter templates</h1>%s"
        "<p class='note'>Pre-fills typical skills + rules for your kind of business — you change everything "
        "afterwards. (Applying replaces those specific presets; your other settings stay put.)</p>"
        "<div class='box'><ul style='list-style:none;padding-left:0'>%s</ul></div>" % (flash, cards))
    return _page("Templates", body)


# ── GROUPS — the bot's discovered groups + their roles ───────────────────────
def render_groups(org_id: str) -> str:
    groups = list_groups(org_id)
    rows = []
    for g in groups:
        opts = "".join("<option value='%s' %s>%s</option>"
                       % (r, "selected" if (g.get("role") or "") == r else "", r or "— unassigned —")
                       for r in [""] + GROUP_ROLES)
        rows.append("<tr><td>%s</td><td><code>%s</code></td>"
                    "<td><form method='post' action='/groups/role' style='display:inline'>"
                    "<input type='hidden' name='chat_id' value='%s'>"
                    "<select name='role' onchange='this.form.submit()'>%s</select></form></td></tr>"
                    % (escape(g.get("title") or "(untitled group)"), g["chat_id"], g["chat_id"], opts))
    table = "".join(rows) or ("<tr><td colspan='3' class='note'>No groups yet — add your bot to your "
                              "Telegram groups; once someone posts there, the group shows up here.</td></tr>")
    body = (
        "<div class='nav'><a href='/'>← admin</a> · <a href='/customer'>customer</a> · <a href='/staff'>staff</a> · "
        "<a href='/expertise'>expertise</a> · <a href='/bot'>bot setup</a></div>"
        "<h1>💬 Groups</h1>"
        "<p class='note'>Add your bot to your Telegram groups; they appear here automatically. Tag your "
        "<b>staff</b> group so the bot knows where to discover staff for confirm. (Each role is held by one "
        "group.)</p>"
        "<div class='box'><table style='width:100%%;border-collapse:collapse' cellpadding='6'>"
        "<tr style='text-align:left;border-bottom:1px solid #eee'><th>Group</th><th>Chat id</th>"
        "<th>Role</th></tr>%s</table></div>" % table)
    return _page("Groups", body)


# ── Guided BotFather setup (create in BotFather → verify + auto-configure via the Bot API) ──
def render_bot_setup(org_id: str) -> str:
    tel = get_config(org_id).get("connections", {}).get("telegram", {})
    username = tel.get("bot_username")
    has_token = has_org_secret(org_id, "telegram_bot_token")
    if username:
        status = "✅ Connected: <b>@%s</b> — commands configured." % escape(username)
    elif has_token:
        status = "Token saved — press “Verify &amp; configure”."
    else:
        status = "Not connected yet."
    ok, err = request.args.get("ok"), request.args.get("err")
    flash = ("<div class='saved'>✅ Connected to @%s and configured.</div>" % escape(ok) if ok
             else ("<div class='saved' style='background:#fee2e2;border-color:#fca5a5'>⚠ %s</div>" % escape(err)
                   if err else ""))
    steps = ("<ol><li>Open <a href='https://t.me/BotFather' target='_blank'>@BotFather</a> in Telegram.</li>"
             "<li>Send <code>/newbot</code>; give it a name + a username ending in <code>bot</code>.</li>"
             "<li>Copy the <b>token</b> it gives you and paste it below.</li>"
             "<li>Back in BotFather: <code>/setprivacy</code> → <b>Disable</b> — so the bot can read your "
             "staff group for discover-confirm.</li></ol>")
    body = (
        "<div class='nav'><a href='/'>← admin</a> · <a href='/customer'>customer</a> · "
        "<a href='/staff'>staff</a> · <a href='/expertise'>expertise</a></div>"
        "<h1>🤖 Create &amp; connect your bot</h1>%s"
        "<div class='box'><b>Status:</b> %s</div>"
        "<div class='box'><h3>1) Make the bot (in Telegram)</h3>%s</div>"
        "<div class='box'><h3>2) Connect &amp; auto-configure</h3>"
        "<form method='post' action='/bot/provision'>Bot token "
        "<input type='password' name='token' placeholder='paste the BotFather token' style='width:320px'> "
        "<button type='submit'>Verify &amp; configure</button></form>"
        "<p class='note'>We verify the token and set the bot's command menu for you. The token is stored "
        "encrypted and never shown again. (Real Bot-API call — only runs when you submit a token.)</p></div>"
        % (flash, status, steps))
    return _page("Create your bot", body)


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

    @app.get("/expertise")
    def expertise():
        return render_expertise(org_id)

    @app.post("/expertise/role/add")
    def exp_role_add():
        name = (request.form.get("name") or "").strip()[:40]
        if name:
            roles = [r for r in (_exp_cfg(org_id).get("roles") or []) if r.get("name") != name]
            roles.append({"name": name, "min_required": _int(request.form.get("min"), 0, 99, 1)})
            _save_exp(org_id, "roles", roles)
        return redirect("/expertise")

    @app.post("/expertise/role/del")
    def exp_role_del():
        name = request.form.get("name")
        _save_exp(org_id, "roles", [r for r in (_exp_cfg(org_id).get("roles") or []) if r.get("name") != name])
        return redirect("/expertise")

    @app.post("/expertise/override/add")
    def exp_ov_add():
        role = (request.form.get("role") or "").strip()[:40]
        if role:
            ov = list(_exp_cfg(org_id).get("coverage_overrides") or [])
            ov.append({"role": role, "min": _int(request.form.get("min"), 0, 99, 1),
                       "days": [d for d in request.form.getlist("days") if d in _DAYS],
                       "hours": (request.form.get("hours") or "").strip()[:20]})
            _save_exp(org_id, "coverage_overrides", ov)
        return redirect("/expertise")

    @app.post("/expertise/override/del")
    def exp_ov_del():
        ov = list(_exp_cfg(org_id).get("coverage_overrides") or [])
        idx = _int(request.form.get("idx"), 0, len(ov) - 1, -1)
        if 0 <= idx < len(ov):
            ov.pop(idx)
            _save_exp(org_id, "coverage_overrides", ov)
        return redirect("/expertise")

    @app.get("/staff")
    def staff():
        return render_staff(org_id)

    @app.post("/staff/add")
    def staff_add():
        name = (request.form.get("name") or "").strip()[:60]
        if name:
            exps = [e.strip()[:30] for e in (request.form.get("expertises") or "").split(",") if e.strip()]
            add_staff_manual(org_id, name,
                             call_name=((request.form.get("call_name") or "").strip()[:40] or None),
                             role=((request.form.get("role") or "").strip()[:40] or None),
                             is_senior=("is_senior" in request.form), expertises=exps,
                             shift_windows=_windows_from_form(request.form))
        return redirect("/staff")

    @app.post("/staff/del")
    def staff_del():
        sid = _int(request.form.get("staff_id"), 1, 10 ** 12, -1)
        if sid > 0:
            remove_staff(org_id, sid)
        return redirect("/staff")

    @app.post("/staff/import")
    def staff_import():
        for line in (request.form.get("bulk") or "").splitlines():
            d = _parse_staff_line(line.strip())
            if d:
                add_staff_manual(org_id, d["name"], role=d["role"], expertises=d["expertises"],
                                 shift_windows=d["shift_windows"])
        return redirect("/staff")

    @app.get("/staff/edit/<int:sid>")
    def staff_edit(sid):
        return render_staff_edit(org_id, sid)

    @app.post("/staff/update")
    def staff_update():
        sid = _int(request.form.get("staff_id"), 1, 10 ** 12, -1)
        name = (request.form.get("name") or "").strip()[:60]
        if sid > 0 and name:
            exps = [e.strip()[:30] for e in (request.form.get("expertises") or "").split(",") if e.strip()]
            update_staff(org_id, sid, name,
                         call_name=((request.form.get("call_name") or "").strip()[:40] or None),
                         role=((request.form.get("role") or "").strip()[:40] or None),
                         is_senior=("is_senior" in request.form), expertises=exps,
                         shift_windows=_windows_from_form(request.form))
        return redirect("/staff")

    @app.get("/setup")
    def setup():
        return render_setup(org_id)

    @app.get("/templates")
    def templates():
        return render_templates(org_id)

    @app.post("/templates/apply")
    def templates_apply():
        from wizard.templates import apply_template
        apply_template(org_id, request.form.get("name") or "")
        return redirect("/templates?applied=1")

    @app.get("/groups")
    def groups():
        return render_groups(org_id)

    @app.post("/groups/role")
    def groups_role():
        try:
            cid = int(request.form.get("chat_id"))
        except (TypeError, ValueError):
            cid = None
        if cid is not None:
            set_group_role(org_id, cid, request.form.get("role") or "")
        return redirect("/groups")

    @app.get("/bot")
    def bot_setup():
        return render_bot_setup(org_id)

    @app.post("/bot/provision")
    def bot_provision():
        token = (request.form.get("token") or "").strip()
        if not token:
            return redirect("/bot?err=" + quote("Paste a token first."))
        from adapters.telegram_provision import provision
        res = provision(token)
        if res.get("ok"):
            set_org_secret(org_id, "telegram_bot_token", token)         # store the VERIFIED token (encrypted-pending)
            set_config(org_id, {"connections": {"telegram": {"bot_username": res["username"]}}})
            return redirect("/bot?ok=" + quote(res["username"]))
        return redirect("/bot?err=" + quote(res.get("error", "could not connect")[:120]))

    @app.get("/healthz")
    def healthz():
        return "ok"

    return app


app = create_app()
