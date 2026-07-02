"""A4 (capacity hygiene): the daily retention tidy ages out ONLY the two unbounded
bookkeeping growers (flip log · send ledger), keeps everything inside the window,
and never touches the evidence tables."""
from core import retention
from core.flip import init_flip_db
from core.sends import init_send_ledger_db
from shared.database import _db

ORG = "rtest"


def _seed():
    init_flip_db()
    init_send_ledger_db()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM core_flip_log WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_send_ledger WHERE org_id=%s", (ORG,))
            cur.execute(
                "INSERT INTO core_flip_log (org_id, path, at, agree, detail) VALUES "
                "(%s,'checkin', now() - interval '40 days', TRUE, 'old'),"
                "(%s,'checkin', now() - interval '5 days',  TRUE, 'fresh')", (ORG, ORG))
            cur.execute(
                "INSERT INTO core_send_ledger (org_id, at, channel, kind, status) VALUES "
                "(%s, now() - interval '100 days', 'gm', 'x', 'sent'),"
                "(%s, now() - interval '10 days',  'gm', 'x', 'sent')", (ORG, ORG))


def _cleanup():
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM core_flip_log WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_send_ledger WHERE org_id=%s", (ORG,))


def test_tidy_deletes_only_aged_rows():
    _seed()
    try:
        counts = retention.tidy()
        assert counts["core_flip_log"] >= 1
        assert counts["core_send_ledger"] >= 1
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT detail FROM core_flip_log WHERE org_id=%s", (ORG,))
                assert [r["detail"] for r in cur.fetchall()] == ["fresh"]
                cur.execute("SELECT count(*) n FROM core_send_ledger WHERE org_id=%s", (ORG,))
                assert cur.fetchone()["n"] == 1
        # idempotent: a second run finds nothing more of ours to delete
        _ = retention.tidy()
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) n FROM core_flip_log WHERE org_id=%s", (ORG,))
                assert cur.fetchone()["n"] == 1
    finally:
        _cleanup()


def test_windows_are_sane():
    # auto-revert reads the last 50 rows — the window must dwarf that at ~470 rows/day
    assert retention.FLIP_LOG_KEEP_DAYS >= 14
    assert retention.SEND_LEDGER_KEEP_DAYS >= 30
