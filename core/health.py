"""core.health — read-only config health-check. Scans a tenant's config + setup for likely mistakes /
inconsistencies and returns a list of (level, message). No writes. Drives the wizard's /health page so a
customer catches a misconfiguration BEFORE it bites (e.g. expertise on with no skills, OT banking with a
zero cap). Add a check = append one line; keep each cheap + read-only."""
from core.tenant_config import get_config
from core.db import has_org_secret
from core.onboarding_flow import list_staff, group_id_for_role


def config_health(org_id) -> list:
    """[(level, message)] — level is 'warn' (likely wrong) or 'info' (heads-up). Empty = all clear."""
    cfg = get_config(org_id)
    att = cfg.get("categories", {}).get("attendance", {})
    leave = att.get("leave", {})
    ot = att.get("ot", {})
    out = []

    # ── attendance config consistency ──
    exp = att.get("expertise", {})
    if exp.get("enabled") and not exp.get("roles"):
        out.append(("warn", "Expertise/coverage is ON but no skills are defined — add skills or turn it off."))
    if ot.get("disposition") == "bank" and not ot.get("bank_cap_min"):
        out.append(("warn", "Overtime is set to BANK but the bank cap is 0 — nothing can accrue."))
    if ot.get("disposition") == "convert_al" and not leave.get("al_annual_days"):
        out.append(("warn", "Overtime converts to annual leave, but the AL entitlement is 0."))
    if att.get("checkin_requires_location") and att.get("checkin_method") in ("fingerprint", "nfc"):
        out.append(("warn", "Location is required at check-in, but the check-in method doesn't capture location."))

    # ── setup completeness (read-only) ──
    staff = list_staff(org_id)
    if not staff:
        out.append(("info", "No staff added yet — add staff to start."))
    elif att.get("schedule", {}).get("split_shift_allowed") and not any(len(s.get("shift_windows") or []) > 1
                                                                        for s in staff):
        out.append(("info", "Split shifts are allowed but no staff have a split schedule yet."))
    if not group_id_for_role(org_id, "staff"):
        out.append(("info", "No staff group tagged — the bot can't discover staff without one."))
    if "telegram" in cfg.get("channels", []) and not has_org_secret(org_id, "telegram_bot_token"):
        out.append(("info", "Telegram is a channel but no bot token is set."))
    if not leave.get("al_annual_days"):
        out.append(("info", "Annual-leave entitlement is 0 — staff get no AL days."))

    # ── staff sanity ──
    if any(not (s.get("shift_windows") or []) for s in staff):
        out.append(("info", "Some staff have no shift hours set — they can't be scheduled until they do."))
    names = [s.get("name") for s in staff if s.get("name")]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        out.append(("warn", "Two staff share a name (%s) — ambiguous for assignments/approvals." % ", ".join(dupes)))

    # ── approvals: someone must be able to approve ──
    for kind, rule in (att.get("approvals", {}) or {}).items():
        if rule.get("required") and rule.get("by") != "bot" and not rule.get("approvers"):
            out.append(("warn", "%s requests require approval but 0 approvers are set — they'd never clear." % kind))
            break

    # ── expertise overrides must reference a real skill ──
    role_names = {r.get("name") for r in (exp.get("roles") or []) if isinstance(r, dict)}
    if any(isinstance(ov, dict) and ov.get("role") and ov["role"] not in role_names
           for ov in (exp.get("coverage_overrides") or [])):
        out.append(("warn", "A coverage override references a skill that isn't in your skills list."))
    return out
