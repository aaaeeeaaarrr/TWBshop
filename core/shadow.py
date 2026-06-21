"""core.shadow — the parallel-run comparator.

The de-risk mechanism: for the SAME real event, record what the NEW core computed vs what LIVE TWB did,
and flag any mismatch. Acts on NOTHING — pure observation. Weeks of agreement = confidence to cut over;
every mismatch is a bug caught before it touches a human. (Per docs/PLATFORM_VISION.md migration plan.)
"""
import json

from shared.database import _db


def _record(org_id, staff_id, kind, agree, live, new, note=""):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO shadow_comparisons (org_id, staff_id, kind, agree, live, new, note)
                           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (org_id, staff_id, kind, agree,
                         json.dumps(live, default=str), json.dumps(new, default=str), note))
            return cur.fetchone()["id"]


def compare_checkin(org_id, staff_id, live_state, live_minutes_late, live_minutes_early,
                    new_result: dict) -> bool:
    """Compare the new check-in verdict to live's. Returns True if they agree (and records either way).
    The first asserts per the design: the STATE + the lateness/earliness MINUTES."""
    if not new_result.get("bound"):
        _record(org_id, staff_id, "checkin", False,
                {"state": live_state, "late": live_minutes_late, "early": live_minutes_early},
                new_result, note="new core did not bind a shift")
        return False
    live = {"state": live_state, "late": int(live_minutes_late or 0), "early": int(live_minutes_early or 0)}
    new = {"state": new_result["state"], "late": int(new_result["minutes_late"]),
           "early": int(new_result["minutes_early"])}
    agree = (live == new)
    _record(org_id, staff_id, "checkin", agree, live, new,
            note="" if agree else "MISMATCH: new=%s live=%s" % (new, live))
    return agree


def comparison_stats(org_id=None) -> dict:
    """Summary for a quick health read during the shadow period: total / agreed / mismatched."""
    with _db() as conn:
        with conn.cursor() as cur:
            where = "WHERE org_id=%s" % "%s" if org_id else ""
            args = (org_id,) if org_id else ()
            cur.execute("SELECT COUNT(*) n, COUNT(*) FILTER (WHERE agree) ok, "
                        "COUNT(*) FILTER (WHERE NOT agree) bad FROM shadow_comparisons " + where, args)
            r = cur.fetchone()
            return {"total": r["n"], "agree": r["ok"], "mismatch": r["bad"]}
