"""Level-1 reconciliation — pure logic, real numbers from the 5 hand-verified days."""
from gm_bot.reconcile import checks_for_day, format_summary, pick_docs

SHEET_TUE = {"doc_type": "expense_sheet",
             "fields": {"day_cash_expense": 155.04, "night_cash_expense": None,
                        "aba_expense": 192.75}}
POS_TUE = {"doc_type": "pos_screen",
           "fields": {"pos_kind": "work_period", "grand_total": 1349.96}}
MID_TUE = {"report_kind": "mid", "cash_expense": 155.04, "aba_expense": 192.75}
FINAL_TUE = {"report_kind": "final", "cash_expense": 217.15, "aba_expense": 192.75,
             "total_sales": 1349.96}


def _by_name(checks):
    return {c["name"]: c for c in checks}


def test_tuesday_all_ok():
    checks = _by_name(checks_for_day(MID_TUE, FINAL_TUE, [SHEET_TUE, POS_TUE]))
    assert checks["Cash sheet vs mid report"]["status"] == "ok"
    assert checks["ABA sheet vs report"]["status"] == "ok"
    assert checks["POS total vs final sales"]["status"] == "ok"


def test_friday_typo_caught():
    # staff typed 16,676.12; POS showed 1,676.12
    final = {"report_kind": "final", "cash_expense": 223.31, "aba_expense": 3429.16,
             "total_sales": 16676.12}
    pos = {"doc_type": "pos_screen", "fields": {"pos_kind": "work_period", "grand_total": 1676.12}}
    checks = _by_name(checks_for_day(None, final, [pos]))
    assert checks["POS total vs final sales"]["status"] == "mismatch"


def test_day_plus_night_vs_final():
    sheet = {"doc_type": "expense_sheet",
             "fields": {"day_cash_expense": 155.04, "night_cash_expense": 62.11,
                        "aba_expense": 192.75}}
    checks = _by_name(checks_for_day(MID_TUE, FINAL_TUE, [sheet, POS_TUE]))
    assert checks["Cash sheet (day+night) vs final"]["status"] == "ok"


def test_missing_docs_reported_not_crashed():
    checks = checks_for_day(MID_TUE, FINAL_TUE, [])
    assert all(c["status"] == "missing" for c in checks)
    text = format_summary("2026-06-02", checks)
    assert "no data" in text


def test_string_numbers_and_commas_parse():
    sheet = {"doc_type": "expense_sheet", "fields": {"aba_expense": "3,429.16"}}
    final = {"report_kind": "final", "aba_expense": "3429.16", "total_sales": None}
    checks = _by_name(checks_for_day(None, final, [sheet]))
    assert checks["ABA sheet vs report"]["status"] == "ok"


def test_pick_docs_prefers_work_period_and_latest_sheet():
    summary = {"doc_type": "pos_screen", "fields": {"pos_kind": "summary", "grand_total": 1534.12}}
    older = {"doc_type": "expense_sheet", "fields": {"day_cash_expense": 1.0}}
    sheet, pos = pick_docs([older, summary, SHEET_TUE, POS_TUE])
    assert sheet["day_cash_expense"] == 155.04   # latest usable sheet wins
    assert pos["grand_total"] == 1349.96         # work_period beats summary


def test_format_summary_flags_mismatch_count():
    final = {"report_kind": "final", "total_sales": 100.0, "aba_expense": 5.0}
    pos = {"doc_type": "pos_screen", "fields": {"pos_kind": "work_period", "grand_total": 90.0}}
    text = format_summary("2026-06-05", checks_for_day(None, final, [pos]))
    assert "⚠️ 1 mismatch" in text and "❌" in text
