"""papers_grace_days + short_notice_days → config-driven (instant-live), BEHAVIOR-PRESERVING.

The live AL/sick callers (bot.py:3361 short-notice, :3873/:4033 papers-deadline) now read
tenant_config.attendance("twb")["leave"][...] fresh, fail-safe to the constants. The config DEFAULT a fresh
tenant gets equals the live constant (PROD verified: TWB leave override = null → papers_grace=2, short_notice=7),
so wiring the callers changes nothing until an owner overrides it; an override flows through instantly.
"""
from datetime import date

import core.db as cdb
from shared.database import _db
from gm_bot.sick import PAPERS_GRACE_DAYS, papers_deadline_passed
from gm_bot.al import SHORT_NOTICE_DAYS
from core.tenant_config import attendance, set_config

ORG = "test_leave_cfg"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))


def test_leave_config_default_equals_live_constants():
    _reset()
    try:
        lv = attendance(ORG)["leave"]
        assert lv["papers_grace_days"] == PAPERS_GRACE_DAYS == 2      # default == current → behavior-preserving
        assert lv["short_notice_days"] == SHORT_NOTICE_DAYS == 7
    finally:
        _reset()


def test_leave_config_override_flows_through():
    _reset()
    try:
        set_config(ORG, {"categories": {"attendance": {"leave": {"papers_grace_days": 3, "short_notice_days": 10}}}})
        lv = attendance(ORG)["leave"]
        assert lv["papers_grace_days"] == 3 and lv["short_notice_days"] == 10            # instant-live
        # the pure function honors what the live caller would now pass it
        assert papers_deadline_passed(date(2026, 6, 1), date(2026, 6, 3), grace=lv["papers_grace_days"]) is False  # 2<3 within
        assert papers_deadline_passed(date(2026, 6, 1), date(2026, 6, 4), grace=lv["papers_grace_days"]) is True   # 3>=3 closed
    finally:
        _reset()
