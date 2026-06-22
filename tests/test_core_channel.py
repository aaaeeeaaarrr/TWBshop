"""core.channel — the channel-agnostic spine. Proves two DIFFERENT native channel shapes translate to the
SAME neutral command → identical brain result (channel-agnosticism), and GUARDS that the brain (core/*)
imports no channel SDK (principle #1, enforced structurally)."""
import glob
import os
from datetime import datetime, timezone

import core.channel as ch

UTC = timezone.utc


# two toy adapters: each takes its channel's NATIVE shape and produces the neutral (command, params)
def _telegram_adapter(update: dict):
    m = update["message"]
    return "verdict", {"when": m["date"], "start_dt": m["shift_start"]}


def _web_adapter(req: dict):
    b = req["json"]
    return "verdict", {"when": b["ts"], "start_dt": b["start"]}


def test_two_channels_one_brain():
    when = datetime(2026, 6, 20, 23, 12, tzinfo=UTC)      # 06:12 PP
    start = datetime(2026, 6, 20, 23, 0, tzinfo=UTC)       # 06:00 PP → late 12
    tg_cmd, tg_params = _telegram_adapter({"message": {"date": when, "shift_start": start}})
    web_cmd, web_params = _web_adapter({"json": {"ts": when, "start": start}})
    tg = ch.handle("twb", tg_cmd, tg_params)
    web = ch.handle("twb", web_cmd, web_params)
    assert tg == web                                       # same brain, two channels
    assert tg == {"ok": True, "state": "late", "minutes_late": 12, "minutes_early": 0}


def test_clean_errors_across_the_boundary():
    assert ch.handle("twb", "nonsense", {})["ok"] is False
    r = ch.handle("twb", "verdict", {})                    # missing params
    assert r["ok"] is False and "missing param" in r["error"]


def test_brain_imports_no_channel_sdk():
    # principle #1, enforced: no core/*.py may import a channel SDK (telegram/telethon/flask/fastapi/...)
    forbidden = ("telegram", "telethon", "flask", "fastapi", "aiohttp", "discord")
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    offenders = []
    for path in glob.glob(os.path.join(here, "core", "*.py")):
        text = open(path, encoding="utf-8").read()
        for tok in forbidden:
            if ("import %s" % tok) in text or ("from %s" % tok) in text:
                offenders.append((os.path.basename(path), tok))
    assert not offenders, "channel SDK leaked into the brain: %s" % offenders
