"""core.tenant_config — the WIZARD'S DATA MODEL + per-tenant config (multi-tenancy).

The system IS its config: a nested category tree (Attendance / Accountant / Stock / POS / HR / …), each
with its sub-settings. The wizard WRITES this; every `core` path READS it — so the same code serves every
tenant, config-driven (no per-tenant code). DEFAULTS = TWB's current rules, so TWB is just "tenant #1 with
a config" and a fresh tenant works out of the box. Stored on orgs.config (deep-merged over DEFAULTS).
Design + the full category brainstorm: docs/WIZARD_DESIGN.md.

(Named tenant_config, NOT config, to stay distinct from the live single-tenant config.py.)
"""
import json

from shared.database import _db
from core.points import CATALOGUE as _CATALOGUE   # TWB's points catalogue = the editable defaults

# An approval row (the wizard's "Approvals" table). Per request type; the AL ladder (step 2) reads it.
_APPROVAL_DEFAULT = {
    "required": True,
    "approvers": 2,                       # seniors needed (code reduces to 1 when the requester is senior)
    "by": "senior",                       # senior | management | bot | [named uids]  — WHO approves
    "bot_rule": "coverage_maintained",    # when by="bot": how the bot decides (see wizard.schema for each)
    "reason_required": False,
    "approver_on_shift": False,           # must an approver be on shift to count?
    "reping_hours": 6,                    # re-ping non-responders every N hours …
    "reping_max": 4,                      # … up to this many times …
    "escalate_to_owner_after_max": True,  # … then escalate to the owner/management …
    "expire_when_window_passes": True,    # … and auto-expire once the request's date/window has passed.
}


def _approval(**over):
    a = dict(_APPROVAL_DEFAULT)
    a.update(over)
    return a


DEFAULTS = {
    "package": "attendance",              # sold bundle (attendance | +stock | +pos | total | …)
    "channels": ["telegram"],             # telegram | web | app (mixable)
    "connections": {                      # the onboarding plumbing the wizard collects (channel-agnostic)
        "telegram": {
            # SECRETS are stored as a REFERENCE only — the value lives in the encrypted org-secret store
            # (core_org_secrets), NEVER in this config blob and NEVER rendered. The wizard shows set/not-set.
            "bot_token": {"__secret__": "telegram_bot_token"},
            "listener_enabled": True,
            "listener_session": {"__secret__": "telegram_listener_session"},   # the user-account session string
            "listener_watch_chat_ids": [],    # groups/DMs the listener monitors (non-secret)
            "owner_chat_id": None,            # where owner alerts go (non-secret)
        },
        "web": {"enabled": False, "subdomain": ""},                 # e.g. acme.<our-domain>
        "app": {"enabled": False, "ios_url": "", "android_url": ""},
        "integrations": {                  # external systems to tap (per the catalog) — keys are SECRETS
            "quickbooks": {"enabled": False, "api_key": {"__secret__": "quickbooks_api_key"}},
            "loyverse": {"enabled": False, "api_key": {"__secret__": "loyverse_api_key"}},
            "bakong": {"enabled": False, "merchant_id": ""},
        },
    },
    "onboarding": {                       # HOW a new tenant gets set up — the wizard's approach (docs/ONBOARDING_DESIGN.md)
        "listener_mode": "bot_in_groups",     # bot_in_groups (simple/safe — the bot reads groups it's in) | user_session (advanced)
        "staff_entry": "discover_confirm",    # discover_confirm (bot finds staff → confirm 1-by-1) | manual | bulk_import
        "auto_provision_bot": "guided",       # guided (walk BotFather + auto-configure via Bot API) | managed (our sub-bot)
        "staff_consent_required": True,       # a staffer's first /start asks consent before any tracking
        "industry_template": "",              # bakery | cafe | retail | … — prefill typical rules/roles/shifts
    },
    "ai_power": "computer",               # computer (rules) | ai (model, 2x API) | mixed — per-decision later
    "categories": {
        "attendance": {
            "enabled": True,
            "checkin_method": "telegram_live",   # telegram_live | fingerprint | app_gps | web_kiosk | nfc
            "checkin_requires_location": True,   # verify the staffer is actually on-site (TWB: yes)
            "verdict": {"grace_min": 5, "early_bonus_min": 5, "rounding": "minute_of_day"},
            "ot": {
                "bank_cap_min": 14 * 60,         # most OT a staffer can save up
                "disposition": "bank",           # bank | convert_al | pay_money | expire — what earned OT BECOMES
                "rate_multiplier": 1.0,          # OT value vs normal time (1.0 same · 1.5 time-and-a-half · 2.0 double)
                "min_block_min": 0,              # ignore OT shorter than this many minutes (0 = count all)
                "auto_settle_at_checkout": True,  # settle OT/payback automatically at checkout
            },
            "leave": {
                "short_notice_days": 7,
                "al_paperless_to_payback": True,
                "papers_grace_days": 2,
                "al_annual_days": 14,            # annual AL entitlement per staffer — CONFIRM your number
                "al_accrual": "annual_grant",    # annual_grant | monthly_accrual | accrue_per_hours_worked
                "carry_over_unused": False,      # roll unused AL into next year?
                "sick": {
                    "own_self_declared": True,        # own-sick needs no approval
                    "family_allowed": True,           # me / child / spouse / parent
                    "late_inform_penalty_points": 15, # the −15 for informing an ABSENCE late
                    "late_inform_threshold_min": 30,
                    "leave_early_exempt": True,       # checked-in-then-fell-ill = no −15 (owner Jun 22)
                    "paperless_to_payback": True,
                },
                "special_leave_types": ["maternity", "bereavement", "unpaid"],
            },
            "schedule": {
                "redefine_allowed": True,
                "swap_allowed": True,
                "swap_partner_rule": "overlap",     # who you can day-off-swap with: overlap | start_or_end | start_window
                "swap_overlap_pct": 50,             # overlap rule: shifts must overlap ≥ this % of the SHORTER shift
                "swap_start_window_min": 180,       # start_or_end / start_window rules: starts/ends within this many minutes
                "dayoff_move_allowed": True,
                "weekly_day_off": True,
                "min_rest_between_shifts_min": 0,   # 0 = no minimum gap enforced (industry option)
                "split_shift_allowed": False,       # two work windows in one day (e.g. 06–10 + 16–20)
                "overnight_shifts": True,           # shifts crossing midnight — handled by the shift-id/interval model
            },
            "staff_rules": {                    # "Rules for staff" — mostly industry options TWB doesn't enforce yet
                "max_consecutive_days": 0,      # 0 = unlimited
                "max_weekly_hours": 0,          # 0 = unlimited
                "probation_days": 0,
                "auto_clockout_grace_min": 0,   # auto-close a forgotten checkout this long after shift end
            },
            "expertise": {                  # minimum SKILL coverage at all times (e.g. always ≥1 baker working)
                "enabled": False,           # TWB doesn't use coverage-by-skill yet → off
                "roles": [],                # [{"name": skill, "min_required": N}] — set in the Expertise editor
                "coverage_overrides": [],   # [{role, days:[…], hours:"HH:MM-HH:MM", min}] — raise/lower for special times
                "coverage_warnings": False,  # planned→wired: alert when a shift would be under-covered
                "auto_schedule": False,      # idea→wired (preview): build rosters that meet the minimums
            },
            "points": {"enabled": True, "catalogue": dict(_CATALOGUE)},
            "approvals": {                  # the wizard's Approvals table (one row per request type)
                "al": _approval(),
                "sick": _approval(required=False),       # own-sick is self-declared (no approval)
                "ot": _approval(),
                "swap": _approval(),
                "special_leave": _approval(),
                "dayoff_move": _approval(),
            },
        },
        # other domains — the accountant's real features modelled as config (still INERT; migrated as ported)
        "accountant": {
            "enabled": False,                     # the accountant is built but not config-driven/live yet
            "receipt_read": {
                "ai_model": "sonnet",             # which model reads receipts
                "temperature": 0,                 # 0 = deterministic read (the Khmer-handwriting fix, session 50)
                "vendor_priors": True,            # feed a vendor's usual items/prices as a soft hint
            },
            "vendors": {
                "auto_dedup": True,               # fuzzy-match a new vendor name before creating a duplicate
                "needs_review_new": True,         # a staff-proposed vendor is usable but flagged for a 1-tap confirm
            },
            "payables": {
                "terms_days_default": 30,         # default payment terms for a new supplier
                "once_off_off_run": True,         # once-off market buys stay OFF the recurring payable run
            },
            "food_money": {
                "enabled": False,
                "rate_per_shift_hour_riel": 500,  # 500៛ per SCHEDULED shift hour
                "divisor_to_usd": 4000,           # ÷4000 → USD, half-up
                "rounding": "half_up",
            },
            "expense_categories": False,          # planned→wired: chart of accounts / categories per expense
            "invoices": False,                    # planned→wired: bill customers, track receivables
            "reconciliation": False,              # planned→wired: match recorded spend to bank/cash
            "financial_reports": False,           # planned→wired: P&L / cash-flow statements
            "tax_vat": False,                     # idea→wired (preview): input/output tax + returns
            "multi_currency": False,              # idea→wired (preview): USD / KHR side by side
        },
        "stock": {                            # stock/inventory — modelled as config (INERT; ported later)
            "enabled": False,
            "count_method": "appsheet",       # appsheet | manual | barcode | photo
            "par_levels": True,               # track par/reorder levels per item
            "reorder_suggestions": True,      # suggest a reorder when an item drops below par
            "supplier_price_compare": True,   # compare the same item's price across suppliers (a PRIMARY goal)
            "low_stock_alert": True,          # alert when stock is low
            "item_catalog": False,            # planned→wired: SKUs, categories, units, photos
            "purchase_orders": False,         # planned→wired: build + send order lists
            "stock_movements": False,         # planned→wired: in/out/waste/transfer
            "barcode_qr": False,              # idea→wired (preview): scan to count / sell
            "recipes_bom": False,             # idea→wired (preview): ingredients per item, auto-deduct
            "valuation": False,               # idea→wired (preview): FIFO / average cost, stock value
        },
        "pos": {                              # point of sale — be the POS or tap theirs (INERT; modelled)
            "enabled": False,
            "mode": "be_the_pos",             # be_the_pos | tap_existing
            "track_inventory": True,          # decrement stock on each sale
            "khqr_payments": True,            # accept KHQR / Bakong
            "receipt": "print_or_send",       # print_or_send | none
            "tips_enabled": False,
            "product_catalog": False,         # planned→wired: items, variants, modifiers
            "discounts": False,               # planned→wired: % / fixed, promos
            "refunds": False,                 # planned→wired: refunds & voids with audit
            "cash_drawer": False,             # planned→wired: open/close + reconcile the drawer
            "tables_orders": False,           # idea→wired (preview): dine-in tabs, kitchen tickets
        },
        "hr_payroll": {                       # staff records · salary/slips · payroll run (INERT; modelled)
            "enabled": False,
            "pay_cycle": "monthly",           # monthly | biweekly | weekly
            "payslips": True,                 # generate payslips
            "nssf_export": False,             # Cambodia social-security export
            "salary_owner_only": True,        # senior+ salaries are owner-only (privacy rule)
            "wage_structures": False,         # planned→wired: monthly/daily/hourly + allowances
            "pay_runs": False,                # planned→wired: scheduled pay runs
            "deductions": False,              # planned→wired: NSSF/tax/advances/paybacks
            "contracts_esign": False,         # idea→wired (preview): store + sign documents
        },
    },
    # Borrowed-from-the-leaders capabilities — WIRED IN but OFF by default; the owner unleashes per client
    # type when each is ready (build early, evolve while switched off). Salesforce/ServiceNow/Shopify lineage.
    "frontier": {
        "reports": False,        # trends & analytics over time (Salesforce Reports · ServiceNow Perf Analytics · QuickBooks)
        "ai_assist": False,      # smart suggestions / anomaly alerts (Salesforce Einstein · ServiceNow Now Assist)
        "automations": False,    # the customer's own if-this-then rules (Salesforce Flow · ServiceNow Workflow)
        "learn": False,          # guided in-app how-tos (Salesforce Trailhead)
        "marketplace": False,    # add-ons & integrations (Shopify App Store · Salesforce AppExchange)
        "mobile_app": False,     # a branded native app
    },
    # Frontier-card SUB-OPTIONS — each wired as a preview toggle so the owner sees/collects ideas (off; the
    # master frontier.<key> gates the card). All planned/idea (the cards' built options stay as badges).
    "frontier_options": {
        "reports": {"expense": False, "stock": False, "sales": False, "payroll": False,
                    "custom": False, "scheduled": False},
        "ai_assist": {"anomaly": False, "suggestions": False, "forecasting": False, "nl_ask": False},
        "automations": {"triggers": False, "conditions": False, "actions": False, "templates": False},
        "learn": {"guided_tours": False, "how_to_library": False, "per_industry_tips": False},
        "marketplace": {"messaging": False, "accounting": False, "payments": False, "pos": False,
                        "delivery": False, "third_party": False},
        "mobile_app": {"staff_app": False, "customer_app": False, "push": False, "offline": False,
                       "app_store": False},
    },
}


def _deep_merge(base: dict, over: dict) -> dict:
    """Recursively overlay `over` onto a copy of `base` (so a stored override of one sub-key keeps its
    siblings' defaults). Lists/scalars replace; dicts merge."""
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _raw(org_id) -> dict:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT config FROM orgs WHERE org_id=%s", (org_id,))
            r = cur.fetchone()
    if r and r["config"]:
        return r["config"] if isinstance(r["config"], dict) else json.loads(r["config"])
    return {}


def get_config(org_id) -> dict:
    """The tenant's EFFECTIVE config = DEFAULTS deep-merged with its stored overrides."""
    return _deep_merge(DEFAULTS, _raw(org_id))


def raw_overrides(org_id) -> dict:
    """The tenant's STORED overrides only (deltas from DEFAULTS) — the portable 'their customizations' blob
    for export/clone. No secrets (those are references, stored separately)."""
    return _raw(org_id)


def set_config(org_id, partial: dict = None, **kw) -> dict:
    """Deep-merge `partial` (and/or top-level kwargs) into the tenant's stored overrides (what the wizard does).
    The read-modify-write runs in ONE transaction with `SELECT … FOR UPDATE`, so two simultaneous tweaks
    SERIALIZE and can't clobber each other (reliability: a setting never silently loses another's change).
    Returns the new effective config."""
    over = dict(partial or {})
    over.update(kw)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT config FROM orgs WHERE org_id=%s FOR UPDATE", (org_id,))   # lock the row
            r = cur.fetchone()
            cur_raw = {}
            if r and r["config"]:
                cur_raw = r["config"] if isinstance(r["config"], dict) else json.loads(r["config"])
            new_raw = _deep_merge(cur_raw, over)
            cur.execute("UPDATE orgs SET config=%s WHERE org_id=%s", (json.dumps(new_raw), org_id))
    return get_config(org_id)


# ── accessors (what core paths call) ─────────────────────────────────────────
def category(org_id, name: str) -> dict:
    return get_config(org_id).get("categories", {}).get(name, {})


def attendance(org_id) -> dict:
    return category(org_id, "attendance")


def verdict_cfg(org_id) -> dict:
    """{grace_min, early_bonus_min, rounding} for the tenant's check-in verdict."""
    return attendance(org_id).get("verdict", DEFAULTS["categories"]["attendance"]["verdict"])


def points_catalogue(org_id) -> dict:
    return attendance(org_id).get("points", {}).get("catalogue", _CATALOGUE)


def approval_rule(org_id, kind: str) -> dict:
    """The approval row for a request type (al/sick/ot/swap/…), merged over the approval defaults."""
    return _deep_merge(_APPROVAL_DEFAULT, attendance(org_id).get("approvals", {}).get(kind, {}))
