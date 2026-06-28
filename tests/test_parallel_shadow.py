"""E (lean): the parallel-shadow / config-diff harness — run real check-in history through several grace
values at once. Structure + the human summary line (read-only; reuses core.whatif)."""
from core import parallel_shadow as ps


def test_matrix_shape_on_empty_org():
    from core.db import init_core_db, ensure_org
    init_core_db()
    ensure_org("pstest58", "PS", "Asia/Phnom_Penh")
    m = ps.verdict_matrix("pstest58", grace_values=(5, 9))
    assert [e["grace"] for e in m] == [5, 9]
    assert all(e["total"] == 0 and e["changed"] == 0 for e in m)     # no events → nothing reclassifies


def test_summary_lines_pure():
    matrix = [{"grace": 9, "early": 5, "total": 300, "changed": 4, "by_transition": {"late→on_time": 4}},
              {"grace": 3, "early": 5, "total": 300, "changed": 0, "by_transition": {}}]
    lines = ps.summary_lines(matrix)
    assert "grace  9" in lines[0] and "4/300" in lines[0] and "late→on_time 4" in lines[0]
    assert "no change" in lines[1]
