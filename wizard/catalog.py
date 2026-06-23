"""wizard.catalog — the POSSIBILITIES the wizard can offer (the menu), distinct from the tenant's CURRENT
config (the order). The viewer shows both so the owner sees "what I have" AND "what's available + the
integrations". Machine-readable companion to the full brainstorm in docs/WIZARD_DESIGN.md (keep them in
step; this is the structured menu, that is the prose design).

Honesty: `live=True` only where TWB actually runs it today. Everything else is a roadmap possibility shown
so integrations/packages are visible from now — never implying it's built.
"""

# Top-level product categories (the wizard's first layer), each with a one-line blurb + integration options.
CATEGORIES = {
    "attendance": {
        "live": True,
        "blurb": "Check-in/out, lateness, OT bank, leave/AL/sick, points, schedule changes, approvals.",
        "integrations": ["Telegram live-location (now)", "Fingerprint / ZKTeco", "App GPS",
                         "Web kiosk", "NFC badge"],
    },
    "accountant": {
        "live": False,   # built but not config-driven / not a live service yet
        "blurb": "Receipts → expenses, vendor identity + dedup, payables run, price trends, food allowance.",
        "integrations": ["QuickBooks", "Xero", "Bakong / KHQR", "Bank statement feed", "Google Sheets"],
    },
    "stock": {
        "live": False,
        "blurb": "Stock counts, par levels / reorder, supplier price compare, paperless /stock.",
        "integrations": ["AppSheet (interim)", "Sortly", "Loyverse", "Our cloud (later)"],
    },
    "pos": {
        "live": False,
        "blurb": "Point of sale — be the POS, or tap the customer's existing one. Source-of-truth = our DB.",
        "integrations": ["Loyverse", "Square", "FoodPanda / Grab", "Our POS (later)"],
    },
    "hr_payroll": {
        "live": False,
        "blurb": "Staff registry, salary/slips, payroll run, hiring intake, ex-staff offboarding/bans.",
        "integrations": ["Bank payroll file", "Deputy", "Local NSSF export"],
    },
    "marketing": {
        "live": False,
        "blurb": "Channel posts, promos, loyalty outreach — opt-in, privacy-gated.",
        "integrations": ["Telegram Channel", "FB / IG (Meta Graph)", "TikTok (gated)"],
    },
    "delivery": {
        "live": False,
        "blurb": "Delivery capture + photo quality control (the WOC archive), driver/customer flow.",
        "integrations": ["In-house", "FoodPanda / Grab", "Nham24"],
    },
    "rostering": {
        "live": False,
        "blurb": "Build & publish shift rosters, demand forecasting, open-shift bidding.",
        "integrations": ["In-house", "Deputy", "When I Work", "Homebase"],
    },
    "crm_loyalty": {
        "live": False,
        "blurb": "Customer profiles, loyalty points/tiers, campaigns, feedback.",
        "integrations": ["In-house", "Telegram", "Mailchimp", "Meta (FB/IG)"],
    },
    "payments_payroll": {
        "live": False,
        "blurb": "Collect payments + run staff payroll/slips, taxes/contributions.",
        "integrations": ["Bakong / KHQR", "ABA", "Wing", "Bank payroll file", "NSSF export"],
    },
}

# Sold bundles (gating). Each unlocks a set of categories; sub-features can lock behind a higher tier.
PACKAGES = {
    "attendance": ["attendance"],
    "ops": ["attendance", "stock", "hr_payroll"],
    "back_office": ["attendance", "accountant", "stock", "hr_payroll"],
    "total": list(CATEGORIES.keys()),
}

# "Computer Power" tiers — per decision, a customer chooses rules vs a model (billed at 2x our API cost).
AI_POWER = {
    "computer": "Rules / deterministic (no model cost).",
    "ai": "A model decides (Haiku→Opus by smartness) — billed at 2x the API cost.",
    "mixed": "Per-decision: cheap rules by default, escalate the hard ones to a model.",
}

# A sellable bonus the shadow itself becomes: prove the new config against live before committing.
BONUSES = [
    "Shadow-run / try-before-cut-over — preview a policy change against real recent events, safely.",
    "Industry template packs (bakery, cafe, retail…) — start from a proven config.",
    "Per-decision AI markup — the 'Computer Power' upsell.",
]
