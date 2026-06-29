"""core.transitions — the universal OLD-vs-NEW cut-over comparison log (owner law 2026-06-29: keep older
data so every transition is provable by comparison). Append-only + best-effort. Tests are accumulation-safe
(delta-based / marker-based) since the staging table persists across runs."""
from core import transitions as tr


def test_note_and_recent_roundtrip():
    tr.init_transitions_db()
    org = "trtest_recent"
    tr.note(org, "route:al_approver", 101, old=[1, 2], new=[28], detail="MARKER_rerouted")
    rows = tr.recent(org, "route:al_approver", n=20)
    assert any(r["detail"] == "MARKER_rerouted" and r["new_val"] == "[28]" and r["old_val"] == "[1, 2]"
               for r in rows)


def test_summary_classifies_matched_mismatched_uncomparable():
    tr.init_transitions_db()
    org = "trtest_summary"
    before = tr.summary(org)
    tr.note(org, "k", 1, old="a", new="a", matched=True)
    tr.note(org, "k", 2, old="a", new="b", matched=False)
    tr.note(org, "k", 3, old="x", new="y")              # reroute → not a parity equality (matched=None)
    after = tr.summary(org)
    assert after["matched"] == before["matched"] + 1
    assert after["mismatched"] == before["mismatched"] + 1
    assert after["uncomparable"] == before["uncomparable"] + 1
    assert after["total"] == before["total"] + 3


def test_note_is_best_effort_and_json_encodes_dicts():
    tr.init_transitions_db()
    org = "trtest_be"
    tr.note(org, "k", None, old=None, new=None)          # all-None must not raise
    tr.note(org, "k", 7, old={"a": 1}, new={"a": 2}, matched=False)
    rows = tr.recent(org, "k", n=10)
    assert any(r["old_val"] == '{"a": 1}' and r["new_val"] == '{"a": 2}' for r in rows)
