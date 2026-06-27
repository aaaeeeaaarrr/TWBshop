"""core.policy — per-setting RESPONSIBILITY microcopy + the /policy page: the lean alternative to a hated
'click I agree' wall. A plain one-liner under each setting (responsibility sits with the client) + a terms page."""
from core import policy, presets
import wizard.app as wa
from wizard.app import create_app


def test_every_vibe_group_has_a_responsibility_line():
    for g in presets.ATTENDANCE_PRESETS:
        assert policy.GROUP_POLICY.get(g), g          # no vibe group ships without its responsibility one-liner


def test_setting_policy_lookup():
    assert "your call" in policy.setting_policy("categories.attendance.ot.bank_cap_min")
    assert policy.setting_policy("nope.nope") == ""   # unknown setting → no line (graceful)


def test_presets_and_policy_pages_show_responsibility(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    c = create_app("twb").test_client()
    pres = c.get("/presets").get_data(as_text=True)
    assert "your policy to set" in pres                # the per-group light-grey line
    assert "Terms &amp; responsibility" in pres        # the footer link
    assert "responsible for outcomes arising" in c.get("/policy").get_data(as_text=True)  # the terms page


def test_config_editor_shows_setting_policy(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    c = create_app("twb").test_client()
    page = c.get("/customer/config").get_data(as_text=True)
    assert "Set the late-grace window to your policy" in page   # grace_min's responsibility line, in the editor
