"""core.tenant_config — per-tenant configuration (multi-tenancy). ONE place a tenant's knobs live:
lateness grace, early threshold, OT-bank cap, short-notice window, enabled channels, package. Defaults =
TWB's, so a fresh tenant works out of the box; the onboarding wizard WRITES overrides here, every core
path READS them — so the SAME code serves every tenant, config-driven (not forked). Stored on orgs.config.
(Named tenant_config, NOT config, to stay clearly distinct from the live single-tenant config.py.)
"""
import json

from shared.database import _db

DEFAULTS = {
    "grace_min": 5,            # ≤ this late = on-time
    "early_bonus_min": 5,      # ≥ this early = "early" (+bonus)
    "bank_cap_min": 14 * 60,   # OT-bank cap
    "short_notice_days": 7,    # AL inside this window = short-notice (points)
    "channels": ["telegram"],  # which channel adapters are enabled
    "package": "attendance",   # the sold bundle (attendance | +pos | +stock | total | …)
}


def _raw(org_id) -> dict:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT config FROM orgs WHERE org_id=%s", (org_id,))
            r = cur.fetchone()
    if r and r["config"]:
        return r["config"] if isinstance(r["config"], dict) else json.loads(r["config"])
    return {}


def get_config(org_id) -> dict:
    """The tenant's effective config = DEFAULTS overlaid with its stored overrides."""
    cfg = dict(DEFAULTS)
    cfg.update(_raw(org_id))
    return cfg


def set_config(org_id, **overrides) -> dict:
    """Set one or more tenant overrides (what the wizard does). Returns the new effective config."""
    raw = _raw(org_id)
    raw.update(overrides)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orgs SET config=%s WHERE org_id=%s", (json.dumps(raw), org_id))
    return get_config(org_id)
