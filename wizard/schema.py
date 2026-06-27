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
    f"{_ATT}.schedule.swap_partner_rule": {
        "label": "Who staff can swap day-offs with", "type": "enum",
        "help": "How the bot decides which co-workers appear in a staffer's swap list. Every swap still needs the "
                "partner + seniors to approve — this only sets who can be PROPOSED.",
        "options": [
            ("overlap", "Overlapping shifts (recommended)",
             "Anyone whose shift overlaps theirs by at least the % below — they mostly work the same hours, so "
             "trading days barely changes coverage."),
            ("start_or_end", "Similar start OR end", "Anyone whose shift STARTS or ENDS within the minutes below."),
            ("start_window", "Similar start only", "Anyone whose shift STARTS within the minutes below (the original rule)."),
        ],
    },
    f"{_ATT}.schedule.swap_overlap_pct": {
        "label": "Swap: minimum shift overlap (%)", "type": "int", "min": 0, "max": 100, "unit": "%",
        "help": "For the 'Overlapping shifts' rule: two shifts must overlap by at least this % of the SHORTER shift "
                "to be swappable. 50 = share at least half their hours. Lower = more partners offered."},
    f"{_ATT}.schedule.swap_start_window_min": {
        "label": "Swap: start/end window (minutes)", "type": "int", "min": 0, "max": 720, "unit": "min",
        "help": "For the 'Similar start' rules: how close (minutes) two shifts' start/end must be. 180 = 3 hours."},
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
    # ── Expertise / skill coverage ──
    f"{_ATT}.expertise.enabled": {"label": "Track minimum skill coverage", "type": "bool",
        "help": "Make sure enough skilled people are always working — e.g. ALWAYS at least 1 baker on shift. "
                "You give each staffer their skills, set each skill's minimum (and special higher/lower numbers "
                "for certain days/hours) in the staff screen, and the bot can use it to approve leave only when "
                "coverage still holds.",
        "true": "ON — skill-coverage minimums are tracked/enforced.", "false": "OFF — no skill-coverage rules."},
    # ── Comms — chasing slow replies (the responsiveness ladder; gm reads it at go-live, OFF until enabled) ──
    f"{_ATT}.comms.enabled": {"label": "Chase slow replies", "type": "bool",
        "help": "When a staffer is @-mentioned or replied-to in a work group and doesn't answer, the bot nudges "
                "them (and can flag a senior). GROUP messages only — 1-to-1 calls are out of scope.",
        "true": "ON — the bot chases unanswered messages.", "false": "OFF — no chasing (default)."},
    f"{_ATT}.comms.nudge_after_min": {"label": "Nudge after (minutes)", "type": "int", "min": 0, "max": 480,
        "unit": "min", "help": "How long an addressed message can go unanswered before a gentle private DM."},
    f"{_ATT}.comms.escalate_after_min": {"label": "Escalate after (minutes)", "type": "int", "min": 0, "max": 1440,
        "unit": "min", "help": "Still unanswered this long → flag the senior group. 0 = never escalate (nudge only)."},
    f"{_ATT}.comms.escalate_to": {"label": "Escalate to", "type": "enum",
        "help": "Who gets the escalation when a message stays unanswered.",
        "options": [("supervisors", "Supervisors", "The supervisors group."),
                    ("management", "Management", "The management group."),
                    ("owner", "Owner only", "A private DM to you.")]},
    f"{_ATT}.comms.only_during_shift": {"label": "Only chase on-shift", "type": "bool",
        "help": "Only nudge a staffer while they're actually working.",
        "true": "ON — no off-hours nudges.", "false": "OFF — chase any time."},
    f"{_ATT}.comms.auto_penalize": {"label": "Auto-penalise repeated misses", "type": "bool",
        "help": "Whether repeated ignored messages automatically deduct points.",
        "true": "ON — repeated misses cost points (use with care).", "false": "OFF — alert + log only (recommended)."},
    f"{_ATT}.comms.scope": {"label": "What counts as 'addressed'", "type": "enum",
        "help": "Which messages start the clock.",
        "options": [("any_mention", "Any mention / reply", "Any @-mention or a reply to their message."),
                    ("questions_only", "Questions only", "Only when they're asked a question (a '?').")]},
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
    # ── Schedule: split-shift + overnight ──
    f"{_ATT}.schedule.split_shift_allowed": {"label": "Allow split shifts", "type": "bool",
        "help": "Two separate work windows in one day (e.g. 06:00–10:00 and 16:00–20:00).",
        "true": "ON — a day can have two windows.", "false": "OFF — one window per day."},
    f"{_ATT}.schedule.overnight_shifts": {"label": "Overnight shifts (cross midnight)", "type": "bool",
        "help": "Shifts that run past midnight (e.g. 21:00–06:00). Handled by the shift-id model, so a 2am "
                "check-in correctly belongs to the PRIOR day's shift — no date confusion.",
        "true": "ON — overnight shifts supported.", "false": "OFF — no shift crosses midnight."},
    # ── Onboarding: how a new tenant is set up ──
    "onboarding.listener_mode": {"label": "How the bot reads chats", "type": "enum",
        "help": "Where the system gets supplier/staff messages from.",
        "options": [("bot_in_groups", "Bot in the groups (simple)", "Add your bot to the groups; it reads them — no account session. Recommended."),
                    ("user_session", "User-account listener (advanced)", "A Telegram user-account reads chats — only if you must read chats the bot can't join.")]},
    "onboarding.staff_entry": {"label": "How staff are added", "type": "enum",
        "help": "How you build your staff list.",
        "options": [("discover_confirm", "Discover & confirm (easiest)", "The bot finds people in your staff group; you confirm each one."),
                    ("manual", "Type them in", "Add each staffer by hand."),
                    ("bulk_import", "Bulk import", "Paste a list / upload a sheet / import from your current tool.")]},
    "onboarding.auto_provision_bot": {"label": "Bot setup", "type": "enum",
        "help": "How your Telegram bot gets created and configured.",
        "options": [("guided", "Guided (recommended)", "We walk you through BotFather, then auto-configure the bot for you."),
                    ("managed", "Use our bot", "Run on one of our bots — less branding, no setup.")]},
    "onboarding.staff_consent_required": {"label": "Ask staff for consent", "type": "bool",
        "help": "A staffer's first message asks them to consent to attendance/location tracking.",
        "true": "ON — consent asked + logged (recommended).", "false": "OFF — no consent step."},
    "onboarding.industry_template": {"label": "Start from a template", "type": "enum",
        "help": "Pre-fill typical rules/roles/shifts for your kind of business; tweak after.",
        "options": [("", "None", "Start blank."), ("bakery", "Bakery", "Bakery defaults."),
                    ("cafe", "Cafe", "Cafe defaults."), ("retail", "Retail", "Retail defaults.")]},
    # ── Accountant (built, not live yet — shown so you see the domain + its options) ──
    "categories.accountant.enabled": {"label": "Accountant module", "type": "bool",
        "help": "Receipts → expenses, vendors, payables, food allowance. Built; not config-driven/live yet.",
        "true": "ON.", "false": "OFF."},
    "categories.accountant.receipt_read.vendor_priors": {"label": "Smarter receipt reads", "type": "bool",
        "help": "Feed a vendor's usual items/prices to the AI as a soft hint (better reads for known vendors).",
        "true": "ON.", "false": "OFF — cold read every time."},
    "categories.accountant.vendors.auto_dedup": {"label": "Auto-dedup vendors", "type": "bool",
        "help": "Fuzzy-match a new vendor name against existing ones before creating a duplicate (Altas→Atlas).",
        "true": "ON (recommended).", "false": "OFF."},
    "categories.accountant.payables.terms_days_default": {"label": "Default payment terms (days)", "type": "int",
        "min": 0, "max": 180, "unit": "days", "help": "Default days-to-pay for a new supplier."},
    "categories.accountant.food_money.enabled": {"label": "Food allowance", "type": "bool",
        "help": "A per-shift food allowance for staff who actually worked.", "true": "ON.", "false": "OFF."},
    "categories.accountant.food_money.rate_per_shift_hour_riel": {"label": "Food rate (៛ per shift hour)",
        "type": "int", "min": 0, "max": 10000, "unit": "riel",
        "help": "Riel per SCHEDULED shift hour (TWB: 500), ÷4000 → USD, rounded half-up."},
    # ── Stock (built features modelled — not live yet) ──
    "categories.stock.enabled": {"label": "Stock module", "type": "bool",
        "help": "Inventory counts, par/reorder levels, reorder suggestions, supplier price compare.",
        "true": "ON.", "false": "OFF."},
    "categories.stock.count_method": {"label": "How stock is counted", "type": "enum",
        "help": "How staff record stock levels.",
        "options": [("appsheet", "AppSheet form", "A mobile form (what TWB uses today)."),
                    ("manual", "Manual entry", "Type the counts in."),
                    ("barcode", "Barcode scan", "Scan items."),
                    ("photo", "Photo of the sheet", "Snap the stock sheet; the AI reads it.")]},
    "categories.stock.par_levels": {"label": "Par / reorder levels", "type": "bool",
        "help": "Track a target level per item so you know when to reorder.", "true": "ON.", "false": "OFF."},
    "categories.stock.reorder_suggestions": {"label": "Reorder suggestions", "type": "bool",
        "help": "Suggest what to reorder when an item drops below its par level.", "true": "ON.", "false": "OFF."},
    "categories.stock.supplier_price_compare": {"label": "Compare supplier prices", "type": "bool",
        "help": "Track each item's price across suppliers so you buy from the cheapest.",
        "true": "ON (a primary goal).", "false": "OFF."},
    # ── POS ──
    "categories.pos.enabled": {"label": "POS module", "type": "bool",
        "help": "Point of sale — be the POS, or tap your existing one.", "true": "ON.", "false": "OFF."},
    "categories.pos.mode": {"label": "POS mode", "type": "enum",
        "help": "Run our point of sale, or connect the one you already use.",
        "options": [("be_the_pos", "Be the POS", "Use our point of sale."),
                    ("tap_existing", "Tap my existing POS", "Connect Loyverse/Square/etc.; we read the sales.")]},
    "categories.pos.track_inventory": {"label": "Decrement stock on sale", "type": "bool",
        "help": "Reduce stock automatically when something sells.", "true": "ON.", "false": "OFF."},
    "categories.pos.khqr_payments": {"label": "Accept KHQR / Bakong", "type": "bool",
        "help": "Take QR payments at checkout.", "true": "ON.", "false": "OFF."},
    "categories.pos.tips_enabled": {"label": "Tips", "type": "bool",
        "help": "Collect tips at checkout.", "true": "ON.", "false": "OFF."},
    # ── HR / payroll ──
    "categories.hr_payroll.enabled": {"label": "HR / payroll module", "type": "bool",
        "help": "Staff records, salary, payslips, payroll run.", "true": "ON.", "false": "OFF."},
    "categories.hr_payroll.pay_cycle": {"label": "Pay cycle", "type": "enum",
        "help": "How often staff are paid.",
        "options": [("monthly", "Monthly", ""), ("biweekly", "Every 2 weeks", ""), ("weekly", "Weekly", "")]},
    "categories.hr_payroll.payslips": {"label": "Generate payslips", "type": "bool",
        "help": "Produce a payslip each pay run.", "true": "ON.", "false": "OFF."},
    "categories.hr_payroll.salary_owner_only": {"label": "Senior salaries owner-only", "type": "bool",
        "help": "Hide senior/above salaries from everyone but the owner (the salary-privacy rule).",
        "true": "ON (recommended).", "false": "OFF."},
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
           "help": "WHO decides this request.",
           "options": [("senior", "Senior staff", "Any senior can approve."),
                       ("management", "Management", "Only management can approve."),
                       ("bot", "The bot (automatic)", "The system decides automatically using the rule below — "
                        "no human needed for the clear cases.")]},
    "bot_rule": {"label": "Bot decision rule (only used when “Approved by” = the bot)", "type": "enum",
                 "help": "HOW the bot decides when you let it approve. Ignored unless 'Approved by' is the bot.",
                 "options": [
                     ("coverage_maintained", "Keep coverage", "IF the minimum skill coverage is STILL met "
                      "without this person → the bot auto-approves; otherwise it asks a senior. (Needs Expertise on.)"),
                     ("within_quota", "Within their quota", "IF the staffer is still within their leave quota "
                      "AND coverage holds → auto-approve; else a senior decides."),
                     ("always", "Always approve", "The bot approves every request of this type automatically (no human)."),
                     ("senior_if_unsure", "Easy ones only", "The bot approves the clear-cut cases and sends "
                      "anything borderline to a senior.")]},
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
                  f"{_ATT}.schedule.split_shift_allowed", f"{_ATT}.schedule.overnight_shifts",
                  f"{_ATT}.schedule.min_rest_between_shifts_min"]),
    ("Staff rules", [f"{_ATT}.staff_rules.max_consecutive_days", f"{_ATT}.staff_rules.max_weekly_hours",
                     f"{_ATT}.staff_rules.probation_days", f"{_ATT}.staff_rules.auto_clockout_grace_min"]),
    ("Expertise &amp; coverage", [f"{_ATT}.expertise.enabled"]),
    ("Points", [f"{_ATT}.points.enabled"]),
    ("Responsiveness (chasing slow replies)", [f"{_ATT}.comms.enabled", f"{_ATT}.comms.nudge_after_min",
        f"{_ATT}.comms.escalate_after_min", f"{_ATT}.comms.escalate_to", f"{_ATT}.comms.only_during_shift",
        f"{_ATT}.comms.auto_penalize", f"{_ATT}.comms.scope"]),
]

# The onboarding "Connections" screen — channels + tokens (tokens are SECRETS, rendered masked).
CONNECTIONS_GROUPS = [
    ("Telegram", ["connections.telegram.bot_token", "connections.telegram.listener_enabled",
                  "connections.telegram.listener_session", "connections.telegram.owner_chat_id"]),
    ("Web & app", ["connections.web.enabled", "connections.web.subdomain", "connections.app.enabled"]),
]

# "Setup" screen — HOW a new tenant is onboarded (discover-confirm staff, guided bot, template). See
# docs/ONBOARDING_DESIGN.md. The actual discover-confirm/staff-CRUD flow is the next build; these are the knobs.
ONBOARDING_GROUPS = [
    ("Setup approach", ["onboarding.auto_provision_bot", "onboarding.listener_mode",
                        "onboarding.staff_entry", "onboarding.industry_template",
                        "onboarding.staff_consent_required"]),
]

# The Accountant domain (built, not config-driven/live yet) — shown so the platform's 2nd domain is visible.
ACCOUNTANT_GROUPS = [
    ("Accountant", ["categories.accountant.enabled", "categories.accountant.receipt_read.vendor_priors",
                    "categories.accountant.vendors.auto_dedup",
                    "categories.accountant.payables.terms_days_default",
                    "categories.accountant.food_money.enabled",
                    "categories.accountant.food_money.rate_per_shift_hour_riel"]),
]

STOCK_GROUPS = [
    ("Stock", ["categories.stock.enabled", "categories.stock.count_method", "categories.stock.par_levels",
               "categories.stock.reorder_suggestions", "categories.stock.supplier_price_compare"]),
]

POS_GROUPS = [
    ("POS", ["categories.pos.enabled", "categories.pos.mode", "categories.pos.track_inventory",
             "categories.pos.khqr_payments", "categories.pos.tips_enabled"]),
]

HR_GROUPS = [
    ("HR &amp; payroll", ["categories.hr_payroll.enabled", "categories.hr_payroll.pay_cycle",
                          "categories.hr_payroll.payslips", "categories.hr_payroll.salary_owner_only"]),
]

# All the modelled-but-not-live domains, in one place (the customer view + apply iterate these).
EXTRA_DOMAIN_GROUPS = ACCOUNTANT_GROUPS + STOCK_GROUPS + POS_GROUPS + HR_GROUPS


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
