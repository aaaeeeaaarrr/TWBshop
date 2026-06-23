"""Wizard — the admin viewer + the customer editor. Proves: badges are grounded; the admin view renders
the badged config; the customer view is friendly (explanations, true/false meanings, Apply/Cancel) and
LEAKS NO internal badges; Apply commits ONLY validated SHADOW knobs (clamps ints, rejects bad enums,
ignores LIVE/unknown). Staging DB; test orgs reset."""
import core.db as cdb
from shared.database import _db
from wizard.app import create_app, apply_changes, _get_path
from wizard.status import status_for
from wizard import schema
from core.tenant_config import get_config

cdb.init_core_db()


def _reset(org):
    cdb.ensure_org(org, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))   # NOT NULL → empty, not NULL


# ── badges + admin view ──────────────────────────────────────────────────────
def test_status_badges_are_grounded():
    assert status_for("categories.attendance.approvals.al") == "LIVE"
    assert status_for("categories.attendance.approvals.al.reping_hours") == "LIVE"
    assert status_for("categories.attendance.verdict.grace_min") == "SHADOW"
    assert status_for("categories.attendance.approvals.sick") == "PLANNED"   # only 'al' is wired live
    assert status_for("categories.accountant") == "PLANNED"


def test_admin_view_renders_with_badges_and_cutover():
    body = create_app("twb").test_client().get("/").get_data(as_text=True)
    assert "grace_min" in body and "LIVE" in body and "SHADOW" in body and "Packages" in body
    assert "Cut-over status" in body and "agree" in body   # the readiness dashboard


def test_healthz():
    assert create_app().test_client().get("/healthz").status_code == 200


# ── schema (the explanations) ────────────────────────────────────────────────
def test_schema_explains_every_grouped_setting():
    for _g, paths in schema.ATTENDANCE_GROUPS:
        for p in paths:
            d = schema.describe(p)
            assert d and d.get("help"), p
            if d["type"] == "bool":
                assert d.get("true") and d.get("false"), p   # both meanings spelled out
    # approval fields describe per-kind (with the kind in the label) + cover the if-conditions
    d = schema.describe("categories.attendance.approvals.al.escalate_to_owner_after_max")
    assert d and "Annual leave" in d["label"] and "IF" in d["true"].upper()   # if-condition spelled out


# ── customer view: friendly + no internal leakage ────────────────────────────
def test_customer_view_friendly_and_no_internal_badges():
    body = create_app("twb").test_client().get("/customer").get_data(as_text=True)
    assert "Apply changes" in body and "Cancel changes" in body
    assert "Lateness grace" in body and "nothing changes until you press" in body
    assert "On:" in body and "Off:" in body                 # true/false meanings shown
    assert 'action="/customer/apply"' in body
    assert "SHADOW" not in body and "PLANNED" not in body   # internal cut-over terms must not leak


# ── Apply: safe, validated, SHADOW-only ──────────────────────────────────────
def test_apply_commits_shadow_only_ignores_live():
    org = "twbtest_wiz1"
    _reset(org)
    try:
        apply_changes(org, {"categories.attendance.verdict.grace_min": "9",
                            "categories.attendance.points.enabled": "on",
                            "categories.attendance.approvals.al.reping_hours": "99"})  # LIVE → ignored
        cfg = get_config(org)
        assert _get_path(cfg, "categories.attendance.verdict.grace_min") == 9
        assert _get_path(cfg, "categories.attendance.points.enabled") is True
        assert _get_path(cfg, "categories.attendance.approvals.al.reping_hours") == 6  # unchanged default
    finally:
        _reset(org)


def test_apply_clamps_int_and_rejects_bad_enum():
    org = "twbtest_wiz2"
    _reset(org)
    try:
        apply_changes(org, {"categories.attendance.verdict.grace_min": "9999",     # clamp to max 60
                            "categories.attendance.checkin_method": "hacker"})      # bad enum → ignored
        cfg = get_config(org)
        assert _get_path(cfg, "categories.attendance.verdict.grace_min") == 60
        assert _get_path(cfg, "categories.attendance.checkin_method") == "telegram_live"
    finally:
        _reset(org)


def test_apply_unchecked_bool_becomes_false():
    org = "twbtest_wiz3"
    _reset(org)
    try:
        apply_changes(org, {})   # points checkbox absent ⇒ False (real form-submit semantics)
        assert _get_path(get_config(org), "categories.attendance.points.enabled") is False
    finally:
        _reset(org)
