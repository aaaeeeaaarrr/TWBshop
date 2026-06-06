"""Roll-call / uid binding — the first piece of the private-DM attendance system.

Staff DM the GM ("hello, I'm Davy") →
  - uid already on an ACTIVE record  → greet by call name (once); a multi-uid record is
    SETTLED to the account they actually wrote from (first DM decides the real account).
  - unknown uid + name matches roster → owner gets a confirm card, sender gets silence
    until the owner approves (catches typos and impersonation).
  - ex-staff / strangers → silence (one private heads-up to the owner per unknown uid).

Pure logic only — no AI calls (zero-API principle). See docs/ATTENDANCE_SYSTEM_DETAILED.md §0/§1.
"""
from __future__ import annotations

import difflib
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from shared.database import (
    gm_get_state,
    gm_set_state,
    staff_all,
    staff_bind_uid,
    staff_get_by_uid,
)

_GREETED_KEY = "rollcall_greeted:%d"
_UNKNOWN_KEY = "rollcall_unknown_notified:%d"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9ក-៿]", "", (s or "").lower())


def _name_keys(rec: dict) -> list[str]:
    """All normalised name forms a person might introduce themselves with."""
    keys = []
    canon = rec.get("canonical_name") or ""
    parts = canon.split()
    for cand in ([canon, rec.get("call_name")] + rec.get("aliases", [])
                 + ([" ".join(reversed(parts))] if len(parts) > 1 else [])
                 + (parts[-1:] if len(parts) > 1 else [])):  # given name = RIGHT token (Khmer order)
        n = _norm(cand or "")
        if n and n not in keys:
            keys.append(n)
    return keys


def match_staff_name(text: str, roster: list[dict]) -> list[dict]:
    """Match a free-text hello ("hi i'm davy", "សួស្តី Pisey") to active staff records.

    Substring pass first (handles greetings around the name), then a difflib pass on
    whole words for typos. Returns unique records, best-first; [] when nothing fits.
    """
    tnorm = _norm(text)
    if not tnorm:
        return []
    words = [_norm(w) for w in re.split(r"[\s,.!?:;@]+", text or "") if _norm(w)]

    scored: list[tuple[float, int, dict]] = []
    for rec in roster:
        if rec.get("status") != "active":
            continue
        best = 0.0
        for key in _name_keys(rec):
            if len(key) >= 3 and key in tnorm:
                best = max(best, 1.0 if len(key) >= 5 else 0.9)
                continue
            for w in words:
                if len(w) >= 3:
                    r = difflib.SequenceMatcher(None, key, w).ratio()
                    if r >= 0.84:
                        best = max(best, r)
        if best:
            scored.append((best, rec["id"], rec))
    scored.sort(key=lambda t: -t[0])
    if not scored:
        return []
    top = scored[0][0]
    return [rec for score, _id, rec in scored if score >= top - 0.05][:4]


def greeting_text(rec: dict) -> str:
    call = rec.get("call_name") or (rec.get("canonical_name") or "").split()[-1]
    return ("Hello %s! ✓ You're registered with me.\n"
            "សួស្តី %s! ✓ អ្នកបានចុះឈ្មោះជាមួយខ្ញុំរួចរាល់ហើយ។" % (call, call))


def _sender_label(user) -> str:
    bits = [user.full_name or "?"]
    if user.username:
        bits.append("@" + user.username)
    bits.append("uid %d" % user.id)
    return " · ".join(bits)


async def _greet_once(message, context, rec: dict, uid: int) -> None:
    if gm_get_state(_GREETED_KEY % uid) == "true":
        return
    await message.reply_text(greeting_text(rec))
    gm_set_state(_GREETED_KEY % uid, "true")


async def handle_staff_private(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Private /start or text from a NON-OWNER sender."""
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return
    uid = user.id

    rec = staff_get_by_uid(uid)
    if rec:
        if rec.get("status") != "active":
            return  # ex-staff: no engagement
        if len(rec.get("telegram_ids", [])) > 1:
            staff_bind_uid(rec["id"], uid)  # first DM settles the real account
        await _greet_once(msg, context, rec, uid)
        return

    # unknown uid — try to match the typed name against the active roster
    matches = match_staff_name(msg.text or "", staff_all("active"))
    if matches:
        rows = [[InlineKeyboardButton("✅ Bind %s" % m["canonical_name"],
                                      callback_data="bind:go:%d:%d" % (m["id"], uid))]
                for m in matches]
        rows.append([InlineKeyboardButton("✋ No, ignore", callback_data="bind:no:0:%d" % uid)])
        await context.bot.send_message(
            config.OWNER_TELEGRAM_ID,
            "Roll-call: %s wrote:\n“%s”\n\nBind this account?"
            % (_sender_label(user), (msg.text or "")[:200]),
            reply_markup=InlineKeyboardMarkup(rows))
        return

    # total stranger — tell the owner once per uid, stay silent to the sender
    if gm_get_state(_UNKNOWN_KEY % uid) != "true":
        gm_set_state(_UNKNOWN_KEY % uid, "true")
        await context.bot.send_message(
            config.OWNER_TELEGRAM_ID,
            "Unknown person messaged the GM (no roster match, not answered):\n%s\n“%s”"
            % (_sender_label(user), (msg.text or "")[:200]))


async def bind_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner taps ✅ Bind / ✋ No on a roll-call confirm card."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    try:
        _, action, sid_s, uid_s = query.data.split(":")
        sid, uid = int(sid_s), int(uid_s)
    except ValueError:
        return
    if action == "no":
        await query.edit_message_text(query.message.text + "\n\n✋ Ignored.")
        return
    rec = next((r for r in staff_all() if r["id"] == sid), None)
    if not rec:
        await query.edit_message_text(query.message.text + "\n\n⚠️ Record not found.")
        return
    staff_bind_uid(sid, uid)
    await query.edit_message_text(
        query.message.text + "\n\n✅ Bound to %s." % rec["canonical_name"])
    try:
        await context.bot.send_message(uid, greeting_text(rec))
        gm_set_state(_GREETED_KEY % uid, "true")
    except Exception:
        pass  # they can be greeted on their next message
