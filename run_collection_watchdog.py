"""Dead-man watchdog for message collection (session 28 — the May 28/29 lesson).

Cron (server — EVERY MINUTE per the live crontab, verified 2026-07-02; an old copy of this docstring
said */30, which had drifted from reality):
  * * * * * cd /root/TWBshop && /root/venv/bin/python run_collection_watchdog.py >> logs/watchdog.log 2>&1
Its own 1-min heartbeat doubles as the cron-DAEMON liveness probe (observability law).

Alerts the OWNER on Telegram when:
  - the twbshop-listener service is not active, or
  - no new ops_messages row has landed for STALE_HOURS (the business talks 24/7 across
    3,600+ chats — hours of total silence means collection is dead, not the shop).
Throttled to one alert per ALERT_GAP_HOURS so a long outage doesn't spam.
Self-healing note: the listener backfills missed history on startup, so once it's
restarted after an alert, the gap closes itself.
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from shared.database import _db  # noqa: E402

STALE_HOURS = 3
ALERT_GAP_HOURS = 6
STATE_FILE = os.path.expanduser("~/.watchdog_last_alert")

# Per-chat freshness (session 28, owner: "watchdogs for stocks and comms too") —
# hours of silence that are suspicious for THAT chat's normal cadence.
CHAT_WATCH = [
    ("TWB REPORT", -5136886404, 26),
    ("Stock Checks", -1003952029131, 26),
    ("COMMS", None, 48),            # id filled from config below
    ("Supervisors", -4980513319, 96),
]


def _alert(text: str) -> None:
    last = None
    try:
        last = datetime.fromisoformat(open(STATE_FILE).read().strip())
    except Exception:
        pass
    if last and datetime.utcnow() - last < timedelta(hours=ALERT_GAP_HOURS):
        print("alert suppressed (throttle):", text)
        return
    # A "collection is down" alert is a BUILDER/system concern → route via the MONITOR bot, NOT the client
    # GM/retail bot (client/builder separation law). notify_monitor is a direct Bot API POST, so it still
    # delivers mid-outage even while the Monitor's own polling process is down — the same guarantee the
    # GM-token send had.
    from shared.monitor_notify import notify_monitor
    if not notify_monitor("🚨 COLLECTION WATCHDOG\n" + text):
        print("ALERT DELIVERY FAILED (Monitor):", text)
        return
    with open(STATE_FILE, "w") as f:
        f.write(datetime.utcnow().isoformat())
    print("alert sent (Monitor):", text)


def main() -> None:
    # OBSERVABILITY LAW (2026-07-02): this cron beats its own heartbeat — running every minute, it is
    # the cron-DAEMON liveness probe (the 2026-06-11 class: daemon inactive, watchdog never ran, found
    # by hand). If IT goes silent past its gap, the gm sentinel sweep alarms 'cron:*' as CRITICAL.
    try:
        from core.heartbeat import beat, init_heartbeats_db
        init_heartbeats_db()
        beat("twb", "cron:collection_watchdog", 10, phase="start")
    except Exception as e:
        print("heartbeat unavailable (non-fatal):", e)
    problems = []
    # twbshop-gm matters doubly: it is the ONLY recorder of Supervisors + Management
    # (owner decision: the listener account stays out of senior rooms — junior staff use it).
    # Bot API can't backfill history, so GM downtime there = permanent loss; detect fast.
    # (Full unit list per the 2026-07-02 dead-end audit: automations/wizard/retail had NO liveness
    # watcher at all. twbshop-b2b stays out — EXPECTED_INACTIVE while B2B is disabled.)
    for svc in ("twbshop-listener", "twbshop-gm", "twbshop-hire",
                "twbshop-retail", "twbshop-automations", "twbshop-wizard"):
        try:
            active = subprocess.run(["systemctl", "is-active", svc],
                                    capture_output=True, text=True).stdout.strip()
            if active != "active":
                problems.append("%s service is %s." % (svc, active or "unknown"))
        except Exception as e:
            print("service check failed:", e)

    def _age_hours(latest) -> float | None:
        if not latest:
            return None
        latest_dt = datetime.fromisoformat(str(latest).replace("Z", "+00:00"))
        return (datetime.utcnow() - latest_dt.replace(tzinfo=None)).total_seconds() / 3600

    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(sent_at) AS m FROM ops_messages")
                age_h = _age_hours((cur.fetchone() or {}).get("m"))
                if age_h is not None and age_h > STALE_HOURS:
                    problems.append("No messages recorded ANYWHERE for %.1f hours." % age_h)
                # per-chat cadence checks
                comms_id = (getattr(config, "COMMS_CHAT_ID", None)
                            or getattr(config, "COMMS_TRANSFERS_CHAT_ID", None))
                for label, cid, max_h in CHAT_WATCH:
                    cid = cid or (comms_id if label == "COMMS" else None)
                    if not cid:
                        continue
                    cur.execute("SELECT MAX(sent_at) AS m FROM ops_messages WHERE chat_id=%s", (cid,))
                    age = _age_hours((cur.fetchone() or {}).get("m"))
                    if age is not None and age > max_h:
                        problems.append("%s: silent for %.0f hours (normal cadence broken — "
                                        "collection problem or the group truly stopped)."
                                        % (label, age))
                # OBSERVABILITY LAW: out-of-process check on the gm brain's OWN watcher jobs — the one
                # class the in-process sentinel sweep can never see (gm service 'active' but its
                # JobQueue stalled → the sweep itself is what died). Kept narrow to these three so the
                # in-process sweep stays the alerter for everything else (no double alarms).
                try:
                    cur.execute("SELECT job, last_run, expected_gap_min FROM core_job_heartbeats "
                                "WHERE org_id='twb' AND job IN "
                                "('gm_sentinel_sweep','gm_live_watchdog','gm_checkin_scheduler')")
                    for r in cur.fetchall():
                        age_min = None if not r.get("last_run") else \
                            (datetime.utcnow() - r["last_run"].replace(tzinfo=None)).total_seconds() / 60
                        if age_min is not None and age_min > r["expected_gap_min"]:
                            problems.append("gm JOB '%s' silent %.0f min (service may be up but its "
                                            "scheduler is stalled — restart twbshop-gm)." % (r["job"], age_min))
                except Exception as e:
                    print("gm-job heartbeat check skipped:", e)
    except Exception as e:
        problems.append("Database check failed: %s" % e)

    if problems:
        # name the actual failing service(s) in the fix line — the 06-30 hire alert said "restart
        # twbshop-listener" while the dead service was hire (canned text; caught in the 07-02 audit)
        down = [p.split(" service", 1)[0] for p in problems if " service is " in p]
        fix = ("systemctl restart " + " ".join(down)) if down else "see the problem lines above"
        _alert("\n".join(problems) +
               "\n\nFix: ssh twbshop, then: %s "
               "(a restarted listener backfills missed history automatically on startup)." % fix)
    else:
        print(datetime.utcnow().isoformat()[:16], "ok")
    try:
        from core.heartbeat import beat
        beat("twb", "cron:collection_watchdog", 10, phase="ok")
    except Exception:
        pass


if __name__ == "__main__":
    main()
