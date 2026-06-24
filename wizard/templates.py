"""wizard.templates — industry STARTER TEMPLATES. Picking one pre-fills typical rules + skills for that
kind of business so a new tenant starts in minutes, not blank. Pure config partials deep-merged over the
tenant's config (DEFAULTS still = TWB) — the customer tweaks everything after. Safe: config-only, nothing
live. Referenced by onboarding.industry_template.
"""
from core.tenant_config import set_config

# Each template = a label + a config partial (only the meaningful differences from DEFAULTS).
TEMPLATES = {
    "bakery": {
        "label": "Bakery",
        "blurb": "Overnight baking, an early counter — bank overtime. Plan: Ops (attendance + stock + payroll).",
        "config": {"package": "ops", "categories": {"attendance": {
            "expertise": {"enabled": True, "roles": [{"name": "baker", "min_required": 1},
                                                     {"name": "cashier", "min_required": 1}]},
            "schedule": {"overnight_shifts": True, "split_shift_allowed": False},
            "ot": {"disposition": "bank"},
        }}},
    },
    "cafe": {
        "label": "Cafe",
        "blurb": "Day trade with a lunch lull — split shifts, no overnight. Plan: Ops.",
        "config": {"package": "ops", "categories": {"attendance": {
            "expertise": {"enabled": True, "roles": [{"name": "barista", "min_required": 1},
                                                     {"name": "cashier", "min_required": 1}]},
            "schedule": {"overnight_shifts": False, "split_shift_allowed": True},
        }}},
    },
    "retail": {
        "label": "Retail shop",
        "blurb": "Sales floor + cashier + stockroom; cap weekly hours. Plan: Back-office (+ accounting).",
        "config": {"package": "back_office", "categories": {"attendance": {
            "expertise": {"enabled": True, "roles": [{"name": "sales", "min_required": 1},
                                                     {"name": "cashier", "min_required": 1},
                                                     {"name": "stockroom", "min_required": 0}]},
            "staff_rules": {"max_weekly_hours": 48},
        }}},
    },
}


def apply_template(org_id: str, name: str) -> bool:
    """Deep-merge a template's preset into the tenant's config + record which template. Returns True if applied."""
    t = TEMPLATES.get(name)
    if not t:
        return False
    over = {k: v for k, v in t["config"].items()}
    over.setdefault("onboarding", {})["industry_template"] = name
    set_config(org_id, over)
    return True
