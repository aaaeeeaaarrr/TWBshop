"""accountant/capture.py — P1 capture pure logic (no Telegram, no DB, fully unit-testable).

The LIVING RECEIPT CARD + the tax-tolerant math check + doc-type routing. The bot layer
(accountant/bot.py) turns the (label, callback) tuples here into Telegram buttons and owns
the DB writes; everything in this file is pure so it can be proven without a token.

Card lifecycle (design §E1):  DRAFT(captured) → CONFIRMED(confirmed) → [💵 cash | 🏦 ABA] → PAID
"""
import re

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
    """Best-effort (amount_cents, orig_currency, orig_amount) from assess_receipt_photo's
    readable_partial. USD is PREFERRED — many suppliers print BOTH Riel and USD and their Riel
    rate is NOT our 4000/1, so when a $ figure exists we trust it; a Riel-only receipt converts at
    the fixed 4000៛=$1 book rate (orig kept for the card). We bias toward the figure after 'total'
    so a cash receipt's 'received/change' doesn't win. A heuristic — confirm + ✏️ Fix is the net."""
    if not text:
        return (None, None, None)
    t = text.replace(",", "")
    usd = [float(x) for x in re.findall(r"\$?\s*(\d+\.\d{2})\b", t)]
    riel = [float(x) for x in re.findall(r"(\d{3,})\s*\(?\s*(?:khmer\s*)?(?:៛|riel|khr)", t, re.I)]
    riel += [float(x) for x in re.findall(r"៛\s*(\d{3,})", t)]

    def _after_total(cands, is_decimal):
        for c in cands:
            needle = f"{c:.2f}" if is_decimal else str(int(c))
            if re.search(r"total[^0-9]{0,15}\$?\s*" + re.escape(needle), t, re.I):
                return c
        return None

    if usd:
        amt = _after_total(usd, True) or max(usd)
        return (int(round(amt * 100)), "USD", amt)
    if riel:
        amt = _after_total(riel, False) or max(riel)
        return (int(round(amt / 4000 * 100)), "KHR", amt)
    return (None, None, None)


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
    if r.get("lines"):
        for i, li in enumerate(r["lines"], 1):
            name = li.get("raw_name") or "?"
            orig = (li.get("orig_name") or "").strip()
            # A fresh translation we haven't had confirmed is a GUESS, not a fact — show the
            # as-written original + a ? so staff verify the translation against the paper, instead
            # of a confident invented English word. A learned/confirmed alias (li['confident']) is
            # trusted, so it drops the ? and shows the clean English name.
            if orig and orig != name and not li.get("confident"):
                label = f"{orig} → {name}?"
            else:
                label = name
            seg = f"  {i}. {label}"
            if li.get("qty"):
                seg += f" ×{float(li['qty']):g}"
            if li.get("line_total_cents") is not None:
                seg += f" = {fmt_money(li['line_total_cents'])}"
            lines.append(seg)
    elif r.get("items_text"):
        lines.append(f"Items: {r['items_text']}")
    meta = []
    if r.get("receipt_date"):
        meta.append(f"📅 {r['receipt_date']}")
    if r.get("invoice_no"):
        meta.append(f"inv #{r['invoice_no']}")
    if meta:
        lines.append(" · ".join(meta))
    if r.get("math_msg"):
        lines.append(r["math_msg"])
    if r.get("dup_suspect_of"):
        lines.append(f"⚠ possible duplicate of #{r['dup_suspect_of']} (same vendor + amount, recent)")
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
    if not r.get("vendor_name"):                  # unresolved vendor → offer the §G7 picker
        rows.append([("🏷 Set supplier", f"acc:setv:{rid}")])
    rows.append([("✏️ Fix", f"acc:fix:{rid}")])
    return rows


def vendor_picker_buttons(rid, candidates, read_vendor=None):
    """Supplier picker for an unresolved receipt (design §G7), as (label, callback) rows. Existing-vendor
    candidates become [✓ Name] buttons whose callback carries BOTH ids (the button never trusts the
    on-screen list — menu-law); plus an 'add the read name as new' button when the model read a name;
    plus Back. Pure → the bot layer turns these into Telegram buttons."""
    rows = [[(f"✓ {c['name']}", f"acc:usev:{rid}_{c['id']}")] for c in (candidates or [])]
    rv = (read_vendor or "").strip()
    if rv:
        rows.append([(f'➕ Add "{rv}" as new', f"acc:addv:{rid}")])
    rows.append([("← Back", f"acc:back:{rid}")])
    return rows


def channel_picker_buttons(vid, channels):
    """Owner picker to link a vendor's paid-signal channel from the listener's known chats (§G9), as
    (label, callback) rows. The callback carries vendor id + chat id (button never trusts the screen);
    DMs (chat_id > 0) are labelled. 'skip' is always offered — linking is optional (works groupless)."""
    rows = []
    for c in (channels or []):
        cid = c.get("chat_id")
        tag = " (DM)" if (cid or 0) > 0 else ""
        rows.append([(f"🔗 {c.get('title') or cid}{tag}", f"acc:lch:{vid}_{cid}")])
    rows.append([("skip (groupless)", f"acc:lskip:{vid}"), ("🗑 once-off", f"acc:1off:{vid}")])
    return rows


# ─────────────── "Received Yet?" candidate flow (design §E3) — pure card logic ───────────────
# A supplier-posted photo, forwarded to the Expense group as a CANDIDATE (never auto-numbered).
# Callback space is 'accand:<action>:<id>' (distinct from the 'acc:' receipt cards).

def candidate_card(c: dict) -> str:
    """The candidate card text for row `c` (keys: id, vendor_name, src_chat_title, status,
    receipt_id). Header shows supplier NAME + GROUP so routing is verifiable (owner's ask)."""
    vendor = c.get("vendor_name") or "❓ unmapped supplier"
    group = c.get("src_chat_title") or "supplier group"
    head = f"📨 From {vendor} · {group}"
    status = c.get("status", "open")
    n = c.get("receipt_id")
    if status == "open":
        return head + "\nA supplier posted this. Received yet?"
    if status == "promoting":
        return head + "\n⏳ Reading the receipt…"
    if status == "promoted":
        return head + (f"\n✅ Logged as receipt #{n}." if n else "\n✅ Promoted to a receipt.")
    if status == "linked":
        return head + (f"\n🔗 Same as #{n} — already logged." if n else "\n🔗 Already logged.")
    if status == "expected":
        return head + "\n📦 Parked as expected (order / quote — not received yet)."
    if status == "ignored":
        return head + "\n✕ Ignored."
    return head


def candidate_buttons(c: dict):
    """Fork buttons for an OPEN candidate, as (label, callback_data) rows; resolved → no buttons."""
    cid = c.get("id")
    if c.get("status") != "open":
        return []
    return [
        [("🆕 New & received", f"accand:new:{cid}")],
        [("🔗 Already logged", f"accand:link:{cid}"), ("📦 Not yet", f"accand:exp:{cid}")],
        [("✕ Ignore", f"accand:ig:{cid}")],
    ]


def lookalike_prompt(receipt: dict) -> str:
    """Shown when promoting a candidate that matches a recent receipt (anti-double-pay §E3)."""
    n = receipt.get("id")
    vendor = receipt.get("vendor_name") or "this supplier"
    amt = fmt_money(receipt.get("amount_cents"))
    return (f"⚠ Looks like #{n} ({vendor} {amt}, already logged recently).\n"
            f"Same receipt, or a genuinely new one?")


def lookalike_buttons(cid, receipt_id):
    """Same-vs-new choice after a look-alike hit (callbacks carry only the candidate id; the matched
    receipt id is recalled bot-side)."""
    return [
        [("✅ New receipt", f"accand:pnew:{cid}")],
        [(f"🔗 No, same as #{receipt_id}", f"accand:psame:{cid}")],
    ]


def receipt_pick_label(r: dict) -> str:
    """One line for the 'Already logged → which #?' picker button."""
    amt = fmt_money(r.get("amount_cents"))
    state = {"paid": "paid", "confirmed": "unpaid", "captured": "draft"}.get(r.get("status"), r.get("status") or "")
    return f"#{r.get('id')} · {amt} · {state}".strip(" ·")
