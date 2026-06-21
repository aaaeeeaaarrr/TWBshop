"""core.shadow nightly digest — carryover (a missed night combines into the next), grouped mismatches +
proposed fixes, and the readiness read. Real staging DB; cleaned up."""
import core.db as cdb
from core.shadow import compare_checkin, build_digest, mark_reconciled
from shared.database import _db

ORG = "test_digest"


def _setup():
    cdb.init_core_db()
    cdb.ensure_org(ORG, "Test", "Asia/Phnom_Penh")
    _clean()


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM shadow_comparisons WHERE org_id=%s", (ORG,))


def _open_ids():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT id FROM shadow_comparisons WHERE org_id=%s AND agree=FALSE AND reconciled=FALSE",
                        (ORG,))
            return [r["id"] for r in cur.fetchall()]


def test_digest_groups_mismatches_with_fixes_and_readiness():
    _setup()
    try:
        compare_checkin(ORG, 1, "early", 0, 5, {"bound": True, "state": "early", "minutes_late": 0, "minutes_early": 5})  # agree
        compare_checkin(ORG, 2, "late", 30, 0, {"bound": True, "state": "on_time", "minutes_late": 0, "minutes_early": 0})  # state mismatch
        compare_checkin(ORG, 3, "late", 10, 0, {"bound": True, "state": "late", "minutes_late": 5, "minutes_early": 0})    # minutes mismatch
        d = build_digest(ORG)
        assert d["stats"]["today"] == 3 and d["stats"]["today_agree"] == 1
        assert d["stats"]["open_groups"] == 2          # two distinct patterns
        assert "proposed:" in d["text"]                 # each pattern carries a proposed fix
        assert d["stats"]["ready"] is False             # open mismatches -> not ready
    finally:
        _clean()


def test_carryover_until_reconciled():
    _setup()
    try:
        compare_checkin(ORG, 2, "late", 30, 0, {"bound": True, "state": "on_time", "minutes_late": 0, "minutes_early": 0})
        # backdate it to 3 days ago — proves the digest carries OLD unresolved mismatches, not just today's
        with _db() as c:
            with c.cursor() as cur:
                cur.execute("UPDATE shadow_comparisons SET at = NOW() - INTERVAL '3 days' WHERE org_id=%s", (ORG,))
        d = build_digest(ORG)
        assert d["stats"]["today"] == 0                 # nothing in the last 24h
        assert d["stats"]["open_count"] == 1            # but the old mismatch is STILL carried over
        # reconcile it -> drops out of the carryover (a missed night that we then act on)
        assert mark_reconciled(_open_ids()) == 1
        d2 = build_digest(ORG)
        assert d2["stats"]["open_count"] == 0 and "No unresolved mismatches" in d2["text"]
    finally:
        _clean()
