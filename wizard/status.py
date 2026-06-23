"""wizard.status — the CUT-OVER STATUS of each config knob (the badge truth + the progress map).

FOUR states (this is what tells you, at a glance, what's real vs proving vs pending vs an idea):
  • LIVE       — config DRIVES the real shop right now. (Editing changes the shop → gated.)
  • SHADOW     — the running shadow actively compares the config-driven engine vs live; it drives nothing
                 real yet. Safe to tune (you watch it prove), then cut over.
  • LIVE_FIXED — the FEATURE runs live TODAY, but with FIXED/hardcoded rules; this config knob will drive
                 it after cut-over. (So "OT/swap/sick approvals" are LIVE_FIXED, NOT 'planned' — the
                 feature is live, just not yet config-driven. This is the badge that clears that confusion.)
  • PLANNED    — an OPTION in the model, not built yet (often a choice other businesses want that TWB
                 doesn't use — e.g. OT→pay-out, accrual models, staff-rule limits, web/app channels).

Longest-matching prefix wins. This registry is also the literal cut-over map: a vertical goes live by
moving its prefix LIVE_FIXED/SHADOW → LIVE (after the shadow agrees + the owner's go).

Grounded in code (2026-06-23): live reads config in ONE place — the AL re-ping ladder
(gm_bot/bot.py approval_rule('twb','al')). The shadow actively compares check-in + settle.
"""

_RULES = [
    # LIVE — config drives the live shop now
    ("categories.attendance.approvals.al", "LIVE"),
    # SHADOW — the running shadow actively compares this vs live
    ("categories.attendance.verdict", "SHADOW"),
    ("categories.attendance.ot.bank_cap_min", "SHADOW"),
    # PLANNED — new OPTIONS not built (override the LIVE_FIXED section default below)
    ("categories.attendance.ot.disposition", "PLANNED"),
    ("categories.attendance.ot.rate_multiplier", "PLANNED"),
    ("categories.attendance.ot.min_block_min", "PLANNED"),
    ("categories.attendance.leave.al_annual_days", "PLANNED"),
    ("categories.attendance.leave.al_accrual", "PLANNED"),
    ("categories.attendance.leave.carry_over_unused", "PLANNED"),
    ("categories.attendance.leave.special_leave_types", "PLANNED"),
    ("categories.attendance.schedule.min_rest_between_shifts_min", "PLANNED"),
    ("categories.attendance.staff_rules", "PLANNED"),
    # LIVE_FIXED — live features today (fixed rules); config will drive them at cut-over
    ("categories.attendance", "LIVE_FIXED"),     # checkin · ot(rest) · leave · sick · points · schedule · non-AL approvals
    ("connections.telegram", "LIVE_FIXED"),      # TWB IS connected (via secrets.py) — this models it
    ("channels", "LIVE_FIXED"),
    # PLANNED — not built / future
    ("connections", "PLANNED"),                  # web · app · integrations
    ("categories.accountant", "PLANNED"),
    ("categories.stock", "PLANNED"),
    ("categories.pos", "PLANNED"),
    ("categories.hr_payroll", "PLANNED"),
    ("categories", "PLANNED"),
    ("package", "PLANNED"),
    ("ai_power", "PLANNED"),
]

LEGEND = {
    "LIVE": "drives the live shop now (editing changes the shop)",
    "SHADOW": "the shadow is proving it vs live — safe to tune, then cut over",
    "LIVE_FIXED": "live TODAY with fixed rules — this knob will drive it after cut-over",
    "PLANNED": "an option, not built yet",
}

# Which states a customer may EDIT here (all SAFE — none change live behavior): SHADOW tunes the shadow;
# PLANNED is a future-preference; LIVE_FIXED is saved as your desired setting that applies AT CUT-OVER (live
# still runs its fixed rules until then). Only LIVE is locked — it drives the real shop right now, so it's
# changed only via the gated cut-over (so a customer can't alter live behavior from here).
EDITABLE = {"SHADOW", "PLANNED", "LIVE_FIXED"}


def status_for(path: str) -> str:
    best, best_len = "PLANNED", -1
    for prefix, st in _RULES:
        if (path == prefix or path.startswith(prefix + ".")) and len(prefix) > best_len:
            best, best_len = st, len(prefix)
    return best


def summary() -> dict:
    out = {"LIVE": 0, "SHADOW": 0, "LIVE_FIXED": 0, "PLANNED": 0}
    for _, st in _RULES:
        out[st] = out.get(st, 0) + 1
    return out
