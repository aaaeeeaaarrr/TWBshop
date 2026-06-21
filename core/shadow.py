"""core.shadow — the parallel-run comparator + the nightly digest brain.

For the SAME real event, record what the NEW core computed vs what LIVE TWB did, flag mismatches, and
produce a nightly digest that (a) CARRIES OVER unresolved mismatches so a missed night is never lost,
(b) groups them by pattern with a PROPOSED FIX to chat about, and (c) gives a cut-over READINESS read.
Acts on NOTHING — pure observation. (docs/PLATFORM_VISION.md migration plan.)
"""
import json

from shared.database import _db


def _record(org_id, staff_id, kind, agree, live, new, note="", source="live"):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO shadow_comparisons
                           (org_id, staff_id, kind, agree, live, new, note, source)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (org_id, staff_id, kind, agree,
                         json.dumps(live, default=str), json.dumps(new, default=str), note, source))
            return cur.fetchone()["id"]


def compare_checkin(org_id, staff_id, live_state, live_minutes_late, live_minutes_early,
                    new_result: dict, source: str = "live") -> bool:
    """Compare the new check-in verdict to live's (STATE + lateness/earliness MINUTES). Records either
    way; returns True if they agree. `source`: 'live' (real-time hook) or 'replay' (historical backfill)."""
    if not new_result.get("bound"):
        _record(org_id, staff_id, "checkin", False,
                {"state": live_state, "late": live_minutes_late, "early": live_minutes_early},
                new_result, note="new core did not bind a shift", source=source)
        return False
    live = {"state": live_state, "late": int(live_minutes_late or 0), "early": int(live_minutes_early or 0)}
    new = {"state": new_result["state"], "late": int(new_result["minutes_late"]),
           "early": int(new_result["minutes_early"])}
    agree = (live == new)
    _record(org_id, staff_id, "checkin", agree, live, new,
            note="" if agree else "MISMATCH new=%s live=%s" % (new, live), source=source)
    return agree


def mark_reconciled(ids) -> int:
    """Mark mismatches as understood/fixed/accepted so they drop out of the carryover."""
    ids = list(ids)
    if not ids:
        return 0
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE shadow_comparisons SET reconciled=TRUE WHERE id = ANY(%s)", (ids,))
            return cur.rowcount


# ── digest analysis ─────────────────────────────────────────────────────────
def _classify(live: dict, new: dict) -> tuple:
    """Group key + a proposed fix for a mismatch pattern (so the report is actionable, not just alarms)."""
    if not new or new.get("bound") is False:
        return ("no-bind", "new core didn't bind a shift — a no-show / schedule gap, or a missing "
                            "materialized shift. Fix: confirm the shift exists for that instant.")
    ls, ns = live.get("state"), new.get("state")
    if ls == ns:
        return ("minutes:%s" % ls,
                "same verdict (%s) but different minutes — live likely applies a GRACE or a REDEFINE "
                "(payback/OT slot) the core slice doesn't model yet. Fix: port grace + redefine-aware "
                "start into core.check_in (EXPECTED until ported)." % ls)
    return ("state:%s->%s" % (ls, ns),
            "verdict differs (live=%s new=%s) — usually a redefine/sick-grace day the core slice doesn't "
            "model yet. Fix: port the redefine/grace rules; if neither applies, a real logic bug to chase."
            % (ls, ns))


def build_digest(org_id) -> dict:
    """Nightly digest. The LIVE real-time stream is the READINESS signal — its unresolved mismatches are
    carried over (a missed night combines into the next) with proposed fixes. The REPLAY backfill is a
    one-time GAP-ANALYSIS, summarised separately so launch-week backfill noise never drags the live read.
    Plus COVERAGE (which verdict types have been seen+agreed) and a cut-over readiness verdict."""
    with _db() as conn:
        with conn.cursor() as cur:
            def _stat(src, day=False):
                q = ("SELECT COUNT(*) n, COUNT(*) FILTER (WHERE agree) ok FROM shadow_comparisons "
                     "WHERE org_id=%s AND source=%s")
                if day:
                    q += " AND at >= NOW() - INTERVAL '24 hours'"
                cur.execute(q, (org_id, src))
                return cur.fetchone()
            lt, la, ra = _stat("live", True), _stat("live"), _stat("replay")
            cur.execute("""SELECT id, staff_id, live, new FROM shadow_comparisons
                           WHERE org_id=%s AND source='live' AND agree=FALSE AND reconciled=FALSE
                           ORDER BY id""", (org_id,))
            open_rows = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT new->>'state' s FROM shadow_comparisons "
                        "WHERE org_id=%s AND source='live' AND agree", (org_id,))
            covered = sorted(r["s"] for r in cur.fetchall() if r["s"])
    groups = {}
    for r in open_rows:
        live = r["live"] if isinstance(r["live"], dict) else json.loads(r["live"] or "{}")
        new = r["new"] if isinstance(r["new"], dict) else json.loads(r["new"] or "{}")
        key, fix = _classify(live, new)
        g = groups.setdefault(key, {"count": 0, "fix": fix, "example": (live, new)})
        g["count"] += 1
    live_rate = (100.0 * la["ok"] / la["n"]) if la["n"] else 0.0
    replay_rate = (100.0 * ra["ok"] / ra["n"]) if ra["n"] else 0.0
    open_count = len(open_rows)
    full_cover = set(covered) >= {"on_time", "late", "early"}
    ready = la["n"] >= 20 and open_count == 0 and full_cover
    lines = ["🌓 SHADOW digest — TWBshop (org twb)",
             "LIVE stream (real-time = the readiness signal): %d today / %d all-time · %.0f%% agree · %d open group(s)."
             % (lt["n"], la["n"], live_rate, len(groups)),
             "Replay backtest (one-time gap-analysis): %d compared · %.0f%% agree." % (ra["n"], replay_rate),
             "Coverage (verdict types agreed live): %s%s"
             % (", ".join(covered) or "none yet", "" if full_cover else "  ⚠ missing some of on_time/late/early")]
    if groups:
        lines.append("\nOpen LIVE mismatch patterns (carried until reconciled):")
        for key, g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
            lines.append("  • [%s] ×%d — e.g. live=%s new=%s\n     ↳ proposed: %s"
                         % (key, g["count"], g["example"][0], g["example"][1], g["fix"]))
    else:
        lines.append("\nNo open LIVE mismatches. 🎉")
    lines.append("\nCut-over readiness: %s — live %.0f%% over %d · backtest %.0f%% over %d · %d open · coverage %s."
                 % ("READY ✅" if ready else "not yet", live_rate, la["n"], replay_rate, ra["n"],
                    open_count, "full" if full_cover else "partial"))
    return {"text": "\n".join(lines),
            "stats": {"live_today": lt["n"], "live_all": la["n"], "live_rate": live_rate,
                      "replay_all": ra["n"], "replay_rate": replay_rate, "open_groups": len(groups),
                      "open_count": open_count, "coverage": covered, "ready": ready}}


def comparison_stats(org_id=None) -> dict:
    with _db() as conn:
        with conn.cursor() as cur:
            where = "WHERE org_id=%s" if org_id else ""
            args = (org_id,) if org_id else ()
            cur.execute("SELECT COUNT(*) n, COUNT(*) FILTER (WHERE agree) ok, "
                        "COUNT(*) FILTER (WHERE NOT agree) bad FROM shadow_comparisons " + where, args)
            r = cur.fetchone()
            return {"total": r["n"], "agree": r["ok"], "mismatch": r["bad"]}
