"""core.sentinel — the universal LIVENESS monitor: an alarm for ANYTHING that didn't reach its next ladder/step.

A FLOW is a multi-step process with an SLA (how long an instance may sit at a step before it's 'stuck'). Each flow
registers a DETECTOR — a pure READ-ONLY function (org_id, now) -> list[alarm] that finds stuck/abnormal instances.
`sweep(org_id)` runs them all and returns the alarms, criticals first (the caller DMs / logs / heals — the sentinel
only DETECTS). Org-scoped, so it works identically for TWBshop, every parallel shadow, and every client. Add a
detector per flow as the platform grows; the first ones guard the platform's own data + the SAFETY NET ITSELF (a
shadow that silently stops = flying blind, the worst case to miss).

This is the 'never silently swallow' law of the self-healing design → docs/SELF_HEALING_AND_SHADOW_PROGRAM.md.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db

_TZ = "Asia/Phnom_Penh"
CRITICAL, WARN, INFO = "critical", "warn", "info"


def _now(tz: str = _TZ) -> datetime:
    return datetime.now(ZoneInfo(tz))


def _alarm(flow: str, key, severity: str, detail: str, age_min=None) -> dict:
    return {"flow": flow, "key": str(key), "severity": severity, "detail": detail, "age_min": age_min}


# ── Detectors — each (org_id, now) -> list[alarm]; pure + read-only ───────────
def detect_shadow_stalled(org_id: str, now: datetime) -> list:
    """META-SAFETY: if the shadow net is ON and real check-ins are still flowing but it has STOPPED recording
    comparisons, the net has gone dark — flying blind. The single most important thing to alarm. Critical."""
    try:
        from shared.database import gm_get_state
        if gm_get_state("shadow_run") != "on":
            return []
    except Exception:
        return []
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT max(at) m FROM attendance_events WHERE org_id=%s AND type='checked_in'", (org_id,))
            last_event = cur.fetchone()["m"]
            cur.execute("SELECT max(at) m FROM shadow_comparisons WHERE org_id=%s AND kind='checkin'", (org_id,))
            last_cmp = cur.fetchone()["m"]
    if not last_event or (now - last_event) > timedelta(hours=24):
        return []                                   # a quiet shop legitimately has no recent events → nothing to judge
    if last_cmp is None or (last_event - last_cmp) > timedelta(hours=6):
        gap = None if last_cmp is None else int((last_event - last_cmp).total_seconds() // 60)
        return [_alarm("shadow", org_id, CRITICAL,
                       "shadow is ON + check-ins are flowing but comparisons stopped — the safety net is dark", gap)]
    return []


def detect_malformed_checkin(org_id: str, now: datetime) -> list:
    """Data integrity: a recorded check-in with no verdict state in its detail (should be impossible)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) n FROM attendance_events WHERE org_id=%s AND type='checked_in' "
                        "AND (detail->>'state') IS NULL AND at > %s", (org_id, now - timedelta(days=2)))
            n = cur.fetchone()["n"]
    return [_alarm("attendance", org_id, WARN, "%d recent check-in event(s) missing a verdict state" % n)] if n else []


# Registered flows — add one tuple per flow as the platform grows (reverse-shadow divergence, stuck payback,
# stuck approval, missed job, invariant breaches, …). Detectors stay pure + read-only.
DETECTORS = [
    ("shadow_stalled", detect_shadow_stalled),
    ("malformed_checkin", detect_malformed_checkin),
]


def sweep(org_id: str, now: datetime = None) -> list:
    """Run every detector for an org → all alarms, criticals first. READ-ONLY. A detector that ITSELF errors is
    reported (never silently swallowed) — the monitor must not go dark on its own bug."""
    now = now or _now()
    out = []
    for name, fn in DETECTORS:
        try:
            out.extend(fn(org_id, now) or [])
        except Exception as exc:
            out.append(_alarm("sentinel", name, WARN, "detector '%s' errored: %s" % (name, type(exc).__name__)))
    order = {CRITICAL: 0, WARN: 1, INFO: 2}
    out.sort(key=lambda a: order.get(a["severity"], 3))
    return out


def summary_line(alarms: list) -> str:
    """A one-line digest for a DM / log: '2 critical, 1 warn' or 'all clear'."""
    if not alarms:
        return "✅ all clear"
    counts = {}
    for a in alarms:
        counts[a["severity"]] = counts.get(a["severity"], 0) + 1
    return ", ".join("%d %s" % (counts[s], s) for s in (CRITICAL, WARN, INFO) if counts.get(s))
