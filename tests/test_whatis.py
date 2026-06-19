"""Smoke guard for scripts/whatis.py — the one-call map/registry lookup (read-only).

Locks the three pure finders + the exit contract so the lookup can't silently rot. Writes nothing.
"""
import os
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, _SCRIPTS)
import facts  # noqa: E402
import whatis  # noqa: E402


def test_matching_facts_finds_a_real_key():
    a_key = next(iter(facts.load()))
    # the topic = the key itself must match that key
    assert a_key in whatis._matching_facts(a_key.lower())


def test_map_blocks_returns_an_area_for_a_known_topic():
    blocks = whatis._map_blocks("attendance")
    assert blocks and all(b.startswith("## ") for b in blocks)


def test_points_lookup_surfaces_the_two_systems_gotcha():
    """The exact slip that started all this: a 'points' lookup must surface the don't-confuse gotcha."""
    blocks = whatis._map_blocks("points")
    assert any("DON'T confuse" in b or "DORMANT" in b for b in blocks)


def test_exit_contract():
    assert whatis.main([]) == 2                       # no arg
    assert whatis.main(["zz-no-such-topic-zz"]) == 1  # no hit
    assert whatis.main(["expense"]) == 0              # a real hit (registry + map)
