"""core.presets — VIBE presets: one tap sets a CLUSTER of related knobs to a *feeling* (Strict / Balanced /
Relaxed), so a client gets real, broad control with ~1 decision instead of many. This is the lean front door
onto the granular knobs (the 'Customize' door stays open — presets aren't a cage). Grouped by INTENT so a
client tunes one area at a time.

KEY: the 'balanced' vibe == the DEFAULTS (== TWB's current rules), so applying it is behaviour-preserving;
Strict/Relaxed shift the whole cluster. Every value here lands in tenant_config (instant-live) through the same
fail-safe live readers the cut-over migrated — so a 'stupid' tweak is allowed but can never break the system.

(Owner direction → docs/TWEAKABILITY_DESIGN.md: OPEN for any business worldwide, LEAN by default = our moat.)
"""
from core.tenant_config import get_config, set_config

# group → {label, dotted config path, vibes:{name: {knob: value, …}}}. 'balanced' must equal the DEFAULTS.
ATTENDANCE_PRESETS = {
    "lateness": {
        "label": "Lateness & grace",
        "path": "categories.attendance.verdict",
        "vibes": {
            "strict":   {"grace_min": 0,  "early_bonus_min": 3},
            "balanced": {"grace_min": 5,  "early_bonus_min": 5},
            "relaxed":  {"grace_min": 15, "early_bonus_min": 10},
        },
    },
    "leave": {
        "label": "Leave & notice",
        "path": "categories.attendance.leave",
        "vibes": {
            "strict":   {"short_notice_days": 14, "papers_grace_days": 1},
            "balanced": {"short_notice_days": 7,  "papers_grace_days": 2},
            "relaxed":  {"short_notice_days": 3,  "papers_grace_days": 5},
        },
    },
    "overtime": {
        "label": "Overtime",
        "path": "categories.attendance.ot",
        "vibes": {
            "capped":   {"bank_cap_min": 10 * 60},
            "balanced": {"bank_cap_min": 14 * 60},
            "generous": {"bank_cap_min": 20 * 60},
        },
    },
    "swaps": {                                    # the day-off swap rule (LIVE: attendance_ui reads it)
        "label": "Shift swaps",
        "path": "categories.attendance.schedule",
        "vibes": {
            "flexible": {"swap_partner_rule": "overlap", "swap_overlap_pct": 25},
            "balanced": {"swap_partner_rule": "overlap", "swap_overlap_pct": 50},
            "strict":   {"swap_partner_rule": "start_window", "swap_start_window_min": 120},
        },
    },
    "approval_chase": {                           # the AL re-ping ladder (LIVE: bot reads approval_rule)
        "label": "Chasing approvers",
        "path": "categories.attendance.approvals.al",
        "vibes": {
            "gentle":     {"reping_hours": 12, "reping_max": 2},
            "balanced":   {"reping_hours": 6,  "reping_max": 4},
            "persistent": {"reping_hours": 3,  "reping_max": 6},
        },
    },
}


def _nested(path: str, knobs: dict) -> dict:
    """Build {a:{b:{c: knobs}}} from a dotted path 'a.b.c'."""
    over: dict = {}
    cur = over
    parts = path.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = dict(knobs)
    return over


def _at(cfg: dict, path: str) -> dict:
    cur = cfg
    for p in path.split("."):
        cur = cur.get(p, {}) if isinstance(cur, dict) else {}
    return cur if isinstance(cur, dict) else {}


def apply_vibe(org_id, group_key: str, vibe: str):
    """Set a group's whole knob cluster to a vibe (one tap). Returns the applied knobs, or None if unknown."""
    g = ATTENDANCE_PRESETS.get(group_key)
    if not g or vibe not in g["vibes"]:
        return None
    knobs = g["vibes"][vibe]
    set_config(org_id, _nested(g["path"], knobs))
    return knobs


def current_vibe(org_id, group_key: str):
    """Which vibe the tenant's current config matches ('strict'/'balanced'/… ), or 'custom' if it's hand-tuned."""
    g = ATTENDANCE_PRESETS.get(group_key)
    if not g:
        return None
    cur = _at(get_config(org_id), g["path"])
    for vibe, knobs in g["vibes"].items():
        if all(cur.get(k) == v for k, v in knobs.items()):
            return vibe
    return "custom"
