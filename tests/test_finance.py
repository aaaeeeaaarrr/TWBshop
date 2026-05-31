"""Tests for gm_bot/finance.py — REPORT daily-books parser. Pure, no DB."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from gm_bot import finance

PP = ZoneInfo("Asia/Phnom_Penh")

# ── Real reports from the REPORT group ──────────────────────────────────────────
REPORT_27 = """27/05/2026
Cash on hand : $ 600
cash income. : $ 17.95
Aba income    : $ 379.87
total sales       : $ 397.82
Cash expense: $ 189.34
ABA Expense:  $ 135
Total                 : $ 428.51
Cash count.   :$ 428.84
Over                 :$ 0.33"""

REPORT_28 = """28/05/2026
Cash on hand : $ 600
cash income. : $ 110.80
Aba income    : $ 1,109.78
total sales       : $ 1,220.58
Cash expense: $ 207.14
ABA Expense:  $ 135.00
Total                 : $ 503.66
Cash count.   :$ 504.00
Over                 :$ 0.34"""

REPORT_30 = """30/05/2026
Cash on hand : $ 600
cash income. : $ 97.35
Aba income    : $ 1,351.92
total sales       : $ 1,449.27
Cash expense: $ 373.18
ABA Expense:  $ 0
Total                 : $ 324.17
Cash count.   :$  323.75
Lost                 :$ 0.42"""


def test_parse_fields():
    p = finance.parse_report_text(REPORT_28)
    assert p["cash_on_hand"] == 600
    assert p["cash_income"] == 110.80
    assert p["aba_income"] == 1109.78          # comma stripped
    assert p["total_sales"] == 1220.58
    assert p["cash_expense"] == 207.14
    assert p["aba_expense"] == 135.00
    assert p["stated_total"] == 503.66
    assert p["cash_count"] == 504.00
    assert p["over"] == 0.34
    assert p["stated_date"] == "2026-05-28"


def test_total_not_stolen_by_total_sales():
    # 'Total' must not be parsed as 'total sales' and vice-versa
    p = finance.parse_report_text(REPORT_28)
    assert p["total_sales"] == 1220.58
    assert p["stated_total"] == 503.66


def test_lost_field():
    p = finance.parse_report_text(REPORT_30)
    assert p["lost"] == 0.42
    assert "over" not in p


def test_recompute_28_reconciles():
    p = finance.parse_report_text(REPORT_28)
    c = finance.recompute(p)
    assert c["expected_drawer"] == 503.66
    assert c["over_lost_computed"] == 0.34
    assert abs(c["sales_check"]) < 0.05
    assert c["math_ok"] is True


def test_recompute_30_reconciles():
    p = finance.parse_report_text(REPORT_30)
    c = finance.recompute(p)
    assert c["expected_drawer"] == 324.17
    assert c["over_lost_computed"] == -0.42      # shortfall
    assert c["math_ok"] is True


def test_recompute_27_catches_staff_math_error():
    # 600 + 17.95 - 189.34 = 428.61, staff wrote 428.51 -> off by 0.10
    p = finance.parse_report_text(REPORT_27)
    c = finance.recompute(p)
    assert c["expected_drawer"] == 428.61
    assert c["total_math_error"] == 0.10
    assert c["math_ok"] is False
    assert c["notes"]


def test_business_day_dawn_final_files_under_previous_day():
    # 05:08 on the 28th closes the window that started 06:00 on the 27th
    posted = datetime(2026, 5, 28, 5, 8, tzinfo=PP)
    assert finance.business_day_for(posted).isoformat() == "2026-05-27"
    assert finance.classify_report(posted) == "final"


def test_business_day_afternoon_mid_is_same_day():
    posted = datetime(2026, 5, 27, 16, 13, tzinfo=PP)
    assert finance.business_day_for(posted).isoformat() == "2026-05-27"
    assert finance.classify_report(posted) == "mid"


def test_business_day_handles_utc_input():
    # 22:08 UTC == 05:08 PP next day -> still files under the 27th, still final
    posted = datetime(2026, 5, 27, 22, 8, tzinfo=timezone.utc)
    assert finance.business_day_for(posted).isoformat() == "2026-05-27"
    assert finance.classify_report(posted) == "final"


def test_final_recognised_at_455():
    # 4:55 is before 06:00 -> still the dawn final, not a hard 5:00 rule
    posted = datetime(2026, 5, 28, 4, 55, tzinfo=PP)
    assert finance.classify_report(posted) == "final"
    assert finance.business_day_for(posted).isoformat() == "2026-05-27"


def test_is_daily_report_true_for_report():
    assert finance.is_daily_report(finance.parse_report_text(REPORT_27)) is True


def test_is_daily_report_false_for_chatter():
    for chatter in ["Yes sir confirmed thanks", "Good morning boss", "ok", ""]:
        assert finance.is_daily_report(finance.parse_report_text(chatter)) is False


def test_spacing_and_caps_variation():
    weird = "CASH INCOME:$110.80\nABA INCOME : $1,109.78\nTOTAL SALES:$1220.58"
    p = finance.parse_report_text(weird)
    assert p["cash_income"] == 110.80
    assert p["aba_income"] == 1109.78
    assert p["total_sales"] == 1220.58


def test_format_correction_shows_full_working():
    p = finance.parse_report_text(REPORT_27)
    c = finance.recompute(p)
    msg = finance.format_correction(p, c)
    assert msg is not None
    # the actual arithmetic must be shown
    for token in ("600.00", "17.95", "189.34", "428.61", "428.51"):
        assert token in msg


def test_format_correction_none_when_reconciles():
    p = finance.parse_report_text(REPORT_28)
    c = finance.recompute(p)
    assert finance.format_correction(p, c) is None


def test_tight_tolerance_catches_one_cent():
    # 1c discrepancy must now flag (staff count to the cent at fixed 4000:1)
    text = ("01/06/2026\nCash on hand: $600\ncash income: $100.00\n"
            "Cash expense: $50.00\nTotal: $649.99\nCash count: $650.00")
    p = finance.parse_report_text(text)
    c = finance.recompute(p)
    assert c["expected_drawer"] == 650.00
    assert c["math_ok"] is False
    assert abs(c["total_math_error"] - 0.01) < 1e-9


def test_parse_full_end_to_end():
    posted = datetime(2026, 5, 28, 5, 8, tzinfo=PP)
    full = finance.parse_full(REPORT_28, posted)
    assert full["business_day"] == "2026-05-27"
    assert full["report_kind"] == "final"
    assert full["raw"]["cash_count"] == 504.00
    assert full["computed"]["math_ok"] is True
