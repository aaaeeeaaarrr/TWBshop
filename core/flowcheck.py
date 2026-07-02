"""core.flowcheck — the universal "did it reach its NEXT step?" engine (observability law, flow tier).

The owner's goal (2026-07-03): with hundreds of differently-configured tenants/shadowruns, EVERY step of
EVERY ladder must be verified to arrive at its next destination — or a legitimate terminal — within its
SLA, mechanically, per-org, with no per-tenant hand-rolled checker and no model cost. TWB's legacy
`gm_bot/audit.py` v_* checks do this hand-rolled and single-tenant; the platform needs it DECLARATIVE:
a RULE = {flow, what-stuck-means, an org-scoped read-only finder}. `core.sentinel.detect_broken_flows`
sweeps every rule for every org on the existing cadences (gm 30-min sweep · morning report · builder
monitor) — a new platform flow adds ONE rule here and is verified for every tenant forever.

First rules cover the platform's own live surfaces:
  • a core check-in whose shift never reached checked-out/closed (the step after checking in)
  • a LIVE shadow mismatch that never reached its terminal `reconciled` flag — a shadowrun log is
    itself a step that must arrive somewhere: understood/fixed/accepted, never rotting in a digest
  • an onboarding candidate staged but never confirmed/skipped (the discover→confirm ladder's step 2)
Rules stay pure + read-only; healing belongs to reapers/closers, alarming to the sentinel.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db

_TZ = "Asia/Phnom_Penh"


def _now() -> datetime:
    return datetime.now(ZoneInfo(_TZ))


def _stuck_sessions(org_id: str, now: datetime) -> list:
    """checked_in (older than 26h, within 7d) whose shift has NO checked_out — the next step never came.
    26h > any legal shift+OT span; pairs by shift_id (the UNIQUE(shift_id,type) session identity)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.shift_id, e.staff_id, e.at FROM attendance_events e
                WHERE e.org_id=%s AND e.type='checked_in' AND e.at < %s AND e.at > %s
                  AND NOT EXISTS (SELECT 1 FROM attendance_events o
                                  WHERE o.shift_id=e.shift_id AND o.type='checked_out')
                ORDER BY e.at LIMIT 20
            """, (org_id, now - timedelta(hours=26), now - timedelta(days=7)))
            rows = cur.fetchall()
    return [{"flow": "core_session", "key": "shift:%s" % r["shift_id"],
             "detail": "staff %s checked in %s but the shift never reached checked-out/closed"
                       % (r["staff_id"], r["at"].strftime("%d/%m %H:%M")),
             "age_min": int((now - r["at"]).total_seconds() // 60)} for r in rows]


def _unreconciled_mismatches(org_id: str, now: datetime) -> list:
    """A LIVE shadow mismatch older than 48h that never reached its terminal (`reconciled`) — the
    owner's law: every shadowrun log must arrive at understood/fixed/accepted, whatever the tenant
    config combination. 14d floor keeps ancient pre-law rows out."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, kind, staff_id, at FROM shadow_comparisons
                WHERE org_id=%s AND agree=FALSE AND reconciled=FALSE AND source='live'
                  AND at < %s AND at > %s
                ORDER BY id LIMIT 20
            """, (org_id, now - timedelta(hours=48), now - timedelta(days=14)))
            rows = cur.fetchall()
    return [{"flow": "shadow_mismatch", "key": "cmp:%s" % r["id"],
             "detail": "shadow %s mismatch #%s (staff %s, %s) unreconciled >48h — resolve it: fix the "
                       "engine, or mark reconciled with the reason"
                       % (r["kind"], r["id"], r["staff_id"], r["at"].strftime("%d/%m")),
             "age_min": int((now - r["at"]).total_seconds() // 60)} for r in rows]


def _stalled_candidates(org_id: str, now: datetime) -> list:
    """An onboarding candidate staged >7d ago still 'pending' — the discover→confirm ladder stalled
    (a real person the tenant saw but never confirmed or skipped)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tg_user_id, tg_name, seen_at FROM core_onboarding_candidates
                WHERE org_id=%s AND status='pending' AND seen_at < %s
                ORDER BY seen_at LIMIT 20
            """, (org_id, now - timedelta(days=7)))
            rows = cur.fetchall()
    return [{"flow": "onboarding_candidate", "key": "cand:%s" % r["tg_user_id"],
             "detail": "candidate '%s' staged %s still pending — confirm or skip them"
                       % (r.get("tg_name") or r["tg_user_id"], r["seen_at"].strftime("%d/%m")),
             "age_min": int((now - r["seen_at"]).total_seconds() // 60)} for r in rows]


# The registry — one line per flow; every rule runs for EVERY org. Finder: (org_id, now) -> list[dict].
RULES = [
    ("core_session", _stuck_sessions),
    ("shadow_mismatch", _unreconciled_mismatches),
    ("onboarding_candidate", _stalled_candidates),
]


def check(org_id: str, now: datetime = None) -> list:
    """Run every flow rule for an org → stuck instances. READ-ONLY. A rule that itself errors is
    reported (never swallowed) — same contract as the sentinel's detectors."""
    now = now or _now()
    out = []
    for name, fn in RULES:
        try:
            out.extend(fn(org_id, now) or [])
        except Exception as exc:
            out.append({"flow": "flowcheck", "key": name,
                        "detail": "rule '%s' errored: %s" % (name, type(exc).__name__), "age_min": None})
    return out
