"""core.audit_anchor — Phase 1b external tamper-anchor (re-tested from scratch): anchor+verify PASS · a full
re-chain (the one thing the in-DB chain can't catch) → anchor FAIL · HMAC detects anchor-file tampering."""
import json

import core.db as cdb
from shared.database import _db
from core import audit
from core import audit_anchor as anchor

cdb.init_core_db()
ORG = "test_audit_anchor"


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_audit WHERE org_id=%s", (ORG,))


def test_anchor_and_verify_pass(monkeypatch, tmp_path):
    monkeypatch.setenv("ANCHOR_DIR", str(tmp_path))
    _clean()
    try:
        audit.write(ORG, "o", "config.update", "config", "a", None)
        audit.write(ORG, "o", "config.update", "config", "b", None)
        rec = anchor.anchor_head(ORG)
        assert rec["count"] == 2 and len(rec["head_hash"]) == 64
        assert anchor.verify_anchors(ORG)["result"] == "PASS"
    finally:
        _clean()


def test_full_rechain_caught_by_anchor(monkeypatch, tmp_path):
    monkeypatch.setenv("ANCHOR_DIR", str(tmp_path))
    _clean()
    try:
        audit.write(ORG, "o", "config.update", "config", "a", None)
        audit.write(ORG, "o", "config.update", "config", "b", None)
        anchor.anchor_head(ORG)                                       # anchors the old head
        # a DB-admin re-chain: wipe + rewrite different rows (a fresh internally-consistent chain)
        _clean()
        audit.write(ORG, "o", "config.update", "config", "a", {"tampered": True})
        audit.write(ORG, "o", "config.update", "config", "b", {"tampered": True})
        assert audit.verify_chain(ORG)["result"] == "PASS"           # in-DB chain is fooled by a full re-chain
        v = anchor.verify_anchors(ORG)
        assert v["result"] == "FAIL" and any("rewritten" in f for f in v["failures"])   # the anchor catches it
    finally:
        _clean()


def test_hmac_detects_anchor_file_tamper(monkeypatch, tmp_path):
    monkeypatch.setenv("ANCHOR_DIR", str(tmp_path))
    monkeypatch.setenv("ANCHOR_HMAC_KEY", "test-key-123")
    _clean()
    try:
        audit.write(ORG, "o", "config.update", "config", "a", None)
        anchor.anchor_head(ORG)
        assert anchor.verify_anchors(ORG)["result"] == "PASS"
        p = anchor._anchor_path()                                    # forge a head in the anchor file
        rec = json.loads(open(p, encoding="utf-8").read().splitlines()[0])
        rec["head_hash"] = "f" * 64
        open(p, "w", encoding="utf-8").write(json.dumps(rec) + "\n")
        assert anchor.verify_anchors(ORG)["result"] == "FAIL"       # HMAC mismatch + head gone
    finally:
        _clean()
