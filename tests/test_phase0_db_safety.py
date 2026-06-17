"""Phase 0 safety guards — fail-closed DB switch + the live-poll refusal.

These are pure-logic tests: they assert which URL the switch returns / that it
raises, and that the poll guard refuses or allows — WITHOUT opening any connection,
so they never touch prod or staging.
"""
import pytest

import config
import shared.database as db
from shared.runtime_guard import assert_polling_allowed


def test_active_url_raises_when_env_unset(monkeypatch):
    monkeypatch.delenv("TWBSHOP_ENV", raising=False)
    with pytest.raises(RuntimeError):
        db.active_database_url()


def test_active_url_raises_on_unknown_env(monkeypatch):
    monkeypatch.setenv("TWBSHOP_ENV", "production")  # not the literal 'prod'
    with pytest.raises(RuntimeError):
        db.active_database_url()


def test_active_url_prod(monkeypatch):
    monkeypatch.setenv("TWBSHOP_ENV", "prod")
    assert db.active_database_url() == config.DATABASE_URL


def test_active_url_staging(monkeypatch):
    monkeypatch.setenv("TWBSHOP_ENV", "staging")
    if not db._STAGING_DATABASE_URL:
        pytest.skip("STAGING_DATABASE_URL not configured")
    assert db.active_database_url() == db._STAGING_DATABASE_URL


def test_polling_refused_without_flags(monkeypatch):
    monkeypatch.delenv("TWBSHOP_POLL_OK", raising=False)
    monkeypatch.delenv("ALLOW_LOCAL_POLLING", raising=False)
    with pytest.raises(SystemExit):
        assert_polling_allowed("test")


def test_polling_allowed_on_server(monkeypatch):
    monkeypatch.setenv("TWBSHOP_POLL_OK", "1")
    assert_polling_allowed("test")  # no raise


def test_polling_allowed_with_local_override(monkeypatch):
    monkeypatch.delenv("TWBSHOP_POLL_OK", raising=False)
    monkeypatch.setenv("ALLOW_LOCAL_POLLING", "1")
    assert_polling_allowed("test")  # no raise
