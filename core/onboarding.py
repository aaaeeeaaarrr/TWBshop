"""core.onboarding — the channel-agnostic onboarding wizard ENGINE (the "stupid-proof self-serve" front
door the platform sells with). Steps are DATA (key/prompt/type/default/options); a channel adapter renders
them + collects answers; validate() checks + coerces; apply() writes the tenant config + creates the org.

The ENGINE is not a product decision; the STEP CONTENT (questions, package names/prices) IS — the list
below is a sensible STARTER the owner refines. Secrets (bot token, listener creds) are collected by the
adapter and stored in secrets, NEVER in config (per the secrets rule) — they're not steps here.
"""

# starter steps — owner refines the wording/options/packages
STEPS = [
    {"key": "name", "prompt": "Business name?", "type": "text", "required": True},
    {"key": "timezone", "prompt": "Timezone?", "type": "text", "default": "Asia/Phnom_Penh"},
    {"key": "channels", "prompt": "Channels? (telegram / web / both)", "type": "choice",
     "options": ["telegram", "web", "both"], "default": "telegram"},
    {"key": "package", "prompt": "Package?", "type": "choice",
     "options": ["attendance", "attendance+stock", "total"], "default": "attendance"},
    {"key": "grace_min", "prompt": "Lateness grace (minutes)?", "type": "int", "default": 5},
    {"key": "early_bonus_min", "prompt": "Early-bonus threshold (minutes)?", "type": "int", "default": 5},
]


def validate(answers: dict) -> dict:
    """{ok, errors, cleaned}. Per step: required check · type coercion (int) · options check. Skippable
    steps fall back to their default — so a tenant can take the bare minimum (owner's 'skip' requirement)."""
    errors, cleaned = {}, {}
    for s in STEPS:
        v = answers.get(s["key"], s.get("default"))
        if s.get("required") and (v is None or v == ""):
            errors[s["key"]] = "required"
            continue
        if v is None:
            continue
        if s["type"] == "int":
            try:
                v = int(v)
            except (TypeError, ValueError):
                errors[s["key"]] = "must be a number"
                continue
        if s["type"] == "choice" and v not in s["options"]:
            errors[s["key"]] = "must be one of %s" % (s["options"],)
            continue
        cleaned[s["key"]] = v
    return {"ok": not errors, "errors": errors, "cleaned": cleaned}


def apply(org_id: str, answers: dict) -> dict:
    """Validate the answers, create the org, and write its tenant config. Returns {ok, config} or
    {ok: False, errors}. Idempotent (ensure_org + set_config). This is all a channel's onboarding flow
    needs to call once the answers are collected."""
    r = validate(answers)
    if not r["ok"]:
        return {"ok": False, "errors": r["errors"]}
    c = r["cleaned"]
    from core.db import ensure_org
    from core.tenant_config import set_config
    ensure_org(org_id, c.get("name"), c.get("timezone", "Asia/Phnom_Penh"))
    chans = ["telegram", "web"] if c.get("channels") == "both" else [c.get("channels", "telegram")]
    cfg = set_config(org_id, channels=chans, package=c.get("package", "attendance"),
                     grace_min=c.get("grace_min", 5), early_bonus_min=c.get("early_bonus_min", 5))
    return {"ok": True, "config": cfg}
