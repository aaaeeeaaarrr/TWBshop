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
    try:
        active = subprocess.run(["systemctl", "is-active", "twbshop-listener"],
                                capture_output=True, text=True).stdout.strip()
        if active != "active":
            problems.append("twbshop-listener service is %s." % (active or "unknown"))
    except Exception as e:
        print("service check failed:", e)

    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(sent_at) AS m FROM ops_messages")
                latest = (cur.fetchone() or {}).get("m")
        if latest:
            latest_dt = datetime.fromisoformat(str(latest).replace("Z", "+00:00"))
            age_h = (datetime.utcnow() - latest_dt.replace(tzinfo=None)).total_seconds() / 3600
            if age_h > STALE_HOURS:
                problems.append("No messages recorded for %.1f hours (last: %s UTC)."
                                % (age_h, str(latest)[:16]))
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
