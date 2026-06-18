"""accountant/capture.py — P1 capture pure logic (no Telegram, no DB, fully unit-testable).

The LIVING RECEIPT CARD + the tax-tolerant math check + doc-type routing. The bot layer
(accountant/bot.py) turns the (label, callback) tuples here into Telegram buttons and owns
the DB writes; everything in this file is pure so it can be proven without a token.

Card lifecycle (design §E1):  DRAFT(captured) → CONFIRMED(confirmed) → [💵 cash | 🏦 ABA] → PAID
"""
import re

_AMT_RE = re.compile(r"(\d[\d,]*\.\d{2})")

STATUS_LABEL = {
    "captured": "DRAFT",
    "confirmed": "CONFIRMED",
    "paid": "PAID",
    "disputed": "DISPUTED",
    "void": "VOID",
}


def fmt_money(cents, currency="USD"):
    """Canonical USD display. None → '?'. (Riel is stored converted; orig kept for the card.)"""
    if cents is None:
        return "?"
    return f"${cents / 100:,.2f}"


def math_check(items_total_cents, printed_total_cents, tol_pct=8.0, tol_floor_cents=50):
    """Tax-tolerant: items summed vs the printed total. VAT/delivery/rounding make items run a
    little under the printed total, so allow a band; only SHOW a gap, never block (design §E1).
    Returns (ok, message). Unknown inputs → (True, '') (can't check, don't cry wolf)."""
    if items_total_cents is None or printed_total_cents is None:
        return True, ""
    diff = abs(items_total_cents - printed_total_cents)
    tol = max(tol_floor_cents, printed_total_cents * tol_pct / 100.0)
    if diff <= tol:
        return True, ""
    return False, (f"⚠ items add to {fmt_money(items_total_cents)} but receipt says "
                   f"{fmt_money(printed_total_cents)} — check the paper")


def parse_amount_cents(text):
    """Best-effort total from assess_receipt_photo's readable_partial — the total is usually the
    largest money figure on the slip. None if nothing parseable (→ card asks for ✏️ Fix). USD only
    for now; Riel handwritten receipts fall through to a manual type-in. A heuristic, never trusted
    blindly — the confirm + ✏️ Fix gate is the safety net."""
    if not text:
        return None
    nums = [float(m.replace(",", "")) for m in _AMT_RE.findall(text)]
    if not nums:
        return None
    return int(round(max(nums) * 100))


def route(assess: dict) -> str:
    """Map an assess_receipt_photo result to the capture action.
    'receipt' → ledger row; 'expense_sheet'/'pos_screen' → the report engine; 'other' → ignore."""
    if not assess.get("is_receipt") and assess.get("doc_type", "other") == "other":
        return "other"
    return assess.get("doc_type", "other")


def render_card(r: dict) -> str:
    """The living status card text for a receipt row `r` (keys: id, vendor_name, amount_cents,
    orig_currency, orig_amount, pay_method, status, items_text, is_handwritten, issues, math_msg)."""
    vendor = r.get("vendor_name") or "❓ vendor?"
    amt = fmt_money(r.get("amount_cents"))
    if (r.get("orig_currency") or "USD") != "USD" and r.get("orig_amount") is not None:
        amt += f"  ({r['orig_amount']:g} {r['orig_currency']})"
    pm = r.get("pay_method")
    pay = {"cash": "💵 Cash", "aba": "🏦 ABA"}.get(pm, "❔ method?")
    status = r.get("status", "captured")
    state = {"paid": "✅ paid", "confirmed": ("⏳ unpaid" if pm == "aba" else "confirmed"),
             "captured": "draft", "disputed": "🚩 disputed", "void": "void"}.get(status, status)

    lines = [f"🧾 #{r.get('id', '?')} · {vendor} · {amt} · {pay} · {state}"]
    if r.get("items_text"):
        lines.append(f"Items: {r['items_text']}")
    if r.get("math_msg"):
        lines.append(r["math_msg"])
    if r.get("is_handwritten"):
        lines.append("✍️ handwritten")
    for issue in (r.get("issues") or []):
        lines.append(f"• {issue}")
    if r.get("amount_cents") is None:
        lines.append("❗ amount not read — tap ✏️ Fix to type it (the books need the number)")
    return "\n".join(lines)


def card_buttons(r: dict):
    """Inline buttons for the current status, as (label, callback_data) rows.
    callback_data = 'acc:<action>:<id>'. ✏️ Fix is ALWAYS present (persistent edit, §E1)."""
    rid = r.get("id")
    status = r.get("status", "captured")
    pm = r.get("pay_method")
    rows = []
    if status == "captured":
        rows.append([("✅ Looks right", f"acc:ok:{rid}")])
        rows.append([("🏦 For ABA", f"acc:aba:{rid}"), ("💵 Cash-paid", f"acc:cash:{rid}")])
    elif status == "confirmed" and pm != "aba":
        rows.append([("🏦 For ABA", f"acc:aba:{rid}"), ("💵 Cash-paid", f"acc:cash:{rid}")])
    # confirmed + ABA → awaiting the P2 slip (no manual "mark paid" in P1)
    rows.append([("✏️ Fix", f"acc:fix:{rid}")])
    return rows
