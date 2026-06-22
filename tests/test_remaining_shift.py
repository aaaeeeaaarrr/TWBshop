"""gm_bot.attendance.remaining_shift_min — the leave-early payback tail ("pay-back from now")."""
from datetime import datetime, timezone, timedelta

from gm_bot.attendance import remaining_shift_min

PP = timezone(timedelta(hours=7))   # Phnom Penh (no DST) — same offset as ZoneInfo for these comparisons


def test_long_jun21_remaining_is_302_not_540():
    # overnight 21:00–06:00 (ws=1260, 540 min); reported sick 00:58:15 PP → ~302 left (NOT the full 540)
    now = datetime(2026, 6, 22, 0, 58, 15, tzinfo=PP)
    assert remaining_shift_min(1260, 540, "2026-06-21", now) == 302


def test_clamps_to_zero_and_full():
    # at start → full shift remaining; at/after end → 0
    assert remaining_shift_min(1260, 540, "2026-06-21", datetime(2026, 6, 21, 21, 0, tzinfo=PP)) == 540
    assert remaining_shift_min(1260, 540, "2026-06-21", datetime(2026, 6, 22, 6, 0, tzinfo=PP)) == 0
    assert remaining_shift_min(1260, 540, "2026-06-21", datetime(2026, 6, 22, 9, 0, tzinfo=PP)) == 0
    # day shift 06:00–15:00, reported at noon → 180 left
    assert remaining_shift_min(360, 540, "2026-06-21", datetime(2026, 6, 21, 12, 0, tzinfo=PP)) == 180
