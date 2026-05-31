"""
REPORT-group daily-books parser.

Turns the staff's free-text daily total into structured numbers, recomputes the
drawer math, and attributes the report to the correct business day + shift.

Pure functions only — no DB, no API. Easy to unit-test.

Decoded model (verified on live reports):
    total sales      = cash income + ABA income
    expected drawer  = cash-on-hand float + cash income - cash expense
    Over / Lost      = cash count - expected drawer   (Over = surplus, Lost = short)
    ABA money never touches the cash-drawer reconciliation (bank-app, tracked apart).

Business day = 06:00 -> 06:00 (Phnom Penh). A timestamp belongs to:
    date(t)        if t.hour >= 6
    date(t) - 1day if t.hour <  6   (the dawn 'final' closes the day that just ended)

So a final posted 05:08 on the 28th files under business day = 27th, exactly as the
owner wants ("the day that just closed"). 4:55, 5:10 — it's the time RANGE, not a
hard clock value, so the close is recognised whenever it lands before 06:00.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

PP_TZ = ZoneInfo("Asia/Phnom_Penh")

# Tolerance for "their arithmetic is internally consistent" (cents-level rounding).
MATH_TOLERANCE = 0.05

# Hour (PP) before which a report is treated as the dawn 'final' close.
FINAL_CLOSE_BEFORE_HOUR = 6

# ── Label aliases ───────────────────────────────────────────────────────────────
# Each canonical field maps to the substrings that may appear before the ':' .
# Order matters: more specific labels (total sales) are checked before generic (total).
_FIELD_ALIASES: list[tuple[str, tuple[str, ...]]] = [
    ("cash_on_hand", ("cash on hand", "cash onhand", "float")),
    ("cash_income",  ("cash income", "cash in", "cashincome")),
    ("aba_income",   ("aba income", "aba in", "abaincome")),
    ("total_sales",  ("total sales", "total sale", "totalsales")),
    ("cash_expense", ("cash expense", "cash ex", "cash exp", "cashexpense")),
    ("aba_expense",  ("aba expense", "aba ex", "aba exp", "abaexpense")),
    ("cash_count",   ("cash count", "cashcount", "count")),
    ("over",         ("over",)),
    ("lost",         ("lost", "loss", "short", "shortage")),
    # 'total' is generic — must be matched LAST so it never steals 'total sales'.
    ("stated_total", ("total",)),
]

_DATE_RE = re.compile(r"\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{2,4})\b")
# A numeric token: optional minus, thousands commas, decimals. Strips $ ៛ and spaces.
_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _parse_number(value_part: str) -> float | None:
    """Pull the numeric amount out of the part after ':' . Returns None if none."""
    cleaned = value_part.replace("$", " ").replace("៛", " ").replace("B", " ")
    matches = _NUM_RE.findall(cleaned)
    if not matches:
        return None
    # Take the last number on the line (label sometimes contains digits).
    raw = matches[-1].replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _match_field(label: str) -> str | None:
    """Map a normalised label (lowercased, before ':') to a canonical field."""
    norm = label.strip().lower().rstrip(". ").strip()
    for field, aliases in _FIELD_ALIASES:
        for alias in aliases:
            if alias in norm:
                return field
    return None


_MONEY_FIELDS = {
    "cash_on_hand", "cash_income", "aba_income", "total_sales", "cash_expense",
    "aba_expense", "stated_total", "cash_count", "over", "lost",
}


def is_daily_report(parsed: dict) -> bool:
    """
    True if a parsed message looks like a daily books report (>= 3 money fields).
    Casual chatter parses to 0 money fields; a real report has ~9.
    """
    found = set(parsed.get("fields_found", []))
    return len(found & _MONEY_FIELDS) >= 3


def parse_report_text(text: str) -> dict:
    """
    Parse a daily-report message into raw fields.

    Returns a dict with any of: stated_date, cash_on_hand, cash_income, aba_income,
    total_sales, cash_expense, aba_expense, stated_total, cash_count, over, lost.
    Missing fields are simply absent. `fields_found` lists what was parsed.
    """
    out: dict = {}
    found: list[str] = []

    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue

        # Date line (anywhere a DD/MM/YYYY appears and no ':' value yet).
        if "stated_date" not in out:
            m = _DATE_RE.search(line)
            if m and ":" not in line:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if y < 100:
                    y += 2000
                try:
                    out["stated_date"] = date(y, mo, d).isoformat()
                    found.append("stated_date")
                    continue
                except ValueError:
                    pass

        if ":" not in line:
            continue
        label, _, value_part = line.partition(":")
        field = _match_field(label)
        if not field or field in out:
            continue
        num = _parse_number(value_part)
        if num is None:
            continue
        out[field] = num
        found.append(field)

    out["fields_found"] = found
    return out


def business_day_for(posted: datetime) -> date:
    """
    The business day (06:00->06:00 PP) a timestamp belongs to.
    Before 06:00 -> the previous calendar date (the day that just closed).
    """
    if posted.tzinfo is not None:
        posted = posted.astimezone(PP_TZ)
    if posted.hour < FINAL_CLOSE_BEFORE_HOUR:
        return (posted - timedelta(days=1)).date()
    return posted.date()


def classify_report(posted: datetime) -> str:
    """
    'final' for the dawn close (posted before 06:00 PP), else 'mid' (daytime checkpoint).
    Time RANGE, not a hard clock value — 4:55 or 5:10 both read as the final close.
    """
    if posted.tzinfo is not None:
        posted = posted.astimezone(PP_TZ)
    return "final" if posted.hour < FINAL_CLOSE_BEFORE_HOUR else "mid"


def recompute(parsed: dict) -> dict:
    """
    Recompute the drawer math from raw fields and check it against what staff wrote.

    Returns:
        expected_drawer        : float | None  (float + cash in - cash out)
        over_lost_computed     : float | None  (cash count - expected; + = over, - = lost)
        sales_check            : float | None  (cash in + aba in - stated total sales)
        total_math_error       : float | None  (expected drawer - stated 'Total')
        math_ok                : bool          (both checks within MATH_TOLERANCE)
        notes                  : list[str]     (human-readable issues found)
    """
    notes: list[str] = []
    cash_on_hand = parsed.get("cash_on_hand")
    cash_income  = parsed.get("cash_income")
    aba_income   = parsed.get("aba_income")
    total_sales  = parsed.get("total_sales")
    cash_expense = parsed.get("cash_expense")
    stated_total = parsed.get("stated_total")
    cash_count   = parsed.get("cash_count")

    result: dict = {
        "expected_drawer": None,
        "over_lost_computed": None,
        "sales_check": None,
        "total_math_error": None,
        "math_ok": True,
        "notes": notes,
    }

    # Drawer = float + cash in - cash out
    if cash_on_hand is not None and cash_income is not None and cash_expense is not None:
        expected = round(cash_on_hand + cash_income - cash_expense, 2)
        result["expected_drawer"] = expected

        if cash_count is not None:
            result["over_lost_computed"] = round(cash_count - expected, 2)

        if stated_total is not None:
            err = round(expected - stated_total, 2)
            result["total_math_error"] = err
            if abs(err) > MATH_TOLERANCE:
                result["math_ok"] = False
                notes.append(
                    f"Drawer total mismatch: staff wrote {stated_total:.2f}, "
                    f"recomputed {expected:.2f} (off by {err:+.2f})."
                )

    # total sales = cash income + aba income
    if cash_income is not None and aba_income is not None and total_sales is not None:
        check = round((cash_income + aba_income) - total_sales, 2)
        result["sales_check"] = check
        if abs(check) > MATH_TOLERANCE:
            result["math_ok"] = False
            notes.append(
                f"Sales mismatch: cash {cash_income:.2f} + ABA {aba_income:.2f} "
                f"= {cash_income + aba_income:.2f}, staff wrote {total_sales:.2f} "
                f"(off by {check:+.2f})."
            )

    return result


def parse_full(text: str, posted: datetime) -> dict:
    """
    Convenience: parse + classify + attribute + recompute in one call.
    Returns a single dict ready to store.
    """
    parsed = parse_report_text(text)
    computed = recompute(parsed)
    bday = business_day_for(posted)
    kind = classify_report(posted)
    return {
        "business_day": bday.isoformat(),
        "report_kind": kind,
        "raw": parsed,
        "computed": computed,
    }
