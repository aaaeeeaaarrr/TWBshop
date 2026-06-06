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

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from gm_bot.attendance import to_min
from shared.database import staff_all

_DOW = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_DOW_NAME = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
_PP = ZoneInfo("Asia/Phnom_Penh")
SHORT_NOTICE_PT_PER_MIN = 0.1   # owner, session 28: AL days within 7 days cost −0.1 pt/min (pending)


def _today() -> date:
    return datetime.now(_PP).date()


def _now_min() -> int:
    n = datetime.now(_PP)
    return n.hour * 60 + n.minute


def _shift_running(p: dict) -> bool:
    ws = to_min(p.get("work_start"))
    ln = shift_len_min(p.get("work_start"), p.get("work_end")) if ws is not None else None
    if ws is None or ln is None:
        return False
    return (_now_min() - ws) % 1440 < ln


def _near_days(picked: set[str]) -> list[str]:
    """Selected dates that are short notice (today..today+6)."""
    cut = _today() + timedelta(days=6)
    return sorted(d for d in picked if date.fromisoformat(d) <= cut)


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
    # Khmer labels reviewed via ChatGPT, owner-approved session 28.
    # Order + grouping per owner (session 28): Check-in, Late, About Work (seniors), About Me.
    # Emergency AL REMOVED by owner — weird emergencies will be handled via the points system (TBD).
    # About Work is open to EVERYONE now (owner session 28): Rules for all, Give OT inside for seniors
    rows = [
        [InlineKeyboardButton("📍 Check in · ចុះវត្តមាន", callback_data="att:ci")],
        [InlineKeyboardButton("🕘 Late · មកយឺត", callback_data="att:late")],
        [InlineKeyboardButton("🧰 About Work · កិច្ចការហាង", callback_data="att:aw")],
        [InlineKeyboardButton("👤 About Me · របស់ខ្ញុំ", callback_data="att:am")],
        [InlineKeyboardButton("🎭 Switch persona", callback_data="att:pick")],
    ]
    return _hdr(p, "Main menu — what they see when they type anything:"), InlineKeyboardMarkup(rows)


def about_me_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        _back_row(),
        [InlineKeyboardButton("🏖 Annual Leave (AL) · ឈប់សម្រាកប្រចាំឆ្នាំ", callback_data="att:al")],
        [InlineKeyboardButton("🕊 Special Leave · ច្បាប់ពិសេស", callback_data="att:sp")],
        [InlineKeyboardButton("🔁 Change day off · ប្តូរថ្ងៃឈប់សម្រាក", callback_data="att:do")],
        [InlineKeyboardButton("⏱ OT · ថែមម៉ោង", callback_data="att:ot")],
        [InlineKeyboardButton("📋 My schedule · កាលវិភាគការងាររបស់ខ្ញុំ", callback_data="att:my")],
    ]
    return _hdr(p, "👤 About Me"), InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------- special leave (session 28)

def _date_grid_rows(prefix: str, start: date, count: int, back: str) -> list[list[InlineKeyboardButton]]:
    btns = [InlineKeyboardButton(day_label(start + timedelta(days=i)),
                                 callback_data="%s:%s" % (prefix, (start + timedelta(days=i)).isoformat()))
            for i in range(count)]
    return [_back_row(back)] + grid(btns, 4)


def special_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        _back_row("att:am"),
        [InlineKeyboardButton("🤒 Sick", callback_data="att:sp:sick")],
        [InlineKeyboardButton("💍 Marriage", callback_data="att:sp:mar")],
        [InlineKeyboardButton("🕊 Family death", callback_data="att:sp:death")],
        [InlineKeyboardButton("👶 Wife giving birth", callback_data="att:sp:birth")],
    ]
    return _hdr(p, "🕊 Special Leave — choose the reason:\n"
                   "(taken from AL; for marriage / family death / birth the balance can go below zero — "
                   "never from salary)"), InlineKeyboardMarkup(rows)


def sick_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        _back_row("att:sp"),
        [InlineKeyboardButton("Me", callback_data="att:sp:me")],
        [InlineKeyboardButton("My child", callback_data="att:sp:sickf:child")],
        [InlineKeyboardButton("My spouse", callback_data="att:sp:sickf:spouse")],
        [InlineKeyboardButton("My parent", callback_data="att:sp:sickf:parent")],
    ]
    return _hdr(p, "🤒 Who is sick?"), InlineKeyboardMarkup(rows)


def sick_me_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    ws = to_min(p.get("work_start"))
    if ws is None:
        return _hdr(p, "⚠️ No work times on record."), InlineKeyboardMarkup([_back_row("att:sp:sick")])
    offs = late_offsets(shift_len_min(p["work_start"], p["work_end"]))
    btns = [InlineKeyboardButton(fmt12(ws + o), callback_data="att:sp:meo:%d" % o) for o in offs]
    rows = [_back_row("att:sp:sick")] + grid(btns, 3)
    rows.append([InlineKeyboardButton("🛌 I really can't come today", callback_data="att:sp:mecant")])
    return _hdr(p, "Sorry to hear 😟 Take some medicine and come try — see how you feel at work.\n"
                   "What time can you come?"), InlineKeyboardMarkup(rows)


def sick_me_time(p: dict, offset: int) -> tuple[str, InlineKeyboardMarkup]:
    ws = to_min(p.get("work_start"))
    txt = _hdr(p,
               "Get well — see you ~%s 🤍\n\n"
               "[TEST PREVIEW → SUPERVISORS group]\n"
               "“%s is sick, coming ~%s today.”\n\n"
               "(Missed time becomes pay-back, same as informed late. Doctor papers later wipe it.)\n"
               "🚧 Next build: arrival watch, papers photo intake → owner tap, frequency dossier."
               % (fmt12(ws + offset), p.get("call_name") or p["canonical_name"], fmt12(ws + offset)))
    return txt, InlineKeyboardMarkup([_back_row("att:sp:me"),
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def sick_me_cant(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    txt = _hdr(p,
               "OK — rest well 🤍 If you see a doctor, send me a photo of the papers.\n\n"
               "(Provisional: the missed shift becomes pay-back time unless papers arrive within 3 days.\n"
               "Papers → real sick day: no pay-back, no points, AL untouched.)\n"
               "🚧 Next build: papers intake → owner tap, provisional debt, frequency dossier.")
    return txt, InlineKeyboardMarkup([_back_row("att:sp:me"),
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def sick_family_dates(p: dict, who: str) -> tuple[str, InlineKeyboardMarkup]:
    rows = _date_grid_rows("att:sp:famd:%s" % who, _today(), 14, "att:sp:sick")
    return _hdr(p, "🤒 Sick leave for your %s — which day?" % who), InlineKeyboardMarkup(rows)


def sick_family_stub(p: dict, who: str, iso: str) -> tuple[str, InlineKeyboardMarkup]:
    d = day_label(date.fromisoformat(iso))
    return _hdr(p, "Sick leave for your %s on %s — from the 7-day special-leave pool (AL), "
                   "no points, no papers needed.\n🚧 Next build: notify seniors (no approval gate) + "
                   "Supervisors plain notice + pool counter." % (who, d)), \
        InlineKeyboardMarkup([_back_row("att:sp:sick"),
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def marriage_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        _back_row("att:sp"),
        [InlineKeyboardButton("💍 My marriage (3 days)", callback_data="att:sp:marmy")],
        [InlineKeyboardButton("👰 My child's marriage (1 day)", callback_data="att:sp:marchild")],
    ]
    return _hdr(p, "💍 Whose marriage?"), InlineKeyboardMarkup(rows)


def marriage_dates(p: dict, child: bool) -> tuple[str, InlineKeyboardMarkup]:
    if child:
        rows = _date_grid_rows("att:sp:marcd", _today() + timedelta(days=1), 28, "att:sp:mar")
        return _hdr(p, "👰 Your child's marriage — which day? (1 day)"), InlineKeyboardMarkup(rows)
    # own marriage: dates start at day 31 (owner rule — plan 30+ days ahead)
    rows = _date_grid_rows("att:sp:mard", _today() + timedelta(days=31), 28, "att:sp:mar")
    return _hdr(p, "💍 Your marriage — first day of leave? (3 days; "
                   "must be planned 30+ days ahead)"), InlineKeyboardMarkup(rows)


def marriage_stub(p: dict, iso: str, child: bool) -> tuple[str, InlineKeyboardMarkup]:
    d = date.fromisoformat(iso)
    if child:
        detail = "👰 Child's marriage: 1 day on %s." % day_label(d)
    else:
        d3 = day_label(d + timedelta(days=2))
        detail = "💍 Your marriage: 3 days, %s → %s." % (day_label(d), d3)
    return _hdr(p, detail + "\nFrom AL — balance can go below zero, never from salary. "
                            "Senior approval like a normal AL.\n🚧 Next build: approval flow + notices."), \
        InlineKeyboardMarkup([_back_row("att:sp:mar"),
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def death_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        _back_row("att:sp"),
        [InlineKeyboardButton("My child", callback_data="att:sp:deathw:child")],
        [InlineKeyboardButton("My parent", callback_data="att:sp:deathw:parent")],
        [InlineKeyboardButton("My spouse", callback_data="att:sp:deathw:spouse")],
    ]
    return _hdr(p, "🕊 We're very sorry. Who passed away?"), InlineKeyboardMarkup(rows)


def death_dates(p: dict, who: str) -> tuple[str, InlineKeyboardMarkup]:
    rows = _date_grid_rows("att:sp:deathd:%s" % who, _today(), 8, "att:sp:death")
    return _hdr(p, "🕊 First day of leave? (3 days)"), InlineKeyboardMarkup(rows)


def death_stub(p: dict, who: str, iso: str) -> tuple[str, InlineKeyboardMarkup]:
    d = date.fromisoformat(iso)
    d3 = day_label(d + timedelta(days=2))
    return _hdr(p, "We're very sorry for your loss 🤍\n"
                   "3 days of leave, %s → %s. No approval needed.\n\n"
                   "[TEST PREVIEW → SUPERVISORS group]\n"
                   "“%s on leave %s → %s (family).”  ← reason NEVER in groups\n\n"
                   "(From AL — balance can go below zero, never from salary. Extra days possible as "
                   "normal AL.)\n🚧 Next build: instant booking + notices + negative-AL ledger."
                % (day_label(d), d3, p.get("call_name") or p["canonical_name"], day_label(d), d3)), \
        InlineKeyboardMarkup([_back_row("att:sp:death"),
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def birth_dates(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = _date_grid_rows("att:sp:birthd", _today(), 8, "att:sp")
    return _hdr(p, "👶 Congratulations! First day of leave? (2 days)"), InlineKeyboardMarkup(rows)


def birth_stub(p: dict, iso: str) -> tuple[str, InlineKeyboardMarkup]:
    d = date.fromisoformat(iso)
    d2 = day_label(d + timedelta(days=1))
    return _hdr(p, "👶 2 days of leave, %s → %s.\nFrom AL — balance can go below zero, never from "
                   "salary.\n🚧 Next build: notify seniors + Supervisors plain notice."
                % (day_label(d), d2)), \
        InlineKeyboardMarkup([_back_row("att:sp"),
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def about_work_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    # Rules for everyone; Give OT seniors only; later: Stocks + other checks (owner)
    rows = [
        _back_row(),
        [InlineKeyboardButton("📜 Rules · ច្បាប់ហាង", callback_data="att:rules")],
    ]
    if p.get("is_senior"):
        rows.append([InlineKeyboardButton("➕ Give OT", callback_data="att:ot:give")])
    return _hdr(p, "🧰 About Work"), InlineKeyboardMarkup(rows)


def rules_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    # FINAL bilingual wording (owner + ChatGPT, session 28, via khmer_inbox)
    return _hdr(p,
                "📜 Shop rules — the short version\n"
                "📜 ច្បាប់ហាង — សង្ខេបខ្លីៗ\n\n"
                "• Check in by sharing live location. Arrive 5+ min early = +10 points ⭐\n"
                "• ចុះវត្តមានដោយចែករំលែកទីតាំងបន្តផ្ទាល់។ មកដល់មុន 5+ នាទី = +10 Points ⭐\n\n"
                "• Late? Tell us as early as you can — the sooner you tell, the fewer points it costs.\n"
                "• មកយឺត? សូមប្រាប់យើងឱ្យបានឆាប់បំផុត — ប្រាប់កាន់តែឆាប់ ពិន្ទុដែលត្រូវដកកាន់តែតិច។\n\n"
                "• The first 5 late minutes are free 😊 More than 5 — every minute counts.\n"
                "• 5 នាទីយឺតដំបូង គឺជានាទីអនុគ្រោះ 😊 បើលើសពី 5 នាទី រាល់នាទីយឺតទាំងអស់នឹងត្រូវរាប់។\n\n"
                "• Late minutes become pay-back time — you work them back when the shop needs you.\n"
                "• នាទីយឺតនឹងក្លាយជាម៉ោងសងវិញ — អ្នកធ្វើសងពេលហាងត្រូវការអ្នក។\n\n"
                "• No-show = 1 day's pay and no bonus this time.\n"
                "• No-show = ប្រាក់ឈ្នួល 1 ថ្ងៃ និងមិនមាន Bonus លើកនេះ។\n\n"
                "• AL: ask 7+ days ahead. Day-off swap: within 7 days, your partner agrees first.\n"
                "• AL៖ សូមស្នើសុំជាមុន 7+ ថ្ងៃ។ ប្តូរថ្ងៃឈប់៖ ក្នុងរយៈពេល 7 ថ្ងៃ ហើយអ្នកប្តូរជាមួយត្រូវយល់ព្រមមុន។\n\n"
                "• OT: given by seniors, saved as hours — take them back when it's calm.\n"
                "• OT៖ បងៗ/អ្នកគ្រប់គ្រងជាអ្នកអនុញ្ញាត ហើយសន្សំជាម៉ោង — អាចសម្រាកសងម៉ោងវិញ ពេលហាងស្ងប់។\n\n"
                "• Points restart after every 2nd pay — every month is a fresh start 🌱\n"
                "• Points ចាប់ផ្ដើមឡើងវិញបន្ទាប់ពីការបើកប្រាក់លើកទី 2 — រៀងរាល់ខែគឺជាការចាប់ផ្ដើមថ្មី 🌱"), \
        InlineKeyboardMarkup([_back_row("att:aw")])


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
    start = _today() + timedelta(days=page * 28)
    days = [start + timedelta(days=i) for i in range(28)]
    near_cut = _today() + timedelta(days=6)
    btns = []
    for d in days:
        iso = d.isoformat()
        mark = "✓ " if iso in picked else ""
        warn = "⚠ " if d <= near_cut else ""
        btns.append(InlineKeyboardButton(warn + mark + day_label(d), callback_data="att:al:d:%s" % iso))
    rows = [_back_row("att:am")] + grid(btns, 4)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Earlier", callback_data="att:al:p:%d" % (page - 1)))
    if (page + 1) * 28 < 90:
        nav.append(InlineKeyboardButton("Later ▶", callback_data="att:al:p:%d" % (page + 1)))
    if nav:
        rows.append(nav)
    if picked:
        rows.append([InlineKeyboardButton("✅ Done (%d day%s)" % (len(picked), "s" if len(picked) > 1 else ""),
                                          callback_data="att:al:done")])
    return _hdr(p, "You have %s AL days left. Choose dates (tap to ✓, then Done).\n"
                   "អ្នកនៅសល់ច្បាប់ %s ថ្ងៃ។ ជ្រើសរើសថ្ងៃ៖\n"
                   "⚠ days are short notice (within 7 days) — they cost points; "
                   "I'll show the exact cost before you confirm."
                % (al_left if al_left is not None else "?", al_left if al_left is not None else "?")), \
        InlineKeyboardMarkup(rows)


def al_fullday_or_time(p: dict, picked: set[str]) -> tuple[str, InlineKeyboardMarkup]:
    days = ", ".join(day_label(date.fromisoformat(d)) for d in sorted(picked))
    today_running = _today().isoformat() in picked and _shift_running(p)
    rows = [_back_row("att:al")]
    if not today_running:  # a half-worked day can only be "from now" — Full day hidden
        rows.append([InlineKeyboardButton("Full day · ពេញមួយថ្ងៃ", callback_data="att:al:full")])
    rows.append([InlineKeyboardButton("Choose time · ជ្រើសម៉ោង", callback_data="att:al:time")])
    txt = "AL for: %s\nFull day or part of the day?\nសុំឈប់ពេញមួយថ្ងៃ ឬសុំឈប់តាមម៉ោង?" % days
    near = _near_days(picked)
    if near:
        sl = shift_len_min(p.get("work_start"), p.get("work_end")) or 0
        pts = SHORT_NOTICE_PT_PER_MIN * sl * len(near)
        txt += ("\n\n⚠ Short notice: %s\nFull-day cost: about −%d points (−0.1/min). "
                "Hours-AL costs less — I'll show the exact number."
                % (", ".join(day_label(date.fromisoformat(d)) for d in near), round(pts)))
    if today_running:
        txt += "\n\n(Your shift already started — time starts from NOW.)"
    return _hdr(p, txt), InlineKeyboardMarkup(rows)


def al_time_grid(p: dict, stage: str, from_min: int | None = None,
                 picked: set[str] | None = None) -> tuple[str, InlineKeyboardMarkup]:
    ws, length = to_min(p.get("work_start")), shift_len_min(p.get("work_start"), p.get("work_end"))
    # today selected + shift running -> first option is NOW, nothing in the past (owner, session 28)
    now_floor = None
    if stage == "from" and picked and _today().isoformat() in picked and _shift_running(p):
        now_floor = ws + ((_now_min() - ws) % 1440)
    btns = []
    if now_floor is not None:
        btns.append(InlineKeyboardButton("Now (%s)" % fmt12(now_floor),
                                         callback_data="att:al:f:%d" % now_floor))
    for o in range(0, length + 1, 15):
        m = ws + o
        if stage == "from" and o == length:
            continue
        if stage == "to" and from_min is not None and m <= from_min:
            continue
        if now_floor is not None and m <= now_floor:
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
    start = _today() + timedelta(days=1)
    own_off = _DOW_NAME.get((p.get("day_off") or "")[:3].title())
    btns = []
    for i in range(30):
        d = start + timedelta(days=i)
        if d.weekday() == own_off:
            continue  # their current day off — nothing to swap there (owner, session 28)
        btns.append(InlineKeyboardButton(day_label(d), callback_data="att:do:d:%s" % d.isoformat()))
    rows = [_back_row("att:am")] + grid(btns, 4)
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
    # everyone's personal OT view — Give OT lives under About Work (seniors)
    return _hdr(p, "Your OT bank: 0h 🚧\n\nOT is given by your seniors when the shop needs extra "
                   "hours — when you have hours banked, I'll show you the times to take them back.\n"
                   "OT ត្រូវបានអនុញ្ញាតដោយបងៗ/អ្នកគ្រប់គ្រង ពេលហាងត្រូវការម៉ោងបន្ថែម។ "
                   "ពេលអ្នកមានម៉ោង OT សន្សំទុក ខ្ញុំនឹងបង្ហាញពេលដែលអ្នកអាចសម្រាកសងម៉ោងវិញបាន។"), \
        InlineKeyboardMarkup([_back_row("att:am")])


def ot_durations(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    btns = []
    m = 30
    while m <= 360:
        label = ("%dmin" % m) if m < 60 else ("%gh" % (m / 60))
        btns.append(InlineKeyboardButton(label, callback_data="att:ot:d:%d" % m))
        m += 30
    rows = [_back_row("att:aw")] + grid(btns, 4)
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
    return txt, InlineKeyboardMarkup([_back_row("att:aw"),
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
        InlineKeyboardMarkup([_back_row("att:am")])


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
    if action == "am":
        return await show(about_me_menu(p))
    if action == "sp":
        sub = data[2] if len(data) > 2 else ""
        if sub == "":
            return await show(special_menu(p))
        if sub == "sick":
            return await show(sick_menu(p))
        if sub == "me":
            return await show(sick_me_screen(p))
        if sub == "meo":
            return await show(sick_me_time(p, int(data[3])))
        if sub == "mecant":
            return await show(sick_me_cant(p))
        if sub == "sickf":
            return await show(sick_family_dates(p, data[3]))
        if sub == "famd":
            return await show(sick_family_stub(p, data[3], data[4]))
        if sub == "mar":
            return await show(marriage_menu(p))
        if sub == "marmy":
            return await show(marriage_dates(p, child=False))
        if sub == "marchild":
            return await show(marriage_dates(p, child=True))
        if sub == "mard":
            return await show(marriage_stub(p, data[3], child=False))
        if sub == "marcd":
            return await show(marriage_stub(p, data[3], child=True))
        if sub == "death":
            return await show(death_menu(p))
        if sub == "deathw":
            return await show(death_dates(p, data[3]))
        if sub == "deathd":
            return await show(death_stub(p, data[3], data[4]))
        if sub == "birth":
            return await show(birth_dates(p))
        if sub == "birthd":
            return await show(birth_stub(p, data[3]))
        return await show(special_menu(p))
    if action == "aw":
        return await show(about_work_menu(p))
    if action == "rules":
        return await show(rules_screen(p))
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
                near = _near_days(picked)
                detail = "Full-day AL for %d day(s) selected." % len(picked)
                if near:
                    sl = shift_len_min(p.get("work_start"), p.get("work_end")) or 0
                    detail += ("\n⚠ %d short-notice day(s) → −%d points (−0.1/min, pending activation)."
                               % (len(near), round(SHORT_NOTICE_PT_PER_MIN * sl * len(near))))
                return await show(al_stub(p, detail))
            if sub == "time":
                return await show(al_time_grid(p, "from", picked=picked))
            if sub == "f":
                context.user_data["att_al_from"] = int(data[3])
                return await show(al_time_grid(p, "to", int(data[3])))
            if sub == "t":
                f = context.user_data.get("att_al_from")
                t = int(data[3])
                detail = "Hours AL: %s → %s (fractional deduction)." % (fmt12(f), fmt12(t))
                near = _near_days(picked)
                if near:
                    window = t - f
                    detail += ("\n⚠ %d short-notice day(s) → −%d points (−0.1/min, pending activation)."
                               % (len(near), round(SHORT_NOTICE_PT_PER_MIN * window * len(near))))
                return await show(al_stub(p, detail))
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
