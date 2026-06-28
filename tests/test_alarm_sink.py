"""B1 (session 58): the durable alarm sink (gm_bot.alarms) — alarms persist (so they survive a failed
Telegram DM), are readable by Claude/the nightly agent, carry severity, and can be acked. Runs against
the staging DB via conftest."""
from gm_bot import alarms


def test_log_and_read_alarm():
    alarms.init_alarms_db()
    aid = alarms.log_alarm("test_kind", "something happened", severity="warn", is_test=True)
    assert aid
    got = [r for r in alarms.recent_alarms(limit=50, include_test=True) if r["id"] == aid]
    assert got and got[0]["kind"] == "test_kind" and got[0]["delivered"] is False


def test_mark_delivered_then_ack():
    alarms.init_alarms_db()
    aid = alarms.log_alarm("test_deliver", "x", is_test=True)
    alarms.mark_delivered(aid)
    alarms.ack_alarm(aid)
    got = [r for r in alarms.recent_alarms(limit=50, include_test=True) if r["id"] == aid][0]
    assert got["delivered"] is True and got["acked"] is True


def test_invalid_severity_defaults_to_warn():
    alarms.init_alarms_db()
    aid = alarms.log_alarm("test_sev", "x", severity="bogus", is_test=True)
    got = [r for r in alarms.recent_alarms(limit=50, include_test=True) if r["id"] == aid][0]
    assert got["severity"] == "warn"


def test_open_excludes_acked():
    alarms.init_alarms_db()
    a_open = alarms.log_alarm("open_one", "live-ish", is_test=False)
    a_ack = alarms.log_alarm("ack_one", "y", is_test=False)
    alarms.ack_alarm(a_ack)
    ids = {r["id"] for r in alarms.open_alarms()}
    assert a_open in ids and a_ack not in ids


def test_severity_filter():
    alarms.init_alarms_db()
    money = alarms.log_alarm("money_kind", "balance off", severity="money", is_test=True)
    rows = alarms.recent_alarms(limit=50, include_test=True, severity="money")
    assert any(r["id"] == money for r in rows) and all(r["severity"] == "money" for r in rows)
