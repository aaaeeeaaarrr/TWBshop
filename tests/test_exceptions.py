"""F1 (session 58): per-staff exceptions/overrides (core.exceptions). Pure whitelist/preset/helper logic
+ a DB round-trip on the staging core_staff. Models the owner's Tyty (fully exempt) + Thyda
(no-supervisor-posts + AL-approver override) cases."""
from core import exceptions as ex
from core.db import init_core_db, ensure_org
from core.onboarding_flow import add_staff_manual


# ---- pure logic (no DB) -------------------------------------------------------------------------

def test_clean_keeps_only_true_toggles_and_drops_unknown():
    clean = ex._clean_exceptions({"no_nudges": True, "no_lateness": False, "bogus": True, "drop_me": 1})
    assert clean == {"no_nudges": True}            # False toggle omitted; unknown keys dropped


def test_clean_approver_coercion():
    assert ex._clean_exceptions({"al_approver_id": "28"}) == {"al_approver_id": 28}
    assert ex._clean_exceptions({"al_approver_id": ""}) == {}      # blank dropped
    assert ex._clean_exceptions({"al_approver_id": "x"}) == {}     # non-numeric dropped


def test_clean_preset_and_notes():
    clean = ex._clean_exceptions({"_preset": "vip_exempt", "notes": "  owner family  "})
    assert clean["_preset"] == "vip_exempt" and clean["notes"] == "owner family"
    assert "_preset" not in ex._clean_exceptions({"_preset": "not_a_preset"})


def test_vip_preset_is_the_tyty_bundle():
    p = ex.apply_preset("vip_exempt")
    for k in ("no_attendance", "no_al", "no_ot", "no_points", "no_nudges", "no_supervisor_posts", "quiet"):
        assert ex.is_exempt(p, k) is True
    assert p["_preset"] == "vip_exempt"


def test_standard_preset_is_empty():
    assert ex.apply_preset("standard") == {"_preset": "standard"}
    assert ex.summary({}) == "" and ex.summary({"_preset": "standard"}) == ""   # lean: nothing for normal


def test_helpers():
    exc = {"no_supervisor_posts": True, "al_approver_id": 28}
    assert ex.is_exempt(exc, "no_supervisor_posts") and not ex.is_exempt(exc, "no_nudges")
    assert ex.approver_for(exc, "al") == 28 and ex.approver_for(exc, "swap") is None
    assert ex.is_exempt(None, "no_nudges") is False         # safe on None
    assert ex.summary(exc) == "⚙ 2"


# ---- DB round-trip (staging core_staff) ---------------------------------------------------------

def test_db_roundtrip_tyty_and_thyda():
    init_core_db()
    org = "extest58"
    ensure_org(org, "ExceptionsTest", "Asia/Phnom_Penh")
    tyty = add_staff_manual(org, name="Tyty")
    thyda = add_staff_manual(org, name="Thyda")

    # Tyty = one-tap VIP preset
    ex.set_exceptions(org, tyty, ex.apply_preset("vip_exempt"))
    t = ex.get_exceptions(org, tyty)
    assert ex.is_exempt(t, "no_nudges") and ex.is_exempt(t, "no_al") and t["_preset"] == "vip_exempt"

    # Thyda = tracked + nudged normally, but off the Supervisors group + AL approved only by Tyty
    ex.set_exceptions(org, thyda, {"no_supervisor_posts": True, "al_approver_id": tyty})
    d = ex.get_exceptions(org, thyda)
    assert ex.is_exempt(d, "no_supervisor_posts") and ex.approver_for(d, "al") == tyty
    assert not ex.is_exempt(d, "no_nudges") and not ex.is_exempt(d, "no_attendance")   # still normal otherwise

    # default = normal staffer
    assert ex.get_exceptions(org, add_staff_manual(org, name="Normal")) == {}


def test_payback_to_al_reroute_is_the_thyda_structure_change():
    # Thyda: still scored (NOT no_points), but pay-back deducts AL instead of being worked off.
    clean = ex._clean_exceptions({"payback_to_al": True, "no_supervisor_posts": True, "al_approver_id": "28"})
    assert clean == {"payback_to_al": True, "no_supervisor_posts": True, "al_approver_id": 28}
    assert ex.is_exempt(clean, "payback_to_al") and not ex.is_exempt(clean, "no_points")
    # a per-person structure choice — NOT bundled into the blanket presets
    assert "payback_to_al" not in ex.apply_preset("vip_exempt")
    assert "payback_to_al" not in ex.apply_preset("freelancer")
