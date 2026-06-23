"""wizard.schema — the HUMAN layer: a plain-English descriptor for every editable setting (label, help,
what True/False means here, what each option means, sane ranges). This is what makes the customer view
friendly — an explanation next to everything, no jargon. Distinct from wizard.status (the internal
cut-over badge, admin-only) and wizard.catalog (the menu of possibilities).

A descriptor: {label, help, type, ...}. type ∈ {bool, int, enum}.
  bool → on/off (what each means HERE)        int → min/max/unit
  enum → options [(value, label, help), …]
Approval-row fields repeat per request type (al/sick/ot/swap/…), so they're described once and reused.
"""

# Per-setting descriptors, keyed by dotted config path (under categories.attendance).
_ATT = "categories.attendance"
DESCRIPTORS = {
    f"{_ATT}.checkin_method": {
        "label": "How staff check in", "type": "enum",
        "help": "The method staff use to clock in/out.",
        "options": [
            ("telegram_live", "Telegram live-location", "Staff share live location in Telegram; we verify they're on-site."),
            ("fingerprint", "Fingerprint / device", "A physical fingerprint or badge device at the door."),
            ("app_gps", "Phone app (GPS)", "A mobile app checks their GPS against the workplace."),
            ("web_kiosk", "Web kiosk", "A shared tablet/screen at the entrance."),
            ("nfc", "NFC badge tap", "Tap an NFC card/badge on a reader."),
        ],
    },
    f"{_ATT}.verdict.grace_min": {
        "label": "Lateness grace (minutes)", "type": "int", "min": 0, "max": 60, "unit": "min",
        "help": "How many minutes late still counts as ON TIME. Example: 5 → arriving up to 5 minutes "
                "late is fine; the 6th minute counts as late.",
    },
    f"{_ATT}.verdict.early_bonus_min": {
        "label": "Early-arrival bonus threshold (minutes)", "type": "int", "min": 0, "max": 120, "unit": "min",
        "help": "Arrive at least this many minutes before the shift start to be marked 'early' (and earn "
                "any early-arrival points). 0 turns the early bonus off.",
    },
    f"{_ATT}.verdict.rounding": {
        "label": "Time rounding", "type": "enum",
        "help": "How the check-in clock time is read.",
        "options": [("minute_of_day", "To the minute", "Use the exact minute (drop seconds). Recommended.")],
    },
    f"{_ATT}.ot.bank_cap_min": {
        "label": "Overtime bank cap", "type": "int", "min": 0, "max": 6000, "unit": "min",
        "help": "The most overtime a staffer can SAVE UP (bank) for later rest/pay. 840 = 14 hours. "
                "Overtime beyond the cap isn't banked.",
    },
    f"{_ATT}.leave.short_notice_days": {
        "label": "Short-notice leave threshold (days)", "type": "int", "min": 0, "max": 60, "unit": "days",
        "help": "Annual leave asked for with fewer than this many days' notice counts as 'short notice' "
                "(it can carry a small penalty). 7 → asking less than a week ahead is short notice.",
    },
    f"{_ATT}.leave.al_paperless_to_payback": {
        "label": "Paperless sick → owed time", "type": "bool",
        "help": "What happens when someone takes a sick day WITHOUT a doctor's note.",
        "true": "ON — a paperless sick day becomes time the staffer owes back (payback).",
        "false": "OFF — a paperless sick day is just unpaid/▪, with no payback owed.",
    },
    f"{_ATT}.leave.papers_grace_days": {
        "label": "Days to bring a doctor's note", "type": "int", "min": 0, "max": 30, "unit": "days",
        "help": "How long after a sick day staff have to submit papers before it's treated as paperless.",
    },
    f"{_ATT}.points.enabled": {
        "label": "Points / reputation system", "type": "bool",
        "help": "A running score for punctuality and reliability (early bonus, late penalties, etc.).",
        "true": "ON — track points for each staffer.",
        "false": "OFF — no points are kept.",
    },
    f"{_ATT}.checkin_requires_location": {
        "label": "Require on-site location to check in", "type": "bool",
        "help": "Whether a check-in must prove the staffer is physically at work.",
        "true": "ON — a check-in only counts from the workplace (live location / GPS / device).",
        "false": "OFF — staff can check in from anywhere (trust-based).",
    },
    # ── Overtime options (bring choices other businesses use) ──
    f"{_ATT}.ot.disposition": {
        "label": "What earned overtime becomes", "type": "enum",
        "help": "How overtime a staffer earns is paid back to them.",
        "options": [
            ("bank", "Bank it (time off later)", "OT is saved as time the staffer can take as rest later. (TWB does this.)"),
            ("convert_al", "Add to annual leave", "OT is converted into extra annual-leave days."),
            ("pay_money", "Pay it out", "OT is paid as money on the next payroll (uses the rate multiplier)."),
            ("expire", "Doesn't carry", "OT is acknowledged but not banked or paid (e.g. salaried roles)."),
        ],
    },
    f"{_ATT}.ot.rate_multiplier": {
        "label": "Overtime rate", "type": "enum",
        "help": "How much an overtime minute is worth vs a normal minute (used when OT is paid out).",
        "options": [("1.0", "Same (×1.0)", "OT paid at the normal rate."),
                    ("1.5", "Time-and-a-half (×1.5)", "OT paid at 1.5× — a common standard."),
                    ("2.0", "Double (×2.0)", "OT paid at 2×.")],
    },
    f"{_ATT}.ot.min_block_min": {
        "label": "Minimum overtime block (minutes)", "type": "int", "min": 0, "max": 120, "unit": "min",
        "help": "Ignore overtime shorter than this (0 = count every minute).",
    },
    f"{_ATT}.ot.auto_settle_at_checkout": {
        "label": "Settle OT/payback automatically at checkout", "type": "bool",
        "help": "Whether OT and payback are worked out the moment a staffer checks out.",
        "true": "ON — settled automatically at checkout.", "false": "OFF — settled manually."},
    # ── Leave / AL options ──
    f"{_ATT}.leave.al_annual_days": {
        "label": "Annual leave days per staffer", "type": "int", "min": 0, "max": 60, "unit": "days",
        "help": "How many paid annual-leave days each staffer gets per year. CONFIRM your number."},
    f"{_ATT}.leave.al_accrual": {
        "label": "How annual leave is granted", "type": "enum",
        "help": "When AL days become available.",
        "options": [("annual_grant", "All at once (yearly)", "The full year's AL is granted up front."),
                    ("monthly_accrual", "Monthly", "AL builds up a bit each month."),
                    ("accrue_per_hours_worked", "Per hours worked", "AL earned in proportion to hours worked.")]},
    f"{_ATT}.leave.carry_over_unused": {
        "label": "Carry unused leave to next year", "type": "bool",
        "help": "What happens to leave a staffer didn't use by year-end.",
        "true": "ON — unused AL rolls over.", "false": "OFF — unused AL is lost at year-end."},
    # ── Sick rules (all LIVE at TWB today) ──
    f"{_ATT}.leave.sick.own_self_declared": {
        "label": "Own sick: self-declared (no approval)", "type": "bool",
        "help": "Whether a staffer's OWN sick day is accepted without a manager approving it.",
        "true": "ON — own-sick is self-declared.", "false": "OFF — own-sick needs approval."},
    f"{_ATT}.leave.sick.family_allowed": {
        "label": "Allow family sick (child/spouse/parent)", "type": "bool",
        "help": "Whether staff can take sick leave to care for a family member.",
        "true": "ON — family sick allowed.", "false": "OFF — only own sick."},
    f"{_ATT}.leave.sick.late_inform_penalty_points": {
        "label": "Penalty for informing an absence late (points)", "type": "int", "min": 0, "max": 100, "unit": "pts",
        "help": "Points deducted when a staffer tells us about a full-day absence too late (TWB: 15)."},
    f"{_ATT}.leave.sick.late_inform_threshold_min": {
        "label": "“Late” means within this many minutes of start", "type": "int", "min": 0, "max": 240, "unit": "min",
        "help": "Informing an absence closer than this to the shift start counts as 'late'."},
    f"{_ATT}.leave.sick.leave_early_exempt": {
        "label": "No late-penalty if they checked in then fell ill", "type": "bool",
        "help": "Someone who came to work and got sick mid-shift shouldn't get the late-informing penalty.",
        "true": "ON — checked-in-then-ill is exempt (TWB, correct).", "false": "OFF — penalty still applies."},
    f"{_ATT}.leave.sick.paperless_to_payback": {
        "label": "Paperless sick → owed time", "type": "bool",
        "help": "A sick day with no doctor's note becomes payback time owed.",
        "true": "ON — paperless sick = payback owed.", "false": "OFF — no payback."},
    # ── Schedule ──
    f"{_ATT}.schedule.redefine_allowed": {"label": "Allow shift redefines", "type": "bool",
        "help": "Can a senior change a staffer's shift times for a day?",
        "true": "ON — redefines allowed.", "false": "OFF."},
    f"{_ATT}.schedule.swap_allowed": {"label": "Allow shift swaps", "type": "bool",
        "help": "Can staff swap shifts?", "true": "ON — swaps allowed.", "false": "OFF."},
    f"{_ATT}.schedule.dayoff_move_allowed": {"label": "Allow moving a day off", "type": "bool",
        "help": "Can a day off be moved to another day?", "true": "ON — allowed.", "false": "OFF."},
    f"{_ATT}.schedule.weekly_day_off": {"label": "Weekly day off", "type": "bool",
        "help": "Does each staffer get a fixed weekly day off?", "true": "ON.", "false": "OFF."},
    f"{_ATT}.schedule.min_rest_between_shifts_min": {
        "label": "Minimum rest between shifts (minutes)", "type": "int", "min": 0, "max": 1440, "unit": "min",
        "help": "Enforce a minimum gap between a checkout and the next check-in (0 = none)."},
    # ── Staff rules (industry limits TWB doesn't enforce yet) ──
    f"{_ATT}.staff_rules.max_consecutive_days": {
        "label": "Max consecutive working days", "type": "int", "min": 0, "max": 31, "unit": "days",
        "help": "Flag/block working more than this many days in a row (0 = unlimited)."},
    f"{_ATT}.staff_rules.max_weekly_hours": {
        "label": "Max weekly hours", "type": "int", "min": 0, "max": 100, "unit": "hrs",
        "help": "Flag/block scheduling beyond this many hours/week (0 = unlimited)."},
    f"{_ATT}.staff_rules.probation_days": {
        "label": "Probation period (days)", "type": "int", "min": 0, "max": 365, "unit": "days",
        "help": "New-staff probation length (0 = none)."},
    f"{_ATT}.staff_rules.auto_clockout_grace_min": {
        "label": "Auto-close a forgotten checkout after (minutes)", "type": "int", "min": 0, "max": 240, "unit": "min",
        "help": "If a staffer forgets to check out, close it automatically this long after their shift end."},
    # ── Connections / onboarding (the wizard's plumbing) ──
    "connections.telegram.bot_token": {"label": "Telegram bot token", "type": "secret",
        "help": "The token from @BotFather for THIS tenant's bot. Stored encrypted; never shown."},
    "connections.telegram.listener_enabled": {"label": "Enable the listener", "type": "bool",
        "help": "A user-account that quietly reads the supplier/staff chats for receipts, paid-signals, etc.",
        "true": "ON — listener runs.", "false": "OFF — no listener."},
    "connections.telegram.listener_session": {"label": "Listener session string", "type": "secret",
        "help": "The Telegram user-account session for the listener. Stored encrypted; never shown."},
    "connections.telegram.owner_chat_id": {"label": "Owner chat id (for alerts)", "type": "int", "min": 0, "max": 9999999999,
        "help": "Where owner alerts/digests are sent."},
    "connections.web.enabled": {"label": "Web access", "type": "bool",
        "help": "Offer a browser login as a channel.", "true": "ON.", "false": "OFF."},
    "connections.web.subdomain": {"label": "Web subdomain", "type": "text",
        "help": "e.g. acme — your customers reach acme.<our-domain>."},
    "connections.app.enabled": {"label": "Mobile app", "type": "bool",
        "help": "Offer a mobile app as a channel.", "true": "ON.", "false": "OFF."},
}

# Approval-row fields — described ONCE, shown per request type (al/sick/ot/swap/special_leave/dayoff_move).
APPROVAL_FIELDS = {
    "required": {"label": "Needs approval", "type": "bool",
                 "help": "Whether this kind of request must be approved before it takes effect.",
                 "true": "ON — a manager/senior must approve it first.",
                 "false": "OFF — it's accepted automatically (self-service)."},
    "approvers": {"label": "Approvers needed", "type": "int", "min": 1, "max": 5, "unit": "people",
                  "help": "How many people must approve. (If the requester is themselves a senior, the "
                          "system needs one fewer.)"},
    "by": {"label": "Approved by", "type": "enum",
           "help": "Who is allowed to approve this request.",
           "options": [("senior", "Senior staff", "Any senior can approve."),
                       ("management", "Management", "Only management can approve.")]},
    "reason_required": {"label": "Reason required", "type": "bool",
                        "help": "Whether the requester must type a reason.",
                        "true": "ON — they must give a reason.", "false": "OFF — a reason is optional."},
    "approver_on_shift": {"label": "Approver must be on shift", "type": "bool",
                          "help": "Whether an approver only counts if they're currently working.",
                          "true": "ON — only on-shift approvers count.", "false": "OFF — any approver counts."},
    "reping_hours": {"label": "Re-ask every (hours)", "type": "int", "min": 1, "max": 48, "unit": "hours",
                     "help": "If no one has answered, how often to re-send the request to those who "
                             "haven't responded yet. IF a request sits unanswered THIS many hours → it's re-sent."},
    "reping_max": {"label": "Re-ask up to (times)", "type": "int", "min": 0, "max": 10, "unit": "times",
                   "help": "The most times to re-send before giving up the re-asking."},
    "escalate_to_owner_after_max": {"label": "Escalate to owner after the last re-ask", "type": "bool",
                                    "help": "What to do once the re-asks are exhausted.",
                                    "true": "ON — IF still unanswered after the last re-ask → notify the owner.",
                                    "false": "OFF — stop after the last re-ask, don't escalate."},
    "expire_when_window_passes": {"label": "Auto-expire once the date passes", "type": "bool",
                                  "help": "What to do if the request's date arrives still unanswered.",
                                  "true": "ON — IF the leave date passes with no decision → auto-cancel it "
                                          "(it's moot).",
                                  "false": "OFF — keep it pending even after the date."},
}

# Friendly labels for each request type in the approvals table.
APPROVAL_KINDS = {
    "al": "Annual leave", "sick": "Sick leave", "ot": "Overtime",
    "swap": "Shift swap", "special_leave": "Special leave", "dayoff_move": "Move a day off",
}

# Customer-view grouping (ordered, friendly) for the attendance category.
ATTENDANCE_GROUPS = [
    ("Check-in", [f"{_ATT}.checkin_method", f"{_ATT}.checkin_requires_location", f"{_ATT}.verdict.grace_min",
                  f"{_ATT}.verdict.early_bonus_min", f"{_ATT}.verdict.rounding"]),
    ("Overtime", [f"{_ATT}.ot.bank_cap_min", f"{_ATT}.ot.disposition", f"{_ATT}.ot.rate_multiplier",
                  f"{_ATT}.ot.min_block_min", f"{_ATT}.ot.auto_settle_at_checkout"]),
    ("Annual leave", [f"{_ATT}.leave.short_notice_days", f"{_ATT}.leave.al_annual_days", f"{_ATT}.leave.al_accrual",
                      f"{_ATT}.leave.carry_over_unused", f"{_ATT}.leave.al_paperless_to_payback",
                      f"{_ATT}.leave.papers_grace_days"]),
    ("Sick leave", [f"{_ATT}.leave.sick.own_self_declared", f"{_ATT}.leave.sick.family_allowed",
                    f"{_ATT}.leave.sick.late_inform_penalty_points", f"{_ATT}.leave.sick.late_inform_threshold_min",
                    f"{_ATT}.leave.sick.leave_early_exempt", f"{_ATT}.leave.sick.paperless_to_payback"]),
    ("Schedule", [f"{_ATT}.schedule.redefine_allowed", f"{_ATT}.schedule.swap_allowed",
                  f"{_ATT}.schedule.dayoff_move_allowed", f"{_ATT}.schedule.weekly_day_off",
                  f"{_ATT}.schedule.min_rest_between_shifts_min"]),
    ("Staff rules", [f"{_ATT}.staff_rules.max_consecutive_days", f"{_ATT}.staff_rules.max_weekly_hours",
                     f"{_ATT}.staff_rules.probation_days", f"{_ATT}.staff_rules.auto_clockout_grace_min"]),
    ("Points", [f"{_ATT}.points.enabled"]),
]

# The onboarding "Connections" screen — channels + tokens (tokens are SECRETS, rendered masked).
CONNECTIONS_GROUPS = [
    ("Telegram", ["connections.telegram.bot_token", "connections.telegram.listener_enabled",
                  "connections.telegram.listener_session", "connections.telegram.owner_chat_id"]),
    ("Web & app", ["connections.web.enabled", "connections.web.subdomain", "connections.app.enabled"]),
]


def describe(path: str) -> dict | None:
    """Descriptor for a config path, incl. the per-kind approval fields (…approvals.<kind>.<field>)."""
    if path in DESCRIPTORS:
        return DESCRIPTORS[path]
    parts = path.split(".")
    if len(parts) >= 2 and parts[-2] in APPROVAL_KINDS and "approvals" in parts:
        d = APPROVAL_FIELDS.get(parts[-1])
        if d:
            return {**d, "label": "%s — %s" % (APPROVAL_KINDS[parts[-2]], d["label"])}
    return None
