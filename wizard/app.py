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
import json
import os
import re
from html import escape
from urllib.parse import quote

from flask import Flask, request, redirect, session

from core.tenant_config import get_config, set_config, raw_overrides, DEFAULTS
from core.db import (set_org_secret, has_org_secret, verify_user, user_count,
                     log_config_change, recent_config_audit)
from core.whatif import verdict_whatif
from core.health import config_health
from core.shadow import comparison_stats, comparison_stats_by_kind, recent_mismatches, comparison_span
from core.reports import attendance_report
from core.onboarding_flow import (list_staff, add_staff_manual, remove_staff, get_staff, update_staff,
                                  list_groups, set_group_role, GROUP_ROLES,
                                  list_candidates, group_id_for_role,
                                  ensure_checkin_token, staff_by_checkin_token)
from wizard.status import status_for, LEGEND, summary, EDITABLE
from wizard import catalog, schema
from wizard.card_details import CARD_DETAILS, TOGGLES

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


def _admin_dashboard(org_id: str) -> str:
    cfg = get_config(org_id)
    st = _setup_state(org_id)
    audit = recent_config_audit(org_id, 1)
    last = ("last change %s <code>%s</code> by %s" % (str(audit[0]["at"])[:16], escape(audit[0]["path"]),
            escape(audit[0]["who"] or "?"))) if audit else "no config changes yet"
    health = "⚠️ %d warning(s)" % len(st["warns"]) if st["warns"] else "✅ config healthy"
    return ("<div class='box'><b>📊 At a glance</b> &nbsp; <a href='/setup'>setup %d/%d</a> · %d staff · "
            "%d groups · channels: %s · <a href='/health'>%s</a> · %s</div>"
            % (st["done"], st["total"], len(st["staff"]), len(list_groups(org_id)),
               escape(", ".join(cfg.get("channels", []) or []) or "—"), health, last))


def render_page(org_id: str = "twb") -> str:
    cfg = get_config(org_id)
    legend = " &nbsp; ".join("%s <small style='color:#555'>%s</small>" % (_badge(k), escape(v))
                             for k, v in LEGEND.items())
    body = ("<div class='nav'><b>Admin</b> · <a href='/customer'>⚡ dashboard</a> · <a href='/setup'>setup</a> · "
            "<a href='/customer/config'>config</a> · "
            "<a href='/staff'>staff</a> · <a href='/expertise'>expertise</a> · <a href='/groups'>groups</a> · "
            "<a href='/bot'>bot setup</a> · <a href='/templates'>templates</a> · <a href='/whatif'>what-if</a> · "
            "<a href='/audit'>audit</a> · <a href='/health'>health</a> · <a href='/shadow'>shadow</a> · "
            "<a href='/export'>export</a></div>"
            "<h1>🧩 Wizard · tenant <code>%s</code> · admin <small style='color:#888'>(internal — badges, read-only)</small></h1>"
            "%s%s<div class='box'><b>Legend:</b> %s</div>"
            "<h2>Effective config</h2><div class='box'><ul>%s</ul></div>"
            "<h2>The menu</h2><div class='box'>%s</div>"
            % (escape(org_id), _admin_dashboard(org_id), render_cutover(org_id), legend,
               _render_node(cfg, "", org_id), _render_catalog()))
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


_CONFIGURABLE_DOMAINS = {"accountant", "stock", "pos", "hr_payroll"}   # have their own editable sections above


def _editable_bool_paths() -> list:
    out = []
    for _g, ps in (schema.ATTENDANCE_GROUPS + schema.CONNECTIONS_GROUPS + schema.ONBOARDING_GROUPS
                   + schema.EXTRA_DOMAIN_GROUPS):
        for p in ps:
            d = schema.describe(p)
            if d and d.get("type") == "bool" and status_for(p) in EDITABLE:
                out.append(p)
    return out


# Hidden field naming the editable bools on the customer form, so Apply can tell "unchecked" from "absent".
_SCOPE_FIELD = "<input type='hidden' name='_scope' value='%s'>" % ",".join(_editable_bool_paths())


def _render_locked_modules(cfg: dict) -> str:
    rows = []
    for name, c in catalog.CATEGORIES.items():
        if c["live"] or name in _CONFIGURABLE_DOMAINS:   # don't also list a configurable domain as upsell
            continue
        pkgs = [p for p, cs in catalog.PACKAGES.items() if name in cs]
        rows.append("<li>🔒 <b>%s</b> — %s <br><small class='note'>available in: %s · integrations: %s</small></li>"
                    % (escape(name), escape(c["blurb"]), escape(", ".join(pkgs) or "—"),
                       escape(" · ".join(c["integrations"]))))
    return "<ul>%s</ul>" % "".join(rows)


def _health_banner(org_id: str) -> str:
    """Show the CUSTOMER their own config warnings (warn-level only) at the top of their view."""
    warns = [m for lvl, m in config_health(org_id) if lvl == "warn"]
    if not warns:
        return ""
    items = "".join("<li>%s</li>" % escape(m) for m in warns)
    return ("<div class='saved' style='background:#fef3c7;border-color:#fcd34d'>"
            "<b>⚠️ A few things worth checking:</b><ul>%s</ul></div>" % items)


def render_customer(org_id: str = "twb", saved: bool = False) -> str:
    cfg = get_config(org_id)
    saved_banner = '<div class="saved">✓ Your changes were applied.</div>' if saved else ""
    body = ("<div class='nav'><a href='/'>← admin</a> · <a href='/dashboard'>⚡ dashboard</a> · "
            "<a href='/setup'>setup</a> · <a href='/staff'>staff</a> · "
            "<a href='/expertise'>expertise</a> · <a href='/groups'>groups</a> · <a href='/bot'>bot setup</a></div>"
            "<h1>⚙️ Configure your system</h1>"
            "<p class='note'>Play with anything — <b>nothing changes until you press “Apply changes”.</b> "
            "“Cancel” throws away your edits. Settings marked 🔒 are live today with fixed rules (you'll set "
            "those when we switch them over). Tokens are write-only — paste to set, never shown back.</p>%s%s"
            "<form method='post' action='/customer/apply'>%s"
            "<h2>Setup &amp; staff</h2><div class='box'>"
            "<p class='note'>How your system gets set up. The easy path: we guide you to create a bot, you "
            "add it to your groups, and it <b>finds your staff for you to confirm one-by-one</b> — no typing "
            "lists. (The guided bot-creation + staff discover-confirm flow is the next build.)</p>%s</div>"
            "<h2>Attendance</h2><div class='box'>%s<p class='note'>"
            "<a href='/whatif'>🔮 Preview how a grace/early change would reclassify recent check-ins</a></p></div>"
            "<h2>Accountant</h2><div class='box'><p class='note'>Built; not live yet — set your preferences "
            "now, they apply when it's switched on.</p>%s</div>"
            "<h2>Stock</h2><div class='box'><p class='note'>Built features modelled; not live yet.</p>%s</div>"
            "<h2>POS</h2><div class='box'><p class='note'>Modelled; not live yet.</p>%s</div>"
            "<h2>HR &amp; payroll</h2><div class='box'><p class='note'>Modelled; not live yet.</p>%s</div>"
            "<h2>Connections (channels &amp; tokens)</h2><div class='box'>%s</div>"
            "<div class='actions'><button type='submit'>✓ Apply changes</button>"
            "<a href='/customer/config' class='btn'>✗ Cancel changes</a> "
            "<a href='/audit' class='btn'>📝 Change history</a></div></form>"
            "<h2>Approvals</h2><div class='box'>%s</div>"
            "<h2>Add more to your system</h2><div class='box'>%s</div>"
            % (saved_banner, _health_banner(org_id), _SCOPE_FIELD,
               _render_groups(cfg, schema.ONBOARDING_GROUPS, org_id),
               _render_groups(cfg, schema.ATTENDANCE_GROUPS, org_id),
               _render_groups(cfg, schema.ACCOUNTANT_GROUPS, org_id),
               _render_groups(cfg, schema.STOCK_GROUPS, org_id),
               _render_groups(cfg, schema.POS_GROUPS, org_id),
               _render_groups(cfg, schema.HR_GROUPS, org_id),
               _render_groups(cfg, schema.CONNECTIONS_GROUPS, org_id), _render_approvals(cfg),
               _render_locked_modules(cfg)))
    return _page("Configure — your system", body)


def apply_changes(org_id: str, form) -> dict:
    """Commit ONLY safe knobs: SHADOW/PLANNED config values (validated) + any SECRET written (to the encrypted
    store, never the config). LIVE / LIVE_FIXED and unknown keys are ignored — a customer can't touch a live
    knob or write an arbitrary key from here."""
    cfg = get_config(org_id)
    over: dict = {}
    changes: list = []                                         # (path, old, new) for the audit trail
    # A checkbox sends nothing when unchecked, so "absent" is ambiguous. The form posts a hidden `_scope`
    # listing the bool paths it actually rendered → we only flip those (absent-in-scope = off; out-of-scope
    # = leave alone). Without `_scope` (a partial/programmatic call) we touch NO bools — never mass-reset.
    raw_scope = form.get("_scope")
    scope = None if raw_scope is None else set(filter(None, raw_scope.split(",")))

    def _put(path, newval):
        if _get_path(cfg, path) != newval:
            changes.append((path, _get_path(cfg, path), newval))
        _set_path(over, path, newval)

    for _glabel, paths in (schema.ATTENDANCE_GROUPS + schema.CONNECTIONS_GROUPS + schema.ONBOARDING_GROUPS
                           + schema.EXTRA_DOMAIN_GROUPS):
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
                    changes.append((path, "(secret)", "(secret set)"))   # log the act, never the value
                continue
            if status_for(path) not in EDITABLE:               # only safe shadow/planned config knobs
                continue
            if t == "bool":
                if scope is not None and path in scope:        # only flip bools this form actually carried
                    _put(path, path in form)
            elif t == "int":
                try:
                    v = int(form.get(path, ""))
                except (TypeError, ValueError):
                    continue
                _put(path, max(desc.get("min", v), min(desc.get("max", v), v)))
            elif t == "enum":
                v = form.get(path)
                if v in [opt[0] for opt in desc["options"]]:
                    _put(path, v)
            elif t == "text":
                _put(path, (form.get(path) or "").strip())
    if over:
        set_config(org_id, over)
    if changes:
        who = _current_user()
        for path, old, new in changes:
            log_config_change(org_id, who, path, old, new)
    return over


def _current_user() -> str:
    try:
        return session.get("user") or "owner"
    except Exception:
        return "owner"


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
        "<td><a href='/staff/edit/%d' class='btn'>edit</a> <a href='/staff/link/%d' class='btn'>link</a> "
        "<form method='post' action='/staff/del' style='display:inline'>"
        "<input type='hidden' name='staff_id' value='%d'><button class='btn'>remove</button></form></td></tr>"
        % (escape(s.get("name", "")), escape(s.get("role") or ""), "senior" if s.get("is_senior") else "",
           escape(", ".join(s.get("expertises") or [])), escape(_windows_str(s.get("shift_windows"))),
           s["staff_id"], s["staff_id"], s["staff_id"])
        for s in staff) or ("<tr><td colspan='6' class='note'>No staff yet — the bot can <b>discover</b> them "
                            "from your staff group (it stages whoever posts), or add one below / paste a list.</td></tr>")
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
def _setup_state(org_id: str) -> dict:
    """Onboarding progress — the single source for both /setup and the dashboard (so they can't drift)."""
    cfg = get_config(org_id)
    bot_user = cfg.get("connections", {}).get("telegram", {}).get("bot_username")
    staff_grp = group_id_for_role(org_id, "staff")
    staff = list_staff(org_id)
    warns = [m for lvl, m in config_health(org_id) if lvl == "warn"]
    flags = [bool(bot_user), bool(staff_grp), len(staff) > 0, True, not warns]
    return {"bot_user": bot_user, "staff_grp": staff_grp, "staff": staff, "warns": warns,
            "done": sum(flags), "total": len(flags)}


def render_setup(org_id: str) -> str:
    st = _setup_state(org_id)
    bot_user, staff_grp, staff, warns = st["bot_user"], st["staff_grp"], st["staff"], st["warns"]
    pending = list_candidates(org_id)

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
        step(True, "Set your rules", "/customer/config","attendance · leave · OT · approvals — tweak anytime"),
        step(not warns, "Clear config warnings", "/health",
             ("%d to resolve" % len(warns)) if warns else "no warnings"),
    ])
    done_n = st["done"]
    ready_banner = ("<div class='saved'>🎉 You're ready to go live!</div>" if done_n == st["total"] else "")
    body = (
        "<div class='nav'><a href='/'>← admin</a> · <a href='/customer'>customer</a> · <a href='/bot'>bot</a> · "
        "<a href='/groups'>groups</a> · <a href='/staff'>staff</a> · <a href='/expertise'>expertise</a></div>"
        "<h1>🚀 Setup — %d of %d done</h1>%s"
        "<p class='note'>Work through these in any order. The bot does the heavy lifting — you just confirm.</p>"
        "<div class='box'><ul style='list-style:none;padding-left:0;line-height:1.8'>%s</ul></div>"
        "<p class='note'>New here? <a href='/templates'>Start from a template</a> to pre-fill typical "
        "skills + rules.</p>"
        % (done_n, st["total"], ready_banner, steps))
    return _page("Setup", body)


# ── DASHBOARD (task-card / completion prototype — benefit-framed cards + colour-shifting bars) ──────────
def _bar_color(frac: float) -> str:
    """Calm amber→teal→green progression (no harsh red — 'not yet' isn't an error)."""
    if frac >= 1.0:
        return "#16a34a"   # green — done
    if frac >= 0.67:
        return "#0d9488"   # teal — getting there
    if frac >= 0.34:
        return "#d97706"   # amber
    if frac > 0:
        return "#f59e0b"   # light amber — started
    return "#9ca3af"       # grey — not started


# Filter index (sticky): "All tools" + named categories → show fewer boxes. (id, label, icon)
_DASH_CATS = [("all", "All tools", "▦"), ("att", "Attendance", "⏱️"), ("cover", "Coverage", "🎯"),
              ("acct", "Accountant", "🍚"), ("stock", "Stock", "📦"), ("pos", "POS", "🛒"),
              ("hr", "Payroll", "💼"), ("more", "Coming soon", "✨")]

# Cascade copy (the "what one task unlocks" reveal — STARTER drafts for the owner to shave).
_CASCADES = {
    "Connect bot": "Staff clock in from their phone — no hardware. Switches on every attendance feature below.",
    "Add your team": "Once they're in: lateness, hours, overtime, points and leave all track on their own.",
    "Tag staff group": "The bot watches that one group and finds new staff for you — confirm with a tap, no typing.",
    "Settings sane": "Your grace / overtime / leave rules with no conflicts — so pay and penalties compute right.",
    "Always covered": "Set how many of each skill you need on shift — get warned before a shift is understaffed.",
    "Turn on accounting": "Snap a receipt → logged as an expense, supplier tracked, prices remembered.",
    "Food allowance": "Staff meal money worked out automatically from who actually worked — no tallying.",
    "Turn on stock": "Track what you have, get low-stock alerts, and build order lists without guesswork.",
    "Par levels": "Set a level once → a reorder nudge before you run out, every time.",
    "Price compare": "Each item's price across suppliers → buy from the cheapest, flagged for you.",
    "Turn on POS": "Ring up sales on any phone — or tap your existing till — tied into stock and reports.",
    "Accept KHQR": "Take Bakong / KHQR payments at checkout — money in, logged instantly.",
    "Turn on payroll": "Turn tracked hours and overtime into pay runs and payslips — no spreadsheets.",
    "Payslips": "Each staffer gets a clear payslip automatically every cycle.",
    "Reports & trends": "See trends over time — busiest days, lateness patterns, top expenses, slow stock.",
    "AI assist": "The system flags oddities and suggests fixes — a late spike, a price jump, a stockout risk.",
    "Automations": "Build your own 'if this → then that' — e.g. if a baker calls in sick, alert the senior.",
    "Learn": "Short guided how-tos right where you are — no manuals, no training day.",
    "Marketplace": "Add-ons and connections to tools you already use — switch on only what you need.",
    "Mobile app": "Your own branded app for staff and customers — on top of Telegram and web.",
}


def dashboard_cards(org_id: str) -> dict:
    """The customer dashboard as benefit-framed task BOXES, each with REAL completion, tagged by category
    (for the sticky filter) and weighted by `value` (for the stable order + the 'do next' spotlight). A
    sub-step only counts once its module is on. Copy/values are STARTER drafts for the owner to shave."""
    st = _setup_state(org_id)
    cfg = get_config(org_id)
    cats, fr = cfg.get("categories", {}), cfg.get("frontier", {})
    att, exp = cats.get("attendance", {}), cats.get("attendance", {}).get("expertise", {})
    acc, stk, pos, hr = (cats.get("accountant", {}), cats.get("stock", {}),
                         cats.get("pos", {}), cats.get("hr_payroll", {}))
    has_bot, has_grp, has_staff = bool(st["bot_user"]), bool(st["staff_grp"]), len(st["staff"]) > 0
    b = lambda x: 1 if x else 0

    def box(cat, icon, name, reward, link, value, done, total=1):
        label = "✓ done" if done >= total else ("tap to start" if done == 0 else "%d/%d" % (done, total))
        return {"cat": cat, "icon": icon, "name": name, "reward": reward, "link": link, "value": value,
                "done": done, "total": total, "label": label, "cascade": _CASCADES.get(name, "")}

    em = (1 if exp.get("enabled") else 0) + (1 if exp.get("enabled") and exp.get("roles") else 0)
    cards = [
        box("att", "🤖", "Connect bot", "staff clock in by phone", "/bot", 100, b(has_bot)),
        box("att", "👥", "Add your team", "everyone tracked", "/staff", 95, b(has_staff)),
        box("att", "🏷️", "Tag staff group", "the bot finds your team", "/groups", 90, b(has_grp)),
        box("att", "✅", "Settings sane", "no rule conflicts", "/health", 60, b(not st["warns"])),
        box("cover", "🎯", "Always covered", "never understaffed on a skill", "/card/coverage", 70, em, 2),
        box("acct", "🍚", "Turn on accounting", "receipts → expenses, auto", "/card/accountant", 58, b(acc.get("enabled"))),
        box("acct", "🍱", "Food allowance", "staff meal money, auto", "/card/accountant", 40,
            b(acc.get("enabled") and acc.get("food_money", {}).get("enabled"))),
        box("stock", "📦", "Turn on stock", "track inventory", "/card/stock", 45, b(stk.get("enabled"))),
        box("stock", "📊", "Par levels", "reorder before you run out", "/card/stock", 35,
            b(stk.get("enabled") and stk.get("par_levels"))),
        box("stock", "💲", "Price compare", "buy from the cheapest", "/card/stock", 30,
            b(stk.get("enabled") and stk.get("supplier_price_compare"))),
        box("pos", "🛒", "Turn on POS", "be the till", "/card/pos", 36, b(pos.get("enabled"))),
        box("pos", "📱", "Accept KHQR", "take QR payments", "/card/pos", 26,
            b(pos.get("enabled") and pos.get("khqr_payments"))),
        box("hr", "💼", "Turn on payroll", "slips + pay runs", "/card/hr_payroll", 32, b(hr.get("enabled"))),
        box("hr", "🧾", "Payslips", "auto payslips", "/card/hr_payroll", 22,
            b(hr.get("enabled") and hr.get("payslips"))),
    ]
    # Frontier capabilities (borrowed from the leaders) — wired in, OFF by default → the owner sees the full
    # breadth + where the shop is 0%; flip them on per client when ready. Each opens its own industry-std inside.
    frontier = [
        box("more", "📊", "Reports & trends", "who/what/when over time", "/card/reports", 20, b(fr.get("reports"))),
        box("more", "🤖", "AI assist", "smart suggestions & alerts", "/card/ai_assist", 18, b(fr.get("ai_assist"))),
        box("more", "⚙️", "Automations", "your own if-this-then rules", "/card/automations", 16, b(fr.get("automations"))),
        box("more", "🎓", "Learn", "guided how-tos in-app", "/card/learn", 12, b(fr.get("learn"))),
        box("more", "🧩", "Marketplace", "add-ons & integrations", "/card/marketplace", 10, b(fr.get("marketplace"))),
        box("more", "📱", "Mobile app", "your branded app", "/card/mobile_app", 8, b(fr.get("mobile_app"))),
    ]
    for f in frontier:
        f["label"] = "on ✓" if f["done"] else "coming soon"
    cards += frontier
    # PACKAGE GATING (lean-per-client): a domain card not in the tenant's plan shows LOCKED (upsell); frontier
    # cards are add-ons (never locked). Locked cards don't count toward progress or the spotlight.
    pkg = cfg.get("package", "attendance")
    pkg_cats = set(catalog.PACKAGES.get(pkg, []))
    _cat_pkg = {"att": "attendance", "cover": "attendance", "acct": "accountant",
                "stock": "stock", "pos": "pos", "hr": "hr_payroll"}
    for c in cards:
        m = _cat_pkg.get(c["cat"])
        c["locked"] = bool(m) and m not in pkg_cats
    cards.sort(key=lambda c: -c["value"])                 # STABLE order by value (never reshuffles)
    active = [c for c in cards if not c.get("locked")]
    nxt = [c for c in active if c["done"] < c["total"]][:4]  # biggest wins still to do (in-plan only) → spotlight
    return {"cards": cards, "next": nxt, "cats": _DASH_CATS, "package": pkg,
            "done": sum(c["done"] for c in active), "total": sum(c["total"] for c in active)}


def _dash_card(c: dict) -> str:
    if c.get("locked"):                                   # out-of-plan → upsell tile (no toggle/progress)
        return ("<div class='dcard' data-cat='%s' style='border:1px dashed #d1d5db;border-radius:14px;"
                "padding:16px;background:#fafafa;opacity:.8'>"
                "<div style='font-size:22px'>%s</div>"
                "<div style='font-weight:600;margin-top:6px;color:#6b7280'>🔒 %s</div>"
                "<div style='color:#9ca3af;font-size:13px'>%s</div>"
                "<div style='color:#9ca3af;font-size:12px;margin-top:8px'>in a higher plan · "
                "<a href='/packages'>see plans →</a></div></div>"
                % (escape(c.get("cat", "all")), c["icon"], escape(c["name"]), escape(c["reward"])))
    frac = (c["done"] / c["total"]) if c["total"] else 0
    bar = ("<div style='background:#eef0f2;border-radius:6px;height:8px;margin:8px 0 6px'>"
           "<div style='background:%s;height:8px;border-radius:6px;width:%d%%'></div></div>"
           % (_bar_color(frac), int(frac * 100)))
    more = (("<details onclick='event.stopPropagation()' style='margin-top:8px'>"
             "<summary style='cursor:pointer;color:#0c4a6e;font-size:12px'>what you unlock ›</summary>"
             "<div style='font-size:12px;color:#374151;margin-top:5px;line-height:1.4'>%s</div></details>"
             % escape(c["cascade"])) if c.get("cascade") else "")
    return ("<div class='dcard' data-cat='%s' onclick=\"location.href='%s'\" "
            "style='cursor:pointer;border:1px solid #e5e7eb;border-radius:14px;padding:16px;background:#fff'>"
            "<div style='font-size:22px'>%s</div><div style='font-weight:600;margin-top:6px'>%s</div>"
            "<div style='color:#6b7280;font-size:13px'>%s</div>%s"
            "<div style='color:#6b7280;font-size:12px'>%s</div>%s</div>"
            % (escape(c.get("cat", "all")), escape(c["link"]), c["icon"], escape(c["name"]),
               escape(c["reward"]), bar, escape(c["label"]), more))


def render_dashboard(org_id: str) -> str:
    from core.attendance import today_summary
    d = dashboard_cards(org_id)
    ts = today_summary(org_id)
    live = (("<div class='box' style='background:#ecfdf5;border-color:#a7f3d0'>"
             "<b>🟢 Live today</b> &nbsp; ⏱️ <b>%d</b> in · <b>%d</b> late "
             "<span class='note'>— the 'evolving card': once a domain is set up, its card flips to today's "
             "status instead of setup steps</span></div>" % (ts["in"], ts["late"])) if ts["in"] else "")
    frac = (d["done"] / d["total"]) if d["total"] else 0
    pct = int(frac * 100)
    big_bar = ("<div style='background:#eef0f2;border-radius:8px;height:12px;margin:10px 0'>"
               "<div style='background:%s;height:12px;border-radius:8px;width:%d%%'></div></div>"
               % (_bar_color(frac), pct))
    grid = ("<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;"
            "margin:12px 0'>" + "".join(_dash_card(c) for c in d["cards"]) + "</div>")
    if d["next"]:
        chips = "".join("<a href='%s' style='display:inline-block;margin:6px 8px 0 0;padding:7px 13px;"
                        "background:#fff;border:1px solid #bae6fd;border-radius:20px;text-decoration:none;"
                        "color:#0c4a6e;font-size:14px'>%s <b>%s</b> <span style='color:#64748b'>· %s</span></a>"
                        % (escape(c["link"]), c["icon"], escape(c["name"]), escape(c["reward"])) for c in d["next"])
        spotlight = ("<div class='box' style='background:#f0f9ff;border-color:#bae6fd'>"
                     "<b>👉 Do this next</b> &nbsp;<span class='note'>biggest wins still to do — one click each</span>"
                     "<div>%s</div></div>" % chips)
    else:
        spotlight = ("<div class='box' style='background:#f0fdf4;border-color:#bbf7d0'>"
                     "<b>✓ You're all set up</b> &nbsp;<span class='note'>tweak anything below, anytime</span></div>")
    pills = "".join(
        "<button class='fpill' data-cat='%s' onclick=\"filt('%s')\" style='margin:0 6px 6px 0;padding:6px 12px;"
        "border:1px solid #e5e7eb;border-radius:20px;background:%s;color:%s;cursor:pointer;font-size:13px'>"
        "%s %s</button>"
        % (cid, cid, "#0c4a6e" if cid == "all" else "#fff", "#fff" if cid == "all" else "#111", icon, escape(label))
        for cid, label, icon in d["cats"])
    filter_bar = ("<div style='position:sticky;top:0;z-index:5;background:#fafafa;padding:10px 0;"
                  "border-bottom:1px solid #eee;margin-bottom:10px;white-space:nowrap;overflow-x:auto'>%s</div>"
                  % pills)
    js = ("<script>function filt(c){"
          "document.querySelectorAll('.dcard').forEach(function(e){e.style.display=(c==='all'||e.dataset.cat===c)?'':'none';});"
          "document.querySelectorAll('.fpill').forEach(function(p){var on=p.dataset.cat===c;"
          "p.style.background=on?'#0c4a6e':'#fff';p.style.color=on?'#fff':'#111';});}</script>")
    body = ("<div class='nav'><a href='/customer/config'>detailed view</a> · <a href='/'>admin</a></div>"
            "<h1>⚡ Your system</h1>%s%s%s"
            "<div class='box'><b>%d%% set up</b> &nbsp;<span class='note'>plan: "
            "<a href='/packages'>%s</a> — locked cards need a higher plan</span>%s</div>%s"
            "<p class='note'>Prototype — pick a category above to narrow · order is fixed (find anything fast) · "
            "the spotlight shows what's next. Names are drafts; tap a card to open it.</p>%s"
            % (filter_bar, live, spotlight, pct, escape(d["package"].replace("_", " ").title()), big_bar, grid, js))
    return _page("Dashboard", body)


def render_reports(org_id: str) -> str:
    """📊 The first frontier capability built out — attendance trends over time (read-only)."""
    rep = attendance_report(org_id, 14)
    maxt = max([d["total"] for d in rep["daily"]], default=1)
    rows = "".join(
        "<tr><td>%s</td><td>%d</td><td>%d</td>"
        "<td><div style='background:#eef0f2;border-radius:4px;height:10px;width:160px;display:inline-block'>"
        "<div style='background:%s;height:10px;border-radius:4px;width:%d%%'></div></div></td></tr>"
        % (escape(d["day"]), d["total"], d["late"],
           _bar_color(1 - (d["late"] / d["total"] if d["total"] else 0)), int(100 * d["total"] / maxt))
        for d in rep["daily"]) or "<tr><td colspan='4' class='note'>No check-ins recorded yet.</td></tr>"
    body = ("<div class='nav'><a href='/customer'>← dashboard</a> · <a href='/'>admin</a></div>"
            "<h1>📊 Reports — attendance (last 14 days)</h1>"
            "<div class='box'><b>%d check-ins · %d late · %d%% on-time</b></div>"
            "<div class='box'><table style='width:100%%;border-collapse:collapse' cellpadding='6'>"
            "<tr style='text-align:left;border-bottom:1px solid #eee'><th>Day</th><th>Check-ins</th>"
            "<th>Late</th><th>Volume</th></tr>%s</table></div>"
            "<p class='note'>The first report — built from the platform's attendance data. Expense, stock and "
            "sales reports follow as those domains record data. (Bar greener = fewer late that day.)</p>"
            % (rep["total"], rep["late"], rep["on_time_rate"], rows))
    return _page("Reports", body)


# Card key → the module's master enable path (so a card's inside can turn the whole module on/off).
_CARD_ENABLE = {
    "accountant": "categories.accountant.enabled", "stock": "categories.stock.enabled",
    "pos": "categories.pos.enabled", "hr_payroll": "categories.hr_payroll.enabled",
    "coverage": "categories.attendance.expertise.enabled",
    "reports": "frontier.reports", "ai_assist": "frontier.ai_assist", "automations": "frontier.automations",
    "learn": "frontier.learn", "marketplace": "frontier.marketplace", "mobile_app": "frontier.mobile_app",
}


def render_card_detail(org_id: str, key: str) -> str:
    """A card's own inside — a master on/off for the module, the industry-standard menu with wired options as
    TOGGLES (config-driven; behavior follows per option), and idea options as status badges."""
    d = CARD_DETAILS.get(key)
    if not d:
        return _page("Not found", "<div class='nav'><a href='/customer'>← dashboard</a></div>"
                     "<div class='box'>Unknown card.</div>")
    toggles = TOGGLES.get(key, {})
    cfg = get_config(org_id)
    ep = _CARD_ENABLE.get(key)
    master = ""
    if ep:
        on = bool(_get_path(cfg, ep))
        master = ("<div class='box' style='background:%s'><label style='cursor:pointer;font-size:15px'>"
                  "<input type='checkbox' name='%s' %s> <b>This module is %s</b> "
                  "<span class='note'>— tick to turn on / untick to turn off</span></label></div>"
                  % ("#ecfdf5" if on else "#fafafa", escape(ep), "checked" if on else "", "ON" if on else "OFF"))
    badge = {"built": ("#16a34a", "✓ built"), "planned": ("#d97706", "planned"), "idea": ("#6b7280", "idea")}
    items = []
    for name, desc, st in d["options"]:
        if name in toggles:
            on = bool(_get_path(cfg, toggles[name]))
            items.append(
                "<li style='margin:10px 0'><label style='cursor:pointer'><input type='checkbox' name='%s' %s> "
                "<b>%s</b> <span style='background:%s;color:#fff;border-radius:10px;padding:1px 8px;font-size:11px'>"
                "%s</span></label><br><span class='note'>%s</span></li>"
                % (escape(toggles[name]), "checked" if on else "", escape(name),
                   "#0d9488" if on else "#9ca3af", "on" if on else "off", escape(desc)))
        else:
            items.append(
                "<li style='margin:10px 0'><b>%s</b> &nbsp;<span style='background:%s;color:#fff;"
                "border-radius:10px;padding:1px 8px;font-size:11px'>%s</span><br><span class='note'>%s</span></li>"
                % (escape(name), badge[st][0], badge[st][1], escape(desc)))
    saved = "<div class='saved'>✓ Saved.</div>" if request.args.get("saved") else ""
    extra = ""
    if key == "ai_assist":                                # the "Computer / AI Power" tier lives on the AI card
        tier = cfg.get("ai_power", "computer")
        opts = "".join("<label style='display:block;margin:5px 0'><input type='radio' name='ai_power' value='%s' %s> "
                       "<b>%s</b> — <span class='note'>%s</span></label>"
                       % (k, "checked" if k == tier else "", escape(k), escape(v))
                       for k, v in catalog.AI_POWER.items())
        extra = ("<div class='box'><h3>AI power tier</h3>"
                 "<p class='note'>How decisions are made — rules vs a model, per the catalog.</p>%s</div>" % opts)
    save_btn = ("<div class='actions'><button type='submit'>Save</button></div>" if (ep or toggles or extra) else "")
    body = ("<div class='nav'><a href='/customer'>← dashboard</a> · <a href='%s'>open / configure →</a></div>"
            "<h1>%s %s</h1>%s"
            "<div class='box'><p>%s</p><p class='note'>Industry standard — like %s. &nbsp;<b>%d</b> options · "
            "<b>%d</b> toggleable now.</p></div>"
            "<form method='post' action='/card/%s/save'>%s%s<div class='box'><h3>What's inside</h3>"
            "<ul style='list-style:none;padding-left:0'>%s</ul>%s</div></form>"
            "<p class='note'>Toggle on what you want — config-driven, behavior follows per option. "
            "<span style='color:#16a34a'>✓ built</span> · <span style='color:#d97706'>planned</span> · "
            "<span style='color:#6b7280'>idea</span>.</p>"
            % (escape(d["configure"]), d["icon"], escape(d["title"]), saved, escape(d["what"]), escape(d["ref"]),
               len(d["options"]), len(toggles), escape(key), master, extra, "".join(items), save_btn))
    return _page(d["title"], body)


def render_packages(org_id: str) -> str:
    """Plans — what each unlocks + switch. Switching changes which dashboard cards are active vs locked."""
    cur = get_config(org_id).get("package", "attendance")
    rows = ""
    for pkg, catlist in catalog.PACKAGES.items():
        is_cur = (pkg == cur)
        rows += ("<div class='box' style='%s'><b>%s</b> %s<br>"
                 "<span class='note'>includes: %s</span><br>"
                 "<form method='post' action='/packages/set' style='margin-top:8px'>"
                 "<input type='hidden' name='package' value='%s'>"
                 "<button %s>%s</button></form></div>"
                 % ("border-color:#16a34a" if is_cur else "", escape(pkg.replace("_", " ").title()),
                    "<span style='color:#16a34a'>✓ current</span>" if is_cur else "",
                    escape(", ".join(catlist)), escape(pkg),
                    "disabled" if is_cur else "", "current plan" if is_cur else "switch to this"))
    body = ("<div class='nav'><a href='/customer'>← dashboard</a> · <a href='/'>admin</a></div>"
            "<h1>🎟️ Plans</h1><p class='note'>What each plan unlocks. Switching changes which cards are active "
            "vs locked on the dashboard — your client only sees their slice.</p>%s" % rows)
    return _page("Plans", body)


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


# ── AUTH (W3 foundation — OFF by default; localhost+tunnel = owner-only) ───────
def auth_enabled() -> bool:
    """Logins are OFF unless WIZARD_AUTH=1 (then it's required for public/multi-tenant). Seed a user with
    core.db.create_user(org, username, password). ⚠ before PUBLIC exposure also add CSRF + login rate-limit
    + HTTPS (W3). Until then the wizard stays localhost-only behind the SSH tunnel."""
    return os.environ.get("WIZARD_AUTH") == "1"


def render_login() -> str:
    err = ("<div class='saved' style='background:#fee2e2;border-color:#fca5a5'>Wrong username or password.</div>"
           if request.args.get("err") else "")
    body = ("<h1>🔒 Wizard login</h1>%s<div class='box'><form method='post' action='/login'>"
            "Username <input type='text' name='username'><br><br>"
            "Password <input type='password' name='password'><br><br>"
            "<button type='submit'>Log in</button></form></div>" % err)
    return _page("Login", body)


# ── WEB CHECK-IN channel (browser check-in via a per-staff link → core; platform, not TWB live) ──
def render_staff_link(org_id: str, staff_id: int) -> str:
    s = get_staff(org_id, staff_id)
    if not s:
        return _page("Link", "<div class='nav'><a href='/staff'>← staff</a></div><p>Not found.</p>")
    url = "%s/checkin/%s" % (request.host_url.rstrip("/"), ensure_checkin_token(org_id, staff_id))
    body = ("<div class='nav'><a href='/staff'>← staff</a></div><h1>🔗 Check-in link — %s</h1>"
            "<div class='box'><p>Share this private link with <b>%s</b>; opening it on their phone checks "
            "them in (browser channel — no app, no Telegram needed):</p><p><code>%s</code></p>"
            "<p class='note'>The link is their identity — keep it private. Records to the platform, never "
            "TWB's live attendance.</p></div>"
            % (escape(s.get("name", "")), escape(s.get("name", "")), escape(url)))
    return _page("Check-in link", body)


def _do_web_checkin(staff: dict, lat, lon) -> dict:
    from datetime import datetime, timezone
    from core.attendance import check_in as core_check_in
    org = staff["org_id"]
    w = (staff.get("shift_windows") or [{}])[0]
    if not w.get("start") or not w.get("end"):
        return {"ok": False, "error": "no shift set for you yet — your manager sets your hours"}
    v = get_config(org).get("categories", {}).get("attendance", {}).get("verdict", {})
    try:
        res = core_check_in(org, staff["staff_id"], datetime.now(timezone.utc), w["start"], w["end"],
                            "Asia/Phnom_Penh", location=({"lat": lat, "lon": lon} if lat else None),
                            grace_min=int(v.get("grace_min", 5)), early_bonus_min=int(v.get("early_bonus_min", 5)))
        res["ok"] = res.get("bound", False)
        return res
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _do_web_checkout(staff: dict, lat, lon) -> dict:
    from datetime import datetime, timezone
    from core.attendance import check_out as core_check_out
    w = (staff.get("shift_windows") or [{}])[0]
    if not w.get("start") or not w.get("end"):
        return {"ok": False, "error": "no shift set for you yet"}
    try:
        res = core_check_out(staff["org_id"], staff["staff_id"], datetime.now(timezone.utc),
                             w["start"], w["end"], "Asia/Phnom_Penh")
        res["ok"] = res.get("bound", False)
        return res
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def render_checkin(token: str, result: dict = None) -> str:
    s = staff_by_checkin_token(token)
    if not s:
        return _page("Check in", "<h1>Check in</h1><div class='box'>This link isn't valid — ask your manager "
                     "for your check-in link.</div>")
    who = escape(s.get("call_name") or s.get("name", ""))
    if result is not None:
        if result.get("ok"):
            if "worked_min" in result:                      # check-OUT
                msg = "✅ Checked out — worked %d min today." % result.get("worked_min", 0)
                if result.get("duplicate"):
                    msg = "You're already checked out for this shift."
            else:                                           # check-IN
                st = result.get("state", "")
                msg = {"on_time": "✅ Checked in — on time!",
                       "late": "⚠️ Checked in — %d min late." % result.get("minutes_late", 0),
                       "early": "✅ Checked in — %d min early." % result.get("minutes_early", 0)}.get(st, "✅ Checked in.")
                if result.get("duplicate"):
                    msg = "You're already checked in for this shift."
        else:
            msg = "Couldn't do that: %s" % result.get("error", "please try again")
        return _page("Check in", "<h1>Hi %s</h1><div class='box'><h2>%s</h2></div>" % (who, escape(msg)))
    from core.attendance import recent_checkins
    recent = recent_checkins(s["org_id"], s["staff_id"], 5)
    rec_html = ("<div class='box'><h3>Your recent check-ins</h3><ul>%s</ul></div>"
                % "".join("<li class='note'>%s &nbsp; %s</li>" % (escape(str(r["day"])), escape(r["state"] or "—"))
                          for r in recent)) if recent else ""
    body = ("<h1>Hi %s 👋</h1><div class='box'><p>Your shift: <b>%s</b></p><p>What would you like to do?</p>"
            "<button onclick=\"go('fi')\" style='font-size:18px;padding:12px 24px'>📍 Check IN</button> &nbsp; "
            "<button onclick=\"go('fo')\" style='font-size:18px;padding:12px 24px;background:#6b7280'>📍 Check OUT</button>"
            "<form id='fi' method='post' action='/checkin/%s'><input type='hidden' name='lat'><input type='hidden' name='lon'></form>"
            "<form id='fo' method='post' action='/checkout/%s'><input type='hidden' name='lat'><input type='hidden' name='lon'></form>"
            "<p class='note'>We use your location to confirm you're at work.</p></div>%s"
            "<script>function go(id){var f=document.getElementById(id);if(!navigator.geolocation){f.submit();return;}"
            "navigator.geolocation.getCurrentPosition(function(p){f.lat.value=p.coords.latitude;"
            "f.lon.value=p.coords.longitude;f.submit();},function(){f.submit();});}</script>"
            % (who, escape(_windows_str(s.get("shift_windows"))), escape(token), escape(token), rec_html))
    return _page("Check in", body)


def render_whatif(org_id: str) -> str:
    """🔮 Preview how changing the check-in grace/early thresholds would reclassify recent check-ins.
    READ-ONLY (core.whatif) — nothing applied. The 'see a change's effect before committing' feature."""
    v = get_config(org_id).get("categories", {}).get("attendance", {}).get("verdict", {})
    cur_g, cur_e = int(v.get("grace_min", 5)), int(v.get("early_bonus_min", 5))

    def _a(name, default):
        try:
            return max(0, min(60, int(request.args.get(name, default))))
        except (TypeError, ValueError):
            return default

    grace, early = _a("grace", cur_g), _a("early", cur_e)
    res = verdict_whatif(org_id, grace, early)
    trans = "".join("<li><b>%d</b> × %s</li>" % (n, escape(k))
                    for k, n in sorted(res["by_transition"].items(), key=lambda x: -x[1])) or "<li>none</li>"
    ex = "".join("<li class='note'>%s &nbsp; %s → %s</li>" % (escape(e["at"][:16]), escape(e["from"]), escape(e["to"]))
                 for e in res["examples"])
    body = ("<div class='nav'><a href='/'>← admin</a> · <a href='/customer'>customer</a></div>"
            "<h1>🔮 What-if — check-in verdict</h1>"
            "<div class='box'><p class='note'>How would changing the grace / early thresholds reclassify your "
            "recent check-ins? (Live config: grace %d, early %d.) Read-only — nothing is applied.</p>"
            "<form method='get' action='/whatif'>"
            "Grace (min) <input type='number' name='grace' value='%d' min='0' max='60'> &nbsp; "
            "Early bonus (min) <input type='number' name='early' value='%d' min='0' max='60'> &nbsp; "
            "<button type='submit'>Preview</button></form></div>"
            "<div class='box'><h2>%d of %d recent check-ins would change</h2>"
            "<p class='note'>Currently: %s</p>"
            "<p>Transitions:</p><ul>%s</ul>%s</div>"
            % (cur_g, cur_e, grace, early, res["changed"], res["total"],
               ", ".join("%d %s" % (n, escape(k.replace("_", " ")))
                         for k, n in sorted(res["current"].items(), key=lambda x: -x[1])) or "—",
               trans, ("<p>Examples:</p><ul>%s</ul>" % ex) if ex else ""))
    return _page("What-if", body)


def render_audit(org_id: str) -> str:
    """📝 The config change log — who changed which knob, when (PRODUCT SECURITY law #5: auditability)."""
    rows = recent_config_audit(org_id, 100)
    items = "".join(
        "<li><b>%s</b> &nbsp; <code>%s</code> &nbsp; %s → %s <span class='note'>(by %s)</span></li>"
        % (escape(str(r["at"])[:16]), escape(r["path"]),
           escape("—" if r["old_val"] is None else r["old_val"]),
           escape("—" if r["new_val"] is None else r["new_val"]), escape(r["who"] or "?"))
        for r in rows) or "<li class='note'>No config changes recorded yet.</li>"
    body = ("<div class='nav'><a href='/'>← admin</a> · <a href='/customer'>customer</a></div>"
            "<h1>📝 Config change log</h1><div class='box'><p class='note'>Who changed which setting, when. "
            "Newest first. (Secrets log the act, never the value.)</p><ul>%s</ul></div>" % items)
    return _page("Audit", body)


# ── CONFIG export / import (clone or back up a tenant's setup) ─────────────────
def _flatten_cfg(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in (d or {}).items():
        p = "%s.%s" % (prefix, k) if prefix else k
        if isinstance(v, dict) and not _is_secret(v):
            out.update(_flatten_cfg(v, p))
        else:
            out[p] = v
    return out


def _form_from_config(flat: dict) -> dict:
    """A flat {path: value} → a form dict apply_changes understands, so an import goes through the SAME
    whitelist/validation/audit as the customer editor (only safe knobs; live ones ignored)."""
    form, bool_paths = {}, []
    for path, val in flat.items():
        desc = schema.describe(path)
        if not desc:
            continue
        if desc["type"] == "bool":
            bool_paths.append(path)
            if val:
                form[path] = "on"
        elif desc["type"] != "secret":
            form[path] = str(val)
    form["_scope"] = ",".join(bool_paths)
    return form


def _readable_changes(org_id: str) -> str:
    """Plain-English 'default → your value' per customized knob (cumulative diff vs DEFAULTS)."""
    rows = []
    for path, val in sorted(_flatten_cfg(raw_overrides(org_id)).items()):
        desc = schema.describe(path)
        label = desc["label"] if desc else path
        rows.append("<li><b>%s</b> <span class='note'>(%s)</span>: %s → <b>%s</b></li>"
                    % (escape(label), escape(path), escape(str(_get_path(DEFAULTS, path))), escape(str(val))))
    return "".join(rows) or "<li class='note'>No customizations yet — using all defaults.</li>"


def render_shadow(org_id: str) -> str:
    """Empirical shadow agreement per vertical — the read-only basis for the owner's cut-over decision."""
    overall = comparison_stats(org_id)
    by_kind = comparison_stats_by_kind(org_id)
    span = comparison_span(org_id)
    pct = (100 * overall["agree"] // overall["total"]) if overall["total"] else 0

    def _verdict(v):
        p = (100 * v["agree"] // v["total"]) if v["total"] else 0
        return ("✓ looks ready" if (v["total"] >= 30 and p >= 98 and span["days"] >= 5)
                else "⏳ keep watching")

    rows = "".join(
        "<tr><td>%s</td><td>%d</td><td>%d</td><td>%d%%</td><td>%s</td></tr>"
        % (escape(k), v["total"], v["agree"], (100 * v["agree"] // v["total"]) if v["total"] else 0, _verdict(v))
        for k, v in by_kind.items()) or "<tr><td colspan='5' class='note'>No shadow comparisons yet.</td></tr>"
    span_html = ("<p class='note'>Data span: <b>%d days</b> (%s → %s)</p>"
                 % (span["days"], str(span["first"])[:16], str(span["last"])[:16])) if span["first"] else ""
    body = ("<div class='nav'><a href='/'>← admin</a></div>"
            "<h1>👥 Shadow agreement — cut-over readiness</h1>"
            "<div class='box'><p class='note'>How often the new platform's computation matched live, on real "
            "data. Cut a vertical over only after enough agreement over enough days (read-only — informs the "
            "decision, changes nothing).</p>"
            "<p><b>Overall: %d%% agree</b> &nbsp; <span class='note'>(%d of %d compared · %d mismatch)</span></p>"
            "%s"
            "<table style='width:100%%;border-collapse:collapse' cellpadding='6'>"
            "<tr style='text-align:left;border-bottom:1px solid #eee'><th>Vertical</th><th>Compared</th>"
            "<th>Agreed</th><th>Agreement</th><th>Cut-over?</th></tr>%s</table>"
            "<p class='note'>“Cut-over?” is a suggestion only (≥98%% agreement · ≥30 comparisons · ≥5 days) — "
            "your decision.</p></div>%s"
            % (pct, overall["agree"], overall["total"], overall["mismatch"], span_html, rows,
               _render_mismatches(org_id)))
    return _page("Shadow", body)


def _render_mismatches(org_id: str) -> str:
    ms = recent_mismatches(org_id, 10)
    if not ms:
        return ""
    items = "".join(
        "<li class='note'><b>%s</b> %s &nbsp; live: <code>%s</code> → new: <code>%s</code></li>"
        % (escape(m["kind"] or "?"), escape(str(m["at"])[:16]),
           escape(str(m["live"])[:80]), escape(str(m["new"])[:80]))
        for m in ms)
    return ("<div class='box'><h3>Recent mismatches</h3><p class='note'>What the new system computed "
            "differently — investigate these before cutting that vertical over.</p><ul>%s</ul></div>" % items)


def render_export(org_id: str) -> str:
    blob = json.dumps(raw_overrides(org_id), indent=2, default=str)
    body = ("<div class='nav'><a href='/'>← admin</a> · <a href='/import'>import</a></div>"
            "<h1>⬇️ Export config</h1>"
            "<div class='box'><h3>Your customizations</h3><p class='note'>What you've changed from the "
            "defaults.</p><ul>%s</ul></div>"
            "<div class='box'><h3>Backup / clone</h3><p class='note'>Copy this (no secrets) to back up or "
            "clone onto another tenant.</p>"
            "<textarea rows='14' style='width:100%%' readonly>%s</textarea></div>"
            % (_readable_changes(org_id), escape(blob)))
    return _page("Export", body)


def render_import(org_id: str, msg: str = "") -> str:
    body = ("<div class='nav'><a href='/'>← admin</a> · <a href='/export'>export</a></div>"
            "<h1>⬆️ Import config</h1>%s<div class='box'>"
            "<p class='note'>Paste an exported config. Only safe (non-live) settings are applied — exactly "
            "like the editor: live knobs are ignored, every change is logged.</p>"
            "<form method='post' action='/import'><textarea name='blob' rows='14' style='width:100%%'></textarea>"
            "<br><button type='submit'>Apply import</button></form></div>" % (msg or ""))
    return _page("Import", body)


def render_health(org_id: str) -> str:
    issues = config_health(org_id)
    if not issues:
        rows = "<li>✅ No config issues found — you're good to go.</li>"
    else:
        icon = {"warn": "⚠️", "info": "ℹ️"}
        rows = "".join("<li>%s %s</li>" % (icon.get(lvl, "•"), escape(msg)) for lvl, msg in issues)
    body = ("<div class='nav'><a href='/'>← admin</a> · <a href='/customer'>customer</a></div>"
            "<h1>🩺 Config health-check</h1><div class='box'><p class='note'>Likely setup mistakes or "
            "inconsistencies (read-only — nothing changed).</p><ul>%s</ul></div>" % rows)
    return _page("Health", body)


def create_app(org_id: str = "twb") -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("WIZARD_SECRET") or ("dev-" + os.urandom(16).hex())
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024   # cap request bodies at 2MB (memory-DoS guard)

    @app.before_request
    def _guard():
        if not auth_enabled() or request.endpoint in ("login", "login_post", "logout", "healthz", "static",
                                                       "checkin", "checkin_post", "checkout_post"):
            return       # staff check in/out via their token link, not a wizard login
        if user_count(org_id) == 0 or session.get("user"):   # no users yet → don't lock out (seed first)
            return
        return redirect("/login")

    @app.after_request
    def _security_headers(resp):
        # defense-in-depth (W3-prep, zero behaviour change). CSP is deferred — the inline check-in JS/styles
        # need a nonce/refactor first; these three break nothing.
        resp.headers["X-Frame-Options"] = "DENY"               # no embedding → anti-clickjacking
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    @app.get("/")
    def index():
        return render_page(org_id)

    @app.get("/customer")
    def customer():
        return render_dashboard(org_id)                       # the customer LANDING is now the dashboard

    @app.get("/customer/config")
    def customer_config():
        return render_customer(org_id, saved=request.args.get("saved") == "1")   # the detailed editor

    @app.post("/customer/apply")
    def customer_apply():
        apply_changes(org_id, request.form)
        return redirect("/customer/config?saved=1")

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

    @app.get("/staff/link/<int:sid>")
    def staff_link(sid):
        return render_staff_link(org_id, sid)

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

    @app.get("/login")
    def login():
        return render_login()

    @app.post("/login")
    def login_post():
        u = (request.form.get("username") or "").strip()
        if verify_user(org_id, u, request.form.get("password") or ""):
            session["user"] = u
            return redirect("/")
        return redirect("/login?err=1")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/whatif")
    def whatif():
        return render_whatif(org_id)

    @app.get("/audit")
    def audit():
        return render_audit(org_id)

    @app.get("/shadow")
    def shadow():
        return render_shadow(org_id)

    @app.get("/dashboard")
    def dashboard():
        return render_dashboard(org_id)

    @app.get("/reports")
    def reports():
        return render_reports(org_id)

    @app.get("/card/<key>")
    def card_detail(key):
        return render_card_detail(org_id, key)

    @app.get("/packages")
    def packages():
        return render_packages(org_id)

    @app.post("/packages/set")
    def packages_set():
        pkg = request.form.get("package")
        if pkg in catalog.PACKAGES:
            set_config(org_id, {"package": pkg})
            log_config_change(org_id, _current_user(), "package", None, pkg)
        return redirect("/packages")

    @app.post("/card/<key>/save")
    def card_save(key):
        toggles = TOGGLES.get(key, {})
        cfg = get_config(org_id)
        over, changes = {}, []
        for _name, path in toggles.items():
            if status_for(path) not in EDITABLE:        # never flip a LIVE knob from a toggle
                continue
            newval = path in request.form
            if _get_path(cfg, path) != newval:
                changes.append((path, _get_path(cfg, path), newval))
            _set_path(over, path, newval)
        ep = _CARD_ENABLE.get(key)                        # the module master on/off
        if ep:
            newval = ep in request.form
            if _get_path(cfg, ep) != newval:
                changes.append((ep, _get_path(cfg, ep), newval))
            _set_path(over, ep, newval)
        ai = request.form.get("ai_power")                 # the AI-power tier selector (ai_assist card)
        if ai in catalog.AI_POWER and cfg.get("ai_power") != ai:
            over["ai_power"] = ai
            changes.append(("ai_power", cfg.get("ai_power"), ai))
        if over:
            set_config(org_id, over)
            who = _current_user()
            for p, old, new in changes:
                log_config_change(org_id, who, p, old, new)
        return redirect("/card/%s?saved=1" % key)

    @app.get("/health")
    def health():
        return render_health(org_id)

    @app.get("/export")
    def export():
        return render_export(org_id)

    @app.get("/import")
    def import_get():
        return render_import(org_id)

    @app.post("/import")
    def import_post():
        try:
            data = json.loads(request.form.get("blob") or "{}")
            if not isinstance(data, dict):
                raise ValueError
        except (ValueError, TypeError):
            return render_import(org_id, "<div class='saved' style='background:#fee2e2;border-color:#fca5a5'>"
                                         "Invalid JSON.</div>")
        applied = apply_changes(org_id, _form_from_config(_flatten_cfg(data)))
        return render_import(org_id, "<div class='saved'>Imported %d setting(s).</div>"
                             % len(_flatten_cfg(applied)))

    @app.get("/checkin/<token>")
    def checkin(token):
        return render_checkin(token)

    @app.post("/checkin/<token>")
    def checkin_post(token):
        s = staff_by_checkin_token(token)
        if not s:
            return render_checkin(token)
        return render_checkin(token, result=_do_web_checkin(s, request.form.get("lat"), request.form.get("lon")))

    @app.post("/checkout/<token>")
    def checkout_post(token):
        s = staff_by_checkin_token(token)
        if not s:
            return render_checkin(token)
        return render_checkin(token, result=_do_web_checkout(s, request.form.get("lat"), request.form.get("lon")))

    @app.get("/healthz")
    def healthz():
        return "ok"

    return app


app = create_app()
