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


def compare_settle(org_id, staff_id, live: dict, new: dict, note="", source="live") -> bool:
    """Compare core's checkout-SETTLE outcome to live's on the SAME real redefine checkout. agree =
    (ot_banked AND pb_cleared) match — that's the money split. `worked` is recorded for visibility but
    not part of agree (a ±1 worked-rounding nuance is not a settle-logic mismatch). `live`/`new` are
    {worked, ot_banked, pb_cleared[, reason]}. Records either way; returns True on agree."""
    agree = (int(live.get("ot_banked", -1)) == int(new.get("ot_banked", -2))
             and int(live.get("pb_cleared", -1)) == int(new.get("pb_cleared", -2)))
    _record(org_id, staff_id, "settle", agree, live, new,
            note=note or ("" if agree else "settle MISMATCH new=%s live=%s" % (new, live)), source=source)
    return agree


def record_settle_info(org_id, staff_id, live: dict, note: str, source="live") -> None:
    """Record a settle observation that core does NOT yet model (e.g. a payback-slot's ext-worked) —
    logged as AGREE so it never raises a false cut-over alarm, but kept for visibility/coverage."""
    _record(org_id, staff_id, "settle", True, live, {"modeled": False, "note": note},
            note=note, source=source)


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
def _classify_checkin(live: dict, new: dict) -> tuple:
    """Group key + a proposed fix for a CHECK-IN mismatch (actionable, not just an alarm)."""
    if not new or new.get("bound") is False:
        return ("checkin/no-bind", "new core didn't bind a shift — a no-show / schedule gap, or a missing "
                "materialized shift. Fix: confirm the shift exists for that instant.")
    ls, ns = live.get("state"), new.get("state")
    if ls == ns:
        return ("checkin/minutes:%s" % ls,
                "same verdict (%s) but different minutes — live likely applies a GRACE or a REDEFINE the "
                "core slice doesn't model yet. Fix: port grace + redefine-aware start (EXPECTED until ported)." % ls)
    return ("checkin/state:%s->%s" % (ls, ns),
            "verdict differs (live=%s new=%s) — usually a redefine/sick-grace day. Fix: port the "
            "redefine/grace rules; if neither applies, a real logic bug to chase." % (ls, ns))


def _classify_settle(live: dict, new: dict) -> tuple:
    """Group key + a proposed fix for a SETTLE mismatch (the money split: OT banked / payback cleared)."""
    return ("settle/%s" % (live.get("reason") or "redefine"),
            "core settle (ot_banked/pb_cleared) differs from live on a real redefine checkout — check the "
            "worked / normal_len / payback inputs and the OT→payback-first→bank split (core.settle vs gm_bot.ot).")


def _classify_for(kind: str, live: dict, new: dict) -> tuple:
    return _classify_settle(live, new) if kind == "settle" else _classify_checkin(live, new)


def build_digest(org_id) -> dict:
    """Nightly digest. The LIVE real-time stream is the READINESS signal — unresolved mismatches are
    carried over (a missed night combines into the next) with proposed fixes, now grouped PER ACTION
    TYPE (check-in, settle, …). The REPLAY backfill is a one-time GAP-ANALYSIS summarised separately.
    Plus check-in COVERAGE (verdict types seen+agreed) and a cut-over readiness verdict (gated on the
    proven high-volume vertical = check-in; other verticals report their own agree-rate as they fill)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT kind, COUNT(*) n, COUNT(*) FILTER (WHERE agree) ok,
                                  COUNT(*) FILTER (WHERE at >= NOW() - INTERVAL '24 hours') n_today
                           FROM shadow_comparisons WHERE org_id=%s AND source='live'
                           GROUP BY kind ORDER BY kind""", (org_id,))
            kinds = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) n, COUNT(*) FILTER (WHERE agree) ok FROM shadow_comparisons "
                        "WHERE org_id=%s AND source='replay'", (org_id,))
            ra = cur.fetchone()
            cur.execute("""SELECT id, kind, staff_id, live, new FROM shadow_comparisons
                           WHERE org_id=%s AND source='live' AND agree=FALSE AND reconciled=FALSE
                           ORDER BY id""", (org_id,))
            open_rows = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT new->>'state' s FROM shadow_comparisons "
                        "WHERE org_id=%s AND source='live' AND agree AND kind='checkin'", (org_id,))
            covered = sorted(r["s"] for r in cur.fetchall() if r["s"])
    groups = {}
    for r in open_rows:
        live = r["live"] if isinstance(r["live"], dict) else json.loads(r["live"] or "{}")
        new = r["new"] if isinstance(r["new"], dict) else json.loads(r["new"] or "{}")
        key, fix = _classify_for(r["kind"], live, new)
        g = groups.setdefault(key, {"count": 0, "fix": fix, "example": (live, new)})
        g["count"] += 1
    by_kind = {k["kind"]: k for k in kinds}
    ci = by_kind.get("checkin", {"n": 0, "ok": 0, "n_today": 0})
    ci_rate = (100.0 * ci["ok"] / ci["n"]) if ci["n"] else 0.0
    replay_rate = (100.0 * ra["ok"] / ra["n"]) if ra["n"] else 0.0
    open_count = len(open_rows)
    full_cover = set(covered) >= {"on_time", "late", "early"}
    # cut-over readiness stays gated on the proven high-volume vertical (check-in): no open CHECK-IN
    # mismatch, enough volume, full verdict coverage. Other verticals report agree-rate, don't gate yet.
    ready = ci["n"] >= 20 and not any(k.startswith("checkin") for k in groups) and full_cover
    lines = ["🌓 SHADOW digest — TWBshop (org twb)",
             "LIVE check-in (readiness signal): %d today / %d all-time · %.0f%% agree." % (ci["n_today"], ci["n"], ci_rate),
             "By action type (live, all-time):"]
    for k in kinds:
        rate = (100.0 * k["ok"] / k["n"]) if k["n"] else 0.0
        lines.append("  • %-9s %d compared · %.0f%% agree · %d today" % (k["kind"] + ":", k["n"], rate, k["n_today"]))
    if not kinds:
        lines.append("  • (no live comparisons yet — shadow_run off, or no events)")
    lines.append("Replay backtest (one-time gap-analysis): %d compared · %.0f%% agree." % (ra["n"], replay_rate))
    lines.append("Check-in coverage (verdict types agreed live): %s%s"
                 % (", ".join(covered) or "none yet", "" if full_cover else "  ⚠ missing some of on_time/late/early"))
    if groups:
        lines.append("\nOpen LIVE mismatch patterns (carried until reconciled):")
        for key, g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
            lines.append("  • [%s] ×%d — e.g. live=%s new=%s\n     ↳ proposed: %s"
                         % (key, g["count"], g["example"][0], g["example"][1], g["fix"]))
    else:
        lines.append("\nNo open LIVE mismatches. 🎉")
    lines.append("\nCut-over readiness (check-in vertical): %s — %.0f%% over %d · %d open total · coverage %s."
                 % ("READY ✅" if ready else "not yet", ci_rate, ci["n"], open_count, "full" if full_cover else "partial"))
    return {"text": "\n".join(lines),
            "stats": {"live_today": ci["n_today"], "live_all": ci["n"], "live_rate": ci_rate,
                      "by_kind": {k["kind"]: {"n": k["n"], "ok": k["ok"]} for k in kinds},
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


def comparison_stats_by_kind(org_id) -> dict:
    """Per-vertical shadow agreement ({kind: {total, agree}}) — the empirical basis for a per-vertical
    cut-over decision (read-only)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT kind, COUNT(*) n, COUNT(*) FILTER (WHERE agree) ok FROM shadow_comparisons "
                        "WHERE org_id=%s GROUP BY kind ORDER BY kind", (org_id,))
            return {r["kind"]: {"total": r["n"], "agree": r["ok"]} for r in cur.fetchall()}


def recent_mismatches(org_id, limit: int = 10) -> list:
    """Recent disagreements (read-only) — what the new platform computed differently from live, so the owner
    can see WHAT differs before cutting over."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT kind, staff_id, live, new, at FROM shadow_comparisons "
                        "WHERE org_id=%s AND NOT agree ORDER BY at DESC LIMIT %s", (org_id, int(limit)))
            return [dict(r) for r in cur.fetchall()]
