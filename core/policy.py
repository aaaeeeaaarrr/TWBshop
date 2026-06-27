"""core.policy — per-setting RESPONSIBILITY microcopy + our standing disclaimer.

The LEAN alternative to a hated 'click I agree' wall (owner direction 2026-06-27): a friendly light-grey
one-liner under each setting that (a) says plainly what it's for and (b) makes clear configuring it is the
CLIENT's call, per their own policies and local laws — so the responsibility sits with them, contextually,
without a modal. Extend GROUP_POLICY / SETTING_POLICY as more settings are covered ("until we cover them all").
"""

# per vibe-preset group → a plain responsibility one-liner (shown light-grey under the group on /presets).
GROUP_POLICY = {
    "lateness":       "How lenient you are on lateness is your policy to set — we just enforce your choice.",
    "leave":          "Notice periods and paperwork windows are yours to set, per your own leave policy.",
    "overtime":       "Your overtime cap and handling are yours to set, per your labour terms and local law.",
    "swaps":          "Who may swap shifts is your call — set it to match how you run coverage.",
    "approval_chase": "How hard the bot chases approvers is your preference — tune it to your team.",
}

# per granular config path → its responsibility line (for the detailed editor; grows as settings are covered).
# Covers every CHOICE a client makes; the only setting deliberately left out is verdict.rounding (one fixed
# option — nothing to responsibly decide). Legal/HR framing appears only where it genuinely fits.
_ATT = "categories.attendance"
_ACC = "categories.accountant"
_STK = "categories.stock"
_POS = "categories.pos"
_HR = "categories.hr_payroll"
SETTING_POLICY = {
    # ── Attendance · check-in ──
    f"{_ATT}.checkin_method":           "How staff clock in is your choice — mind your local privacy rules.",
    f"{_ATT}.checkin_requires_location": "Requiring location to check in is your call — mind your local privacy rules.",
    f"{_ATT}.verdict.grace_min":        "Set the late-grace window to your policy — you decide what counts as on time.",
    f"{_ATT}.verdict.early_bonus_min":  "How early earns a bonus is your choice — set it to reward what you value.",
    # ── Attendance · overtime ──
    f"{_ATT}.ot.bank_cap_min":          "Cap saved overtime to suit your labour terms and local law — your call.",
    f"{_ATT}.ot.disposition":           "What earned overtime becomes (bank / pay / convert) is your policy, per local law.",
    f"{_ATT}.ot.rate_multiplier":       "Your overtime rate is yours to set, per your contracts and local law.",
    f"{_ATT}.ot.min_block_min":         "The smallest overtime worth counting is yours to set, per your terms.",
    f"{_ATT}.ot.auto_settle_at_checkout": "When overtime is worked out is your preference to set.",
    # ── Attendance · annual leave ──
    f"{_ATT}.leave.short_notice_days":  "Define short notice for leave to match your own rules.",
    f"{_ATT}.leave.al_annual_days":     "Annual-leave entitlement is yours to set, per contracts and local law.",
    f"{_ATT}.leave.al_accrual":         "How annual leave is earned is yours to set, per contracts and local law.",
    f"{_ATT}.leave.carry_over_unused":  "Whether unused leave carries over is your policy, per local law.",
    f"{_ATT}.leave.al_paperless_to_payback": "Whether a no-note sick day is owed back is your policy to set.",
    f"{_ATT}.leave.papers_grace_days":  "The sick-paper deadline is yours to set — your sick-leave policy.",
    # ── Attendance · sick leave ──
    f"{_ATT}.leave.sick.own_self_declared":   "Whether own-sick needs approval is your call, per your sick policy.",
    f"{_ATT}.leave.sick.family_allowed":      "Whether staff may take family sick leave is your policy to set.",
    f"{_ATT}.leave.sick.late_inform_penalty_points": "Any penalty for late sick-notice is your policy — set it fairly and lawfully.",
    f"{_ATT}.leave.sick.late_inform_threshold_min":  "What counts as informing late is yours to define.",
    f"{_ATT}.leave.sick.leave_early_exempt":  "How you treat falling ill mid-shift is your policy to set.",
    f"{_ATT}.leave.sick.paperless_to_payback": "Whether a no-note sick day is owed back is your policy, per your sick rules.",
    # ── Attendance · schedule ──
    f"{_ATT}.schedule.redefine_allowed":   "Whether shifts can be redefined is your call — set it to how you run scheduling.",
    f"{_ATT}.schedule.swap_allowed":       "Whether staff may swap shifts is your call.",
    f"{_ATT}.schedule.dayoff_move_allowed": "Whether a day off can move is your call.",
    f"{_ATT}.schedule.weekly_day_off":     "Whether everyone gets a weekly day off is your policy, per local law.",
    f"{_ATT}.schedule.split_shift_allowed": "Whether you allow split shifts is your call.",
    f"{_ATT}.schedule.overnight_shifts":   "Whether shifts cross midnight is your call — set it to how you operate.",
    f"{_ATT}.schedule.min_rest_between_shifts_min": "Minimum rest between shifts is yours to set, per your terms and local law.",
    f"{_ATT}.schedule.swap_partner_rule":  "Who may be offered as a swap partner is your call.",
    f"{_ATT}.schedule.swap_overlap_pct":   "How much shift overlap makes a swap fair is yours to set.",
    f"{_ATT}.schedule.swap_start_window_min": "How close two shifts must be to swap is yours to set.",
    # ── Attendance · staff rules ──
    f"{_ATT}.staff_rules.max_consecutive_days": "Maximum days worked in a row is yours to set, per your terms and local law.",
    f"{_ATT}.staff_rules.max_weekly_hours":     "Maximum weekly hours is yours to set, per your terms and local law.",
    f"{_ATT}.staff_rules.probation_days":       "Probation length is yours to set, per your contracts and local law.",
    f"{_ATT}.staff_rules.auto_clockout_grace_min": "When a forgotten checkout auto-closes is your preference to set.",
    # ── Attendance · expertise / points ──
    f"{_ATT}.expertise.enabled":        "Using skill-coverage minimums is your choice — a scheduling tool, your call.",
    f"{_ATT}.points.enabled":           "Using a points / score system is your choice — a management tool, not a legal one.",
    # ── Accountant ──
    f"{_ACC}.enabled":                  "Keeping your books here is your choice — your records and tax stay your responsibility.",
    f"{_ACC}.receipt_read.vendor_priors": "Letting past prices hint the reader is your preference — always check the figures that matter.",
    f"{_ACC}.vendors.auto_dedup":       "How aggressively similar supplier names are merged is your preference to set.",
    f"{_ACC}.payables.terms_days_default": "Default payment terms are yours to set, per your supplier agreements.",
    f"{_ACC}.food_money.enabled":       "Whether you give a staff food allowance is your policy to set.",
    f"{_ACC}.food_money.rate_per_shift_hour_riel": "The food-allowance rate is yours to set, per your own staff terms.",
    # ── Stock ──
    f"{_STK}.enabled":                  "Tracking stock here is your choice — set it to how you run inventory.",
    f"{_STK}.count_method":             "How you count stock is your call — pick what fits your team.",
    f"{_STK}.par_levels":               "Your reorder levels are yours to set, per how you like to hold stock.",
    f"{_STK}.reorder_suggestions":      "Reorder nudges are a helper — the buying decision stays yours.",
    f"{_STK}.supplier_price_compare":   "Price comparison is a tool for you — the purchasing call is yours.",
    # ── POS ──
    f"{_POS}.enabled":                  "Running the POS is your choice — set it to how you ring up sales.",
    f"{_POS}.mode":                     "Be the till or tap your existing one — your call.",
    f"{_POS}.track_inventory":          "Auto-reducing stock on a sale is your preference to set.",
    f"{_POS}.khqr_payments":            "Accepting KHQR / Bakong is your choice, per your own payment and tax setup.",
    f"{_POS}.tips_enabled":             "Whether you take tips is your policy, per your staff terms and local law.",
    # ── HR / payroll ──
    f"{_HR}.enabled":                   "Running payroll here is your choice — pay accuracy and compliance stay yours.",
    f"{_HR}.pay_cycle":                 "Your pay cycle is yours to set, per your contracts and local law.",
    f"{_HR}.payslips":                  "Whether you issue payslips is your policy, per your local requirements.",
    f"{_HR}.salary_owner_only":         "Keeping senior pay private is your call — set it to your confidentiality policy.",
    # ── Onboarding / connections (setup & channels — mostly "your choice"; consent/listener carry a privacy angle) ──
    "onboarding.auto_provision_bot":     "How your bot gets created is your choice — guided, or run on ours.",
    "onboarding.listener_mode":          "How the bot reads your chats is your call — mind what you're comfortable monitoring.",
    "onboarding.staff_entry":            "How you add staff is your preference — pick whatever's easiest for you.",
    "onboarding.industry_template":      "Starting from a template is optional — it pre-fills sensible defaults you can change.",
    "onboarding.staff_consent_required": "Asking staff to consent to tracking is your call — and may be required by your local privacy law.",
    "connections.telegram.listener_enabled": "Running a listener that reads chats is your choice — mind staff privacy and local law.",
    "connections.telegram.owner_chat_id":    "Where owner alerts are sent is yours to set.",
    "connections.web.enabled":           "Offering a browser login is your choice — set it to how your people prefer to work.",
    "connections.web.subdomain":         "Your web address is yours to choose.",
    "connections.app.enabled":           "Offering a mobile app is your choice.",
}


def setting_policy(path: str) -> str:
    return SETTING_POLICY.get(path, "")


# the standing disclaimer (footer + the /policy page). Plain language, not legalese — the owner refines the page.
DISCLAIMER = ("These are your settings to configure for your own business, policies and local laws. You decide, "
              "and you're responsible for how you set them — we provide the tool, not legal or HR advice.")

POLICY_PAGE = (
    "Your settings, your responsibility.\n\n"
    "This platform lets you configure how your business runs — attendance, leave, overtime, approvals and more. "
    "Those choices are yours to make, in line with your own policies and the laws that apply to you.\n\n"
    "We provide the software and enforce the rules you choose. We don't provide legal, tax or HR advice, and we "
    "aren't responsible for outcomes arising from how you configure or use it. Defaults are sensible starting "
    "points, not recommendations for your jurisdiction.\n\n"
    "Your data is handled per our privacy practices; access is yours and your authorised staff's.\n\n"
    "(Plain-language summary — your full, finalised terms will live on this page.)")
