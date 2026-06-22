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
    tg = ch.handle("twb", tg_cmd, tg_params, config={})    # config={} → defaults, no DB
    web = ch.handle("twb", web_cmd, web_params, config={})
    assert tg == web                                       # same brain, two channels
    assert tg == {"ok": True, "state": "late", "minutes_late": 12, "minutes_early": 0}


def test_clean_errors_across_the_boundary():
    assert ch.handle("twb", "nonsense", {}, config={})["ok"] is False
    r = ch.handle("twb", "verdict", {}, config={})         # missing params
    assert r["ok"] is False and "missing param" in r["error"]


def test_tenant_config_flows_into_the_brain():
    # set a tenant override (grace=0) and prove handle() loads + applies it (no params override)
    import core.db as cdb
    from core import tenant_config as tc
    org = "test_chcfg"
    cdb.init_core_db()
    cdb.ensure_org(org, "Test")
    from shared.database import _db
    with _db() as c:                                       # reset to a clean slate (orgs persist)
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))
    assert tc.get_config(org)["grace_min"] == 5            # default out of the box
    tc.set_config(org, grace_min=0, early_bonus_min=0)
    assert tc.get_config(org)["grace_min"] == 0
    when = datetime(2026, 6, 20, 23, 3, tzinfo=UTC)        # 3 min late
    start = datetime(2026, 6, 20, 23, 0, tzinfo=UTC)
    r = ch.handle(org, "verdict", {"when": when, "start_dt": start})   # config=None → loads tenant cfg
    assert r["state"] == "late" and r["minutes_late"] == 3            # grace=0 → 3 late is LATE, not on-time


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
