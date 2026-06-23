"""core.onboarding_flow — discover-confirm staff onboarding. The bot stages people it sees; the owner
confirms each into a core_staff record (idempotent per Telegram id) or skips. Staging; org-scoped; cleaned."""
import core.db as cdb
from shared.database import _db
from core.onboarding_flow import (record_seen_member, list_candidates, confirm_candidate, skip_candidate,
                                  add_staff_manual, list_staff)

cdb.init_core_db()
ORG = "test_onb"


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_onboarding_candidates WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_org_groups WHERE org_id=%s", (ORG,))


def test_group_discovery_and_single_role_mapping():
    from core.onboarding_flow import record_group, list_groups, set_group_role, group_id_for_role
    _clean()
    try:
        record_group(ORG, -100, "Staff Chat")
        record_group(ORG, -200, "Suppliers")
        record_group(ORG, -100, "Staff Chat v2")          # re-seen → refresh title, stays one row
        assert len(list_groups(ORG)) == 2
        set_group_role(ORG, -100, "staff")
        assert group_id_for_role(ORG, "staff") == -100
        set_group_role(ORG, -200, "staff")                # single-occupancy → moves the staff role
        assert group_id_for_role(ORG, "staff") == -200
        assert next(g for g in list_groups(ORG) if g["chat_id"] == -100)["role"] is None
    finally:
        _clean()


def test_discover_then_confirm_builds_roster():
    _clean()
    try:
        record_seen_member(ORG, 1001, "Sok", "sok_t", chat_id=-500)
        record_seen_member(ORG, 1002, "Dara")
        record_seen_member(ORG, 1001, "Sok Sovann")          # re-seen → still ONE candidate (upsert)
        assert len(list_candidates(ORG)) == 2
        sid = confirm_candidate(ORG, 1001, "Sok Sovann", call_name="Sok", role="baker",
                                is_senior=True, expertises=["baker", "cashier"])
        skip_candidate(ORG, 1002)                            # Dara = not staff
        assert list_candidates(ORG) == []                   # both decided → confirm list empty
        staff = list_staff(ORG)
        assert len(staff) == 1
        assert staff[0]["staff_id"] == sid and staff[0]["telegram_id"] == 1001
        assert staff[0]["is_senior"] is True and staff[0]["expertises"] == ["baker", "cashier"]
    finally:
        _clean()


def test_confirm_idempotent_per_telegram_id():
    _clean()
    try:
        record_seen_member(ORG, 2001, "Lin")
        s1 = confirm_candidate(ORG, 2001, "Lin A")
        s2 = confirm_candidate(ORG, 2001, "Lin B", role="cashier")   # same tg id → updates the SAME row
        assert s1 == s2 and len(list_staff(ORG)) == 1
        assert list_staff(ORG)[0]["role"] == "cashier"
    finally:
        _clean()


def test_manual_add():
    _clean()
    try:
        sid = add_staff_manual(ORG, "Manual Person", role="barista", expertises=["barista"])
        staff = list_staff(ORG)
        assert sid > 0 and len(staff) == 1 and staff[0]["expertises"] == ["barista"]
    finally:
        _clean()
