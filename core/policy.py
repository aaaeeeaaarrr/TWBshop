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
_ATT = "categories.attendance"
SETTING_POLICY = {
    f"{_ATT}.verdict.grace_min":        "Set the late-grace window to your policy — you decide what counts as on time.",
    f"{_ATT}.verdict.early_bonus_min":  "How early earns a bonus is your choice — set it to reward what you value.",
    f"{_ATT}.ot.bank_cap_min":          "Cap saved overtime to suit your labour terms and local law — your call.",
    f"{_ATT}.ot.disposition":           "What earned overtime becomes (bank / pay / convert) is your policy, per local law.",
    f"{_ATT}.ot.rate_multiplier":       "Your overtime rate is yours to set, per your contracts and local law.",
    f"{_ATT}.leave.short_notice_days":  "Define short notice for leave to match your own rules.",
    f"{_ATT}.leave.papers_grace_days":  "The sick-paper deadline is yours to set — your sick-leave policy.",
    f"{_ATT}.leave.al_annual_days":     "Annual-leave entitlement is yours to set, per contracts and local law.",
    f"{_ATT}.leave.carry_over_unused":  "Whether unused leave carries over is your policy, per local law.",
    f"{_ATT}.leave.sick.late_inform_penalty_points": "Any penalty for late sick-notice is your policy — set it fairly and lawfully.",
    f"{_ATT}.checkin_requires_location": "Requiring location to check in is your call — mind your local privacy rules.",
    f"{_ATT}.points.enabled":           "Using a points / score system is your choice — a management tool, not a legal one.",
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
