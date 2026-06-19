"""Pure-function tests for scripts/lane_guard.py.

ONLY the pure helpers (_decide / _gate_shared / _sibling_contention) are tested here — NEVER main(),
because main() appends to the real cross-lane event sink (~/.twbshop_lane_events.jsonl) and the monitor
would DM the owner our test inputs as if a lane really did them. (Learned the hard way.)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import lane_guard as lg  # noqa: E402

MAP = {
    "lanes": {"accountant": ["accountant/"], "gm": ["gm_bot/"], "stock": ["stock/"], "docs": ["docs/"]},
    "shared": ["shared/", "tests/", "parallel_lanes.json"],
}


# --- _decide: the ownership matrix ---------------------------------------------------------------
def test_own_lane_is_silent():
    assert lg._decide("accountant", "accountant/db.py", MAP, False)[0] == "silent"


def test_other_code_lane_blocks():
    assert lg._decide("accountant", "gm_bot/bot.py", MAP, False)[0] == "block"


def test_other_lane_with_ack_warns_not_blocks():
    assert lg._decide("accountant", "gm_bot/bot.py", MAP, True)[0] == "warn"


def test_docs_is_a_soft_lane_warns_never_blocks():
    assert lg._decide("accountant", "docs/anything.md", MAP, False)[0] == "warn"


def test_claude_md_is_hub_only_blocked_in_a_lane():
    assert lg._decide("gm", "CLAUDE.md", MAP, False)[0] == "block"


def test_claude_md_ack_downgrades_to_warn():
    assert lg._decide("gm", "CLAUDE.md", MAP, True)[0] == "warn"


def test_shared_file_yields_the_shared_mark():
    assert lg._decide("accountant", "shared/database.py", MAP, False) == ("warn", lg.SHARED_MARK)


def test_unowned_file_warns():
    v, c = lg._decide("accountant", "some_new_root_file.py", MAP, False)
    assert v == "warn" and c == "the SHARED / unowned area"


# --- _gate_shared: the new contention gate (the v4 change) ---------------------------------------
def test_lone_shared_edit_is_silent():
    # No other worktree is touching it -> a shared edit is fine, no noise.
    assert lg._gate_shared("warn", lg.SHARED_MARK, []) == ("silent", "")


def test_contended_shared_edit_warns_and_names_the_lane():
    v, c = lg._gate_shared("warn", lg.SHARED_MARK, ["gm"])
    assert v == "warn"
    assert "gm" in c and "CONTENTION" in c and "pull" in c


def test_gate_passes_block_through_untouched():
    assert lg._gate_shared("block", "GM", ["gm"]) == ("block", "GM")


def test_gate_passes_unowned_warn_through_untouched():
    # An unowned-file warn must stay a warn (it signals a map gap) even with no contention.
    assert lg._gate_shared("warn", "the SHARED / unowned area", []) == ("warn", "the SHARED / unowned area")


# --- _sibling_contention: must fail OPEN (a guard bug must never lock the workflow) ---------------
def test_sibling_contention_fails_open_on_bad_root():
    assert lg._sibling_contention("x.py", os.path.join(os.sep, "no", "such", "repo", "here")) == []
