"""core.presets — VIBE presets: one tap sets a knob cluster to a feeling; 'balanced' == the DEFAULTS
(behaviour-preserving); current_vibe detects the active vibe or 'custom' (the Customize door)."""
import core.db as cdb
from shared.database import _db
from core import presets
from core.tenant_config import get_config, set_config

ORG = "test_presets"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))


def test_balanced_equals_defaults():
    _reset()
    try:
        for g in presets.ATTENDANCE_PRESETS:                    # the DEFAULTS map to a recognised vibe (not 'custom')
            expected = "off" if g == "responsiveness" else "balanced"   # comms is an opt-in feature → OFF by default
            assert presets.current_vibe(ORG, g) == expected, g
    finally:
        _reset()


def test_apply_vibe_moves_the_whole_cluster():
    _reset()
    try:
        knobs = presets.apply_vibe(ORG, "lateness", "strict")
        assert knobs == {"grace_min": 0, "early_bonus_min": 3}
        v = get_config(ORG)["categories"]["attendance"]["verdict"]
        assert v["grace_min"] == 0 and v["early_bonus_min"] == 3       # cluster moved together, one tap
        assert presets.current_vibe(ORG, "lateness") == "strict"        # detected
        assert presets.apply_vibe(ORG, "lateness", "nope") is None      # unknown vibe rejected
    finally:
        _reset()


def test_apply_swaps_vibe_live_path():
    _reset()
    try:
        presets.apply_vibe(ORG, "swaps", "flexible")            # the swap rule the gm reads live
        sc = get_config(ORG)["categories"]["attendance"]["schedule"]
        assert sc["swap_partner_rule"] == "overlap" and sc["swap_overlap_pct"] == 25
        assert presets.current_vibe(ORG, "swaps") == "flexible"
    finally:
        _reset()


def test_vibe_caption_plain_words():
    assert presets.vibe_caption("lateness", "strict") == "0 min grace · +3 min early"
    assert presets.vibe_caption("overtime", "generous") == "20h OT cap"
    assert presets.vibe_caption("swaps", "strict") == "start window · 120-min window"
    assert presets.vibe_caption("approval_chase", "gentle") == "chase every 12h · up to 2×"


def test_hand_tuned_reads_as_custom():
    _reset()
    try:
        set_config(ORG, {"categories": {"attendance": {"verdict": {"grace_min": 9}}}})  # an off-preset value
        assert presets.current_vibe(ORG, "lateness") == "custom"        # → 'custom' (the granular Customize door)
    finally:
        _reset()


def test_presets_page_renders_and_applies(monkeypatch):
    import wizard.app as wa
    from wizard.app import create_app
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        c = create_app(ORG).test_client()
        assert "Set the vibe" in c.get("/presets").get_data(as_text=True)
        c.post("/presets/apply", data={"group": "overtime", "vibe": "generous"})
        assert presets.current_vibe(ORG, "overtime") == "generous"      # one tap moved the cluster, live
    finally:
        _reset()
