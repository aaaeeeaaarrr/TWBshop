"""core.audit — tamper-evident, hash-chained audit log.

Harvested from POSBusiness (`backend/app/services/audit_service.py` + `verify_audit_chain.py`), re-derived for
our psycopg2 / `orgs.config` core and RE-TESTED FROM SCRATCH (its design was an external/ChatGPT plan, proven on
its own SQLAlchemy stack — we re-prove ours). Two tamper layers:

  • entry_hash    = SHA-256(canonical row)            → detects CONTENT tampering (edit a field → won't recompute)
  • previous_hash = the prior row's entry_hash for that org (genesis = "0"*64) → detects ROW DELETION (a gap
                    leaves a dangling previous_hash)

`verify_chain` re-walks an org's chain and returns PASS/FAIL. Org-scoped, channel-free. Both hash columns are
NOT NULL from row 1 (we have no legacy rows → no nullable→NOT-NULL retrofit, unlike POSBusiness's migration 0012).
A per-org advisory lock serializes writes so concurrent writers can't fork the chain.

Limits (honest): (1) `changes` must be JSON-serializable (callers stringify Decimals/datetimes). (2) The chain
catches NAIVE tampering — an edited or deleted row. A DB-credential holder who edits a row AND re-chains every
following row produces an internally-consistent chain that verify_chain passes; only the external ANCHOR layer
(POSBusiness `audit_anchor_service` — our Phase 1b, not yet built) catches that, by holding the chain head in a
file outside Postgres.
"""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from shared.database import _db

GENESIS_HASH = "0" * 64                                        # the "no predecessor" sentinel (first row in a chain)


def _at_key(at: datetime) -> str:
    """Deterministic, tz-robust timestamp string for the hash (normalize to UTC; handle naive)."""
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at.astimezone(timezone.utc).isoformat()


def _canonical(row_id, who, action, resource_type, resource_id, changes, at) -> str:
    return "%s|%s|%s|%s|%s|%s|%s" % (
        row_id, who or "", action, resource_type, resource_id or "",
        json.dumps(changes or {}, sort_keys=True), _at_key(at))


def write(org_id, who, action, resource_type, resource_id=None, changes=None, cur=None) -> str:
    """Append a hash-chained audit row. Returns the entry_hash. If `cur` is given, the row is written on THAT
    cursor — i.e. in the SAME transaction as the caller's state change, so a money/config op can never commit
    while its audit row is lost (and both roll back together on failure). Without `cur`, opens its own txn. The
    id is generated Python-side so entry_hash is set on the single INSERT — no NULL-hash window ever exists."""
    if cur is not None:
        return _append(cur, org_id, who, action, resource_type, resource_id, changes)
    with _db() as conn:
        with conn.cursor() as c:
            return _append(c, org_id, who, action, resource_type, resource_id, changes)


def _append(cur, org_id, who, action, resource_type, resource_id, changes) -> str:
    # serialize this org's chain for the txn so two concurrent writers can't both read the same head and FORK
    # the chain. The partial-unique on (org_id, previous_hash) is the DB backstop. Released at commit.
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (org_id,))
    at = datetime.now(timezone.utc)                              # captured AFTER the lock — no skew vs the chain
    cur.execute("SELECT entry_hash FROM core_audit WHERE org_id=%s ORDER BY seq DESC LIMIT 1", (org_id,))
    r = cur.fetchone()
    previous_hash = (r["entry_hash"] if r else None) or GENESIS_HASH
    row_id = str(uuid4())
    entry_hash = hashlib.sha256(
        _canonical(row_id, who, action, resource_type, resource_id, changes, at).encode()).hexdigest()
    cur.execute("INSERT INTO core_audit (id, org_id, who, action, resource_type, resource_id, changes, "
                "at, previous_hash, entry_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (row_id, org_id, who, action, resource_type, resource_id,
                 json.dumps(changes) if changes is not None else None, at, previous_hash, entry_hash))
    return entry_hash


def verify_chain(org_id) -> dict:
    """Re-walk an org's chain oldest→newest (by seq): recompute each entry_hash, check previous_hash points to a
    real prior entry_hash, AND flag a FORK (a previous_hash referenced by >1 row). Returns
    {result: 'PASS'|'FAIL', checked, failures:[...]} — empty failures = intact."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, who, action, resource_type, resource_id, changes, at, previous_hash, "
                        "entry_hash FROM core_audit WHERE org_id=%s ORDER BY seq ASC, at ASC, id ASC", (org_id,))
            rows = cur.fetchall()
    known, used_prev, failures = set(), set(), []
    for row in rows:
        expected = hashlib.sha256(
            _canonical(row["id"], row["who"], row["action"], row["resource_type"], row["resource_id"],
                       row["changes"], row["at"]).encode()).hexdigest()
        if row["entry_hash"] != expected:
            failures.append("entry_hash mismatch at %s — content tampered" % row["id"])
        if row["previous_hash"] != GENESIS_HASH:
            if row["previous_hash"] not in known:
                failures.append("previous_hash dangling at %s — a prior row was deleted or tampered" % row["id"])
            if row["previous_hash"] in used_prev:
                failures.append("chain fork at %s — previous_hash referenced by more than one row" % row["id"])
            used_prev.add(row["previous_hash"])
        known.add(row["entry_hash"])
    return {"result": "FAIL" if failures else "PASS", "checked": len(rows), "failures": failures}


def recent(org_id, limit=100) -> list:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT who, action, resource_type, resource_id, changes, at FROM core_audit "
                        "WHERE org_id=%s ORDER BY seq DESC LIMIT %s", (org_id, int(limit)))
            return [dict(r) for r in cur.fetchall()]
