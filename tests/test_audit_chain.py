"""core.audit — tamper-evident hash-chained audit (harvested from POSBusiness, re-derived for our core, RE-TESTED
FROM SCRATCH): chain links · content-tamper detect · row-deletion detect · genesis · per-org isolation · NOT NULL
· log_config_change round-trip."""
import core.db as cdb
from shared.database import _db
from core import audit

cdb.init_core_db()
ORG, ORG2 = "test_audit_chain", "test_audit_chain2"


def _clean(*orgs):
    with _db() as c:
        with c.cursor() as cur:
            for o in orgs:
                cur.execute("DELETE FROM core_audit WHERE org_id=%s", (o,))


def test_write_chains_and_verifies():
    _clean(ORG)
    try:
        h1 = audit.write(ORG, "owner", "config.update", "config", "a", {"old": "1", "new": "2"})
        h2 = audit.write(ORG, "owner", "config.update", "config", "b", {"old": "x", "new": "y"})
        assert len(h1) == 64 and len(h2) == 64 and h1 != h2          # non-null, 64-char, distinct
        with _db() as c:
            with c.cursor() as cur:
                cur.execute("SELECT entry_hash, previous_hash FROM core_audit WHERE org_id=%s ORDER BY seq", (ORG,))
                rows = cur.fetchall()
        assert rows[0]["previous_hash"] == audit.GENESIS_HASH        # genesis sentinel on the first row
        assert rows[1]["previous_hash"] == rows[0]["entry_hash"]     # row 2 links to row 1
        assert audit.verify_chain(ORG)["result"] == "PASS"
    finally:
        _clean(ORG)


def test_content_tamper_detected():
    _clean(ORG)
    try:
        audit.write(ORG, "owner", "config.update", "config", "a", {"old": "1", "new": "2"})
        audit.write(ORG, "owner", "config.update", "config", "b", {"old": "x", "new": "y"})
        with _db() as c:                                            # edit a stored value without re-hashing
            with c.cursor() as cur:
                cur.execute("UPDATE core_audit SET changes='{\"old\": \"HACKED\", \"new\": \"2\"}' "
                            "WHERE org_id=%s AND resource_id='a'", (ORG,))
        v = audit.verify_chain(ORG)
        assert v["result"] == "FAIL" and any("content tampered" in f for f in v["failures"])
    finally:
        _clean(ORG)


def test_row_deletion_detected():
    _clean(ORG)
    try:
        for rid in ("a", "b", "c"):
            audit.write(ORG, "owner", "config.update", "config", rid, None)
        with _db() as c:                                            # delete the MIDDLE row → c's prev dangles
            with c.cursor() as cur:
                cur.execute("DELETE FROM core_audit WHERE org_id=%s AND resource_id='b'", (ORG,))
        v = audit.verify_chain(ORG)
        assert v["result"] == "FAIL" and any("deleted" in f for f in v["failures"])
    finally:
        _clean(ORG)


def test_per_org_isolation():
    _clean(ORG, ORG2)
    try:
        audit.write(ORG, "o", "config.update", "config", "a", None)
        audit.write(ORG2, "o", "config.update", "config", "a", None)
        audit.write(ORG, "o", "config.update", "config", "b", None)
        assert audit.verify_chain(ORG)["result"] == "PASS"          # interleaved orgs → independent chains
        assert audit.verify_chain(ORG2)["result"] == "PASS"
        assert audit.verify_chain(ORG2)["checked"] == 1
    finally:
        _clean(ORG, ORG2)


def test_hash_columns_not_null():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT column_name, is_nullable FROM information_schema.columns "
                        "WHERE table_name='core_audit' AND column_name IN ('entry_hash','previous_hash')")
            cols = {r["column_name"]: r["is_nullable"] for r in cur.fetchall()}
    assert cols.get("entry_hash") == "NO" and cols.get("previous_hash") == "NO"


def test_log_config_change_is_chained():
    from core.db import log_config_change
    _clean(ORG)
    try:
        log_config_change(ORG, "owner", "categories.stock.enabled", False, True)
        assert any(r["resource_id"] == "categories.stock.enabled" for r in audit.recent(ORG, 5))   # chained
        assert audit.verify_chain(ORG)["result"] == "PASS"
    finally:
        _clean(ORG)


def test_same_txn_write_rolls_back_with_the_caller():
    """AUDIT-TXN (s55): with a caller cursor, the audit row lives in the caller's transaction — if the caller
    fails AFTER writing it, the audit row rolls back WITH the state change (no applied-but-unaudited, and no
    audited-but-not-applied). A separately-committed audit row could never give this."""
    _clean(ORG)
    try:
        try:
            with _db() as c:
                with c.cursor() as cur:
                    audit.write(ORG, "owner", "x.do", "x", "1", {"a": 1}, cur=cur)
                    raise RuntimeError("caller blows up after the audit write")
        except RuntimeError:
            pass
        assert audit.verify_chain(ORG)["checked"] == 0          # rolled back together — nothing persisted
    finally:
        _clean(ORG)


def test_fork_is_rejected_structurally():
    """AUDIT-FORK (s55): a non-genesis previous_hash can be referenced by at most ONE row per org (DB-enforced
    CAS) → the chain physically cannot fork, the gap the advisory lock alone couldn't prove."""
    import psycopg2
    _clean(ORG)
    try:
        audit.write(ORG, "o", "config.update", "config", "a", None)        # genesis
        audit.write(ORG, "o", "config.update", "config", "b", None)        # previous_hash = row a's entry_hash
        with _db() as c:
            with c.cursor() as cur:
                cur.execute("SELECT previous_hash FROM core_audit WHERE org_id=%s AND resource_id='b'", (ORG,))
                prev_of_b = cur.fetchone()["previous_hash"]                 # = row a's entry_hash
        raised = False
        try:                                                                # a 2nd row off the same predecessor = a fork
            with _db() as c:
                with c.cursor() as cur:
                    cur.execute("INSERT INTO core_audit (id, org_id, who, action, resource_type, resource_id, "
                                "changes, at, previous_hash, entry_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(),%s,%s)",
                                ("forged-id", ORG, "x", "a", "r", "c", None, prev_of_b, "f" * 64))
        except psycopg2.errors.UniqueViolation:
            raised = True
        assert raised
        assert audit.verify_chain(ORG)["result"] == "PASS"                  # the real chain is intact
    finally:
        _clean(ORG)
