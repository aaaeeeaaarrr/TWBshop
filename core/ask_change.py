"""core.ask_change — natural-language CONFIG TWEAKS: the write-side companion to core.ask (which only READS).

"make lateness stricter" → propose setting the Lateness vibe to Strict. The point: a client tunes their system
in plain words, not by hunting knobs — the "stupid-proof" half of OPEN-yet-LEAN (docs/TWEAKABILITY_DESIGN.md).

SAFE BY CONSTRUCTION:
  • It can only ever map to one of the existing vibe PRESETS — a known group × a known vibe (core.presets).
    Never an arbitrary knob, never a raw number, never a LIVE-locked path. A typed sentence has exactly the
    reach of tapping a preset button.
  • It only PARSES here; it writes NOTHING. The wizard shows a confirm step, and applying goes through the
    same audited core.presets.apply_vibe / the /presets/apply route a button tap uses.
  • Ambiguous input → None (the wizard treats it as a QUESTION, never a silent change). A change needs BOTH a
    clear direction AND a change verb AND a known area; missing any → None.
"""
from core import presets

# Which preset group a phrase refers to → its trigger keywords. (Bare "ot" is intentionally NOT a trigger —
# it collides with " not"/" got"/" lot"; say "overtime".)
_GROUP_WORDS = {
    "lateness":       ("late", "lateness", "grace", "on time", "on-time", "punctual", "tardy",
                       "clock in", "clock-in", "check in", "check-in"),
    "leave":          ("leave", "notice", "holiday", "annual leave", "time off", "vacation", "papers",
                       "sick note", "day off", "days off"),
    "overtime":       ("overtime", "over time", "extra hours"),
    "swaps":          ("swap", "swaps", "shift change", "trade shift", "trade day", "switch shift", "switch day"),
    "approval_chase": ("chase", "chasing", "approver", "approval", "remind", "reminder", "nag",
                       "follow up", "follow-up", "ping"),
}

# Direction → the vibe name at each end, PER group (the groups use different vibe vocab).
_DIRECTION_VIBE = {
    "lateness":       {"strict": "strict",     "balanced": "balanced", "relaxed": "relaxed"},
    "leave":          {"strict": "strict",     "balanced": "balanced", "relaxed": "relaxed"},
    "overtime":       {"strict": "capped",     "balanced": "balanced", "relaxed": "generous"},
    "swaps":          {"strict": "strict",     "balanced": "balanced", "relaxed": "flexible"},
    "approval_chase": {"strict": "persistent", "balanced": "balanced", "relaxed": "gentle"},
}

# Ordered so NEGATION phrases ("less strict" → relaxed, "less lenient" → strict) win over the plain words.
_DIRECTION_PHRASES = [
    ("relaxed", ("less strict", "less tight", "less harsh", "less tough", "less aggressive", "not so strict",
                 "more lenient", "more relaxed", "more flexible", "more generous", "more forgiving")),
    ("strict",  ("less lenient", "less relaxed", "less flexible", "less generous", "less forgiving",
                 "not so lenient", "more strict", "more aggressive", "more persistent")),
    ("balanced", ("balanced", "default", "normal", "standard", "moderate", "middle", "reset to normal", "reset")),
    ("strict",  ("strict", "tight", "tough", "harsh", "harder", "crack down", "capped", "persistent",
                 "aggressive", "stronger", "stern")),
    ("relaxed", ("relax", "loose", "lenient", "easier", "easy", "soft", "gentle", "generous", "flexible",
                 "chill", "forgiving", "lax")),
]

# A real change needs an imperative — guards a QUESTION that merely contains a direction word
# (e.g. "is lateness strict?" must NOT be read as a change). tighten/loosen/relax/ease double as verbs.
_CHANGE_VERBS = ("make", "set ", "change", "turn", "adjust", "tune", "tweak", "tighten", "loosen", "relax",
                 "ease", "switch", "crack down", "want", "raise", "lower", "increase", "decrease", "reset")


def _direction(q: str):
    for d, phrases in _DIRECTION_PHRASES:
        if any(p in q for p in phrases):
            return d
    return None


def _group(q: str):
    for g, words in _GROUP_WORDS.items():
        if any(w in q for w in words):
            return g
    return None


def parse_change(question):
    """An imperative phrase → a {group, group_label, vibe, caption} preset change, or None if it isn't a clear
    change request. Stateless + side-effect free — the caller confirms and applies through core.presets."""
    q = (question or "").lower().strip()
    if not q:
        return None
    direction = _direction(q)
    if direction is None:                      # no clear "stricter / more relaxed / back to normal" → not a change
        return None
    if not any(v in q for v in _CHANGE_VERBS):  # no imperative → treat as a question, never a silent write
        return None
    group = _group(q)
    if group is None:                          # couldn't tell WHICH area → don't guess
        return None
    vibe = _DIRECTION_VIBE[group][direction]
    g = presets.ATTENDANCE_PRESETS[group]
    return {"group": group, "group_label": g["label"], "vibe": vibe,
            "caption": presets.vibe_caption(group, vibe)}
