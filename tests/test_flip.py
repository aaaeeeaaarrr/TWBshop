"""C1 (self-healing program): the instant-revert net. Default OFF = today's behaviour (old engine); when ON,
core decides + the old engine shadows it; if recent divergence breaches the threshold the flip AUTO-REVERTS
to the known-good old engine (a misbehaving flip un-flips itself). Pure threshold + DB round-trip on staging."""
from core import flip

ORG = "fliptest58"


# ---- pure auto-revert decision ------------------------------------------------------------------

def test_should_auto_revert_pure():
    assert flip.should_auto_revert(5, 5) is False        # too few samples (< 10) → hold
    assert flip.should_auto_revert(20, 1) is False        # 5% ≤ 10% → healthy, stay flipped
    assert flip.should_auto_revert(20, 5) is True         # 25% > 10% → revert
    assert flip.should_auto_revert(10, 2) is True         # 20% > 10% at exactly min_samples → revert


# ---- the net (DB round-trip) --------------------------------------------------------------------

def test_off_by_default_returns_live():
    flip.init_flip_db()
    res, rev = flip.decide(ORG, "checkin", "CORE", "LIVE")   # never flipped on
    assert res == "LIVE" and rev is False


def test_on_and_agreeing_returns_core():
    flip.init_flip_db()
    flip.set_authoritative(ORG, "checkin_agree", True)
    res, rev = flip.decide(ORG, "checkin_agree", "X", "X")    # core == live
    assert res == "X" and rev is False
    assert flip.is_authoritative(ORG, "checkin_agree") is True


def test_diverging_flip_auto_reverts_itself():
    flip.init_flip_db()
    path = "checkin_diverge"
    flip.set_authoritative(ORG, path, True)
    reverted = False
    for _ in range(15):                                       # core always disagrees with live
        res, rev = flip.decide(ORG, path, "CORE", "LIVE")
        reverted = reverted or rev
    assert reverted is True                                   # it un-flipped itself…
    assert flip.is_authoritative(ORG, path) is False          # …and authority is back on the old engine
    res, rev = flip.decide(ORG, path, "CORE", "LIVE")         # now OFF → lands on live
    assert res == "LIVE" and rev is False


def test_manual_revert():
    flip.init_flip_db()
    flip.set_authoritative(ORG, "p", True)
    assert flip.is_authoritative(ORG, "p") is True
    flip.set_authoritative(ORG, "p", False, "manual")
    assert flip.is_authoritative(ORG, "p") is False


def test_sentinel_flags_a_diverging_flip_early():
    """Proactive: the Sentinel flags a wobbling authoritative flip BEFORE it auto-reverts (and B2's sweep
    routes that straight to the alarm sink → me)."""
    from core import sentinel
    flip.init_flip_db()
    path = "settle_wobble"
    flip.set_authoritative(ORG, path, True)
    for _ in range(3):
        flip.record_divergence(ORG, path, agree=False, detail="x")
    flip.record_divergence(ORG, path, agree=True)
    al = sentinel.sweep(ORG)
    assert any(a["flow"] == "flip" and path in a["key"] for a in al)   # caught early
    assert flip.is_authoritative(ORG, path) is True                    # detector only WARNS; doesn't revert
