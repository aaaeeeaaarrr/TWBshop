"""core.derive — the self-deriving resolver. Proves the core decides a day from its OWN overrides
(no live feed): the override→modifier mapping + the parity-locked precedence, all from core state.
Real staging DB; cleaned up."""
import core.db as cdb
from core import derive
from shared.database import _db

ORG = "test_derive"
WS, WE, DOFF = 360, 900, 6        # 06:00–15:00, Sunday off
MON, SUN = "2026-06-22", "2026-06-21"


def _setup():
    cdb.init_core_db()
    cdb.ensure_org(ORG, "Test")
    _clean()


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_day_overrides WHERE org_id=%s", (ORG,))


def test_self_derive_precedence_from_core_state():
    _setup()
    try:
        # no override → normal working (Mon) / weekly day-off (Sun)
        assert derive.resolve(ORG, 1, MON, WS, WE, DOFF)["reason"] == "normal"
        assert derive.resolve(ORG, 1, SUN, WS, WE, DOFF)["reason"] == "day_off"
        # AL → away
        derive.set_override(ORG, 1, MON, "al")
        assert derive.resolve(ORG, 1, MON, WS, WE, DOFF) == \
               {"working": False, "reason": "al", "start_min": None, "end_min": None}
        # redefine → working at the moved interval
        derive.set_override(ORG, 2, MON, "redefine", 1051, 1411)
        r = derive.resolve(ORG, 2, MON, WS, WE, DOFF)
        assert r["working"] and r["reason"] == "redefine" and r["start_min"] == 1051 and r["end_min"] == 1411
        # swap_work onto a Sunday day-off → working at base
        derive.set_override(ORG, 3, SUN, "swap_work")
        assert derive.resolve(ORG, 3, SUN, WS, WE, DOFF)["reason"] == "swap_work"
        # precedence: AL beats a redefine when both are set → away (parity-locked precedence)
        derive.set_override(ORG, 4, MON, "al")
        derive.set_override(ORG, 4, MON, "redefine", 1051, 1411)
        assert derive.resolve(ORG, 4, MON, WS, WE, DOFF)["reason"] == "al"
        # clear → back to normal
        derive.clear_overrides(ORG, 1, MON)
        assert derive.resolve(ORG, 1, MON, WS, WE, DOFF)["reason"] == "normal"
    finally:
        _clean()
