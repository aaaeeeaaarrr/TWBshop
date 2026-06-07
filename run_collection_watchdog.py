"""Dead-man watchdog for message collection (session 28 — the May 28/29 lesson).

Cron (server, every 30 min):
  */30 * * * * cd /root/TWBshop && /root/venv/bin/python run_collection_watchdog.py >> logs/watchdog.log 2>&1

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
    data = urllib.parse.urlencode({
        "chat_id": config.OWNER_TELEGRAM_ID,
        "text": "🚨 COLLECTION WATCHDOG\n" + text,
    }).encode()
    url = "https://api.telegram.org/bot%s/sendMessage" % config.BOT_TOKEN
    with urllib.request.urlopen(url, data=data, timeout=20) as resp:
        json.load(resp)
    with open(STATE_FILE, "w") as f:
        f.write(datetime.utcnow().isoformat())
    print("alert sent:", text)


def main() -> None:
    problems = []
    # twbshop-gm matters doubly: it is the ONLY recorder of Supervisors + Management
    # (owner decision: the listener account stays out of senior rooms — junior staff use it).
    # Bot API can't backfill history, so GM downtime there = permanent loss; detect fast.
    for svc in ("twbshop-listener", "twbshop-gm"):
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
    except Exception as e:
        problems.append("Database check failed: %s" % e)

    if problems:
        _alert("\n".join(problems) +
               "\n\nFix: ssh twbshop, then: systemctl restart twbshop-listener "
               "(it backfills missed history automatically on startup).")
    else:
        print(datetime.utcnow().isoformat()[:16], "ok")


if __name__ == "__main__":
    main()
