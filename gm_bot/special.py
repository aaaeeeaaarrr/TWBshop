"""Special-leave pure logic — marriage / family-death / wife-birth (session 28). No DB/Telegram.

Funded from AL; for these the balance MAY go below zero (never salary). Marriage = senior approval
(30+ days ahead). Death = NO approval (instant + condolence); law-tier (child/parent/spouse) 3–7d,
compassion-tier (sibling/grandparent) 1d → owner can upgrade. Wife-birth 2d, notify only.
"""
from __future__ import annotations

LAW_DEATH = {"child", "parent", "spouse"}        # Labor Law Art.171 tier
COMPASSION_DEATH = {"sibling", "grandparent"}     # owner's compassion tier (1d → upgrade)
MARRIAGE_DAYS = {"own": 3, "child": 1}
BIRTH_DAYS = 2
DEATH_MIN, DEATH_MAX = 3, 7


def marriage_days(which: str) -> int:
    return MARRIAGE_DAYS.get(which, 1)


def death_tier(who: str) -> str:
    if who in LAW_DEATH:
        return "law"
    if who in COMPASSION_DEATH:
        return "compassion"
    return "other"


def death_default_days(who: str) -> int:
    """Compassion tier starts at 1 (owner upgrades); law tier defaults to 3 (owner may extend to 7)."""
    return 1 if death_tier(who) == "compassion" else DEATH_MIN


def death_day_options() -> list[int]:
    return list(range(DEATH_MIN, DEATH_MAX + 1))
