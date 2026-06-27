"""core.ask_change — natural-language config tweaks → a vibe-preset change proposal. The parser is pure
(no DB); the wizard confirm card is GET-only here (it must NEVER mutate config without the POST confirm)."""
from core import ask_change, presets
import wizard.app as wa
from wizard.app import create_app


# ── the parser (pure) ─────────────────────────────────────────────────────────
def test_make_lateness_stricter():
    c = ask_change.parse_change("make lateness stricter")
    assert c and c["group"] == "lateness" and c["vibe"] == "strict"


def test_relax_overtime_maps_to_generous():
    c = ask_change.parse_change("relax the overtime cap")
    assert c and c["group"] == "overtime" and c["vibe"] == "generous"   # overtime uses capped/balanced/generous


def test_negation_less_strict_is_relaxed():
    c = ask_change.parse_change("make leave less strict")
    assert c and c["group"] == "leave" and c["vibe"] == "relaxed"       # "less strict" must NOT read as strict


def test_negation_less_lenient_is_strict():
    c = ask_change.parse_change("make leave less lenient")
    assert c and c["group"] == "leave" and c["vibe"] == "strict"


def test_swaps_and_chase_vocab():
    assert ask_change.parse_change("loosen the swap rule")["vibe"] == "flexible"     # swaps end = flexible
    assert ask_change.parse_change("make chasing persistent")["vibe"] == "persistent"
    assert ask_change.parse_change("set chasing to gentle")["vibe"] == "gentle"


def test_reset_to_normal_is_balanced():
    c = ask_change.parse_change("reset leave to normal")
    assert c and c["vibe"] == "balanced"


def test_every_proposed_vibe_is_a_real_preset():
    # safety: the parser can ONLY ever name a vibe that actually exists in core.presets (no arbitrary write).
    for phrase in ("make lateness stricter", "relax overtime", "make leave less strict",
                   "loosen swaps", "make chasing persistent", "reset lateness to normal"):
        c = ask_change.parse_change(phrase)
        assert c["vibe"] in presets.ATTENDANCE_PRESETS[c["group"]]["vibes"]


def test_questions_are_not_changes():
    # a QUESTION (no imperative) or an unscoped/empty phrase must NOT be read as a change → None (→ ask path).
    for phrase in ("how many late this week", "is lateness strict", "make a report on lateness",
                   "make it stricter", "who is working today", ""):
        assert ask_change.parse_change(phrase) is None


# ── the wizard confirm card (GET-only — proves no silent write) ────────────────
def test_ask_change_shows_confirm_card_without_mutating(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    from core.tenant_config import get_config
    before = get_config("twb")["categories"]["attendance"]["verdict"].get("grace_min")
    c = create_app("twb").test_client()
    page = c.get("/ask?q=make+lateness+stricter").get_data(as_text=True)
    assert "Change a setting" in page                       # the confirm card rendered
    assert "action='/presets/apply'" in page                # Apply posts to the audited preset route
    assert "name='group' value='lateness'" in page and "name='vibe' value='strict'" in page
    after = get_config("twb")["categories"]["attendance"]["verdict"].get("grace_min")
    assert before == after                                  # a GET proposes only — it changes NOTHING
