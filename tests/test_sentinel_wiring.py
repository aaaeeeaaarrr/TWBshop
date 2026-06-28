"""s58 B2: the Sentinel sweep is wired to the alarm sink, de-duped so a persistent issue alarms ONCE
(not every 30-min sweep), and a newly-appearing issue alarms while a cleared one drops out."""
from gm_bot.bot import _sentinel_new_alarms


def test_first_sweep_alarms_all_then_persistent_dedupes():
    found = [{"flow": "shadow", "key": "twb", "severity": "critical", "detail": "net dark"},
             {"flow": "attendance", "key": "twb", "severity": "warn", "detail": "3 malformed check-ins"}]
    new, cur = _sentinel_new_alarms(found, None)          # first sweep → both are new
    assert len(new) == 2
    new2, cur2 = _sentinel_new_alarms(found, cur)         # same issues persist → none new
    assert new2 == []


def test_new_issue_appears_cleared_one_drops():
    seed = [{"flow": "attendance", "key": "twb", "severity": "warn", "detail": "3 malformed"}]
    _, cur = _sentinel_new_alarms(seed, None)
    found = [{"flow": "attendance", "key": "twb", "severity": "warn", "detail": "3 malformed"},
             {"flow": "job", "key": "reaper", "severity": "warn", "detail": "missed run"}]
    new, cur2 = _sentinel_new_alarms(found, cur)          # only the job alarm is new
    assert len(new) == 1 and new[0]["flow"] == "job"
    # the cleared one is no longer tracked → if it recurs later it alarms again
    new3, _ = _sentinel_new_alarms(seed, cur2)
    assert len(new3) == 0   # 'attendance' still present in cur2, so not re-alarmed
