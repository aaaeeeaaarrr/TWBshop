"""core.investigate — the Investigation card: who-present-on · item-timeline · activity-timeline + /investigate.
Cross-domain forensic queries (pinpoint when + who, for camera checks)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core import investigate, stock, pos
from core.attendance import check_in

cdb.init_core_db()
ORG = "test_investigate"
TZ = "Asia/Phnom_Penh"


def _clean():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            for t in ("attendance_events", "shifts", "core_stock_items", "core_stock_counts", "core_sales",
                      "core_expenses", "core_staff"):
                cur.execute("DELETE FROM %s WHERE org_id=%%s" % t, (ORG,))


def test_who_present_on():
    _clean()
    try:
        now = datetime.now(ZoneInfo(TZ))
        check_in(ORG, 1, now, "00:00", "23:59", TZ)
        present = investigate.who_present_on(ORG, now.strftime("%Y-%m-%d"))
        assert len(present) == 1 and present[0]["events"]            # someone present that day, with a time
    finally:
        _clean()


def test_item_timeline_and_activity():
    _clean()
    try:
        iid = stock.add_item(ORG, "Wine", "btl", par_level=5)
        stock.record_count(ORG, iid, 10, actor="sok")
        pos.record_sale(ORG, iid, 2, 8, actor="dara")
        tl = investigate.item_timeline(ORG, iid)
        assert len(tl) == 2                                          # the count + the sale
        assert {t["by"] for t in tl} == {"sok", "dara"}             # actor captured per action
        acts = investigate.activity_timeline(ORG, 48)
        assert any("Wine" in a["what"] for a in acts)               # cross-domain recent feed
    finally:
        _clean()


def test_investigate_page(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        body = create_app(ORG).test_client().get("/investigate").get_data(as_text=True)
        assert "Investigate" in body and "Who was working" in body and "Recent activity" in body
    finally:
        _clean()


def test_who_in_window():
    from datetime import timedelta
    _clean()
    try:
        now = datetime.now(ZoneInfo(TZ))
        check_in(ORG, 7, now, "00:00", "23:59", TZ)
        assert len(investigate.who_in_window(ORG, now - timedelta(hours=1), now + timedelta(hours=1))) == 1  # inside
        assert investigate.who_in_window(ORG, now + timedelta(hours=1), now + timedelta(hours=2)) == []       # outside
    finally:
        _clean()


def test_unattended_activity():
    _clean()
    try:
        iid = stock.add_item(ORG, "Vodka", "btl", par_level=2)
        stock.record_count(ORG, iid, 10)                                 # actions with NO check-in on record
        pos.record_sale(ORG, iid, 1, 5)
        assert len(investigate.unattended_activity(ORG)) >= 2            # both flagged — no one was clocked in
        check_in(ORG, 7, datetime.now(ZoneInfo(TZ)), "00:00", "23:59", TZ)
        assert investigate.unattended_activity(ORG) == []               # now someone was clocked in around then
    finally:
        _clean()


def test_shrinkage_in_feed_and_page(monkeypatch):
    from core import insights
    from core.tenant_config import set_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        set_config(ORG, {"categories": {"stock": {"enabled": True}}})
        iid = stock.add_item(ORG, "Gin", "btl", par_level=2)
        stock.record_count(ORG, iid, 20)
        stock.record_count(ORG, iid, 15)                                 # short by 5
        assert any("shrinkage" in a["msg"] for a in insights.attention_feed(ORG))   # in the needs-attention feed
        body = create_app(ORG).test_client().get("/investigate").get_data(as_text=True)
        assert "Shrinkage" in body and "Gin" in body                    # on the Investigate page
    finally:
        _clean()
