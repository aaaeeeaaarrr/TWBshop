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


def detect_flip_divergence(org_id: str, now: datetime) -> list:
    """PROACTIVE: a path that's been FLIPPED to core (authoritative) but is starting to disagree with the
    old engine — alarm EARLY, before the auto-revert threshold trips, so a misbehaving cut-over is caught
    the moment it wobbles (not only once it un-flips itself). No-op while no flip is active (the default)."""
    try:
        from core import flip
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT path FROM core_flip WHERE org_id=%s AND authoritative=TRUE", (org_id,))
                paths = [r["path"] for r in cur.fetchall()]
        out = []
        for p in paths:
            total, dis = flip.recent_divergence(org_id, p)
            if dis > 0:
                sev = CRITICAL if flip.should_auto_revert(total, dis) else WARN
                out.append(_alarm("flip", "%s:%s" % (org_id, p), sev,
                                  "core is authoritative for '%s' but diverging from the old engine (%d/%d) "
                                  "— review before/at auto-revert" % (p, dis, total)))
        return out
    except Exception:
        return []   # no flip table / none authoritative → nothing to watch (flip is inert by default)


def detect_config_health(org_id: str, now: datetime) -> list:
    """PROACTIVE: a dangerous CONFIG (a foot-gun setting) flagged BEFORE it produces a wrong verdict or
    payroll — reuses core.health.config_health, routing only the 'warn' (likely-wrong) items, not the 'info'
    heads-up. The dashboard's tweakability lets a client set a bad value; this catches it via the sink (→
    owner + Claude), not only on the /health page they might never open."""
    try:
        from core.health import config_health
        return [_alarm("config", "%s:%s" % (org_id, msg[:48]), WARN, msg)
                for level, msg in config_health(org_id) if level == "warn"]
    except Exception:
        return []


def detect_undelivered_alarms(org_id: str, now: datetime) -> list:
    """OBSERVABILITY LAW: an alarm written to the durable sink whose owner-DM never landed (delivered=FALSE)
    is a message shouting into a void — re-raise it within the half-hour, not at the next 08:00 digest.
    CRITICAL if any of them is a money alarm."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) n, count(*) FILTER (WHERE severity='money') m FROM gm_alarms "
                        "WHERE delivered=FALSE AND acked=FALSE AND is_test=FALSE "
                        "AND at < %s AND at > %s",
                        (now - timedelta(minutes=15), now - timedelta(days=7)))
            r = cur.fetchone()
    if not r["n"]:
        return []
    sev = CRITICAL if r["m"] else WARN
    return [_alarm("alarm_delivery", org_id, sev,
                   "%d alarm(s) in the sink were never delivered to the owner (%d money) — "
                   "read them: python scripts/alarms.py --open" % (r["n"], r["m"]))]


def detect_stale_heartbeats(org_id: str, now: datetime) -> list:
    """OBSERVABILITY LAW: a dead checker is the ultimate dead-end (the 2026-06-11 cron-daemon incident).
    Every scheduled job/cron/service-loop beats core_job_heartbeats with its OWN expected gap; anything
    silent past its gap, or running-but-failing, alarms here. A silent 'cron:*' job is CRITICAL — the
    cron DAEMON itself is likely down, so every other cron is too."""
    from core import heartbeat
    out = []
    for h in heartbeat.stale(org_id, now):
        sev = CRITICAL if (h["kind"] == "silent" and h["job"].startswith("cron:")) else WARN
        out.append(_alarm("heartbeat", "%s:%s" % (org_id, h["job"]), sev,
                          "job '%s' %s — %s" % (h["job"], h["kind"], h["detail"]), h.get("overdue_min")))
    return out


def detect_stuck_sends(org_id: str, now: datetime) -> list:
    """OBSERVABILITY LAW: a proactive send that never completed — an 'intent' ledger row with no outcome
    (the process died mid-send) or a 'failed' row (every retry lost). Attempted ≠ delivered."""
    from core import sends
    out = []
    for s in sends.stuck(org_id, now):
        detail = ("send #%s (%s/%s → %s) stuck at 'intent' — the sender died mid-send"
                  % (s["id"], s["channel"], s["kind"], s["target"])) if s["status"] == "intent" else (
                  "send #%s (%s/%s → %s) failed after retries: %s"
                  % (s["id"], s["channel"], s["kind"], s["target"], (s.get("err") or "?")[:120]))
        out.append(_alarm("sends", "%s:%s" % (org_id, s["id"]), WARN, detail))
    return out


def detect_silent_flip_revert(org_id: str, now: datetime) -> list:
    """BELT for the cut-over net: an auto-revert flips authority off and expects its CALLER to alarm —
    a future caller that forgets leaves the revert a silent DB-only event (and detect_flip_divergence
    stops watching once authoritative=FALSE). Any recent auto-revert alarms here regardless of caller."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT path, reason, updated_at FROM core_flip "
                            "WHERE org_id=%s AND authoritative=FALSE AND reason LIKE 'auto-revert%%' "
                            "AND updated_at > %s", (org_id, now - timedelta(hours=48)))
                rows = cur.fetchall()
        return [_alarm("flip", "%s:%s:reverted" % (org_id, r["path"]), CRITICAL,
                       "path '%s' AUTO-REVERTED to the old engine (%s) — review the divergence before "
                       "re-flipping" % (r["path"], r["reason"])) for r in rows]
    except Exception:
        return []   # no flip table yet → nothing to watch


def detect_broken_flows(org_id: str, now: datetime) -> list:
    """OBSERVABILITY LAW, flow tier (owner 2026-07-03): every step of every ladder — across ANY tenant
    config combination — must reach its next destination or a legitimate terminal within its SLA.
    Declarative rules live in core.flowcheck (one line per flow, swept for every org); this bridges
    them onto every existing cadence. A stuck shadow-mismatch (never `reconciled`) is WARN-with-teeth:
    it is the platform's own accuracy signal rotting."""
    from core import flowcheck
    return [_alarm("flow:%s" % f["flow"], "%s:%s" % (org_id, f["key"]),
                   f.get("severity", WARN), f["detail"], f.get("age_min"))
            for f in flowcheck.check(org_id, now)]


# Registered flows — add one tuple per flow as the platform grows (reverse-shadow divergence, stuck payback,
# stuck approval, missed job, invariant breaches, …). Detectors stay pure + read-only. Prefer a DECLARATIVE
# rule in core.flowcheck.RULES for anything shaped "step A must reach step B within T" — it multi-tenants
# for free; hand-rolled detectors are for the bespoke rest.
DETECTORS = [
    ("shadow_stalled", detect_shadow_stalled),
    ("malformed_checkin", detect_malformed_checkin),
    ("flip_divergence", detect_flip_divergence),
    ("config_health", detect_config_health),
    ("undelivered_alarms", detect_undelivered_alarms),
    ("stale_heartbeats", detect_stale_heartbeats),
    ("stuck_sends", detect_stuck_sends),
    ("silent_flip_revert", detect_silent_flip_revert),
    ("broken_flows", detect_broken_flows),
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
