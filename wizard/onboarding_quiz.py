"""wizard.onboarding_quiz — the first-run questionnaire (the 'packaging per client-type' front door).

A few SELECT questions, ordered so the EARLIEST answers carry the MOST setup signal (industry → size →
biggest pain), then diminishing-signal extras. Skippable at any point — we set sensible defaults from
whatever was answered. The answers map to a starter TEMPLATE + PACKAGE + enabled DOMAINS, then hand off to
'Customize your experience' (the dashboard / config editor). Config-only, nothing live; every choice stays
fully tweakable afterward. The map heuristics below are deliberately a plain table so they're easy to tune.
"""
from core.tenant_config import set_config, get_config
from wizard import templates

# Ordered by INFORMATION GAIN — the first 3 (essential) decide template + package + which domains to spotlight
# (most of the setup); the rest are optional refinements ('answer more for a sharper fit').
QUIZ = [
    {"key": "industry", "essential": True, "multi": False, "q": "What kind of business is this?",
     "options": [("bakery", "🍞 Bakery"), ("cafe", "☕ Café"), ("restaurant", "🍽️ Restaurant"),
                 ("retail", "🛍️ Retail shop"), ("services", "💈 Services / salon"), ("other", "Something else")]},
    {"key": "size", "essential": True, "multi": False, "q": "How many people work here?",
     "options": [("solo", "Just me (1–2)"), ("small", "A small team (3–10)"),
                 ("medium", "Mid-sized (11–30)"), ("large", "Large (30+)")]},
    {"key": "pain", "essential": True, "multi": True, "q": "What do you most want to get under control? (pick any)",
     "options": [("attendance", "⏰ Lateness / no-shows"), ("theft", "🔍 Theft / shrinkage"),
                 ("cash", "💵 Cash / the till"), ("stock", "📦 Stock / waste"),
                 ("payroll", "💼 Payroll"), ("coverage", "🗓️ Scheduling / coverage")]},
    {"key": "checkin", "essential": False, "multi": False, "q": "How should staff clock in?",
     "options": [("telegram_live", "📍 Telegram location"), ("app_gps", "📱 Phone app (GPS)"),
                 ("web_kiosk", "🖥️ Web kiosk / tablet"), ("fingerprint", "👆 Fingerprint / badge")]},
    {"key": "online", "essential": False, "multi": False, "q": "Do you also sell online or deliver?",
     "options": [("yes", "Yes"), ("no", "No")]},
]

_PKG_RANK = {"attendance": 0, "ops": 1, "back_office": 2, "total": 3}
_PKG_BY_SIZE = {"solo": "attendance", "small": "ops", "medium": "back_office", "large": "total"}
# a 'biggest pain' switches the relevant domains ON (categories.<key>.enabled); they then surface on the
# dashboard and the dynamic 'do this next' spotlight picks them up. attendance/coverage are the core (always on).
_PAIN_DOMAINS = {"theft": ["stock", "pos", "accountant"], "cash": ["pos"],
                 "stock": ["stock"], "payroll": ["hr_payroll"]}


def next_question(answers: dict):
    """The next unanswered question (essential first, in order), or None when nothing's left to ask."""
    for item in QUIZ:
        if item["key"] not in answers:
            return item
    return None


def saved_answers(org_id) -> dict:
    return dict(get_config(org_id).get("onboarding", {}).get("quiz", {}) or {})


def record_answer(org_id, key: str, value) -> None:
    """Persist one answer progressively (so the flow can be resumed / skipped at any point)."""
    set_config(org_id, {"onboarding": {"quiz": {key: value}}})


def apply_quiz(org_id, answers: dict | None = None) -> dict:
    """Finalize: turn whatever was answered into a starter setup. Safe with a PARTIAL answers dict (a skip) —
    the more they answered, the sharper the fit; unanswered = sensible defaults. Returns a summary."""
    answers = answers if answers is not None else saved_answers(org_id)
    industry = answers.get("industry")
    if industry in templates.TEMPLATES:
        templates.apply_template(org_id, industry)              # sets a sensible package + domains + records it
    cur_pkg = get_config(org_id).get("package", "attendance")
    size_pkg = _PKG_BY_SIZE.get(answers.get("size"), cur_pkg)   # bump the package up to the size's tier (never down)
    pkg = cur_pkg if _PKG_RANK.get(cur_pkg, 0) >= _PKG_RANK.get(size_pkg, 0) else size_pkg
    over = {"package": pkg, "categories": {}, "onboarding": {"quiz": answers, "quiz_done": True}}
    for p in (answers.get("pain") or []):
        for dom in _PAIN_DOMAINS.get(p, []):
            over["categories"].setdefault(dom, {})["enabled"] = True
    if answers.get("checkin"):
        over["categories"].setdefault("attendance", {})["checkin_method"] = answers["checkin"]
    set_config(org_id, over)
    return {"package": pkg, "industry": industry, "pains": answers.get("pain") or []}
