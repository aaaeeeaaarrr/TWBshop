"""Invariant auditor — owner /audit (session 32, pre-go-live checklist).

Every button press must leave the data in a LAWFUL state. Instead of re-checking each tap,
this codifies the laws and verifies ALL rows in one pass — inputs → outputs cross-check:
approved AL ⇒ deducted exactly its passed days; cleared debt ⇔ fully paid; settled shift ⇒
OT banked within cap; checkout ≥ checkin; no-show never on a checked-in day; …

Mode-aware like everything else: in TEST mode it audits the is_test rows (cross-checks the
owner's role-play), live it audits the real rows. Pure validators (testable, no DB) + a thin
SQL runner. Each problem line is self-contained — the owner can paste it to Claude as-is.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

OT_CAP_MIN = 840          # 14h bank cap
STALE_PENDING_DAYS = 4    # a request nobody decided for this long = stuck ladder
STALE_OPEN_SESSION_DAYS = 2


def _nm(staff_by_id: dict, sid) -> str:
    s = staff_by_id.get(sid) or {}
    cn = (s.get("call_name") or "").strip()
    return cn.upper() if cn else (s.get("canonical_name") or ("staff#%s" % sid))


# ───────────────────────────── pure validators ─────────────────────────────

def v_payback(debts: list[dict], staff: dict) -> list[str]:
    out = []
    open_count: dict = {}
    for d in debts:
        nm = _nm(staff, d["staff_id"])
        owed, paid, st = int(d["minutes_owed"] or 0), int(d["minutes_paid"] or 0), d["status"]
        if owed <= 0:
            out.append("PB: %s debt #%s has owed=%d (must be >0)" % (nm, d["id"], owed))
        if st == "cleared" and paid < owed:
            out.append("PB: %s debt #%s is 'cleared' but only %d/%d min paid" % (nm, d["id"], paid, owed))
        if st == "open" and paid >= owed:
            out.append("PB: %s debt #%s is fully paid (%d/%d) but still 'open'" % (nm, d["id"], paid, owed))
        if st not in ("open", "cleared"):
            out.append("PB: %s debt #%s has unknown status '%s'" % (nm, d["id"], st))
        if st == "open":
            open_count[d["staff_id"]] = open_count.get(d["staff_id"], 0) + 1
    for sid, n in open_count.items():
        if n > 1:
            out.append("PB: %s has %d OPEN debts — the system assumes one; they must be merged"
                       % (_nm(staff, sid), n))
    return out


def v_al(requests: list[dict], staff: dict, today: date) -> list[str]:
    out = []
    for r in requests:
        nm = _nm(staff, r["staff_id"])
        days = json.loads(r.get("days") or "[]")
        ded = json.loads(r.get("deducted_days") or "[]")
        st = r["status"]
        bad = [d for d in ded if d not in days]
        if bad:
            out.append("AL: %s req #%s deducted days not in the request: %s" % (nm, r["id"], bad))
        if st == "approved" and r.get("kind") == "days":
            missed = [d for d in days if d < today.isoformat() and d not in ded]
            if missed:
                out.append("AL: %s req #%s approved, dates passed but NOT deducted: %s"
                           % (nm, r["id"], missed))
        if st in ("rejected", "cancelled") and ded:
            out.append("AL: %s req #%s is %s but has deductions %s (refund missing?)"
                       % (nm, r["id"], st, ded))
        if st == "pending" and r.get("created_at"):
            age = (today - r["created_at"].date()).days
            if age >= STALE_PENDING_DAYS:
                out.append("AL: %s req #%s PENDING for %d days — approval ladder stuck?"
                           % (nm, r["id"], age))
    return out


def v_shift_changes(rows: list[dict], staff: dict, today: date) -> list[str]:
    out = []
    for r in rows:
        nm = _nm(staff, r["staff_id"])
        st = r["status"]
        if st not in ("proposed", "approved", "declined", "cancelled", "done"):
            out.append("OT: %s change #%s unknown status '%s'" % (nm, r["id"], st))
        if st == "done":
            ob = r.get("ot_banked")
            if ob is None or not (0 <= int(ob) <= OT_CAP_MIN):
                out.append("OT: %s change #%s is done but ot_banked=%s (must be 0..%d)"
                           % (nm, r["id"], ob, OT_CAP_MIN))
        if st == "approved" and r.get("when_date") and r["when_date"] < today:
            out.append("OT: %s change #%s APPROVED for %s but never settled — OT may not have "
                       "banked at checkout" % (nm, r["id"], r["when_date"]))
        if st == "proposed" and r.get("when_date") and r["when_date"] < today:
            out.append("OT: %s change #%s still PROPOSED but its date %s passed (staff never "
                       "answered)" % (nm, r["id"], r["when_date"]))
        if st in ("approved", "done") and not r.get("normal_len"):
            out.append("OT: %s change #%s %s without normal_len — settle can't compute OT"
                       % (nm, r["id"], st))
    return out


def v_sessions(rows: list[dict], staff: dict, today: date) -> list[str]:
    out = []
    for r in rows:
        nm = _nm(staff, r["staff_id"])
        ci, co = r.get("checked_in_at"), r.get("checked_out_at")
        if ci and co and co < ci:
            out.append("ATT: %s session %s checkout %s BEFORE checkin %s"
                       % (nm, r["shift_date"], co, ci))
        if r.get("status") == "closed" and not co:
            out.append("ATT: %s session %s closed without a checkout time" % (nm, r["shift_date"]))
        if (r.get("status") == "open" and r.get("shift_date")
                and r["shift_date"] < today - timedelta(days=STALE_OPEN_SESSION_DAYS - 1)):
            out.append("ATT: %s session %s still OPEN (never checked out / never closed)"
                       % (nm, r["shift_date"]))
        for f in ("minutes_late", "minutes_early"):
            if r.get(f) is not None and int(r[f]) < 0:
                out.append("ATT: %s session %s has %s=%s (negative)" % (nm, r["shift_date"], f, r[f]))
    return out


def v_ot_bank(rows: list[dict], staff: dict) -> list[str]:
    return ["OT BANK: %s balance %s min outside 0..%d" % (_nm(staff, r["staff_id"]),
            r["balance_min"], OT_CAP_MIN)
            for r in rows if not (0 <= int(r["balance_min"] or 0) <= OT_CAP_MIN)]


def v_noshow_vs_sessions(noshows: list[dict], sessions: list[dict], staff: dict) -> list[str]:
    checked_in = {(s["staff_id"], s["shift_date"]) for s in sessions if s.get("checked_in_at")}
    return ["NOSHOW: %s marked no-show on %s but a CHECK-IN exists that day (reverse it?)"
            % (_nm(staff, n["staff_id"]), n["shift_date"])
            for n in noshows if n.get("status") == "open"
            and (n["staff_id"], n["shift_date"]) in checked_in]


def v_bookings(bookings: list[dict], debts_by_id: dict, staff: dict, today: date) -> list[str]:
    out = []
    for b in bookings:
        nm = _nm(staff, b["staff_id"])
        if b.get("debt_id") and b["debt_id"] not in debts_by_id:
            out.append("PB-BOOK: %s booking #%s points at debt #%s which doesn't exist"
                       % (nm, b["id"], b["debt_id"]))
        if int(b.get("minutes") or 0) <= 0:
            out.append("PB-BOOK: %s booking #%s has minutes=%s" % (nm, b["id"], b.get("minutes")))
        if (b.get("status") == "booked" and b.get("slot_date")
                and b["slot_date"] < today - timedelta(days=1)):
            out.append("PB-BOOK: %s booking #%s slot %s passed but still 'booked' "
                       "(neither done nor missed)" % (nm, b["id"], b["slot_date"]))
    return out


def v_swaps(rows: list[dict], staff: dict, today: date) -> list[str]:
    out = []
    for r in rows:
        nm = _nm(staff, r["requester_id"])
        if r["status"] == "approved" and r.get("partner_ok") is not True:
            out.append("SWAP: %s swap #%s approved but the partner never agreed" % (nm, r["id"]))
        if (r["status"] in ("pending", "partner_ok") and r.get("req_off_date")
                and r["req_off_date"] < today):
            out.append("SWAP: %s swap #%s still %s but its date %s passed"
                       % (nm, r["id"], r["status"], r["req_off_date"]))
    return out


def _hhmm_min(s) -> int | None:
    try:
        h, m = str(s).split(":")[:2]
        return int(h) * 60 + int(m)
    except Exception:
        return None


def v_late_points(sessions: list[dict], events: list[dict], staff: dict) -> list[str]:
    """ACTIVE-points law: a late check-in must carry late events totaling EXACTLY its minutes —
    the informed/uninformed split may vary (declaration-time split), the SUM may not."""
    totals: dict = {}
    for e in events:
        if e.get("cause") in ("late_informed", "late_uninformed"):
            k = (e["staff_id"], str(e.get("ref")))
            totals[k] = totals.get(k, 0) + int(e.get("quantity") or 0)
    out = []
    for s in sessions:
        ml = int(s.get("minutes_late") or 0)
        if ml <= 0:
            continue
        got = totals.get((s["staff_id"], str(s["shift_date"])), 0)
        if got != ml:
            out.append("POINTS: %s was %d min late on %s but late-events total %d min "
                       "(missing or doubled scoring)"
                       % (_nm(staff, s["staff_id"]), ml, s["shift_date"], got))
    return out


AL_GATE_LAW_FROM = "2026-06-11"   # the day the gate shipped (owner may go live same day) —
                                  # older requests predate it AND predate location check-ins
                                  # entirely (no sessions exist pre-go-live)


def v_al_same_day_gate(requests: list[dict], sessions: list[dict], staff: dict) -> list[str]:
    """The AL-today gate's data-side law: a request CREATED on a day it covers, at/after that
    day's shift start −30 min, with NO check-in that day = the no-show laundering the gate
    blocks. Catches any path around the button (pre-start same-day requests are fine).
    Only judges requests from AL_GATE_LAW_FROM onward (the law can't apply before the gate
    or before check-ins existed)."""
    from datetime import timezone as _tz, timedelta as _tdelta
    pp = _tz(_tdelta(hours=7))
    checked = {(s["staff_id"], str(s["shift_date"]))
               for s in sessions if s.get("checked_in_at")}
    out = []
    for r in requests:
        if r.get("status") in ("rejected", "cancelled") or not r.get("created_at"):
            continue
        days = json.loads(r.get("days") or "[]")
        cd = r["created_at"].astimezone(pp)
        ciso = cd.date().isoformat()
        if ciso < AL_GATE_LAW_FROM or ciso not in days:
            continue
        ws = _hhmm_min((staff.get(r["staff_id"]) or {}).get("work_start"))
        if ws is None:
            continue
        if (cd.hour * 60 + cd.minute) < ws - 30:
            continue                      # asked well before the shift — legitimate same-day
        if (r["staff_id"], ciso) not in checked:
            out.append("AL-GATE: %s req #%s asked for SAME-DAY AL at %s (shift starts %02d:%02d) "
                       "with NO check-in that day — gate bypass / laundering symptom"
                       % (_nm(staff, r["staff_id"]), r["id"], cd.strftime("%H:%M"),
                          ws // 60, ws % 60))
    return out


def v_staff_sanity(staff_rows: list[dict]) -> list[str]:
    out = []
    for s in staff_rows:
        if s.get("status") != "active" or (s.get("org") or "").upper() != "TWB":
            continue
        if s["canonical_name"] == "Tyty":
            continue
        nm = (s.get("call_name") or s["canonical_name"]).upper()
        al = s.get("al_left")
        if al is not None and (float(al) < -10 or float(al) > 30):
            out.append("STAFF: %s AL balance %.1f looks wrong (expected −10..30)" % (nm, float(al)))
        if not s.get("work_start") or not s.get("work_end"):
            out.append("STAFF: %s has NO shift times — the check-in scheduler skips them entirely"
                       % nm)
    return out


# ───────────────────────────── DB runner ─────────────────────────────

def run_audit(today: date | None = None, test_rows: bool | None = None) -> tuple[list[str], dict]:
    """Run every invariant. test_rows: None = follow the current mode (test rows in test mode,
    real rows live — the /audit command); True/False = explicit (the daily auto-audit passes
    False so it ALWAYS checks the real ledger, even if the owner left test mode on).
    Returns (problems, stats). Each problem string is self-contained for pasting to Claude."""
    from shared.database import _db, _ATT_TEST, staff_all
    today = today or date.today()
    flag = _ATT_TEST if test_rows is None else test_rows
    staff = {s["id"]: s for s in staff_all(None)}

    def q(cur, sql, args=()):
        cur.execute(sql, args)
        return [dict(r) for r in cur.fetchall()]

    with _db() as conn:
        with conn.cursor() as cur:
            debts = q(cur, "SELECT * FROM payback_debts WHERE is_test=%s", (flag,))
            als = q(cur, "SELECT * FROM al_requests WHERE is_test=%s", (flag,))
            scs = q(cur, "SELECT * FROM shift_changes WHERE is_test=%s", (flag,))
            sess = q(cur, "SELECT * FROM attendance_sessions WHERE is_test=%s", (flag,))
            banks = q(cur, "SELECT * FROM ot_bank")          # no is_test: test never mutates it
            nos = q(cur, "SELECT * FROM no_show_records WHERE is_test=%s", (flag,))
            books = q(cur, "SELECT * FROM payback_bookings WHERE is_test=%s", (flag,))
            swaps = q(cur, "SELECT * FROM dayoff_swaps WHERE is_test=%s", (flag,))
            pevents = q(cur, "SELECT * FROM points_events WHERE is_test=%s", (flag,))

    problems = (v_payback(debts, staff)
                + v_al(als, staff, today)
                + v_shift_changes(scs, staff, today)
                + v_sessions(sess, staff, today)
                + v_ot_bank(banks, staff)
                + v_noshow_vs_sessions(nos, sess, staff)
                + v_bookings(books, {d["id"]: d for d in debts}, staff, today)
                + v_swaps(swaps, staff, today)
                + v_late_points(sess, pevents, staff)
                + v_al_same_day_gate(als, sess, staff)
                + v_staff_sanity(list(staff.values())))
    stats = {"payback": len(debts), "AL": len(als), "shift-changes": len(scs),
             "sessions": len(sess), "OT banks": len(banks), "no-shows": len(nos),
             "bookings": len(books), "swaps": len(swaps), "point-events": len(pevents)}
    return problems, stats
