"""Day-off swap pure logic."""
from datetime import date

from gm_bot import swap
from gm_bot.attendance import to_min


def test_within_7_days():
    assert swap.within_7_days(date(2026, 6, 8), date(2026, 6, 15)) is True
    assert swap.within_7_days(date(2026, 6, 8), date(2026, 6, 16)) is False
    assert swap.within_7_days(date(2026, 6, 8), date(2026, 6, 8)) is True


def test_is_own_dayoff():
    assert swap.is_own_dayoff("Wed", date(2026, 6, 10)) is True   # Jun 10 2026 = Wed
    assert swap.is_own_dayoff("Wed", date(2026, 6, 11)) is False


def test_partner_eligible_similar_shift():
    req = {"id": 1, "org": "TWB", "work_start": "11:00", "work_end": "21:00"}
    near = {"id": 2, "org": "TWB", "canonical_name": "X", "work_start": "12:00", "work_end": "21:00"}
    far = {"id": 3, "org": "TWB", "canonical_name": "Y", "work_start": "21:00", "work_end": "06:00"}
    assert swap.partner_eligible(req, near, to_min) is True
    assert swap.partner_eligible(req, far, to_min) is False


def test_partner_eligible_excludes_self_tyty_delis():
    req = {"id": 1, "org": "TWB", "work_start": "06:00", "work_end": "15:00"}
    assert swap.partner_eligible(req, dict(req), to_min) is False           # self
    assert swap.partner_eligible(req, {"id": 2, "org": "DELIS", "work_start": "06:00",
                                       "work_end": "15:00"}, to_min) is False
    assert swap.partner_eligible(req, {"id": 3, "org": "TWB", "canonical_name": "Tyty",
                                       "work_start": "06:00", "work_end": "15:00"}, to_min) is False


def test_partner_eligible_overlap_based_norin_chomreun():
    """Real case (s55): Norin 13:00-23:00 and Chomreun 09:00-21:00 overlap 8h (80% of Norin's 10h shift) →
    eligible, even though their START times are 4h apart (the old 'starts within 3h' rule wrongly hid him)."""
    norin = {"id": 2, "org": "TWB", "work_start": "13:00", "work_end": "23:00"}
    chomreun = {"id": 19, "org": "TWB", "canonical_name": "Chun Chomruen",
                "work_start": "09:00", "work_end": "21:00"}
    assert swap.partner_eligible(norin, chomreun, to_min) is True
    assert swap.partner_eligible(chomreun, norin, to_min) is True            # symmetric


def test_partner_eligible_excludes_barely_overlapping():
    """A pair that barely overlaps stays excluded — trading their days would shift coverage too much."""
    req = {"id": 1, "org": "TWB", "work_start": "06:00", "work_end": "14:00"}              # 8h morning
    barely = {"id": 2, "org": "TWB", "canonical_name": "Z", "work_start": "13:00", "work_end": "21:00"}  # 1h overlap
    disjoint = {"id": 3, "org": "TWB", "canonical_name": "W", "work_start": "15:00", "work_end": "23:00"}  # 0 overlap
    assert swap.partner_eligible(req, barely, to_min) is False               # 1h of 8h < half → out
    assert swap.partner_eligible(req, disjoint, to_min) is False             # no overlap → out


def test_partner_eligible_rule_types_are_config_driven():
    """The 3 selectable rules + tweakable thresholds (the dashboard knob). Norin 13-23 vs Chomreun 09-21:
    starts 4h apart, ends 2h apart, overlap 8h of a 10h shift."""
    norin = {"id": 2, "org": "TWB", "work_start": "13:00", "work_end": "23:00"}
    chom = {"id": 19, "org": "TWB", "work_start": "09:00", "work_end": "21:00"}
    assert swap.partner_eligible(norin, chom, to_min, rule="overlap", overlap_frac=0.5) is True     # 80% ≥ 50%
    assert swap.partner_eligible(norin, chom, to_min, rule="overlap", overlap_frac=0.9) is False    # 80% < 90% (stricter)
    assert swap.partner_eligible(norin, chom, to_min, rule="start_window", start_window_min=180) is False  # starts 4h apart
    assert swap.partner_eligible(norin, chom, to_min, rule="start_window", start_window_min=240) is True   # widen → in
    assert swap.partner_eligible(norin, chom, to_min, rule="start_or_end", start_window_min=180) is True    # ends 2h apart


def test_swap_config_defaults():
    """The dashboard's swap-rule knobs exist with TWB's chosen defaults (overlap, half the shorter shift)."""
    from core.tenant_config import DEFAULTS
    sch = DEFAULTS["categories"]["attendance"]["schedule"]
    assert sch["swap_partner_rule"] == "overlap"
    assert sch["swap_overlap_pct"] == 50
    assert sch["swap_start_window_min"] == 180
