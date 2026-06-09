"""Sick-leave pure logic (session 28). No DB/Telegram.

Own sickness: take-a-pill ladder; paperless missed time → payback; papers → owner card (5b).
Family sickness (child/spouse/parent): from the 7-day/yr special-leave pool (costs AL),
papers optional. This module: papers deadline, family-pool math, who-strings.
"""
from __future__ import annotations

from datetime import date

PAPERS_GRACE_DAYS = 2      # paperless own-sick is pay-back from declaration; accepted doctor's
#                            papers within 2 days CANCEL it. After 2 days the pay-back is final.
FAMILY_POOL_DAYS = 7       # special-leave pool per year

WHO_KH = {"child": "កូនរបស់អ្នក", "spouse": "ប្តី/ប្រពន្ធរបស់អ្នក", "parent": "ឪពុក/ម្តាយរបស់អ្នក"}


def papers_deadline_passed(created: date, today: date, grace: int = PAPERS_GRACE_DAYS) -> bool:
    """True once the paperless grace window has elapsed (→ the missed time becomes payback)."""
    return (today - created).days >= grace


def family_pool_remaining(used_days: float, cap: int = FAMILY_POOL_DAYS) -> float:
    return max(0.0, cap - used_days)


def who_kh(who: str) -> str:
    return WHO_KH.get(who, who)
