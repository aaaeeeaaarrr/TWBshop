"""Sick pure logic."""
from datetime import date

from gm_bot import sick


def test_papers_deadline():
    created = date(2026, 6, 8)
    assert sick.papers_deadline_passed(created, date(2026, 6, 10)) is False  # 2 days
    assert sick.papers_deadline_passed(created, date(2026, 6, 11)) is True   # 3 days


def test_family_pool_remaining():
    assert sick.family_pool_remaining(0) == 7.0
    assert sick.family_pool_remaining(5) == 2.0
    assert sick.family_pool_remaining(9) == 0.0


def test_who_kh():
    assert sick.who_kh("child") == "កូនរបស់អ្នក"
    assert sick.who_kh("unknown") == "unknown"
