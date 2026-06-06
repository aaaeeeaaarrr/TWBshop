"""Attendance main-menu SHELL — TEST MODE, OWNER ONLY.

⚠️ SAFETY CONTRACT (owner instruction, session 28): while this shell exists, NOTHING here
may message anyone except the OWNER. Structurally enforced:
  - the only entry point is the owner-only /test command in the owner's own DM;
  - every screen is an edit of that same message in that same chat;
  - there is NO send_message to any other chat id anywhere in this module;
  - cross-audience messages (Supervisors posts, senior cards…) appear as [TEST PREVIEW]
    text to the owner instead.

The owner picks a PERSONA (any active staff) and walks the ladders as that person.
Real flows (DB writes, timers, group posts) are 🚧 next-build stubs.
Pure helpers live at the top — unit-tested in tests/test_attendance_ui.py.
"""
from __future__ import annotations

from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from gm_bot.attendance import to_min
from shared.database import staff_all

_DOW = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_DOW_NAME = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


# ---------------------------------------------------------------- pure helpers

def fmt12(minutes: int) -> str:
    """Minutes-of-day -> '9:05pm' (compact button style)."""
    m = minutes % (24 * 60)
    h, mm = divmod(m, 60)
    suffix = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return ("%d:%02d%s" % (h12, mm, suffix)) if mm else ("%d%s" % (h12, suffix))


def day_label(d: date) -> str:
    """'Mo 29/06' — date-grid button label."""
    return "%s %02d/%02d" % (_DOW[d.weekday()], d.day, d.month)


def shift_len_min(ws: str, we: str) -> int | None:
    """Shift length in minutes; handles overnight (9pm→6am = 540)."""
    a, b = to_min(ws), to_min(we)
    if a is None or b is None:
        return None
    return (b - a) % (24 * 60) or 24 * 60


def late_offsets(shift_minutes: int) -> list[int]:
    """Owner-spec Late ladder offsets (min after shift start), capped 2h before shift end:
    +5,10,15,20,30,45,60,75,90,120, then every 30 min."""
    cap = shift_minutes - 120
    base = [5, 10, 15, 20, 30, 45, 60, 75, 90, 120]
    out = [o for o in base if o <= cap]
    t = 150
    while t <= cap:
        out.append(t)
        t += 30
    return out


def grid(buttons: list[InlineKeyboardButton], per_row: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


# ---------------------------------------------------------------- shell state

def _persona(context) -> dict | None:
    sid = context.user_data.get("att_persona")
    if sid is None:
        return None
    return next((r for r in staff_all("active") if r["id"] == sid), None)


def _hdr(p: dict, line: str = "") -> str:
    head = "🧪 TEST — acting as %s (%s)" % (p["canonical_name"], p.get("call_name") or "-")
    return head + ("\n\n" + line if line else "")


def _back_row(target: str = "att:menu") -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton("←Back", callback_data=target)]


# ---------------------------------------------------------------- screens

def main_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    # Khmer labels reviewed via ChatGPT, owner-approved session 28
    rows = [
        [InlineKeyboardButton("🕘 Late · មកយឺត", callback_data="att:late")],
        [InlineKeyboardButton("🏖 Annual Leave (AL) · ឈប់សម្រាកប្រចាំឆ្នាំ", callback_data="att:al")],
        [InlineKeyboardButton("🚨 Emergency AL · ឈប់សម្រាកបន្ទាន់", callback_data="att:em")],
        [InlineKeyboardButton("🔁 Change day off · ប្តូរថ្ងៃឈប់សម្រាក", callback_data="att:do")],
        [InlineKeyboardButton("⏱ OT · ថែមម៉ោង", callback_data="att:ot")],
        [InlineKeyboardButton("📍 Check in · ចូលវត្តមាន", callback_data="att:ci")],
        [InlineKeyboardButton("📋 My schedule · កាលវិភាគការងាររបស់ខ្ញុំ", callback_data="att:my")],
        [InlineKeyboardButton("🎭 Switch persona", callback_data="att:pick")],
    ]
    return _hdr(p, "Main menu — what they see when they type anything:"), InlineKeyboardMarkup(rows)


def late_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    ws, we = to_min(p.get("work_start")), to_min(p.get("work_end"))
    if ws is None or we is None:
        return _hdr(p, "⚠️ No work times on record."), InlineKeyboardMarkup([_back_row()])
    offs = late_offsets(shift_len_min(p["work_start"], p["work_end"]))
    btns = [InlineKeyboardButton(fmt12(ws + o), callback_data="att:late:o:%d" % o) for o in offs]
    rows = [_back_row()] + grid(btns, 3)
    return _hdr(p, "How late will you be? Pick the time you'll arrive:\n"
                   "តើអ្នកនឹងមកដល់ម៉ោងប៉ុន្មាន?"), InlineKeyboardMarkup(rows)


def late_picked(p: dict, offset: int) -> tuple[str, InlineKeyboardMarkup]:
    ws = to_min(p.get("work_start"))
    txt = _hdr(p,
               "Noted — arriving ~%s (%d min late).\n\n"
               "[TEST PREVIEW → SUPERVISORS group]\n"
               "“%s will be ~%d min late for the %s shift today.”\n\n"
               "🚧 Next build: arrival watch (4×15min nudges), reason quick-buttons ON ARRIVAL, "
               "settle debt (payback slots / take from AL)."
               % (fmt12(ws + offset), offset, p.get("call_name") or p["canonical_name"],
                  offset, fmt12(ws)))
    return txt, InlineKeyboardMarkup([_back_row("att:late"), _back_row()[0:0] or
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def al_screen(p: dict, picked: set[str], page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    al_left = p.get("al_left")
    start = date.today() + timedelta(days=7 + page * 28)
    days = [start + timedelta(days=i) for i in range(28)]
    btns = []
    for d in days:
        iso = d.isoformat()
        mark = "✓ " if iso in picked else ""
        btns.append(InlineKeyboardButton(mark + day_label(d), callback_data="att:al:d:%s" % iso))
    rows = [_back_row()] + grid(btns, 4)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Earlier", callback_data="att:al:p:%d" % (page - 1)))
    if 7 + (page + 1) * 28 <= 90:
        nav.append(InlineKeyboardButton("Later ▶", callback_data="att:al:p:%d" % (page + 1)))
    if nav:
        rows.append(nav)
    if picked:
        rows.append([InlineKeyboardButton("✅ Done (%d day%s)" % (len(picked), "s" if len(picked) > 1 else ""),
                                          callback_data="att:al:done")])
    return _hdr(p, "You have %s AL days left. Choose dates (tap to ✓, then Done).\n"
                   "អ្នកនៅសល់ច្បាប់ %s ថ្ងៃ។ ជ្រើសរើសថ្ងៃ៖\n"
                   "(Today + next 6 days are Emergency AL only.)"
                % (al_left if al_left is not None else "?", al_left if al_left is not None else "?")), \
        InlineKeyboardMarkup(rows)


def al_fullday_or_time(p: dict, picked: set[str]) -> tuple[str, InlineKeyboardMarkup]:
    days = ", ".join(day_label(date.fromisoformat(d)) for d in sorted(picked))
    rows = [_back_row("att:al"),
            [InlineKeyboardButton("Full day · ពេញមួយថ្ងៃ", callback_data="att:al:full")],
            [InlineKeyboardButton("Choose time · ជ្រើសម៉ោង", callback_data="att:al:time")]]
    return _hdr(p, "AL for: %s\nFull day or part of the day?\n"
                   "សុំឈប់ពេញមួយថ្ងៃ ឬសុំឈប់តាមម៉ោង?" % days), InlineKeyboardMarkup(rows)


def al_time_grid(p: dict, stage: str, from_min: int | None = None) -> tuple[str, InlineKeyboardMarkup]:
    ws, length = to_min(p.get("work_start")), shift_len_min(p.get("work_start"), p.get("work_end"))
    btns = []
    for o in range(0, length + 1, 15):
        m = ws + o
        if stage == "from" and o == length:
            continue
        if stage == "to" and from_min is not None and m <= from_min:
            continue
        btns.append(InlineKeyboardButton(
            fmt12(m), callback_data="att:al:%s:%d" % ("f" if stage == "from" else "t", m)))
    rows = [_back_row("att:al")] + grid(btns, 4)
    q = "From what time?" if stage == "from" else "Until what time?"
    return _hdr(p, q), InlineKeyboardMarkup(rows)


def al_stub(p: dict, detail: str) -> tuple[str, InlineKeyboardMarkup]:
    return _hdr(p, detail + "\n\n🚧 Next build: reason step → senior approval cards "
                            "(ALL seniors, availability picture) → Supervisors notice → deduction."), \
        InlineKeyboardMarkup([_back_row(), [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def emergency_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [_back_row(),
            [InlineKeyboardButton("I fully understand · យល់ច្បាស់ហើយ", callback_data="att:em:ok")],
            [InlineKeyboardButton("❌ No Emergency AL · មិនប្រើ", callback_data="att:menu")]]
    return _hdr(p, "⚠️ You can only use Emergency AL once every 30 days. Do you understand?\n"
                   "អ្នកអាចប្រើឈប់សម្រាកបន្ទាន់បានតែ ១ដងក្នុង ៣០ថ្ងៃ។ តើអ្នកយល់ច្បាស់ទេ?"), InlineKeyboardMarkup(rows)


def emergency_dates(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    btns = [InlineKeyboardButton("Today", callback_data="att:em:d:today")]
    start = date.today() + timedelta(days=1)
    btns += [InlineKeyboardButton(day_label(start + timedelta(days=i)),
                                  callback_data="att:em:d:%s" % (start + timedelta(days=i)).isoformat())
             for i in range(28)]
    rows = [_back_row("att:em")] + grid(btns, 4)
    rows.append([InlineKeyboardButton("Later ▶ (29-60d) 🚧", callback_data="att:noop")])
    return _hdr(p, "Which day? (today + next 60)"), InlineKeyboardMarkup(rows)


def dayoff_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    start = date.today() + timedelta(days=1)
    own_off = _DOW_NAME.get((p.get("day_off") or "")[:3].title())
    btns = []
    for i in range(30):
        d = start + timedelta(days=i)
        if d.weekday() == own_off:
            continue  # their current day off — nothing to swap there (owner, session 28)
        btns.append(InlineKeyboardButton(day_label(d), callback_data="att:do:d:%s" % d.isoformat()))
    rows = [_back_row()] + grid(btns, 4)
    return _hdr(p, "Change day off — pick the NEW day you want off (next 30 days, not today).\n"
                   "Current day off: %s" % (p.get("day_off") or "?")), InlineKeyboardMarkup(rows)


def dayoff_partners(p: dict, iso: str) -> tuple[str, InlineKeyboardMarkup]:
    """Swap-partner candidates: active TWB staff with overlapping shift hours (shell version —
    expertise-bottleneck filter lands with the coverage engine)."""
    ws, we = to_min(p.get("work_start")), to_min(p.get("work_end"))
    cands = []
    for r in staff_all("active"):
        if r["id"] == p["id"] or r.get("org") != "TWB" or r.get("canonical_name") == "Tyty":
            continue
        rs, re_ = to_min(r.get("work_start")), to_min(r.get("work_end"))
        if rs is None or ws is None:
            continue
        # overlap on the 24h circle, both directions
        diff = min((rs - ws) % (24 * 60), (ws - rs) % (24 * 60))
        if diff <= 180:  # starts within 3h of each other = "similar/close shift times"
            cands.append(r)
    rows = [_back_row("att:do")]
    rows += [[InlineKeyboardButton(c["canonical_name"], callback_data="att:do:p:%d" % c["id"])]
             for c in cands[:8]]
    d = date.fromisoformat(iso)
    return _hdr(p, "Swap day-off for %s — with whom? (similar shift times; "
                   "must be the same week)" % day_label(d)), InlineKeyboardMarkup(rows)


def ot_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    if p.get("is_senior"):
        rows = [_back_row(), [InlineKeyboardButton("➕ Give OT", callback_data="att:ot:give")]]
        return _hdr(p, "Your OT bank: 0h 🚧\n\nAs a SENIOR you can grant OT (owner approves)."), \
            InlineKeyboardMarkup(rows)
    return _hdr(p, "Your OT bank: 0h 🚧\n\nOT is given by your seniors when the shop needs extra "
                   "hours — when you have hours banked, I'll show you the times to take them back.\n"
                   "OT ត្រូវបានអនុញ្ញាតដោយបងៗ/អ្នកគ្រប់គ្រង ពេលហាងត្រូវការម៉ោងបន្ថែម។ "
                   "ពេលអ្នកមានម៉ោង OT សន្សំទុក ខ្ញុំនឹងបង្ហាញពេលដែលអ្នកអាចសម្រាកសងម៉ោងវិញបាន។"), \
        InlineKeyboardMarkup([_back_row()])


def ot_durations(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    btns = []
    m = 30
    while m <= 360:
        label = ("%dmin" % m) if m < 60 else ("%gh" % (m / 60))
        btns.append(InlineKeyboardButton(label, callback_data="att:ot:d:%d" % m))
        m += 30
    rows = [_back_row("att:ot")] + grid(btns, 4)
    return _hdr(p, "Give OT — how much?"), InlineKeyboardMarkup(rows)


def ot_staff_pick(p: dict, minutes: int) -> tuple[str, InlineKeyboardMarkup]:
    rows = [_back_row("att:ot:give")]
    rows += [[InlineKeyboardButton(r["canonical_name"], callback_data="att:ot:s:%d:%d" % (minutes, r["id"]))]
             for r in staff_all("active") if r.get("org") == "TWB" and r.get("canonical_name") != "Tyty"][:35]
    label = ("%dmin" % minutes) if minutes < 60 else ("%gh" % (minutes / 60))
    return _hdr(p, "Give %s OT — to whom?" % label), InlineKeyboardMarkup(rows)


def ot_stub(p: dict, minutes: int, sid: int) -> tuple[str, InlineKeyboardMarkup]:
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    label = ("%dmin" % minutes) if minutes < 60 else ("%gh" % (minutes / 60))
    txt = _hdr(p, "Give %s OT to %s.\n\n[TEST PREVIEW → OWNER approval card]\n"
                  "“%s gives %s OT to %s — when: …, why: … · bank now: 0h/14h · [✅ Approve] [❌ No]”\n\n"
                  "🚧 Next build: when+why steps, owner card, banking, buyback slots, daily reminder."
               % (label, rec["canonical_name"] if rec else "?", p["canonical_name"], label,
                  rec["canonical_name"] if rec else "?"))
    return txt, InlineKeyboardMarkup([_back_row("att:ot"),
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def checkin_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    return _hdr(p, "Tap 📎 (Attach) → Location / ទីតាំង → Share Live Location / "
                   "ចែករំលែកទីតាំងបន្តផ្ទាល់\n\n"
                   "Shift: %s–%s"
                % (p.get("work_start") or "?", p.get("work_end") or "?")), \
        InlineKeyboardMarkup([_back_row()])


def my_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    exp = ", ".join(p.get("expertise") or []) or "-"
    return _hdr(p, "📋 My schedule\n"
                   "Shift: %s–%s\nDay off: %s\nExpertise: %s\n\n"
                   "AL left: %s days\nPayback debt: 0 min 🚧\nOT bank: 0h 🚧\n"
                   "Upcoming AL: 🚧 (reads al_requests next build)"
                % (p.get("work_start") or "?", p.get("work_end") or "?",
                   p.get("day_off") or "?", exp, p.get("al_left", "?"))), \
        InlineKeyboardMarkup([_back_row()])


def persona_picker(page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    staff = [r for r in staff_all("active")]
    chunk = staff[page * 8:(page + 1) * 8]
    rows = [[InlineKeyboardButton("%s (%s)" % (r["canonical_name"], r.get("org") or "?"),
                                  callback_data="att:persona:%d" % r["id"])] for r in chunk]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀", callback_data="att:pickp:%d" % (page - 1)))
    if (page + 1) * 8 < len(staff):
        nav.append(InlineKeyboardButton("▶", callback_data="att:pickp:%d" % (page + 1)))
    if nav:
        rows.append(nav)
    return "🧪 TEST MODE — pick who you want to act as:", InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------- handlers (OWNER ONLY)

async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only: open the role-play shell."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    if update.effective_chat.type != "private":
        return
    text, kb = persona_picker(0)
    await update.message.reply_text(text, reply_markup=kb)


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """All att:* buttons. Owner-only — everything edits the owner's own message."""
    query = update.callback_query
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        await query.answer()
        return
    await query.answer()
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else ""

    async def show(pair):
        text, kb = pair
        await query.edit_message_text(text, reply_markup=kb)

    if action == "pick":
        return await show(persona_picker(0))
    if action == "pickp":
        return await show(persona_picker(int(data[2])))
    if action == "persona":
        context.user_data["att_persona"] = int(data[2])
        context.user_data["att_al_picked"] = set()
        return await show(main_menu(_persona(context)))

    p = _persona(context)
    if not p:
        return await show(persona_picker(0))

    if action == "menu":
        context.user_data["att_al_picked"] = set()
        return await show(main_menu(p))
    if action == "late":
        if len(data) > 2 and data[2] == "o":
            return await show(late_picked(p, int(data[3])))
        return await show(late_screen(p))
    if action == "al":
        picked = context.user_data.setdefault("att_al_picked", set())
        if len(data) > 2:
            sub = data[2]
            if sub == "d":
                iso = data[3]
                picked.symmetric_difference_update({iso})
                return await show(al_screen(p, picked, context.user_data.get("att_al_page", 0)))
            if sub == "p":
                context.user_data["att_al_page"] = int(data[3])
                return await show(al_screen(p, picked, int(data[3])))
            if sub == "done":
                return await show(al_fullday_or_time(p, picked))
            if sub == "full":
                return await show(al_stub(p, "Full-day AL for %d day(s) selected." % len(picked)))
            if sub == "time":
                return await show(al_time_grid(p, "from"))
            if sub == "f":
                context.user_data["att_al_from"] = int(data[3])
                return await show(al_time_grid(p, "to", int(data[3])))
            if sub == "t":
                f = context.user_data.get("att_al_from")
                return await show(al_stub(p, "Hours AL: %s → %s (fractional deduction)."
                                          % (fmt12(f), fmt12(int(data[3])))))
        context.user_data["att_al_page"] = 0
        return await show(al_screen(p, picked, 0))
    if action == "em":
        if len(data) > 2 and data[2] == "ok":
            return await show(emergency_dates(p))
        if len(data) > 2 and data[2] == "d":
            return await show(al_stub(p, "Emergency AL for %s." % data[3]))
        return await show(emergency_screen(p))
    if action == "do":
        if len(data) > 2 and data[2] == "d":
            return await show(dayoff_partners(p, data[3]))
        if len(data) > 2 and data[2] == "p":
            return await show(al_stub(p, "Day-off swap partner picked. (Partner approval FIRST, "
                                         "then 2 seniors — same week rule.)"))
        return await show(dayoff_screen(p))
    if action == "ot":
        if len(data) > 2 and data[2] == "give":
            return await show(ot_durations(p))
        if len(data) > 2 and data[2] == "d":
            return await show(ot_staff_pick(p, int(data[3])))
        if len(data) > 2 and data[2] == "s":
            return await show(ot_stub(p, int(data[3]), int(data[4])))
        return await show(ot_screen(p))
    if action == "ci":
        return await show(checkin_screen(p))
    if action == "my":
        return await show(my_screen(p))
    # att:noop and anything unknown: stay put
