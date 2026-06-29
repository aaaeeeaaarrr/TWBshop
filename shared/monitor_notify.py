"""shared.monitor_notify — deliver a BUILDER/system alarm to the owner via the MONITOR bot (NOT a client
bot). ONE place so every bot's error-handler + the gm alarm chokepoint route builder concerns to the same
oversight channel. (TWB = client #1: a client's bot must never DM us, the builder, its plumbing alarms —
crashes / 409s / data-integrity belong on the Monitor bot + the sink. owner direction, s58.)

A direct Telegram API POST — no PTB/async needed — so it works from sync code AND even when the Monitor bot
isn't polling. NEVER raises. Callers in an async context should run it via asyncio.to_thread (it does a
short blocking HTTP POST)."""
import json
import os
import urllib.parse
import urllib.request

import config


def notify_monitor(text: str) -> bool:
    """POST `text` to the owner via the Monitor bot. Returns True on delivery, False otherwise. Never raises.
    Sends ONLY from the live (prod) environment — never from tests/staging/dev — so a test that exercises an
    alarm path can't message the owner a real DM (the s58 test-leakage bug: a couple of test runs POSTed real
    'DAVY audit' / 'TestBot crashed' DMs before this guard)."""
    if os.environ.get("TWBSHOP_ENV") != "prod":
        return False
    try:
        from secrets import MONITOR_BOT_TOKEN
    except Exception:
        MONITOR_BOT_TOKEN = ""
    owner = getattr(config, "OWNER_TELEGRAM_ID", 0)
    if not MONITOR_BOT_TOKEN or not owner:
        return False
    try:
        body = text if len(text) <= 4000 else (text[:3950] + "\n…(truncated — full in the alarm sink/log)")
        data = urllib.parse.urlencode({"chat_id": owner, "text": body}).encode()
        with urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage" % MONITOR_BOT_TOKEN,
                                    data=data, timeout=15) as r:
            return bool(json.load(r).get("ok"))
    except Exception:
        return False
