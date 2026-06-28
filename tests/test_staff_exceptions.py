"""F1 (s58): the wizard per-staff Exceptions page — e2e via the Flask test client over the staging core
DB. Covers the staff-row button, one-tap preset apply, and a toggle-save with the payback_to_al reroute +
approval-routing override (the owner's Thyda structure)."""
from core.db import init_core_db, ensure_org
from core.onboarding_flow import add_staff_manual
from core import exceptions as exc
from wizard.app import create_app

ORG = "exwiz58"


def _setup():
    init_core_db()
    ensure_org(ORG, "ExWiz", "Asia/Phnom_Penh")
    return add_staff_manual(ORG, name="Thyda"), add_staff_manual(ORG, name="Tyty")


def test_exceptions_page_renders_and_row_links_to_it():
    sid, _ = _setup()
    c = create_app(ORG).test_client()
    assert c.get("/staff/exceptions/%d" % sid).status_code == 200
    staff_pg = c.get("/staff").get_data(as_text=True)
    assert "/staff/exceptions/%d" % sid in staff_pg          # the row carries the ⚙ exceptions button


def test_apply_preset_then_save_toggles_thyda_structure():
    sid, tyty = _setup()
    c = create_app(ORG).test_client()
    # one-tap VIP preset
    c.post("/staff/exceptions/preset", data={"staff_id": sid, "preset": "vip_exempt"})
    assert exc.is_exempt(exc.get_exceptions(ORG, sid), "no_nudges")
    # the Thyda structure: keeps points, pay-back -> AL, off the Supervisors group, AL approved by Tyty
    c.post("/staff/exceptions/save", data={"staff_id": sid, "payback_to_al": "on",
                                           "no_supervisor_posts": "on", "al_approver_id": str(tyty)})
    e = exc.get_exceptions(ORG, sid)
    assert e.get("payback_to_al") and e.get("no_supervisor_posts") and e.get("al_approver_id") == tyty
    assert not exc.is_exempt(e, "no_points")        # she still gets points
    assert not exc.is_exempt(e, "no_nudges")        # save replaced the vip bundle with only the ticked set


def test_badge_counts_only_real_exceptions():
    sid, _ = _setup()
    create_app(ORG)  # ensure schema
    exc.set_exceptions(ORG, sid, {"no_nudges": True, "no_al": True, "_preset": "vip_exempt", "notes": "x"})
    from wizard.app import _exc_badge
    assert _exc_badge(ORG, sid) == " (2)"           # counts toggles/approvers, not _preset/notes
