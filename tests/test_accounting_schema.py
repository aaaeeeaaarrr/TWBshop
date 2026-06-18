"""Accountant P0 — schema applies + vendor master / group map round-trips (staging only).

Pure data-layer tests: they create the schema (idempotent) and exercise the vendor map, then
clean up the test vendor. No prod (conftest forces TWBSHOP_ENV=staging).
"""
import pytest

from accountant.db import (
    init_accounting_db, vendor_link, vendor_by_group, list_vendors,
    to_usd_cents, KHR_PER_USD,
)
from shared.database import _db

_TEST_GID = -999000111  # a fake supplier-group id, cleaned up at the end


@pytest.fixture(autouse=True)
def _schema_and_cleanup():
    init_accounting_db()  # idempotent — safe to call every test
    yield
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM acc_vendors WHERE tg_group_id = %s", (_TEST_GID,))


def test_schema_creates_all_four_tables():
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name LIKE 'acc_%'
            """)
            names = {r["table_name"] for r in cur.fetchall()}
    assert {"acc_vendors", "acc_receipts", "acc_payments", "acc_payment_allocations"} <= names


def test_vendor_link_and_resolve_by_group():
    vid = vendor_link("ZZ_TestVendor", tg_group_id=_TEST_GID, category="supplies")
    v = vendor_by_group(_TEST_GID)
    assert v is not None
    assert v["id"] == vid
    assert v["name"] == "ZZ_TestVendor"
    assert v["category"] == "supplies"


def test_vendor_link_upsert_is_idempotent_on_group():
    v1 = vendor_link("ZZ_TestVendor", tg_group_id=_TEST_GID)
    v2 = vendor_link("ZZ_TestVendor Renamed", tg_group_id=_TEST_GID)  # same group -> update, not dup
    assert v1 == v2
    assert vendor_by_group(_TEST_GID)["name"] == "ZZ_TestVendor Renamed"


def test_vendor_by_group_unknown_is_none():
    assert vendor_by_group(-12345678) is None


def test_riel_converts_at_books_rate():
    assert to_usd_cents(20000, "KHR") == 500        # 20,000៛ / 4000 = $5.00 = 500 cents
    assert to_usd_cents(138.60, "USD") == 13860     # $138.60 = 13860 cents
    assert to_usd_cents(None, "USD") is None         # no total -> None (the only blocker)
    assert KHR_PER_USD == 4000
