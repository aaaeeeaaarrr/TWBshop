"""accountant/bot.py — the Telegram shell for the accountant (P1 capture).

A thin layer over the pure logic (accountant/capture.py) + the DB (accountant/db.py):
receipt photo → assess_receipt_photo → numbered living card → confirm / cash|ABA / ✏️ Fix.
Payment matching + the owner→supplier slip relay are P2 (not here).

NOT real-path-tested yet — gated on ACCOUNTANT_BOT_TOKEN (owner creates the bot via @BotFather).
The pure logic + DB lifecycle it calls ARE proven (tests/test_accountant_capture.py).
"""
import hashlib
import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          MessageHandler, filters)

from accountant import capture
from accountant.db import (add_candidate, add_receipt, attach_vendor_channel, claim_candidate,
                           confirm_receipt, confirm_vendor, delete_receipt, edit_receipt,
                           finalize_promote, find_lookalike_receipt, find_similar_vendors,
                           flag_dup_suspect, get_candidate, get_candidate_by_sha, get_item_alias,
                           get_receipt, get_receipt_by_sha, get_receipt_lines, get_vendor,
                           learn_item_alias, link_candidate, list_unconfirmed_vendors,
                           listener_channels_matching, list_vendors, propose_vendor,
                           recent_receipts_for_vendor, rename_receipt_line, resolve_candidate,
                           save_receipt_lines, set_candidate_card, set_payment, set_vendor_kind,
                           to_usd_cents, unclaim_candidate, vendor_by_group, vendor_by_name,
                           vendor_link)
from shared.ai_client import extract_receipt

try:
    from config import OWNER_TELEGRAM_ID
except Exception:
    OWNER_TELEGRAM_ID = 0

EXPENSE_GROUP_ID = -5417163768   # "Expenses TWB" — the one internal capture group
LISTENER_ACTOR = 1271537077      # the shop/listener account (Café Wine O'clock / TheWineBakery24PP)
CARD_ACTORS = {OWNER_TELEGRAM_ID, LISTENER_ACTOR}  # who may capture + tap cards (Tyty only observes)

logger = logging.getLogger(__name__)


def _allowed(update):
    """Who may capture / act: the OWNER in a private DM; OWNER + the listener/shop account in the
    Expenses group. Everyone else (incl. Tyty, who observes) is ignored; other groups are ignored."""
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return False
    if chat.type == "private":
        return user.id == OWNER_TELEGRAM_ID
    if chat.id == EXPENSE_GROUP_ID:
        return user.id in CARD_ACTORS
    return False


def _rows_kb(rows):
    """Build an InlineKeyboardMarkup from (label, callback_data) rows, or None if empty."""
    if not rows:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for (label, data) in row] for row in rows])


def _kb(r):
    return _rows_kb(capture.card_buttons(r))


def _cand_kb(c):
    return _rows_kb(capture.candidate_buttons(c))


def _card_text_kb(rid):
    """The living receipt card (text, keyboard) for receipt #rid — shared by reply + group send."""
    r = get_receipt(rid)
    r["lines"] = get_receipt_lines(rid)
    vid = r.get("vendor_id")
    for li in r["lines"]:
        # A line is "confident" (no ? on the card) when nothing was translated, OR a learned/
        # confirmed alias backs this exact English name. A fresh, never-confirmed translation
        # stays tentative so staff eyeball it (see capture.render_card).
        orig = (li.get("orig_name") or "").strip()
        li["confident"] = (not orig) or (orig == (li.get("raw_name") or "")) or \
                          (get_item_alias(vid, orig) == li.get("raw_name"))
    items_sum = sum(li["line_total_cents"] for li in r["lines"]
                    if li.get("line_total_cents") is not None)
    if r["lines"] and items_sum and r.get("amount_cents"):
        ok, msg = capture.math_check(items_sum + (r.get("tax_cents") or 0), r["amount_cents"])
        r["math_msg"] = msg if not ok else "✓ items add up"
    return capture.render_card(r), _kb(r)


async def _send_card(update, rid):
    text, kb = _card_text_kb(rid)
    await update.effective_message.reply_text(text, reply_markup=kb)


async def _download(context, file_id):
    """Fetch photo bytes by file_id (a bot file_id works across chats). None on a network hiccup."""
    try:
        f = await context.bot.get_file(file_id)
        return bytes(await f.download_as_bytearray())
    except Exception:
        logger.exception("photo fetch failed (network)")
        return None


async def cmd_start(update, context):
    if not _allowed(update):
        return
    await update.message.reply_text(
        "🧾 Accountant — send a receipt photo here (or in the Expense group) and I'll log it as a "
        "numbered receipt.\nOwner: run /vendor link <name> inside a supplier group to map it.")


async def cmd_vendor(update, context):
    """/vendor link <name> — owner, INSIDE a supplier group → map group→vendor (the paid-signal)."""
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        return
    args = context.args or []
    if len(args) >= 2 and args[0] == "link":
        name = " ".join(args[1:])
        vid = vendor_link(name, update.effective_chat.id)
        await update.message.reply_text(f"✅ Linked this group → {name} (vendor #{vid}).")
    else:
        await update.message.reply_text("Usage: /vendor link <name>  (run inside the supplier group)")


async def cmd_vendors(update, context):
    """/vendors — owner: the interim confirm-list of staff-proposed suppliers, each a one-tap ✅ (§G7)."""
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        return
    pending = list_unconfirmed_vendors()
    if not pending:
        await update.message.reply_text("✅ No suppliers awaiting confirm.")
        return
    for v in pending:
        await update.message.reply_text(
            f"🆕 {v['name']} (vendor #{v['id']})",
            reply_markup=_rows_kb([[("✅ Confirm", f"acc:vok:{v['id']}"),
                                    ("🔗 Link channel", f"acc:lsug:{v['id']}")]]))


async def on_photo(update, context):
    """Photo router. A LINKED supplier group → the bot stays SILENT there and forwards a
    'Received Yet?' candidate to the Expense group (§E3). Otherwise (Expense group / owner DM) →
    P1 capture as a numbered living receipt card."""
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup") and chat.id != EXPENSE_GROUP_ID:
        v = vendor_by_group(chat.id)            # only linked supplier groups produce candidates
        if v:
            await _on_supplier_photo(update, context, v)
        return                                   # never capture or post in a non-Expense group
    if not _allowed(update):
        return
    await _capture_expense_photo(update, context)


async def _on_supplier_photo(update, context, vendor):
    """A supplier posted a photo in their group → forward it to the Expense group as a CANDIDATE
    (never auto-numbered). The bot stays silent in the supplier group; the card + buttons land in
    the Expense group, headed with the supplier NAME + GROUP so routing is verifiable."""
    msg = update.effective_message
    photo = msg.photo[-1]
    raw = await _download(context, photo.file_id)
    if raw is None:
        return                                   # transient fetch fail → silent (it's a supplier group)
    sha = hashlib.sha256(raw).hexdigest()
    if get_candidate_by_sha(sha):
        return                                   # same supplier photo again → one candidate, no re-post
    chat = update.effective_chat
    cid = add_candidate(vendor_id=vendor["id"], src_chat_id=chat.id, src_msg_id=msg.message_id,
                        src_chat_title=(chat.title or vendor["name"]), photo_file_id=photo.file_id,
                        photo_sha=sha, posted_by=update.effective_user.id)
    c = get_candidate(cid)
    try:
        sent = await context.bot.send_photo(EXPENSE_GROUP_ID, photo.file_id,
                                            caption=capture.candidate_card(c), reply_markup=_cand_kb(c))
        set_candidate_card(cid, EXPENSE_GROUP_ID, sent.message_id)
    except Exception:
        logger.exception("posting candidate card to the Expense group failed")


async def _capture_expense_photo(update, context):
    """Receipt photo → one focused Sonnet read → numbered living card. Cash/ABA + ✏️ Fix from the card."""
    msg = update.effective_message
    photo = msg.photo[-1]
    try:
        raw = bytes(await (await photo.get_file()).download_as_bytearray())
    except Exception:
        logger.exception("photo fetch failed (network)")
        try:
            await msg.reply_text("⚠️ Couldn't fetch that photo (network hiccup) — please resend it.")
        except Exception:
            pass
        return
    sha = hashlib.sha256(raw).hexdigest()
    existing = get_receipt_by_sha(sha)
    if existing and existing.get("status") not in (None, "captured"):
        await msg.reply_text(f"🧾 Already logged as #{existing['id']} ({existing['status']}).")
        return
    if existing:  # still a draft → re-read it fresh (a clearer re-send, or a re-test)
        delete_receipt(existing["id"])
    try:
        rec = await extract_receipt(raw)
    except Exception:
        logger.exception("extract_receipt failed")
        return
    if not rec.get("is_receipt"):
        return  # POS screens / expense sheets / other are the report engine's job (P3)

    v = vendor_by_group(update.effective_chat.id)  # zero-read vendor if posted in a supplier group
    if not v:  # else learn from the printed name (vendor-learning lite): "SONG HENG" → "Song Heng Gas"
        v = vendor_by_name(rec.get("vendor"))
    total, cur = rec.get("total_amount"), (rec.get("total_currency") or "USD")
    cents = to_usd_cents(total, cur) if total is not None else None
    rid = add_receipt(
        vendor_id=(v["id"] if v else None),
        amount_cents=cents,
        orig_currency=cur,
        orig_amount=total,
        items_text=(rec.get("items_text") or None),
        is_handwritten=rec.get("is_handwritten", False),
        invoice_no=rec.get("invoice_no"),
        receipt_date=rec.get("date"),
        tax_cents=(to_usd_cents(rec["tax_amount"], cur) if rec.get("tax_amount") else None),
        supplier_account=rec.get("supplier_account"),
        bank_name=rec.get("bank_name"),
        photo_file_id=photo.file_id,
        photo_sha=sha,
        tg_chat_id=update.effective_chat.id,
        tg_msg_id=msg.message_id,
        captured_by=update.effective_user.id,
        read_vendor=(rec.get("vendor") or None),    # seeds the §G7 picker when the vendor doesn't resolve
    )
    save_receipt_lines(rid, rec.get("line_items"), cur, vendor_id=(v["id"] if v else None))
    # anti-double-pay heads-up (§E3 layer 3): a prior receipt, same vendor+amount within 7 days →
    # flag THIS one as a possible duplicate (informational; excludes the row just created).
    look = find_lookalike_receipt((v["id"] if v else None), cents, 7, exclude_id=rid)
    if look:
        flag_dup_suspect(rid, look["id"])
    await _send_card(update, rid)


async def _safe_edit(q, text, kb=None):
    """Edit a message's text/keyboard, swallowing Telegram's benign 'not modified' / edit races."""
    try:
        await q.edit_message_text(text, reply_markup=kb)
    except Exception:
        pass


async def _rerender(q, rid):
    """Re-draw receipt #rid's living card in place from current DB state (full lines + confidence)."""
    text, kb = _card_text_kb(rid)
    await _safe_edit(q, text, kb)


async def _show_channel_suggestions(q, vid, head=None):
    """§G9 — offer to link a vendor's paid-signal channel from the listener's known chats (groups + DMs),
    fuzzy-matched by name so the owner taps instead of scrolling hundreds. Always offers skip / once-off,
    so it NEVER blocks (a vendor works fine groupless)."""
    v = get_vendor(vid)
    if not v:
        return
    chans = listener_channels_matching(v["name"])
    head = head or f"Link a channel for {v['name']}?"
    if not chans:
        head += "\n(no matching channel the listener sees — skip to leave it groupless)"
    await _safe_edit(q, head, _rows_kb(capture.channel_picker_buttons(vid, chans)))


async def _show_vendor_picker(q, rid):
    """🏷 Set supplier → fuzzy candidates for the READ name (the §G7 dedup gate) + 'add as new' + Back.
    Button-driven so it works in the Expense group (text replies are owner-DM only)."""
    r = get_receipt(rid)
    if not r:
        return
    read_vendor = r.get("read_vendor")
    cands = find_similar_vendors(read_vendor) if read_vendor else list_vendors()[:6]
    head = "🏷 Which supplier?" + (f'  (read: "{read_vendor}")' if read_vendor else "")
    try:
        await q.edit_message_text(head, reply_markup=_rows_kb(capture.vendor_picker_buttons(rid, cands, read_vendor)))
    except Exception:
        pass


async def _add_new_vendor(q, context, rid):
    """➕ Add the READ name as a NEW supplier (decision A): create it usable-now + needs_review, attach
    it to the receipt, re-draw the card, and DM the owner a one-tap confirm. No typing → works in-group."""
    r = get_receipt(rid)
    if not r:
        return
    name = (r.get("read_vendor") or "").strip()
    if not name:                                  # nothing was read → can't name it here; owner does it in DM
        try:
            await q.edit_message_text("No supplier name was read — owner, set it from your DM.",
                                      reply_markup=_rows_kb([[("← Back", f"acc:back:{rid}")]]))
        except Exception:
            pass
        return
    vid = propose_vendor(name, created_by=q.from_user.id)   # the dedup gate was the picker the staffer just left
    edit_receipt(rid, vendor_id=vid)
    await _rerender(q, rid)
    try:                                          # the interim ❗ confirm lives here until the Pending queue exists
        await context.bot.send_message(
            OWNER_TELEGRAM_ID,
            f'🆕 New supplier added by staff: "{name}" (vendor #{vid}, on receipt #{rid}).\n'
            "Confirm the name, or rename later.",
            reply_markup=_rows_kb([[("✅ Confirm", f"acc:vok:{vid}")]]))
    except Exception:
        logger.exception("owner new-vendor notify failed")


async def on_callback(update, context):
    q = update.callback_query
    await q.answer()
    if not _allowed(update):
        return
    parts = (q.data or "").split(":")
    if len(parts) < 3:
        return
    action, sid = parts[1], parts[2]
    # ── composite callbacks (carry a chat/vendor id beyond the receipt id) ──
    if action == "usev":                          # sid = "rid_vid" → attach an existing vendor
        try:
            rid, vid = (int(x) for x in sid.split("_"))
        except ValueError:
            return
        edit_receipt(rid, vendor_id=vid)
        await _rerender(q, rid)
        return
    if action == "lch":                           # sid = "vid_chatid" → link a listener channel (§G9)
        try:
            vid, cid = (int(x) for x in sid.split("_"))
        except ValueError:
            return
        attach_vendor_channel(vid, cid)
        v = get_vendor(vid)
        await _safe_edit(q, f"🔗 Linked {v['name'] if v else vid} → channel {cid}.")
        return
    # ── vendor-id actions (sid = a vendor id) ──
    if action in ("vok", "lsug", "lskip", "1off"):
        try:
            vid = int(sid)
        except ValueError:
            return
        if action == "vok":                       # owner one-tap confirm → then offer channel-link
            confirm_vendor(vid)
            v = get_vendor(vid)
            await _show_channel_suggestions(q, vid, head=f"✅ Confirmed: {v['name'] if v else vid}. Link its channel?")
        elif action == "lsug":                    # 🔗 Link channel (from /vendors)
            await _show_channel_suggestions(q, vid)
        elif action == "lskip":
            await _safe_edit(q, "👍 Left groupless — link a channel later via /vendors.")
        elif action == "1off":
            set_vendor_kind(vid, "oneoff")
            await _safe_edit(q, "🗑 Marked once-off (groupless, kept off the payable run).")
        return
    # ── receipt-id actions ──
    try:
        rid = int(sid)
    except ValueError:
        return
    if action == "ok":
        confirm_receipt(rid)
    elif action == "cash":
        set_payment(rid, "cash")
    elif action == "aba":
        set_payment(rid, "aba")
    elif action == "fix":
        context.user_data["acc_fix"] = rid
        await q.message.reply_text(
            "✏️ Send a correction:\n"
            "• a number = the total (e.g. 135.30)\n"
            "• `1 Apple` = rename item 1 (I'll remember it for next time)\n"
            "• anything else = a note")
        return
    elif action == "setv":
        await _show_vendor_picker(q, rid)
        return
    elif action == "addv":
        await _add_new_vendor(q, context, rid)
        return
    # "back" + the pay/confirm actions fall through to a fresh full-card render
    await _rerender(q, rid)


# ─────────────── "Received Yet?" candidate card taps (Expense group, §E3) ───────────────

async def _edit_cand(q, cid):
    """Re-render a candidate card in place from its current DB state ('not modified' is benign)."""
    c = get_candidate(cid)
    if not c:
        return
    try:
        await q.edit_message_caption(caption=capture.candidate_card(c), reply_markup=_cand_kb(c))
    except Exception:
        pass


async def _show_link_picker(q, c):
    """🔗 Already logged → pick which existing receipt # this candidate duplicates."""
    cid = c["id"]
    recents = recent_receipts_for_vendor(c.get("vendor_id"), 8)
    if not recents:
        try:
            await q.edit_message_caption(
                caption=capture.candidate_card(c) + "\n(no receipts logged for this supplier yet — "
                "promote as 🆕 New, or ✕ Ignore)", reply_markup=_cand_kb(c))
        except Exception:
            pass
        return
    rows = [[(capture.receipt_pick_label(r), f"accand:lpick:{cid}:{r['id']}")] for r in recents]
    rows.append([("← Back", f"accand:back:{cid}")])
    try:
        await q.edit_message_caption(caption="🔗 Which receipt is this the same as?",
                                     reply_markup=_rows_kb(rows))
    except Exception:
        pass


async def _candidate_new(q, context, c):
    """🆕 New & received → OCR → look-alike guard (anti-double-pay §E3); promote if clear."""
    cid = c["id"]
    if c["status"] != "open":
        await _edit_cand(q, cid)
        return
    raw = await _download(context, c.get("photo_file_id"))
    if raw is None:
        return
    rec = await extract_receipt(raw)
    context.user_data[f"cand_extract:{cid}"] = rec
    cents = to_usd_cents(rec.get("total_amount"), rec.get("total_currency") or "USD")
    look = find_lookalike_receipt(c.get("vendor_id"), cents, 7)
    if look:
        context.user_data[f"cand_look:{cid}"] = look["id"]
        try:
            await q.edit_message_caption(caption=capture.lookalike_prompt(look),
                                         reply_markup=_rows_kb(capture.lookalike_buttons(cid, look["id"])))
        except Exception:
            pass
        return
    await _candidate_promote(q, context, c, rec=rec)


async def _candidate_promote(q, context, c, rec=None):
    """Create the numbered receipt from a candidate. Claim-first (atomic 'open'→'promoting') so a
    double-tap can NEVER create two numbered receipts from one supplier photo."""
    cid = c["id"]
    uid = q.from_user.id
    if rec is None:
        rec = context.user_data.get(f"cand_extract:{cid}")
    if rec is None:                              # stash lost (e.g. restart) → re-read
        raw = await _download(context, c.get("photo_file_id"))
        if raw is None:
            return
        rec = await extract_receipt(raw)
    if not rec.get("is_receipt"):                # not a receipt → don't number it
        resolve_candidate(cid, "ignored", uid, note="not a receipt")
        await _edit_cand(q, cid)
        return
    if not claim_candidate(cid):                 # lost the race / already handled
        await _edit_cand(q, cid)
        return
    try:
        vid = c.get("vendor_id")
        total, cur = rec.get("total_amount"), (rec.get("total_currency") or "USD")
        cents = to_usd_cents(total, cur) if total is not None else None
        rid = add_receipt(
            vendor_id=vid, amount_cents=cents, orig_currency=cur, orig_amount=total,
            items_text=(rec.get("items_text") or None), is_handwritten=rec.get("is_handwritten", False),
            invoice_no=rec.get("invoice_no"), receipt_date=rec.get("date"),
            tax_cents=(to_usd_cents(rec["tax_amount"], cur) if rec.get("tax_amount") else None),
            supplier_account=rec.get("supplier_account"), bank_name=rec.get("bank_name"),
            photo_file_id=c.get("photo_file_id"), photo_sha=c.get("photo_sha"),
            tg_chat_id=c.get("src_chat_id"), tg_msg_id=c.get("src_msg_id"), captured_by=uid)
        save_receipt_lines(rid, rec.get("line_items"), cur, vendor_id=vid)
    except Exception:
        unclaim_candidate(cid)                   # revert the claim; row stays 'open' for a retry
        logger.exception("candidate promote failed")
        return
    finalize_promote(cid, rid, uid)
    context.user_data.pop(f"cand_extract:{cid}", None)
    context.user_data.pop(f"cand_look:{cid}", None)
    await _edit_cand(q, cid)                      # candidate card → "✅ Logged as #N"
    try:                                          # the living receipt card → owner confirms/cash/aba/fix
        text, kb = _card_text_kb(rid)
        await context.bot.send_message(EXPENSE_GROUP_ID, text, reply_markup=kb)
    except Exception:
        logger.exception("sending the promoted receipt card failed")


async def on_candidate_callback(update, context):
    """Taps on a 'Received Yet?' candidate card. Actor-gated (Expense group → owner / listener)."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update):
        return
    parts = (q.data or "").split(":")
    if len(parts) < 3:
        return
    action, sid = parts[1], parts[2]
    try:
        cid = int(sid)
    except ValueError:
        return
    c = get_candidate(cid)
    if not c:
        return
    uid = update.effective_user.id
    if action == "exp":
        resolve_candidate(cid, "expected", uid)
    elif action == "ig":
        resolve_candidate(cid, "ignored", uid)
    elif action == "link":
        await _show_link_picker(q, c)
        return
    elif action == "back":
        await _edit_cand(q, cid)
        return
    elif action == "lpick":
        if len(parts) >= 4:
            try:
                link_candidate(cid, int(parts[3]), uid)
            except ValueError:
                pass
    elif action == "new":
        await _candidate_new(q, context, c)
        return
    elif action == "pnew":
        await _candidate_promote(q, context, c)
        return
    elif action == "psame":
        rid = context.user_data.get(f"cand_look:{cid}")
        if rid:
            link_candidate(cid, rid, uid)
    await _edit_cand(q, cid)


async def on_text(update, context):
    """A ✏️ Fix reply: a number updates the total, anything else updates the item note."""
    if not _allowed(update):
        return
    rid = context.user_data.pop("acc_fix", None)
    if not rid:
        return
    text = (update.message.text or "").strip()
    # per-item correction: "1 Apple" → rename item 1 AND remember it (vendor + original name → English)
    m = re.match(r"^(\d+)\s+(.+)$", text)
    if m:
        idx, newname = int(m.group(1)), m.group(2).strip()
        lines = get_receipt_lines(rid)
        if 1 <= idx <= len(lines):
            line = lines[idx - 1]
            rename_receipt_line(line["id"], newname)
            learn_item_alias((get_receipt(rid) or {}).get("vendor_id"), line.get("orig_name"), newname)
            await _send_card(update, rid)
            return
    cents, currency, orig = capture.parse_amount_cents(text)
    if cents is None and text.replace(".", "", 1).isdigit():
        cents, currency, orig = int(round(float(text) * 100)), "USD", float(text)
    if cents is not None:
        edit_receipt(rid, amount_cents=cents, orig_currency=(currency or "USD"), orig_amount=orig)
    else:
        edit_receipt(rid, items_text=text)
    await _send_card(update, rid)


def build_application(token: str) -> Application:
    # generous timeouts — photo fetch over a slow link was timing out at the 5s default
    app = (Application.builder().token(token)
           .read_timeout(30).write_timeout(30).connect_timeout(15).pool_timeout(10)
           .media_write_timeout(60).build())
    from shared.error_handler import make_error_handler
    app.add_error_handler(make_error_handler("Accountant"))   # crashes are never silent
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("vendor", cmd_vendor))
    app.add_handler(CommandHandler("vendors", cmd_vendors))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(CallbackQueryHandler(on_candidate_callback, pattern=r"^accand:"))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^acc:"))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, on_text))
    return app
