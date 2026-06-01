"""Tests for gm_bot/stock.py — daily stock-order brain (pure, no DB/AI)."""

from gm_bot import stock


# ── is_low ────────────────────────────────────────────────────────────────────

def test_is_low():
    assert stock.is_low(2, 1) is True
    assert stock.is_low(2, 2) is False        # at min is not low
    assert stock.is_low(2, 3) is False
    assert stock.is_low(None, 1) is False
    assert stock.is_low(2, None) is False


# ── suggest_order_qty ─────────────────────────────────────────────────────────

def test_order_qty_zero_when_not_low():
    assert stock.suggest_order_qty(2, 2) == 0
    assert stock.suggest_order_qty(2, 5) == 0


def test_order_qty_back_to_min_plus_buffer():
    # min 2, current 0 -> target 2*1.5=3 -> order 3
    assert stock.suggest_order_qty(2, 0) == 3
    # min 2, current 1 -> target 3 -> gap 2
    assert stock.suggest_order_qty(2, 1) == 2


def test_order_qty_uses_usage_when_higher():
    # min 2, current 0, usage 3/day, lead 2 -> min+usage*lead = 2+6 = 8 > 3 -> 8
    assert stock.suggest_order_qty(2, 0, usage_per_day=3) == 8


def test_order_qty_fractional_units_keep_decimals():
    # min 0.25 tin, current 0 -> target 0.375 -> gap < 1 -> keep 2dp
    q = stock.suggest_order_qty(0.25, 0)
    assert q == 0.38 or q == 0.37


# ── build_order_list + format ─────────────────────────────────────────────────

def test_build_order_list_filters_and_sorts():
    items = [
        {"item": "Almond Ground", "unit": "packs", "min_n": 2, "current_n": 1},   # short 1
        {"item": "Eggs", "unit": "pc", "min_n": 500, "current_n": 1570},          # not low
        {"item": "White sesame", "unit": "kg", "min_n": 1, "current_n": 0},       # short 1
        {"item": "Milk condensed", "unit": "cans", "min_n": 5, "current_n": 0},   # short 5
    ]
    rows = stock.build_order_list(items)
    names = [r["item"] for r in rows]
    assert "Eggs" not in names
    assert names[0] == "Milk condensed"          # biggest shortfall first
    assert set(names) == {"Milk condensed", "Almond Ground", "White sesame"}


def test_format_order_message():
    rows = [{"item": "Almond Ground", "unit": "packs", "qty": 3},
            {"item": "White sesame", "unit": "kg", "qty": 1}]
    msg = stock.format_order_message(rows)
    assert msg.splitlines()[0] == "Check if we need to order:"
    assert "- 3 packs  Almond Ground" in msg
    assert "- 1 kg  White sesame" in msg


def test_format_empty_is_none():
    assert stock.format_order_message([]) is None


# ── no-sheet escalation ───────────────────────────────────────────────────────

def test_no_sheet_decision():
    assert stock.no_sheet_decision(0) == "reuse"
    assert stock.no_sheet_decision(1) == "reuse"
    assert stock.no_sheet_decision(2) == "escalate"
    assert stock.no_sheet_decision(3) == "escalate"


# ── usage trend ───────────────────────────────────────────────────────────────

def test_usage_trend():
    assert stock.usage_trend(10, 10) == "steady"
    assert stock.usage_trend(6, 10) == "declining"      # 40% down
    assert stock.usage_trend(15, 10) == "rising"
    assert stock.usage_trend(None, 10) == "unknown"
    assert stock.usage_trend(5, 0) == "unknown"


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception as e:
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
