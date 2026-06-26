"""core.audit_anchor — Phase 1b: the external tamper-anchor for the audit chain (harvested from POSBusiness
`audit_anchor_service`, re-derived for our core, re-tested from scratch).

Appends each org's chain HEAD (latest entry_hash + row count) to an append-only JSONL file OUTSIDE Postgres,
HMAC-signed if `ANCHOR_HMAC_KEY` is set. Why: `core.audit`'s in-DB chain catches a naive edit/deletion, but a
DB-credential holder who rewrites rows AND re-chains every following row produces an internally-consistent chain
the in-DB verifier passes. A re-chain changes the historical hashes, so the OLD anchored heads vanish from the DB
→ `verify_anchors` FAILS. The anchor file must live off the DB host and be copied offsite to be meaningful.

Cadence: run `scripts/anchor_audit.py` on a schedule (e.g. nightly cron). Verify: `verify_audit_core.py --anchors`.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from shared.database import _db
from core.audit import GENESIS_HASH

_FILE = "core_audit_anchors.jsonl"


def _anchor_path() -> str:
    d = os.environ.get("ANCHOR_DIR") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit_anchors")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, _FILE)


def _sig(payload: str):
    key = os.environ.get("ANCHOR_HMAC_KEY")
    return hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest() if key else None


def _head(org_id):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM core_audit WHERE org_id=%s", (org_id,))
            n = cur.fetchone()["n"]
            if not n:
                return GENESIS_HASH, 0
            cur.execute("SELECT entry_hash FROM core_audit WHERE org_id=%s ORDER BY seq DESC LIMIT 1",
                        (org_id,))
            return cur.fetchone()["entry_hash"], n


def anchor_head(org_id) -> dict:
    """Append the org's current chain head to the anchor file (HMAC-signed if a key is set). Returns the record."""
    head, n = _head(org_id)
    rec = {"org_id": org_id, "head_hash": head, "count": n, "at": datetime.now(timezone.utc).isoformat()}
    rec["sig"] = _sig(json.dumps(rec, sort_keys=True))
    with open(_anchor_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def _read_anchors(org_id) -> list:
    p = _anchor_path()
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue                                           # tolerate a torn trailing line (power-loss append)
        if rec.get("org_id") == org_id:
            out.append(rec)
    return out


def verify_anchors(org_id) -> dict:
    """Every anchored head for the org must still exist in core_audit (a re-chain erases it), the row count must
    not have shrunk (deletion), and each anchor's HMAC must validate (file tamper). {result, checked, failures}."""
    anchors = _read_anchors(org_id)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT entry_hash FROM core_audit WHERE org_id=%s", (org_id,))
            hashes = {r["entry_hash"] for r in cur.fetchall()}
            cur_count = len(hashes)
    failures = []
    for a in anchors:
        base = {k: a.get(k) for k in ("org_id", "head_hash", "count", "at")}
        expect = _sig(json.dumps(base, sort_keys=True))
        if expect is not None and a.get("sig") != expect:
            failures.append("anchor signature mismatch at %s — anchor file tampered" % a.get("at"))
        if a.get("head_hash") != GENESIS_HASH and a.get("head_hash") not in hashes:
            failures.append("anchored head %s… gone from DB — chain rewritten after %s"
                            % (str(a.get("head_hash"))[:12], a.get("at")))
        if (a.get("count") or 0) > cur_count:
            failures.append("row count shrank: anchored %d > current %d — rows deleted" % (a["count"], cur_count))
    return {"result": "FAIL" if failures else "PASS", "checked": len(anchors), "failures": failures}
