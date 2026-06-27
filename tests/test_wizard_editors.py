"""Wizard staff + expertise editors — CRUD over core_staff + the expertise config, server-validated.
Staging; a test org; cleaned up."""
import core.db as cdb
from shared.database import _db
from wizard.app import create_app
from core.tenant_config import get_config
from core.onboarding_flow import list_staff

cdb.init_core_db()
ORG = "test_ed"


def _client():
    cdb.ensure_org(ORG, "T")
    return create_app(ORG).test_client()


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_org_groups WHERE org_id=%s", (ORG,))


def test_groups_screen_lists_and_assigns_role():
    from core.onboarding_flow import record_group, group_id_for_role
    c = _client()
    _clean()
    try:
        record_group(ORG, -100, "Staff Chat")
        body = c.get("/groups").get_data(as_text=True)
        assert "Staff Chat" in body and "staff" in body
        c.post("/groups/role", data={"chat_id": "-100", "role": "staff"})
        assert group_id_for_role(ORG, "staff") == -100
    finally:
        _clean()


def _exp(org):
    return get_config(org)["categories"]["attendance"]["expertise"]


def test_editors_render():
    c = _client()
    assert c.get("/staff").status_code == 200 and c.get("/expertise").status_code == 200


def test_setup_checklist_renders():
    body = _client().get("/setup").get_data(as_text=True)
    for s in ("Setup", "Connect your bot", "Tag your staff group", "Add your staff", "Set your rules",
              "Clear config warnings", "of 5 done"):
        assert s in body


def test_template_apply_prefills_config():
    c = _client()
    _clean()
    try:
        assert "Bakery" in c.get("/templates").get_data(as_text=True)
        c.post("/templates/apply", data={"name": "bakery"})
        cfg = get_config(ORG)
        assert cfg["onboarding"]["industry_template"] == "bakery"
        exp = cfg["categories"]["attendance"]["expertise"]
        assert exp["enabled"] is True and any(r["name"] == "baker" for r in exp["roles"])
        assert cfg["package"] == "ops"                          # template also sets a sensible plan
    finally:
        _clean()


def test_expertise_add_remove_role():
    c = _client()
    _clean()
    try:
        c.post("/expertise/role/add", data={"name": "baker", "min": "2"})
        assert any(r["name"] == "baker" and r["min_required"] == 2 for r in _exp(ORG)["roles"])
        c.post("/expertise/role/del", data={"name": "baker"})
        assert not any(r["name"] == "baker" for r in _exp(ORG)["roles"])
    finally:
        _clean()


def test_expertise_override_add_remove():
    c = _client()
    _clean()
    try:
        c.post("/expertise/role/add", data={"name": "baker", "min": "1"})
        c.post("/expertise/override/add",
               data={"role": "baker", "min": "2", "days": ["sat", "sun"], "hours": "06:00-12:00"})
        ov = _exp(ORG)["coverage_overrides"]
        assert len(ov) == 1 and ov[0]["role"] == "baker" and ov[0]["min"] == 2 and "sat" in ov[0]["days"]
        c.post("/expertise/override/del", data={"idx": "0"})
        assert _exp(ORG)["coverage_overrides"] == []
    finally:
        _clean()


def test_staff_add_overnight_and_remove():
    c = _client()
    _clean()
    try:
        c.post("/staff/add", data={"name": "Sok Sovann", "call_name": "Sok", "role": "baker",
                                   "is_senior": "on", "expertises": "baker, cashier",
                                   "work_start": "21:00", "work_end": "06:00"})   # overnight window
        staff = list_staff(ORG)
        assert len(staff) == 1
        s = staff[0]
        assert s["name"] == "Sok Sovann" and s["is_senior"] is True and s["expertises"] == ["baker", "cashier"]
        assert s["shift_windows"] == [{"start": "21:00", "end": "06:00"}]
        c.post("/staff/del", data={"staff_id": str(s["staff_id"])})
        assert list_staff(ORG) == []
    finally:
        _clean()


def test_staff_edit_updates_fields():
    from core.onboarding_flow import add_staff_manual, get_staff
    c = _client()
    _clean()
    try:
        sid = add_staff_manual(ORG, "Old Name", role="baker", shift_windows=[{"start": "06:00", "end": "14:00"}])
        body = c.get("/staff/edit/%d" % sid).get_data(as_text=True)
        assert "Old Name" in body and "06:00" in body                      # pre-filled
        c.post("/staff/update", data={"staff_id": str(sid), "name": "New Name", "role": "cashier",
                                      "expertises": "cashier", "work_start": "21:00", "work_end": "06:00"})
        s = get_staff(ORG, sid)
        assert s["name"] == "New Name" and s["role"] == "cashier" and s["expertises"] == ["cashier"]
        assert s["shift_windows"] == [{"start": "21:00", "end": "06:00"}]   # overnight, replaced
    finally:
        _clean()


def test_staff_profile_fields_saved():
    # The universal employee record: the edit form renders the HR fields and the route saves them to core_staff.
    from core.onboarding_flow import add_staff_manual, get_staff
    c = _client()
    _clean()
    try:
        sid = add_staff_manual(ORG, "Profile P", role="baker")
        body = c.get("/staff/edit/%d" % sid).get_data(as_text=True)
        for label in ("National ID", "Passport no.", "Nationality", "Emergency contact", "Indemnity", "Tax ID"):
            assert label in body, label
        c.post("/staff/update", data={
            "staff_id": str(sid), "name": "Profile P", "national_id": "012345678", "passport_no": "N1234567",
            "nationality": "Cambodian", "department": "Bakery", "employment_type": "full_time",
            "start_date": "2026-01-15", "emergency_contact_name": "Mom", "indemnity_enabled": "on", "tax_id": "TX-9",
        })
        s = get_staff(ORG, sid)
        assert s["national_id"] == "012345678" and s["passport_no"] == "N1234567"
        assert s["nationality"] == "Cambodian" and s["department"] == "Bakery"
        assert str(s["start_date"]) == "2026-01-15"
        assert s["indemnity_enabled"] is True and s["right_to_work_verified"] is False   # unchecked bool → False
        assert s["emergency_contact_name"] == "Mom" and s["tax_id"] == "TX-9"
    finally:
        _clean()


def test_staff_bulk_import():
    c = _client()
    _clean()
    try:
        c.post("/staff/import", data={"bulk": "Sok, baker, 21:00-06:00, baker;cashier\nDara, cashier\n\nLin"})
        staff = list_staff(ORG)
        assert len(staff) == 3                                          # blank line skipped, 3 imported
        sok = next(s for s in staff if s["name"] == "Sok")
        assert sok["role"] == "baker" and sok["expertises"] == ["baker", "cashier"]
        assert sok["shift_windows"] == [{"start": "21:00", "end": "06:00"}]
    finally:
        _clean()


def test_staff_split_shift_two_windows():
    c = _client()
    _clean()
    try:
        c.post("/staff/add", data={"name": "Split P", "work_start": "06:00", "work_end": "10:00",
                                   "split_start": "16:00", "split_end": "20:00"})
        assert len(list_staff(ORG)[0]["shift_windows"]) == 2     # split = two windows
    finally:
        _clean()
