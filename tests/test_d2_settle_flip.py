"""D2 — the settle cut-over net (gm_bot.checkin_net.settle_via_net through core.flip 'settle').
FLAG OFF (default) → byte-identical to live's (pb_cleared, ot_banked); FLAG ON → core's values
(parity-locked: settle_shift for a normal day + settle_payback_slot for a slot), auto-reverting on
divergence. Throwaway orgs + an isolation fixture so divergence rows accumulating across suite re-runs
can't trip the auto-revert threshold (same lesson as the C2 flip tests)."""
import pytest

from core import flip
from gm_bot.checkin_net import settle_via_net


@pytest.fixture(autouse=True)
def _isolate():
    flip.init_flip_db()
    from shared.database import _db
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_flip_log WHERE org_id LIKE %s", ("d2set_%",))
            cur.execute("DELETE FROM core_flip WHERE org_id LIKE %s", ("d2set_%",))
    yield


def test_flag_off_returns_live_even_if_core_differs():
    org = "d2set_off"
    flip.set_authoritative(org, "settle", False)
    assert settle_via_net((89, 0), (89, 5), org_id=org) == ((89, 5), False)   # live kept as-is while OFF


def test_flag_on_agreeing_returns_core():
    org = "d2set_on"
    flip.set_authoritative(org, "settle", True)
    assert settle_via_net((89, 30), (89, 30), org_id=org) == ((89, 30), False)


def test_flag_on_core_overrides_a_wrong_pb_cleared():
    org = "d2set_ovpb"
    flip.set_authoritative(org, "settle", True)
    out, rev = settle_via_net((89, 0), (50, 0), org_id=org)   # live under-cleared the debt; core says 89
    assert out == (89, 0) and rev is False


def test_flag_on_ot_banked_difference_is_caught():
    org = "d2set_ovot"
    flip.set_authoritative(org, "settle", True)
    out, rev = settle_via_net((89, 30), (89, 0), org_id=org)  # ot_banked differs → core wins (1 divergence)
    assert out == (89, 30) and rev is False
