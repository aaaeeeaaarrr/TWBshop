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
MAX_DAY_TOTAL_MIN = 900   # 15h — one day's total work time cap (owner rule, = payback.MAX_DAY_TOTAL_MIN)
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
        st = r["status"]
        # stale-pending applies to BOTH deduction models
        if st == "pending" and r.get("created_at"):
            age = (today - r["created_at"].date()).days
            if age >= STALE_PENDING_DAYS:
                out.append("AL: %s req #%s PENDING for %d days — approval ladder stuck?"
                           % (nm, r["id"], age))
        dmap = r.get("deducted_map")   # dict on deduct-at-approval rows; None on legacy / never-approved
        if dmap is not None:
            # NEW model: the frozen per-day map IS the truth — mechanical, no recompute (no false
            # positives). approved ⇒ keys == days (0 for day-off/absent/PH-comp); a refunded/rejected
            # request must hold no leftover map.
            if st == "approved" and set(dmap.keys()) != set(days):
                out.append("AL: %s req #%s approved but deducted_map keys %s != days %s"
                           % (nm, r["id"], sorted(dmap), sorted(days)))
            if st in ("rejected", "cancelled") and dmap:
                out.append("AL: %s req #%s is %s but deducted_map still holds %s (refund missing?)"
                           % (nm, r["id"], st, dmap))
            continue
        # LEGACY model: the daily job deducts as dates pass (deducted_days list)
        ded = json.loads(r.get("deducted_days") or "[]")
        bad = [d for d in ded if d not in days]
        if bad:
            out.append("AL: %s req #%s deducted days not in the request: %s" % (nm, r["id"], bad))
        is_ph = (r.get("reason") or "").upper().startswith("PH")   # PH-comp is NEVER deducted
        if st == "approved" and r.get("kind") == "days" and not is_ph:
            missed = [d for d in days if d < today.isoformat() and d not in ded]
            if missed:
                out.append("AL: %s req #%s approved, dates passed but NOT deducted: %s"
                           % (nm, r["id"], missed))
        if st in ("rejected", "cancelled") and ded:
            out.append("AL: %s req #%s is %s but has deductions %s (refund missing?)"
                       % (nm, r["id"], st, ded))
    return out


def v_special(leaves: list[dict], staff: dict) -> list[str]:
    """Special leave (marriage / death / birth): status in a known domain, and every row carries a
    frozen deducted_amount (so the grant has a clean refundable inverse and is auditable)."""
    out = []
    for r in leaves:
        nm = _nm(staff, r["staff_id"])
        st = r.get("status")
        if st not in ("booked", "cancelled"):
            out.append("SPECIAL: %s leave #%s unknown status '%s'" % (nm, r["id"], st))
        if r.get("deducted_amount") is None:
            out.append("SPECIAL: %s leave #%s has no frozen deducted_amount — not refundable/auditable"
                       % (nm, r["id"]))
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
        if st in ("approved", "done") and r.get("normal_len") is None:
            out.append("OT: %s change #%s %s without normal_len — settle can't compute OT"
                       % (nm, r["id"], st))   # normal_len=0 is VALID (day-off payback window)
        if (st in ("approved", "done") and r.get("start_min") is not None
                and r.get("end_min") is not None
                and int(r["end_min"]) - int(r["start_min"]) > MAX_DAY_TOTAL_MIN):
            out.append("OT: %s change #%s spans %dmin — one day's total work time caps at 15h "
                       "(owner rule)" % (nm, r["id"], int(r["end_min"]) - int(r["start_min"])))
    return out


def v_pb_overbook(debts: list[dict], changes: list[dict], staff: dict) -> list[str]:
    """Owner law (Jun 11): payback-slot redefines may never out-size the debt they repay —
    over-booking was the book-and-book-again OT mint. Per staff: (a) the summed extension of
    APPROVED 'payback slot' redefines must fit inside the open balance; (b) a settled ('done')
    payback-slot redefine must have banked 0 (a slot repays debt only, never mints OT)."""
    out = []
    open_bal: dict[int, int] = {}
    for d in debts:
        if d.get("status") == "open":
            open_bal[d["staff_id"]] = (open_bal.get(d["staff_id"], 0)
                                       + int(d["minutes_owed"]) - int(d["minutes_paid"]))
    ext_sum: dict[int, int] = {}
    for c in changes:
        if c.get("reason") != "payback slot":
            continue
        if (c.get("status") == "done" and int(c.get("ot_banked") or 0) > 0):
            out.append("PB-MINT: %s payback-slot redefine #%s banked %smin OT — payback slots "
                       "must never mint OT" % (_nm(staff, c["staff_id"]), c["id"], c["ot_banked"]))
        if c.get("status") != "approved" or c.get("start_min") is None or c.get("end_min") is None:
            continue
        ext = max(0, int(c["end_min"]) - int(c["start_min"]) - int(c.get("normal_len") or 0))
        ext_sum[c["staff_id"]] = ext_sum.get(c["staff_id"], 0) + ext
    for sid, tot in ext_sum.items():
        bal = open_bal.get(sid, 0)
        if tot > bal:
            out.append("PB-OVERBOOK: %s has %dmin of approved payback-slot bookings vs %dmin "
                       "open debt — over-booked (the surplus would become unearned OT)"
                       % (_nm(staff, sid), tot, bal))
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


PB_UNIFY_LAW_FROM = "2026-06-11"   # the slot→redefine unification's birthday (payback AND rest)


def v_booking_redefine_pair(bookings: list[dict], changes: list[dict], staff: dict,
                            buybacks: list[dict] | None = None) -> list[str]:
    """The unification's law (Jun 11): a booked slot and its auto-approved redefine are ONE thing
    — each side must have the other. Covers BOTH currencies: payback slots ('payback slot'
    redefines) and OT-rest buybacks ('OT rest' redefines). A booking with no redefine = the dead
    mini-shift bug reborn (no prompts / no credit / false-late on rest); a tagged redefine with
    no booking = orphan. Judged from the unification's birthday onward."""
    redef_dates = {(c["staff_id"], str(c["when_date"]))
                   for c in changes if c.get("status") in ("approved", "done")}
    booked_dates = {(b["staff_id"], str(b["slot_date"]))
                    for b in bookings if b.get("status") in ("booked", "done")}
    rest_dates = {(b["staff_id"], str(b["slot_date"]))
                  for b in (buybacks or []) if b.get("status") in ("booked", "taken")}
    out = []
    for b in bookings:
        if b.get("status") != "booked" or str(b.get("slot_date")) < PB_UNIFY_LAW_FROM:
            continue
        if (b["staff_id"], str(b["slot_date"])) not in redef_dates:
            out.append("PB-PAIR: %s booking #%s (%s) has NO shift-redefine — the slot won't "
                       "fire prompts or credit the debt (dead mini-shift bug)"
                       % (_nm(staff, b["staff_id"]), b["id"], b["slot_date"]))
    for b in (buybacks or []):
        if b.get("status") != "booked" or str(b.get("slot_date")) < PB_UNIFY_LAW_FROM:
            continue
        if (b["staff_id"], str(b["slot_date"])) not in redef_dates:
            out.append("REST-PAIR: %s OT-rest #%s (%s) has NO shift-redefine — attendance would "
                       "mark them LATE for taking earned rest"
                       % (_nm(staff, b["staff_id"]), b["id"], b["slot_date"]))
    for c in changes:
        if c.get("status") != "approved" or str(c.get("when_date")) < PB_UNIFY_LAW_FROM:
            continue
        key = (c["staff_id"], str(c["when_date"]))
        if c.get("reason") == "payback slot" and key not in booked_dates:
            out.append("PB-PAIR: %s redefine #%s (%s) says 'payback slot' but NO booking exists "
                       "— orphan" % (_nm(staff, c["staff_id"]), c["id"], c["when_date"]))
        if c.get("reason") == "OT rest" and key not in rest_dates:
            out.append("REST-PAIR: %s redefine #%s (%s) says 'OT rest' but NO buyback exists — "
                       "orphan" % (_nm(staff, c["staff_id"]), c["id"], c["when_date"]))
    return out


def v_buybacks(buybacks: list[dict], staff: dict, today: date) -> list[str]:
    """OT-rest bookings: valid status, positive minutes, and never left 'booked' after the date
    passed (the settle marks them 'taken'; a stale one = the rest day never settled)."""
    out = []
    for b in buybacks:
        nm = _nm(staff, b["staff_id"])
        if b.get("status") not in ("booked", "taken"):
            out.append("REST: %s buyback #%s unknown status '%s'" % (nm, b["id"], b.get("status")))
        if int(b.get("minutes") or 0) <= 0:
            out.append("REST: %s buyback #%s has minutes=%s" % (nm, b["id"], b.get("minutes")))
        if (b.get("status") == "booked" and b.get("slot_date")
                and b["slot_date"] < today - timedelta(days=1)):
            out.append("REST: %s buyback #%s slot %s passed but still 'booked' (never settled)"
                       % (nm, b["id"], b["slot_date"]))
    return out


def v_sick(cases: list[dict], staff: dict, today: date | None = None) -> list[str]:
    """Sick cases: valid status (incl. 'extended' — the explain re-book), chain integrity (an
    'extended' case must have CREATED the next day's case), family pool overruns (>7/year), and
    — the explain ladder's new failure mode (owner, Jun 11) — a FAMILY case left 'open' after its
    date passed = the nudge was never answered (or 'explain' tapped but no reason ever typed)."""
    valid = {"open", "provisional", "papered", "cleared", "no_papers", "extended"}
    by_staff_dates = {}
    for c in cases:
        by_staff_dates.setdefault(c["staff_id"], set()).add(str(c.get("the_date")))
    out, fam_count = [], {}
    for c in cases:
        nm = _nm(staff, c["staff_id"])
        if c.get("status") not in valid:
            out.append("SICK: %s case #%s unknown status '%s'" % (nm, c["id"], c.get("status")))
        if c.get("status") == "extended":
            nxt = (date.fromisoformat(str(c["the_date"])) + timedelta(days=1)).isoformat()
            if nxt not in by_staff_dates.get(c["staff_id"], set()):
                out.append("SICK: %s case #%s 'extended' but NO case exists for %s — the one-tap "
                           "re-book never landed" % (nm, c["id"], nxt))
        if (today is not None and (c.get("who") or "me") != "me" and c.get("status") == "open"
                and str(c.get("the_date")) < (today - timedelta(days=1)).isoformat()):
            out.append("SICK: %s family case #%s (%s) still OPEN after its date — the night nudge "
                       "was never answered (explain tapped but no reason typed?)"
                       % (nm, c["id"], c.get("the_date")))
        if (c.get("who") or "me") != "me":
            k = (c["staff_id"], str(c.get("the_date"))[:4])
            fam_count[k] = fam_count.get(k, 0) + 1
    for (sid, yr), n in fam_count.items():
        if n > 7:
            out.append("SICK: %s has used %d family-sick days in %s (pool is 7)"
                       % (_nm(staff, sid), n, yr))
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


def v_exclusivity(als: list[dict], scs: list[dict], staff: dict, today: date) -> list[str]:
    """F14 exclusivity law (owner Jun 13): at most one approved leave/redefine may claim a staff-date.
    Flags the two UNAMBIGUOUS, harmful collisions only (so the daily auto-audit stays false-alarm-free):
      (a) the SAME calendar day approved by >1 AL request → double AL deduction;
      (b) an approved-AL day that ALSO carries an approved/done shift-change → 'on leave AND scheduled
          to work'.
    Two shift-changes on one date are NOT a collision (the redefine model: latest-per-date wins).
    Day-off SWAPS are deferred — their day-off semantics need their own pass before auditing here."""
    out = []
    al_day_reqs: dict = {}   # (sid, 'YYYY-MM-DD') -> [approved AL req ids claiming that day]
    for r in als:
        if r.get("status") == "approved":
            for d in json.loads(r.get("days") or "[]"):
                al_day_reqs.setdefault((r["staff_id"], str(d)), []).append(r["id"])
    for (sid, d), ids in sorted(al_day_reqs.items()):
        if len(ids) > 1:
            out.append("EXCL: %s has %d approved AL requests claiming the SAME day %s (#%s) — "
                       "double deduction" % (_nm(staff, sid), len(ids), d,
                                             ", #".join(str(i) for i in ids)))
    sc_days: dict = {}       # (sid, 'YYYY-MM-DD') -> [approved/done shift-change ids]
    for r in scs:
        if r.get("status") in ("approved", "done") and r.get("when_date"):
            sc_days.setdefault((r["staff_id"], str(r["when_date"])), []).append(r["id"])
    for (sid, d), ids in sorted(al_day_reqs.items()):
        if (sid, d) in sc_days:
            out.append("EXCL: %s is on approved AL for %s but also has an approved shift-change "
                       "(#%s) that day — on leave AND scheduled to work"
                       % (_nm(staff, sid), d, sc_days[(sid, d)][0]))
    return out


def v_one_active_redefine(scs: list[dict], staff: dict) -> list[str]:
    """At most ONE live (approved, not yet settled) shift-redefine per staff-date. More than one means a
    multi-writer clobber — a senior re-edit that didn't supersede, OR a senior redefine landing on a
    payback / OT-rest slot — which can shadow a booking pairing and trip the never-settled law. ('done'
    rows are settled history and don't count.)"""
    out = []
    by: dict = {}
    for r in scs:
        if r.get("status") == "approved" and r.get("when_date"):
            by.setdefault((r["staff_id"], str(r["when_date"])), []).append(r["id"])
    for (sid, d), ids in sorted(by.items()):
        if len(ids) > 1:
            out.append("REDEFINE: %s has %d live redefines on %s (#%s) — only one may be active; a "
                       "re-edit must supersede, and a senior redefine must not collide with a payback/"
                       "OT-rest slot" % (_nm(staff, sid), len(ids), d, ", #".join(str(i) for i in ids)))
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


def v_dead_taps(rows: list[tuple], today: date) -> list[str]:
    """Dead/expired button taps (recorded by the catch-all + the in-handler toasts, owner Jun 11):
    any taps today or yesterday = a button died somewhere — investigate the samples. This is the
    law that makes silent dead buttons VISIBLE (they write nothing else anywhere)."""
    import json as _json
    out = []
    floor = (today - timedelta(days=1)).isoformat()
    for key, val in rows:
        day = key.split(":", 1)[1] if ":" in key else ""
        if day < floor:
            continue
        try:
            rec = _json.loads(val or "{}")
        except Exception:
            continue
        if int(rec.get("n", 0)) > 0:
            out.append("UI: %d dead/expired button tap(s) on %s — samples: %s"
                       % (rec["n"], day, ", ".join(rec.get("samples", [])[:5]) or "?"))
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
            buybacks = q(cur, "SELECT * FROM ot_buyback WHERE is_test=%s", (flag,))
            sick = q(cur, "SELECT * FROM sick_cases WHERE is_test=%s", (flag,))
            specials = q(cur, "SELECT * FROM special_leaves WHERE is_test=%s", (flag,))
            cur.execute("SELECT key, value FROM gm_state WHERE key LIKE 'dead_taps:%%'")
            taps = [(r["key"], r["value"]) for r in cur.fetchall()]

    problems = (v_payback(debts, staff)
                + v_al(als, staff, today)
                + v_shift_changes(scs, staff, today)
                + v_sessions(sess, staff, today)
                + v_ot_bank(banks, staff)
                + v_noshow_vs_sessions(nos, sess, staff)
                + v_bookings(books, {d["id"]: d for d in debts}, staff, today)
                + v_booking_redefine_pair(books, scs, staff, buybacks)
                + v_pb_overbook(debts, scs, staff)
                + v_buybacks(buybacks, staff, today)
                + v_sick(sick, staff, today)
                + v_swaps(swaps, staff, today)
                + v_late_points(sess, pevents, staff)
                + v_al_same_day_gate(als, sess, staff)
                + v_exclusivity(als, scs, staff, today)
                + v_one_active_redefine(scs, staff)
                + v_special(specials, staff)
                + v_dead_taps(taps, today)
                + v_staff_sanity(list(staff.values())))
    stats = {"payback": len(debts), "AL": len(als), "shift-changes": len(scs),
             "sessions": len(sess), "OT banks": len(banks), "no-shows": len(nos),
             "bookings": len(books), "swaps": len(swaps), "point-events": len(pevents),
             "OT-rests": len(buybacks), "sick": len(sick), "special": len(specials)}
    return problems, stats
