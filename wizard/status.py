"""wizard.status — the CUT-OVER STATUS of each config path (the badge truth + the progress map).

A config knob is one of:
  • LIVE    — live code reads it NOW; editing it changes the real shop. (HIGH-RISK to edit.)
  • SHADOW  — only the platform CORE reads it; the shadow proves it vs live, but it drives nothing real
              yet. Safe to tune — you watch the shadow react, then we cut it over.
  • PLANNED — defined in the model but not wired to any code path yet.

This registry is the single source for those badges AND the literal cut-over map: making a vertical go
live = move its prefix here from SHADOW to LIVE (after the shadow agrees). Longest-prefix wins.

Grounded in the code (2026-06-23): live reads the config in exactly ONE place — the AL re-ping ladder
(gm_bot/bot.py: approval_rule('twb','al')). Everything else attendance is read by core/* (shadow).
"""

# (path-prefix, status) — longest matching prefix wins. Keep ordering irrelevant; matching is by length.
_RULES = [
    ("categories.attendance.approvals.al", "LIVE"),       # the AL re-ping ladder (step 2) — live
    ("categories.attendance.verdict", "SHADOW"),          # core check-in (proven ~98% on replay)
    ("categories.attendance.ot", "SHADOW"),               # core settle (just wired live as shadow)
    ("categories.attendance.leave", "SHADOW"),            # core leave (parity-locked)
    ("categories.attendance.points", "SHADOW"),           # core points (parity-locked)
    ("categories.attendance.checkin_method", "SHADOW"),
    ("categories.attendance.approvals", "PLANNED"),       # sick/ot/swap/… rows not wired yet (only al is)
    ("categories.attendance", "SHADOW"),
    ("categories.accountant", "PLANNED"),
    ("categories.stock", "PLANNED"),
    ("categories.pos", "PLANNED"),
    ("categories.hr_payroll", "PLANNED"),
    ("categories", "PLANNED"),
    ("channels", "SHADOW"),
    ("package", "SHADOW"),
    ("ai_power", "SHADOW"),
]

LEGEND = {
    "LIVE": "live reads this now — editing changes the shop",
    "SHADOW": "only the shadow reads it — safe to tune, watch it prove, then cut over",
    "PLANNED": "in the model, not wired to any code yet",
}


def status_for(path: str) -> str:
    """Badge for a dotted config path (e.g. 'categories.attendance.verdict.grace_min')."""
    best, best_len = "PLANNED", -1
    for prefix, st in _RULES:
        if (path == prefix or path.startswith(prefix + ".")) and len(prefix) > best_len:
            best, best_len = st, len(prefix)
    return best


def summary() -> dict:
    """Count of top-level cut-over posture — for the page header / a future progress bar."""
    out = {"LIVE": 0, "SHADOW": 0, "PLANNED": 0}
    for _, st in _RULES:
        out[st] = out.get(st, 0) + 1
    return out
