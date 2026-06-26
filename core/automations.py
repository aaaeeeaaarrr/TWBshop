"""core.automations — the AUTOMATIONS recipes (lean Fin-borrow). A recipe = a plain-words {condition → action}
the tenant turns ON with one tap. The CONDITIONS ride our EXISTING detectors (insights.attention_feed +
investigate) — pure statistics, NO model call (computer-tier). The ACTION is a notification spec (who to alert).
Recipes live per-tenant in config (automations.recipes.<key> = {enabled, who}); this module is the CATALOG +
the EVALUATOR ('what would fire right now'). Channel-agnostic: the actual SEND is the live/adapter step.

Both these one-tap recipes and a future custom builder compile to the SAME {condition, action} shape — recipes
are the simple front door onto one engine; the builder is the advanced one. Start with recipes (covers most).
"""
from core.tenant_config import get_config, set_config
from core import insights, investigate

# Who-to-alert options (plain labels; the customer picks per recipe, with a sensible default).
WHO = {"owner": "the owner", "manager": "the manager", "senior": "the senior on duty",
       "buyer": "whoever buys stock", "cashier": "the cashier"}


def _cash_short(org_id):
    return ["💸 %s short $%.2f at close (%s)" % (d["who"] or "till", -d["variance"], d["when"])
            for d in investigate.cash_drawer_report(org_id, 14) if d["variance"] < 0]


def _repeat(org_id):
    return ["🔁 %s on shift at %d shortfall(s)" % (o["name"], o["count"])
            for o in investigate.repeat_offenders(org_id) if o["count"] >= 2]


# key → {plain-words label (with a %s for who) · domain (for grouping) · default who · src}.
# src = ("feed", domain, marker|None) reuses insights.attention_feed; ("fn", callable) is a direct detector.
RECIPES = {
    "lateness":       {"label": "Lateness spikes or turnout drops → alert %s",
                       "domain": "attendance", "who": "manager", "src": ("feed", "attendance", None)},
    "low_stock":      {"label": "Items hit their reorder point → tell %s",
                       "domain": "stock", "who": "buyer", "src": ("feed", "stock", "📦")},
    "shrinkage":      {"label": "A stock count comes up short → flag %s for a camera check",
                       "domain": "stock", "who": "owner", "src": ("feed", "stock", "⚠️")},
    "spend_spike":    {"label": "Spending jumps vs usual → ping %s",
                       "domain": "accountant", "who": "owner", "src": ("feed", "expenses", None)},
    "sales_drop":     {"label": "Sales drop vs last week → ping %s",
                       "domain": "pos", "who": "owner", "src": ("feed", "sales", None)},
    "unattended":     {"label": "Something's recorded with no one clocked in → flag %s",
                       "domain": "security", "who": "owner", "src": ("feed", "security", None)},
    "cash_short":     {"label": "A till comes up short at close → flag %s",
                       "domain": "pos", "who": "manager", "src": ("fn", _cash_short)},
    "repeat_suspect": {"label": "The same person is on shift at repeated shortfalls → flag %s for review",
                       "domain": "security", "who": "owner", "src": ("fn", _repeat)},
}


def recipe_label(key, who_key=None) -> str:
    r = RECIPES[key]
    return r["label"] % WHO.get(who_key or r["who"], WHO[r["who"]])


def enabled_recipes(org_id) -> dict:
    return dict(get_config(org_id).get("automations", {}).get("recipes", {}) or {})


def set_recipe(org_id, key: str, on: bool, who: str = None) -> bool:
    """Turn a recipe on/off (+ optionally who to alert). Config-only. Returns True if a real recipe."""
    if key not in RECIPES:
        return False
    rec = {"enabled": bool(on)}
    if who in WHO:
        rec["who"] = who
    set_config(org_id, {"automations": {"recipes": {key: rec}}})
    return True


def evaluate(org_id) -> list:
    """What the ENABLED recipes would do RIGHT NOW: [{key, label, who, fires:[msg,…]}] (only those that fire).
    The attention feed is computed once and shared across the feed-based recipes."""
    en = enabled_recipes(org_id)
    active = [k for k in RECIPES if en.get(k, {}).get("enabled")]
    if not active:
        return []
    feed = insights.attention_feed(org_id) if any(RECIPES[k]["src"][0] == "feed" for k in active) else []
    out = []
    for key in active:
        r = RECIPES[key]
        kind = r["src"][0]
        if kind == "feed":
            _, domain, marker = r["src"]
            fires = [f["msg"] for f in feed if f["domain"] == domain and (marker is None or marker in f["msg"])]
        else:
            fires = r["src"][1](org_id)
        if fires:
            who_key = en[key].get("who") or r["who"]
            out.append({"key": key, "label": recipe_label(key, who_key),
                        "who": WHO.get(who_key, WHO[r["who"]]), "fires": fires})
    return out
