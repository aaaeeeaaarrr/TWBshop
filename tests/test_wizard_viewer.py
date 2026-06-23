"""Wizard — admin viewer + customer editor, 4-state model. Proves: badges grounded (the live-but-fixed
mechanisms read LIVE_FIXED, NOT 'planned'); admin renders all sections with secrets MASKED; customer view
is friendly, covers attendance + connections, leaks no internal badges, masks tokens; Apply commits only
safe SHADOW/PLANNED knobs (LIVE_FIXED locked) and writes secrets to the encrypted store. Staging DB."""
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
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))
            cur.execute("DELETE FROM core_org_secrets WHERE org_id=%s", (org,))


# ── badges (the LIVE_FIXED fix) ──────────────────────────────────────────────
def test_status_badges_four_state_grounded():
    assert status_for("categories.attendance.approvals.al") == "LIVE"
    assert status_for("categories.attendance.verdict.grace_min") == "SHADOW"
    # the confusion fix: live-but-not-config-driven features read LIVE_FIXED, not PLANNED
    assert status_for("categories.attendance.approvals.sick") == "LIVE_FIXED"
    assert status_for("categories.attendance.approvals.ot.reping_hours") == "LIVE_FIXED"
    assert status_for("categories.attendance.leave.sick.late_inform_penalty_points") == "LIVE_FIXED"
    assert status_for("connections.telegram.bot_token") == "LIVE_FIXED"
    # genuinely new options are PLANNED
    assert status_for("categories.attendance.ot.disposition") == "PLANNED"
    assert status_for("categories.attendance.staff_rules.max_consecutive_days") == "PLANNED"
    assert status_for("connections.web.enabled") == "PLANNED"


def test_admin_renders_all_states_and_masks_secrets():
    body = create_app("twb").test_client().get("/").get_data(as_text=True)
    assert "LIVE_FIXED" in body and "SHADOW" in body and "PLANNED" in body
    assert "Cut-over status" in body and "disposition" in body and "staff_rules" in body
    assert "🔒 secret" in body            # token shown as a secret status …
    assert "__secret__" not in body       # … never the raw ref/value
    assert "At a glance" in body and "href='/whatif'" in body and "href='/audit'" in body  # dashboard + tool nav


def test_healthz():
    assert create_app().test_client().get("/healthz").status_code == 200


def test_every_descriptor_maps_to_a_real_config_knob():
    # structural guard (truth-consolidation): a customer-facing descriptor must point to a knob that EXISTS
    # in DEFAULTS — else the UI shows a setting that can't be set, or apply silently drops it.
    from core.tenant_config import DEFAULTS

    def _exists(path):
        cur = DEFAULTS
        for k in path.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return False
            cur = cur[k]
        return True

    missing = [p for p in schema.DESCRIPTORS if not _exists(p)]
    assert missing == [], "schema descriptors with no config knob: %s" % missing


def test_security_headers_present():
    r = create_app("twb").test_client().get("/healthz")
    assert r.headers.get("X-Frame-Options") == "DENY"                 # anti-clickjacking
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


# ── schema explains everything new ───────────────────────────────────────────
def test_schema_explains_new_mechanisms():
    for _g, paths in (schema.ATTENDANCE_GROUPS + schema.CONNECTIONS_GROUPS + schema.ONBOARDING_GROUPS):
        for p in paths:
            d = schema.describe(p)
            assert d and d.get("help"), p
    assert schema.describe("categories.attendance.ot.disposition")["type"] == "enum"
    assert schema.describe("connections.telegram.bot_token")["type"] == "secret"
    assert schema.describe("onboarding.staff_entry")["type"] == "enum"          # discover-confirm/manual/bulk
    assert schema.describe("categories.attendance.schedule.split_shift_allowed")["type"] == "bool"
    # bot-as-approver: 'by' offers the bot, and bot_rule explains each if-condition
    by = schema.APPROVAL_FIELDS["by"]
    assert any(o[0] == "bot" for o in by["options"])
    assert "IF" in schema.APPROVAL_FIELDS["bot_rule"]["options"][0][2].upper()   # the rules spell out the condition


# ── customer view: complete + friendly + no leak ─────────────────────────────
def test_customer_view_complete_no_internal_leak():
    body = create_app("twb").test_client().get("/customer").get_data(as_text=True)
    assert "Apply changes" in body and "Cancel changes" in body
    assert "Sick leave" in body and "Staff rules" in body and "Connections" in body  # all mechanisms shown
    assert "Setup &amp; staff" in body and "Discover &amp; confirm" in body          # onboarding section
    assert "Overnight shifts" in body and "Allow split shifts" in body               # split/midnight options
    assert "Track minimum skill coverage" in body                                    # expertise/coverage
    assert "The bot (automatic)" in body and "Keep coverage" in body                 # bot-as-approver + a rule
    assert "What earned overtime becomes" in body                                    # the new OT options
    assert "paste to set" in body and "not set" in body                              # token field, masked
    assert "SHADOW" not in body and "PLANNED" not in body and "LIVE_FIXED" not in body  # no internals leak


# ── Apply: safe, validated, status-aware ─────────────────────────────────────
def test_apply_commits_safe_knobs_only():
    org = "twbtest_wiz1"
    _reset(org)
    try:
        apply_changes(org, {
            "categories.attendance.verdict.grace_min": "9",                       # SHADOW → commits
            "categories.attendance.ot.disposition": "pay_money",                  # PLANNED → commits
            "categories.attendance.leave.sick.late_inform_penalty_points": "20",  # LIVE_FIXED → commits (preference)
            "categories.attendance.approvals.al.reping_hours": "99",             # LIVE + not an editable group → ignored
        })
        cfg = get_config(org)
        assert _get_path(cfg, "categories.attendance.verdict.grace_min") == 9
        assert _get_path(cfg, "categories.attendance.ot.disposition") == "pay_money"
        assert _get_path(cfg, "categories.attendance.leave.sick.late_inform_penalty_points") == 20  # preference saved
        assert _get_path(cfg, "categories.attendance.approvals.al.reping_hours") == 6  # LIVE never writable here
    finally:
        _reset(org)


def test_apply_writes_secret_to_store_not_config():
    from core.db import has_org_secret
    org = "twbtest_wiz2"
    _reset(org)
    try:
        apply_changes(org, {"connections.telegram.bot_token": "123456:ABCDEF"})
        assert has_org_secret(org, "telegram_bot_token") is True       # written to the encrypted store
        cfg = get_config(org)
        # the readable config still holds only the REFERENCE, never the value
        assert _get_path(cfg, "connections.telegram.bot_token") == {"__secret__": "telegram_bot_token"}
    finally:
        _reset(org)


def test_accountant_domain_shown_and_editable():
    org = "twbtest_acc"
    _reset(org)
    try:
        body = create_app(org).test_client().get("/customer").get_data(as_text=True)
        assert "Accountant" in body and "Food allowance" in body and "Auto-dedup vendors" in body
        apply_changes(org, {"categories.accountant.food_money.rate_per_shift_hour_riel": "600"})  # PLANNED → editable
        assert _get_path(get_config(org), "categories.accountant.food_money.rate_per_shift_hour_riel") == 600
    finally:
        _reset(org)


def test_stock_domain_shown_and_editable():
    org = "twbtest_stk"
    _reset(org)
    try:
        body = create_app(org).test_client().get("/customer").get_data(as_text=True)
        assert "Stock" in body and "Compare supplier prices" in body and "How stock is counted" in body
        apply_changes(org, {"categories.stock.count_method": "barcode"})   # PLANNED → editable
        assert _get_path(get_config(org), "categories.stock.count_method") == "barcode"
    finally:
        _reset(org)


def test_customer_view_shows_health_warning():
    from core.tenant_config import set_config
    org = "twbtest_hb"
    _reset(org)
    try:
        set_config(org, {"categories": {"attendance": {"expertise": {"enabled": True, "roles": []}}}})
        body = create_app(org).test_client().get("/customer").get_data(as_text=True)
        assert "worth checking" in body and "Expertise" in body          # customer sees their own warning
        assert "SHADOW" not in body and "PLANNED" not in body            # still no internal badge leak
    finally:
        _reset(org)


def test_pos_and_hr_domains_shown_and_editable():
    org = "twbtest_dom"
    _reset(org)
    try:
        body = create_app(org).test_client().get("/customer").get_data(as_text=True)
        assert "POS" in body and "HR &amp; payroll" in body and "Pay cycle" in body and "Be the POS" in body
        apply_changes(org, {"categories.pos.mode": "tap_existing", "categories.hr_payroll.pay_cycle": "weekly"})
        cfg = get_config(org)
        assert _get_path(cfg, "categories.pos.mode") == "tap_existing"
        assert _get_path(cfg, "categories.hr_payroll.pay_cycle") == "weekly"
    finally:
        _reset(org)


def test_apply_rejects_bad_enum_and_clamps_int():
    org = "twbtest_wiz3"
    _reset(org)
    try:
        apply_changes(org, {"categories.attendance.ot.disposition": "hacker",      # bad enum → ignored
                            "categories.attendance.ot.min_block_min": "9999"})      # PLANNED int → clamp 120
        cfg = get_config(org)
        assert _get_path(cfg, "categories.attendance.ot.disposition") == "bank"     # unchanged default
        assert _get_path(cfg, "categories.attendance.ot.min_block_min") == 120
    finally:
        _reset(org)
