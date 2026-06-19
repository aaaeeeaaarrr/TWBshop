"""Tests for stock/db.py — the count event log (staging; is_test-isolated, self-cleaning).

Proves: one count per item per day (re-count upserts the figure), last-count / days-since for the
no-sheet escalation, and is_test isolation."""
import uuid
from datetime import date

import pytest

from shared.database import _db
from shared import stock_shared as ss
from stock import db as stockdb


@pytest.fixture
def item_id():
    ss.init_stock_shared_db()
    stockdb.init_stock_db()
    # last_count_date / days_since are GLOBAL by design (the whole-shop sheet). Control the is_test
    # scope so those assertions are deterministic on the shared staging DB. (Only the stock lane
    # touches this table; suites run serially.) Real (is_test=FALSE) rows are never touched.
    with _db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM stock_count_events WHERE is_test=TRUE")
    iid = ss.upsert_item("ZZTEST_cnt_" + uuid.uuid4().hex[:8], unit="kg", min_qty=5)
    yield iid
    with _db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM stock_count_events WHERE item_id=%s", (iid,))
        cur.execute("DELETE FROM stock_movements WHERE item_id=%s", (iid,))
        cur.execute("DELETE FROM acc_items WHERE id=%s", (iid,))


def test_record_count_event_one_per_day_upserts(item_id):
    d = date(2026, 6, 19)
    id1 = stockdb.record_count_event(item_id, 10, d, source="appsheet", is_test=True)
    id2 = stockdb.record_count_event(item_id, 8, d, is_test=True)   # same day -> upsert
    assert id1 == id2
    assert stockdb.counts_on(d, is_test=True)[item_id] == 8.0       # latest figure wins
    # COALESCE keeps the existing source when the re-count omits it
    with _db() as c, c.cursor() as cur:
        cur.execute("SELECT source FROM stock_count_events WHERE id=%s", (id1,))
        assert cur.fetchone()["source"] == "appsheet"


def test_record_count_event_new_day_new_row(item_id):
    stockdb.record_count_event(item_id, 10, date(2026, 6, 18), is_test=True)
    stockdb.record_count_event(item_id, 9, date(2026, 6, 19), is_test=True)
    with _db() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM stock_count_events WHERE item_id=%s AND is_test=TRUE",
                    (item_id,))
        assert cur.fetchone()["n"] == 2


def test_last_count_and_days_since(item_id):
    stockdb.record_count_event(item_id, 5, date(2026, 6, 15), is_test=True)
    stockdb.record_count_event(item_id, 7, date(2026, 6, 17), is_test=True)
    assert stockdb.last_count_date(is_test=True) == date(2026, 6, 17)
    assert stockdb.days_since_last_count(date(2026, 6, 19), is_test=True) == 2
    assert stockdb.days_since_last_count("2026-06-17", is_test=True) == 0


def test_is_test_isolation_and_never_counted(item_id):
    # the is_test scope starts empty (fixture cleaned it) -> the never-counted case
    assert stockdb.last_count_date(is_test=True) is None
    assert stockdb.days_since_last_count(date(2026, 6, 19), is_test=True) is None
    stockdb.record_count_event(item_id, 5, date(2026, 6, 17), is_test=True)
    # item/date-scoped isolation (robust on shared staging): the test count is not on the real side
    assert item_id not in stockdb.counts_on(date(2026, 6, 17), is_test=False)
    assert stockdb.counts_on(date(2026, 6, 17), is_test=True)[item_id] == 5.0
