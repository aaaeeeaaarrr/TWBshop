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
    """The nightly digest: today's tally + ALL unresolved mismatches (carryover — a missed night combines
    into the next), grouped by pattern with a proposed fix, plus a cut-over readiness read. Returns
    {text, stats} — text is the owner-facing report."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*) n, COUNT(*) FILTER (WHERE agree) ok
                           FROM shadow_comparisons WHERE org_id=%s AND at >= NOW() - INTERVAL '24 hours'""",
                        (org_id,))
            t = cur.fetchone()
            today_n, today_ok = t["n"], t["ok"]
            cur.execute("SELECT COUNT(*) n, COUNT(*) FILTER (WHERE agree) ok FROM shadow_comparisons "
                        "WHERE org_id=%s", (org_id,))
            a = cur.fetchone()
            all_n, all_ok = a["n"], a["ok"]
            cur.execute("""SELECT id, staff_id, live, new, source FROM shadow_comparisons
                           WHERE org_id=%s AND agree=FALSE AND reconciled=FALSE ORDER BY id""", (org_id,))
            open_rows = [dict(r) for r in cur.fetchall()]
    # group the open mismatches by pattern
    groups = {}
    for r in open_rows:
        live = r["live"] if isinstance(r["live"], dict) else json.loads(r["live"] or "{}")
        new = r["new"] if isinstance(r["new"], dict) else json.loads(r["new"] or "{}")
        key, fix = _classify(live, new)
        g = groups.setdefault(key, {"count": 0, "fix": fix, "ids": [], "example": (live, new)})
        g["count"] += 1
        g["ids"].append(r["id"])
    rate = (100.0 * all_ok / all_n) if all_n else 0.0
    open_count = len(open_rows)
    ready = all_n >= 20 and not open_count   # simple v1 gate: enough volume + zero open mismatches
    lines = ["🌓 SHADOW digest — TWBshop (org twb)",
             "Today: %d check-ins shadowed, %d agreed, %d mismatched." % (today_n, today_ok, today_n - today_ok),
             "All-time: %d compared · %.0f%% agree · %d UNRESOLVED mismatch group(s) carried over." %
             (all_n, rate, len(groups))]
    if groups:
        lines.append("\nOpen mismatch patterns (carried until reconciled):")
        for key, g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
            lines.append("  • [%s] ×%d — e.g. live=%s new=%s\n     ↳ proposed: %s"
                         % (key, g["count"], g["example"][0], g["example"][1], g["fix"]))
    else:
        lines.append("\nNo unresolved mismatches. 🎉")
    lines.append("\nCut-over readiness: %s (%.0f%% agree over %d compared; %d open)."
                 % ("READY ✅" if ready else "not yet", rate, all_n, open_count))
    return {"text": "\n".join(lines),
            "stats": {"today": today_n, "today_agree": today_ok, "all": all_n, "agree_rate": rate,
                      "open_groups": len(groups), "open_count": open_count, "ready": ready}}


def comparison_stats(org_id=None) -> dict:
    with _db() as conn:
        with conn.cursor() as cur:
            where = "WHERE org_id=%s" if org_id else ""
            args = (org_id,) if org_id else ()
            cur.execute("SELECT COUNT(*) n, COUNT(*) FILTER (WHERE agree) ok, "
                        "COUNT(*) FILTER (WHERE NOT agree) bad FROM shadow_comparisons " + where, args)
            r = cur.fetchone()
            return {"total": r["n"], "agree": r["ok"], "mismatch": r["bad"]}
