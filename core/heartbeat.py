"""core.heartbeat — self-describing JOB/CRON liveness (observability law, 2026-07-02).

A dead checker is the ultimate dead-end: the 2026-06-11 incident (cron daemon inactive, the collection
watchdog had NEVER run, found only by manual inspection) proved nothing watches whether the scheduled
things themselves fire. Every scheduled thing — a gm job_queue job, a server cron script, a service
main-loop — now writes ONE row per (org, job) via beat(): last_run on start, last_ok on success,
last_err on failure, carrying its OWN expected_gap_min (the max healthy silence, slack included). The
staleness detector (core.sentinel.detect_stale_heartbeats) therefore needs NO separate registry that
can drift: a row that stops beating past its own declared gap alarms ("silent"); a row that keeps
running but stops succeeding alarms ("failing").

Cross-process mutual watch by design: the 1-minute collection-watchdog cron beats from OUTSIDE the gm
process, so the gm sweep doubles as a cron-DAEMON liveness check (~10 min to alarm), while the daily
morning report (a cron) re-surfaces sink alarms if gm itself goes quiet. Writes are BEST-EFFORT — a
heartbeat must never break the job it measures.
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db

logger = logging.getLogger(__name__)

_TZ = "Asia/Phnom_Penh"


def _now() -> datetime:
    return datetime.now(ZoneInfo(_TZ))


def init_heartbeats_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_job_heartbeats (
                    org_id           TEXT NOT NULL,
                    job              TEXT NOT NULL,
                    expected_gap_min INTEGER NOT NULL,
                    last_run         TIMESTAMPTZ,
                    last_ok          TIMESTAMPTZ,
                    last_err         TEXT,
                    err_at           TIMESTAMPTZ,
                    note             TEXT,
                    PRIMARY KEY (org_id, job)
                )
            """)


def beat(org_id: str, job: str, expected_gap_min: int, phase: str = "ok", err=None) -> None:
    """Record a liveness tick. phase: 'start' (the job began) | 'ok' (it finished clean — implies it
    ran) | 'err' (it ran and failed; pass err). BEST-EFFORT — never raises into the job it measures."""
    try:
        now = _now()
        sets = {"expected_gap_min": expected_gap_min, "last_run": now}
        if phase == "ok":
            sets["last_ok"] = now
        elif phase == "err":
            sets["last_err"] = str(err)[:500] if err else "unknown"
            sets["err_at"] = now
        cols = ", ".join(sets)
        upd = ", ".join("%s=EXCLUDED.%s" % (k, k) for k in sets)
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO core_job_heartbeats (org_id, job, %s) VALUES (%%s, %%s, %s) "
                    "ON CONFLICT (org_id, job) DO UPDATE SET %s" % (cols, ", ".join(["%s"] * len(sets)), upd),
                    (org_id, job, *sets.values()))
    except Exception:
        logger.exception("heartbeat.beat failed (non-fatal): %s/%s", org_id, job)


def stale(org_id: str, now: datetime = None) -> list:
    """Every unhealthy heartbeat for an org — READ-ONLY, for the sentinel detector.
    'silent'  = hasn't run within its own expected_gap_min (job/cron/daemon dead or unscheduled).
    'failing' = still running, but not SUCCEEDING: a first run hung >10 min with no ok yet, or the
                last success is older than the gap while runs continue (an err/crash loop).
    A start-beat sampled seconds before its ok-beat must NOT flag — hence the 10-min hang floor.
    Returns [{job, kind, overdue_min, detail}]."""
    now = now or _now()
    out = []
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM core_job_heartbeats WHERE org_id=%s", (org_id,))
            rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        gap = timedelta(minutes=r["expected_gap_min"])
        last_run, last_ok = r.get("last_run"), r.get("last_ok")
        if last_run is None or (now - last_run) > gap:
            over = None if last_run is None else int((now - last_run - gap).total_seconds() // 60)
            out.append({"job": r["job"], "kind": "silent", "overdue_min": over,
                        "detail": "no run for >%dmin (last: %s)" % (r["expected_gap_min"],
                                                                    last_run.strftime("%d/%m %H:%M") if last_run else "never")})
        elif ((last_ok is None and (now - last_run) > timedelta(minutes=10))
              or (last_ok is not None and (now - last_ok) > gap and last_run > last_ok)):
            out.append({"job": r["job"], "kind": "failing", "overdue_min": None,
                        "detail": "runs but hasn't succeeded in >%dmin — last_err: %s"
                                  % (r["expected_gap_min"], (r.get("last_err") or "none")[:160])})
    return out
