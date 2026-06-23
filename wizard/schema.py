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
    ("Check-in", [f"{_ATT}.checkin_method", f"{_ATT}.verdict.grace_min",
                  f"{_ATT}.verdict.early_bonus_min", f"{_ATT}.verdict.rounding"]),
    ("Overtime", [f"{_ATT}.ot.bank_cap_min"]),
    ("Leave & sick", [f"{_ATT}.leave.short_notice_days", f"{_ATT}.leave.al_paperless_to_payback",
                      f"{_ATT}.leave.papers_grace_days"]),
    ("Points", [f"{_ATT}.points.enabled"]),
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
