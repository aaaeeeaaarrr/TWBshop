"""One-off repair for the s59c mispair class (A2, 2026-07-03): a check-in landed on the
RESOLVED-start shift instance while its checkout landed on the BASE-start instance —
two orphan half-shifts per day (Nak's 20:56 come-early slots, Thyda's 06:00 ones).

For each (org, staff, business_day) holding exactly ONE in-only instance and ONE
out-only sibling, MOVE the checkout event onto the check-in's instance (recomputing
worked_min from the real pair, capped at that instance's end and floored at its
start) and delete the then-empty sibling. PLATFORM SHADOW TABLES ONLY (shifts /
attendance_events) — touches NOTHING the live system reads. Anything not exactly
that shape is reported and left alone. Idempotent. Dry-run by default; --apply to write.

Run (server):  TWBSHOP_ENV=prod python scripts/repair_core_mispairs.py [--apply]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.database import _db  # noqa: E402


def find_pairs(org_id: str) -> list:
    """(in_shift, out_shift) siblings: same staff+business_day, one holds only the
    check-in, the other only the checkout."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH counts AS (
                    SELECT s.shift_id, s.staff_id, s.business_day, s.start_dt, s.end_dt,
                           count(*) FILTER (WHERE e.type='checked_in')  AS ins,
                           count(*) FILTER (WHERE e.type='checked_out') AS outs
                    FROM shifts s LEFT JOIN attendance_events e ON e.shift_id = s.shift_id
                    WHERE s.org_id = %s
                    GROUP BY s.shift_id
                )
                SELECT i.shift_id  AS in_id,  i.start_dt AS in_start, i.end_dt AS in_end,
                       o.shift_id  AS out_id, o.start_dt AS out_start,
                       i.staff_id, i.business_day
                FROM counts i
                JOIN counts o ON o.staff_id = i.staff_id AND o.business_day = i.business_day
                             AND o.shift_id <> i.shift_id
                WHERE i.ins = 1 AND i.outs = 0 AND o.ins = 0 AND o.outs = 1
                ORDER BY i.staff_id, i.business_day""", (org_id,))
            return [dict(r) for r in cur.fetchall()]


def repair(org_id: str, apply: bool) -> int:
    pairs = find_pairs(org_id)
    if not pairs:
        print("no mispaired half-shifts found — nothing to do")
        return 0
    moved = 0
    for p in pairs:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT event_id, at FROM attendance_events "
                            "WHERE shift_id=%s AND type='checked_out'", (p["out_id"],))
                co = cur.fetchone()
                cur.execute("SELECT at FROM attendance_events "
                            "WHERE shift_id=%s AND type='checked_in'", (p["in_id"],))
                ci = cur.fetchone()
                if not co or not ci:
                    print("SKIP odd pair (events moved underneath?):", p)
                    continue
                end_cap = min(co["at"], p["in_end"])
                start_floor = max(ci["at"], p["in_start"])
                worked = max(0, round((end_cap - start_floor).total_seconds() / 60.0))
                print("%s staff %-3s day %s: move checkout ev#%s  %s → shift %s  (worked %s min)%s"
                      % ("APPLY " if apply else "DRY   ", p["staff_id"], p["business_day"],
                         co["event_id"], p["out_id"], p["in_id"], worked,
                         "" if apply else "  [not written]"))
                if apply:
                    cur.execute("UPDATE attendance_events SET shift_id=%s, detail=%s "
                                "WHERE event_id=%s",
                                (p["in_id"], json.dumps({"worked_min": worked,
                                                         "repaired": "A2 mispair 2026-07-03"}),
                                 co["event_id"]))
                    cur.execute("SELECT count(*) n FROM attendance_events WHERE shift_id=%s",
                                (p["out_id"],))
                    if cur.fetchone()["n"] == 0:
                        cur.execute("DELETE FROM shifts WHERE shift_id=%s", (p["out_id"],))
                    moved += 1
    print("\n%d pair(s) %s" % (len(pairs), "repaired" if apply else "found (dry-run; --apply to write)"))
    return moved


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", default="twb")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args()
    repair(args.org, args.apply)
