"""/att owner snapshot — the pure formatter + minute helpers (owner Jun 16, read-only command)."""
from gm_bot.bot import _fmt_att_snapshot, _att_hm, _att_overdue


def test_minute_and_overdue_helpers():
    assert _att_hm(720) == "12:00"
    assert _att_hm(1320) == "22:00"
    assert _att_hm(1380 + 60) == "00:00"   # overnight end wraps past midnight
    assert _att_overdue(45) == "(45m ago)"
    assert _att_overdue(185) == "(3h 5m ago)"


def test_formatter_groups_and_counts():
    b = {
        "stuck": [("Chomreun", 1080, 185), ("Vannary", 1200, 60)],
        "onshift": [("Norin", "11:40", 1380)],
        "out": [("Sony", "06:01", "15:01"), ("Visal", "06:00", "15:02")],
        "notin": [("Dara", 1020)],
        "absent": [],
        "upcoming": [],
    }
    s = _fmt_att_snapshot(b, "Tue 16/06 · 21:03 PP")
    # stuck sorted worst-first, with overdue
    assert "⏰ Past shift-end, NOT checked out (2)" in s
    assert s.index("Chomreun") < s.index("Vannary")
    assert "ended 18:00 (3h 5m ago)" in s
    assert "🟢 Still on shift (1)" in s
    assert "✅ Checked out (2)" in s
    assert "❓ On shift now, never checked in (1)" in s
    # counts: expected = 2 stuck + 1 onshift + 2 out + 1 notin = 6; in = 5; missing = 1
    assert "6 expected · 5 in · 2 out · 2 stuck · 1 missing" in s


def test_empty_buckets_drop_out():
    b = {"stuck": [], "onshift": [], "out": [("Sony", "06:01", "15:01")],
         "notin": [], "absent": [], "upcoming": []}
    s = _fmt_att_snapshot(b, "now")
    assert "Past shift-end" not in s          # empty groups hidden
    assert "✅ Checked out (1)" in s
    assert "1 expected · 1 in · 1 out · 0 stuck · 0 missing" in s
