"""core.till — POS shift / cash-drawer money model (harvested from POSBusiness `shift_service`, adapted to our
cash-only sales log, re-derived + re-tested from scratch). HIGH-RISK money → State-Integrity Laws:

  • S3 atomic claim   — at most ONE open shift per org (partial-unique index `uq_one_open_shift`); a 2nd open is
                        rejected by the DB, not by a check-then-write race.
  • S2 idempotent     — close flips status FIRST (UPDATE … WHERE status='open' RETURNING); a 2nd close → already_closed.
  • S4 shown = true   — expected_cash is computed from the real cash events + cash sales, not stored/guessed.
  • close is final    — no reopen in v1 (matches POSBusiness).

expected_cash = opening_float + cash_sales − drops − payouts − refunds.
Every shift open/close and cash event is written to the tamper-evident audit chain (core.audit).
"""
from decimal import Decimal

import psycopg2

from shared.database import _db
from core import audit

VARIANCE_REASON_THRESHOLD = Decimal("2.00")          # |variance| ≥ this needs a typed reason before close
_USER_EVENTS = {"drop", "payout", "refund", "no_sale"}


def _f(x):
    return float(x) if x is not None else 0.0


def current_shift(org_id):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT shift_id, who, opened_at, opening_float, status FROM core_shifts "
                        "WHERE org_id=%s AND status='open'", (org_id,))
            r = cur.fetchone()
    return dict(r) if r else None


def open_shift(org_id, who=None, opening_float=0):
    """Open a shift. ATOMIC: the partial-unique index rejects a 2nd open shift (not a check-then-write race).
    Returns (shift|None, error)."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO core_shifts (org_id, who, opening_float, status) "
                            "VALUES (%s,%s,%s,'open') RETURNING shift_id", (org_id, who, opening_float or 0))
                sid = cur.fetchone()["shift_id"]
                cur.execute("INSERT INTO core_cash_events (org_id, shift_id, type, amount) "
                            "VALUES (%s,%s,'open',%s)", (org_id, sid, opening_float or 0))
    except psycopg2.errors.UniqueViolation:
        return None, "already_open"
    audit.write(org_id, who, "shift.opened", "shift", str(sid), {"opening_float": str(opening_float or 0)})
    return current_shift(org_id), None


def cash_event(org_id, event_type, amount, note=None):
    """Record a mid-shift drawer event (drop/payout/refund/no_sale) on the open shift. Returns (event_id|None, err)."""
    if event_type not in _USER_EVENTS:
        return None, "bad_event_type"
    s = current_shift(org_id)
    if not s:
        return None, "no_open_shift"
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_cash_events (org_id, shift_id, type, amount, note) "
                        "VALUES (%s,%s,%s,%s,%s) RETURNING event_id",
                        (org_id, s["shift_id"], event_type, amount, note))
            eid = cur.fetchone()["event_id"]
    audit.write(org_id, s["who"], "cash_drawer.event", "cash_event", str(eid),
                {"type": event_type, "amount": str(amount), "note": note})
    return eid, None


def _financials(org_id, shift_id) -> dict:
    """The numbers for a shift's summary / Z-report (read-only). expected_cash + sales + drawer movements."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT opening_float, opened_at, closed_at, who FROM core_shifts "
                        "WHERE org_id=%s AND shift_id=%s", (org_id, shift_id))
            sh = cur.fetchone()
            cur.execute("SELECT COALESCE(SUM(qty*unit_price),0) g, COUNT(*) n FROM core_sales "
                        "WHERE org_id=%s AND shift_id=%s", (org_id, shift_id))
            r = cur.fetchone()
            cur.execute("SELECT type, COALESCE(SUM(amount),0) s, COUNT(*) c FROM core_cash_events "
                        "WHERE org_id=%s AND shift_id=%s GROUP BY type", (org_id, shift_id))
            ev = {row["type"]: (_f(row["s"]), row["c"]) for row in cur.fetchall()}
    of = _f(sh["opening_float"])
    cash_sales = _f(r["g"])
    drops, payouts, refunds = ev.get("drop", (0, 0))[0], ev.get("payout", (0, 0))[0], ev.get("refund", (0, 0))[0]
    expected = of + cash_sales - drops - payouts - refunds
    return {"shift_id": shift_id, "who": sh["who"], "opened_at": sh["opened_at"], "closed_at": sh["closed_at"],
            "opening_float": of, "cash_sales": cash_sales, "net_sales": cash_sales, "order_count": r["n"],
            "drops": drops, "payouts": payouts, "refunds": refunds, "no_sale_count": ev.get("no_sale", (0, 0))[1],
            "net_after_refunds": cash_sales - refunds, "expected_cash": expected}


def shift_summary(org_id):
    """Live numbers for the open shift (or None)."""
    s = current_shift(org_id)
    return _financials(org_id, s["shift_id"]) if s else None


def zreport(org_id, shift_id):
    """Full Z-report for any shift (incl. the stored counted_cash/variance/note for a closed one)."""
    z = _financials(org_id, shift_id)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT counted_cash, variance, note, status FROM core_shifts "
                        "WHERE org_id=%s AND shift_id=%s", (org_id, shift_id))
            r = cur.fetchone()
    if r:
        z.update({"counted_cash": _f(r["counted_cash"]), "variance": _f(r["variance"]),
                  "note": r["note"], "status": r["status"]})
    return z


def close_shift(org_id, counted_cash, note=None):
    """Close the open shift: variance-reason gate, then flip status FIRST (S2 idempotent), record the close cash
    event, audit, and return the Z-report. Returns (zreport|None, error). error may be a dict
    {code:'variance_reason_required', variance, threshold, expected_cash}."""
    s = current_shift(org_id)
    if not s:
        return None, "no_open_shift"
    sid = s["shift_id"]
    fin = _financials(org_id, sid)
    counted = _f(counted_cash)
    variance = round(counted - fin["expected_cash"], 2)
    if abs(variance) >= float(VARIANCE_REASON_THRESHOLD) and not (note or "").strip():
        return None, {"code": "variance_reason_required", "variance": variance,
                      "threshold": float(VARIANCE_REASON_THRESHOLD), "expected_cash": round(fin["expected_cash"], 2)}
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_shifts SET status='closed', closed_at=NOW(), counted_cash=%s, "
                        "expected_cash=%s, variance=%s, note=%s WHERE org_id=%s AND shift_id=%s AND status='open' "
                        "RETURNING shift_id", (counted, round(fin["expected_cash"], 2), variance, note, org_id, sid))
            if cur.fetchone() is None:
                return None, "already_closed"                # a concurrent close won — idempotent, not double-counted
            cur.execute("INSERT INTO core_cash_events (org_id, shift_id, type, amount, note) "
                        "VALUES (%s,%s,'close',%s,%s)", (org_id, sid, counted, note))
    audit.write(org_id, s["who"], "shift.closed", "shift", str(sid),
                {"counted_cash": str(counted), "expected_cash": str(round(fin["expected_cash"], 2)),
                 "variance": str(variance)})
    z = dict(fin)
    z.update({"counted_cash": counted, "variance": variance, "note": note})
    return z, None
