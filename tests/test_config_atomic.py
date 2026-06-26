"""core.tenant_config.set_config — the read-modify-write must run under SELECT … FOR UPDATE so concurrent
tweaks serialize and never clobber a sibling. This guards the deep-merge + the locked write path."""
import core.db as cdb
from shared.database import _db
from core.tenant_config import set_config, get_config

ORG = "test_cfgatomic"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))


def test_two_nested_writes_both_survive():
    _reset()
    try:
        set_config(ORG, {"categories": {"attendance": {"verdict": {"grace_min": 9}}}})
        set_config(ORG, {"categories": {"attendance": {"ot": {"disposition": "pay_money"}}}})  # sibling key
        cfg = get_config(ORG)
        assert cfg["categories"]["attendance"]["verdict"]["grace_min"] == 9       # first write kept
        assert cfg["categories"]["attendance"]["ot"]["disposition"] == "pay_money"  # second didn't clobber it
        # and a deeper default sibling is still present (deep-merge intact)
        assert cfg["categories"]["attendance"]["verdict"]["early_bonus_min"] == 5
    finally:
        _reset()
