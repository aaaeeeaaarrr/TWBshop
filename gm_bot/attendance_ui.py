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


# ---------------------------------------------------------------- day dry-run (owner, session 28)

def staff_day_events(p: dict) -> list[tuple[int, str]]:
    """The check-in message schedule for ONE staff member's shift (minutes-of-day, label).
    Pure — the same brain the real scheduler will use at launch."""
    ws = to_min(p.get("work_start"))
    ln = shift_len_min(p.get("work_start"), p.get("work_end")) if ws is not None else None
    if ws is None or ln is None:
        return []
    end = (ws + ln) % 1440
    return [
        ((ws - 10) % 1440, "T−10 pre-reminder"),
        (ws, "T0 start prompt (only if not checked in)"),
        ((ws + 5) % 1440, "T+5 free-minutes message (only if still not checked in)"),
        (end, "check-out request"),
        ((end + 10) % 1440, "leave-early ask (only if no check-out)"),
    ]


def compute_day_events(target: date) -> list[tuple[int, str, str, str]]:
    """All would-be check-in messages for one date, whole active TWB roster, chronological.
    Skips: Tyty, Delis, day-off staff, staff on approved AL that date.
    Returns (minute_of_day, staff_name, label, message_text)."""
    import json as _json

    from shared.database import _db
    on_al: set[int] = set()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_id, days FROM al_requests WHERE status='approved'")
            for r in cur.fetchall():
                try:
                    if target.isoformat() in _json.loads(r["days"] or "[]"):
                        on_al.add(r["staff_id"])
                except Exception:
                    pass
    events = []
    for p in staff_all("active"):
        if p.get("org") != "TWB" or p.get("canonical_name") == "Tyty" or p["id"] in on_al:
            continue
        if _DOW_NAME.get((p.get("day_off") or "")[:3].title()) == target.weekday():
            continue
        name = p.get("call_name") or p["canonical_name"]
        for minute, label in staff_day_events(p):
            if label.startswith("T−10"):
                text = _ci_msg_pre(p)
            elif label.startswith("T0"):
                text = _ci_msg_start()[0]
            elif label.startswith("T+5"):
                text = _CI_MSG_PLUS5
            elif label.startswith("check-out"):
                text = _CI_MSG_OUT
            else:
                text = _CI_MSG_OUT2
            events.append((minute, name, label, text))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


async def _dryrun_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    events = context.user_data.get("att_dr_events") or []
    i = context.user_data.get("att_dr_i", 0)
    chat_id = update.effective_chat.id
    if i >= len(events):
        await context.bot.send_message(chat_id, "📅 Dry-run finished — %d messages walked." % len(events))
        return
    minute, name, label, text = events[i]
    context.user_data["att_dr_i"] = i + 1
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(
        "Next ▶ (%d/%d)" % (i + 2, len(events)), callback_data="att:dr:next")]]) \
        if i + 1 < len(events) else None
    await context.bot.send_message(
        chat_id, "🕘 %s → %s — %s\n────────────\n%s" % (fmt12(minute), name, label, text),
        reply_markup=kb)


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
    # minimal header (owner: buttons explain themselves); (𝗔𝗟) marks AL-funded reasons —
    # Sick unmarked (depends on papers/paperless)
    rows = [
        _back_row("att:am"),
        [InlineKeyboardButton("🤒 Sick · ឈឺ", callback_data="att:sp:sick")],
        [InlineKeyboardButton("💍 Marriage · រៀបការ (𝗔𝗟)", callback_data="att:sp:mar")],
        [InlineKeyboardButton("🕊 Family death · មរណភាពគ្រួសារ (𝗔𝗟)", callback_data="att:sp:death")],
        [InlineKeyboardButton("👶 Wife giving birth · ប្រពន្ធសម្រាលកូន (𝗔𝗟)", callback_data="att:sp:birth")],
    ]
    return _hdr(p, "🕊 Special Leave · ច្បាប់ពិសេស"), InlineKeyboardMarkup(rows)


_WHO_KH = {"child": "កូនរបស់អ្នក", "spouse": "ប្តី/ប្រពន្ធរបស់អ្នក", "parent": "ឪពុក/ម្តាយរបស់អ្នក"}


def sick_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        _back_row("att:sp"),
        [InlineKeyboardButton("Me · ខ្ញុំ", callback_data="att:sp:me")],
        [InlineKeyboardButton("My child · កូនខ្ញុំ (𝗔𝗟)", callback_data="att:sp:sickf:child")],
        [InlineKeyboardButton("My spouse · ប្តី/ប្រពន្ធខ្ញុំ (𝗔𝗟)", callback_data="att:sp:sickf:spouse")],
        [InlineKeyboardButton("My parent · ឪពុក/ម្តាយខ្ញុំ (𝗔𝗟)", callback_data="att:sp:sickf:parent")],
    ]
    return _hdr(p, "🤒 Who is sick?\n🤒 អ្នកណាឈឺ?"), InlineKeyboardMarkup(rows)


def sick_me_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    ws = to_min(p.get("work_start"))
    if ws is None:
        return _hdr(p, "⚠️ No work times on record."), InlineKeyboardMarkup([_back_row("att:sp:sick")])
    offs = late_offsets(shift_len_min(p["work_start"], p["work_end"]))
    btns = [InlineKeyboardButton(fmt12(ws + o), callback_data="att:sp:meo:%d" % o) for o in offs]
    rows = [_back_row("att:sp:sick")] + grid(btns, 3)
    rows.append([InlineKeyboardButton("🛌 I really can't come today · ថ្ងៃនេះមកមិនបានមែនទែន",
                                      callback_data="att:sp:mecant")])
    return _hdr(p, "Sorry to hear 😟 Take some medicine and come try — see how you feel at work.\n"
                   "សោកស្តាយណាស់ 😟 សូមលេបថ្នាំ ហើយមកសាកធ្វើការមើល — មើលថាអ្នកមានអារម្មណ៍យ៉ាងម៉េច"
                   "នៅកន្លែងធ្វើការ។\n\n"
                   "What time can you come?\nអ្នកអាចមកម៉ោងប៉ុន្មាន?"), InlineKeyboardMarkup(rows)


def sick_me_time(p: dict, offset: int) -> tuple[str, InlineKeyboardMarkup]:
    ws = to_min(p.get("work_start"))
    t = fmt12(ws + offset)
    txt = _hdr(p,
               "Get well — see you ~%s 🤍\n"
               "សូមឱ្យឆាប់ធូរស្បើយ — ជួបគ្នាប្រហែល %s 🤍\n\n"
               "[TEST PREVIEW → SUPERVISORS group]\n"
               "“%s is sick, coming ~%s today.”\n\n"
               "(Missed time becomes pay-back, same as informed late. Doctor papers later wipe it.)\n"
               "🚧 Next build: arrival watch, papers photo intake → owner tap, frequency dossier."
               % (t, t, p.get("call_name") or p["canonical_name"], t))
    return txt, InlineKeyboardMarkup([_back_row("att:sp:me"),
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def sick_me_cant(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    txt = _hdr(p,
               "OK — rest well 🤍 If you see a doctor, send me a photo of the papers.\n"
               "បានហើយ — សម្រាកឱ្យបានល្អ 🤍 បើអ្នកបានទៅជួបពេទ្យ សូមផ្ញើរូបថតឯកសារពេទ្យមកខ្ញុំ។\n\n"
               "(Provisional: the missed shift becomes pay-back time unless papers arrive within 3 days.\n"
               "Papers → real sick day: no pay-back, no points, AL untouched.)\n"
               "🚧 Next build: papers intake → owner tap, provisional debt, frequency dossier.")
    return txt, InlineKeyboardMarkup([_back_row("att:sp:me"),
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def sick_family_dates(p: dict, who: str) -> tuple[str, InlineKeyboardMarkup]:
    # ONE day at a time (owner): still sick tomorrow -> ask again before the shift / the night before
    rows = _date_grid_rows("att:sp:famd:%s" % who, _today(), 14, "att:sp:sick")
    return _hdr(p, "🤒 Sick leave for your %s — which day? (one day at a time)\n"
                   "🤒 %sឈឺ — សុំច្បាប់ថ្ងៃណា? (ម្ដងមួយថ្ងៃ)"
                % (who, _WHO_KH.get(who, who))), InlineKeyboardMarkup(rows)


def sick_family_fulltime(p: dict, who: str, iso: str) -> tuple[str, InlineKeyboardMarkup]:
    d = day_label(date.fromisoformat(iso))
    today_running = iso == _today().isoformat() and _shift_running(p)
    rows = [_back_row("att:sp:sickf:%s" % who)]
    if not today_running:
        rows.append([InlineKeyboardButton("Full day · ពេញមួយថ្ងៃ",
                                          callback_data="att:sp:famf:%s:%s" % (who, iso))])
    rows.append([InlineKeyboardButton("Choose time · ជ្រើសម៉ោង",
                                      callback_data="att:sp:famt:%s:%s" % (who, iso))])
    txt = "Sick leave for your %s — %s\nFull day or part of the day?\nសុំឈប់ពេញមួយថ្ងៃ ឬសុំឈប់តាមម៉ោង?" \
          % (who, d)
    return _hdr(p, txt), InlineKeyboardMarkup(rows)


def sick_family_time_grid(p: dict, who: str, iso: str, stage: str,
                          from_min: int | None = None) -> tuple[str, InlineKeyboardMarkup]:
    ws, length = to_min(p.get("work_start")), shift_len_min(p.get("work_start"), p.get("work_end"))
    now_floor = None
    if stage == "from" and iso == _today().isoformat() and _shift_running(p):
        now_floor = ws + ((_now_min() - ws) % 1440)
    btns = []
    if now_floor is not None:
        btns.append(InlineKeyboardButton("Now (%s)" % fmt12(now_floor),
                                         callback_data="att:sp:famtf:%s:%s:%d" % (who, iso, now_floor)))
    for o in range(0, length + 1, 15):
        m = ws + o
        if stage == "from" and o == length:
            continue
        if stage == "to" and from_min is not None and m <= from_min:
            continue
        if now_floor is not None and m <= now_floor:
            continue
        cb = ("att:sp:famtf:%s:%s:%d" % (who, iso, m)) if stage == "from" else \
             ("att:sp:famtt:%s:%s:%d:%d" % (who, iso, from_min, m))
        btns.append(InlineKeyboardButton(fmt12(m), callback_data=cb))
    rows = [_back_row("att:sp:famd:%s:%s" % (who, iso))] + grid(btns, 4)
    q = ("From what time?\nចាប់ពីម៉ោងប៉ុន្មាន?" if stage == "from"
         else "Until what time?\nដល់ម៉ោងប៉ុន្មាន?")
    return _hdr(p, q), InlineKeyboardMarkup(rows)


def sick_family_stub(p: dict, who: str, iso: str, window: str = "full day") -> tuple[str, InlineKeyboardMarkup]:
    d = day_label(date.fromisoformat(iso))
    return _hdr(p, "Sick leave for your %s — %s, %s ✓\n"
                   "ច្បាប់ឈឺសម្រាប់%s — %s, %s ✓\n"
                   "Take care 🤍\nថែទាំឱ្យបានល្អ 🤍\n\n"
                   "🚧 Next build: senior notify + Supervisors notice + the night-before "
                   "one-tap re-book nudge (12h before next shift)."
                % (who, d, window, _WHO_KH.get(who, who), d, window)), \
        InlineKeyboardMarkup([_back_row("att:sp:sick"),
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def marriage_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        _back_row("att:sp"),
        [InlineKeyboardButton("💍 My marriage · រៀបការខ្ញុំ — ស្នើមុន 30+ ថ្ងៃ", callback_data="att:sp:marmy")],
        [InlineKeyboardButton("👰 My child's marriage · រៀបការកូនខ្ញុំ — ស្នើមុន 30+ ថ្ងៃ",
                              callback_data="att:sp:marchild")],
    ]
    return _hdr(p, "💍 Whose marriage?\n💍 អ្នកណារៀបការ?\n"
                   "(Marriages: ask at least 30 days before.)\n"
                   "(រៀបការ៖ សូមស្នើសុំជាមុនយ៉ាងតិច 30 ថ្ងៃ។)"), InlineKeyboardMarkup(rows)


def marriage_dates(p: dict, child: bool) -> tuple[str, InlineKeyboardMarkup]:
    if child:
        rows = _date_grid_rows("att:sp:marcd", _today() + timedelta(days=31), 28, "att:sp:mar")
        return _hdr(p, "👰 Your child's marriage — which day? (1 day; "
                       "must be planned 30+ days ahead)"), InlineKeyboardMarkup(rows)
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
        [InlineKeyboardButton("My child · កូនខ្ញុំ", callback_data="att:sp:deathw:child")],
        [InlineKeyboardButton("My parent · ឪពុក/ម្តាយខ្ញុំ", callback_data="att:sp:deathw:parent")],
        [InlineKeyboardButton("My spouse · ប្តី/ប្រពន្ធខ្ញុំ", callback_data="att:sp:deathw:spouse")],
    ]
    return _hdr(p, "🕊 We're very sorry. Who passed away?\n"
                   "🕊 យើងសូមចូលរួមរំលែកទុក្ខ។ តើអ្នកណាទទួលមរណភាព?"), InlineKeyboardMarkup(rows)


def death_dates(p: dict, who: str) -> tuple[str, InlineKeyboardMarkup]:
    rows = _date_grid_rows("att:sp:deathd:%s" % who, _today(), 8, "att:sp:death")
    return _hdr(p, "🕊 First day of leave?\n🕊 ថ្ងៃចាប់ផ្តើមសម្រាក?"), InlineKeyboardMarkup(rows)


def death_days(p: dict, who: str, iso: str) -> tuple[str, InlineKeyboardMarkup]:
    # owner, session 28: choose 3–7 once at booking (no re-applying mid-funeral); more later = re-enter
    btns = [InlineKeyboardButton("%d ថ្ងៃ / days" % n, callback_data="att:sp:deathn:%s:%s:%d" % (who, iso, n))
            for n in range(3, 8)]
    rows = [_back_row("att:sp:death")] + grid(btns, 3)
    return _hdr(p, "🕊 How many days do you need?\n🕊 ត្រូវការសម្រាកប៉ុន្មានថ្ងៃ?"), InlineKeyboardMarkup(rows)


def death_stub(p: dict, who: str, iso: str, days: int) -> tuple[str, InlineKeyboardMarkup]:
    d = date.fromisoformat(iso)
    dn = day_label(d + timedelta(days=days - 1))
    return _hdr(p, "We're very sorry for your loss 🤍\n"
                   "យើងសូមចូលរួមរំលែកទុក្ខចំពោះការបាត់បង់នេះ 🤍\n\n"
                   "%d days of leave, %s → %s. No approval needed.\n"
                   "សម្រាក %d ថ្ងៃ, %s → %s។ មិនចាំបាច់រង់ចាំការអនុម័តទេ។\n\n"
                   "[TEST PREVIEW → SUPERVISORS group]\n"
                   "“%s on leave %s → %s (family).”  ← reason NEVER in groups\n\n"
                   "(From AL — balance can go below zero, never from salary. Need more later? Just open "
                   "Special Leave again.)\n🚧 Next build: instant booking + notices + negative-AL ledger."
                % (days, day_label(d), dn, days, day_label(d), dn,
                   p.get("call_name") or p["canonical_name"], day_label(d), dn)), \
        InlineKeyboardMarkup([_back_row("att:sp:death"),
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def birth_dates(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = _date_grid_rows("att:sp:birthd", _today(), 8, "att:sp")
    return _hdr(p, "👶 Congratulations! First day of leave? (2 days)\n"
                   "👶 អបអរសាទរ! ថ្ងៃចាប់ផ្តើមសម្រាក? (2 ថ្ងៃ)"), InlineKeyboardMarkup(rows)


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
                "• AL: free when asked 7+ days ahead. Within 7 days is possible — it costs points.\n"
                "• AL៖ ស្នើមុន 7+ ថ្ងៃ = មិនដក Points។ ក្នុង 7 ថ្ងៃ អាចស្នើបាន — តែដក Points។\n\n"
                "• Special Leave (sick, marriage, family death, birth): see the menu — money is never "
                "taken for these.\n"
                "• ច្បាប់ពិសេស (ឈឺ, រៀបការ, មរណភាពគ្រួសារ, ប្រពន្ធសម្រាលកូន)៖ សូមមើលក្នុង menu — "
                "មិនដកលុយសម្រាប់រឿងទាំងនេះទេ។\n\n"
                "• Day-off swap: within 7 days, your partner agrees first.\n"
                "• ប្តូរថ្ងៃឈប់៖ ក្នុងរយៈពេល 7 ថ្ងៃ ហើយអ្នកប្តូរជាមួយត្រូវយល់ព្រមមុន។\n\n"
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
                   "អ្នកនឹងមកដល់ម៉ោងប៉ុន្មាន? សូមជ្រើសម៉ោងដែលអ្នកនឹងមកដល់៖"), InlineKeyboardMarkup(rows)


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
        nav.append(InlineKeyboardButton("◀ Earlier · មុន", callback_data="att:al:p:%d" % (page - 1)))
    if (page + 1) * 28 < 90:
        nav.append(InlineKeyboardButton("Later · បន្ទាប់ ▶", callback_data="att:al:p:%d" % (page + 1)))
    if nav:
        rows.append(nav)
    if picked:
        rows.append([InlineKeyboardButton("✅ Done · រួចរាល់ (%d)" % len(picked),
                                          callback_data="att:al:done")])
    return _hdr(p, "You have %s AL days left. Choose dates (tap to ✓, then Done).\n"
                   "អ្នកនៅសល់ AL %s ថ្ងៃ។ ជ្រើសថ្ងៃ (ចុចដើម្បី ✓ បន្ទាប់មកចុច Done)។\n"
                   "⚠ days are short notice (within 7 days) — they cost points; "
                   "I'll show the exact cost before you confirm.\n"
                   "⚠ ថ្ងៃដែលមានសញ្ញា ⚠ គឺស្នើជិតពេល (ក្នុង 7 ថ្ងៃ) — ត្រូវដក Points; "
                   "ខ្ញុំនឹងបង្ហាញចំនួនដកពិតប្រាកដ មុនពេលអ្នកបញ្ជាក់។"
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
        pts = round(SHORT_NOTICE_PT_PER_MIN * sl * len(near))
        nd = ", ".join(day_label(date.fromisoformat(d)) for d in near)
        txt += ("\n\n⚠ Short notice: %s\n⚠ ស្នើជិតពេល៖ %s\n"
                "Full-day cost: about −%d points (−0.1/min). Hours-AL costs less — I'll show the "
                "exact number.\n"
                "ពេញមួយថ្ងៃ៖ ប្រហែល −%d points (−0.1/min)។ AL តាមម៉ោងដក points តិចជាង — "
                "ខ្ញុំនឹងបង្ហាញចំនួនពិត។" % (nd, nd, pts, pts))
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
    q = ("From what time?\nចាប់ពីម៉ោងប៉ុន្មាន?" if stage == "from"
         else "Until what time?\nដល់ម៉ោងប៉ុន្មាន?")
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
                   "ប្តូរថ្ងៃឈប់ — ជ្រើសថ្ងៃឈប់ថ្មីដែលអ្នកចង់បាន (30 ថ្ងៃខាងមុខ មិនមែនថ្ងៃនេះ)។\n"
                   "Current day off · ថ្ងៃឈប់បច្ចុប្បន្ន៖ %s" % (p.get("day_off") or "?")), \
        InlineKeyboardMarkup(rows)


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
    return _hdr(p, "Swap day-off for %s — with whom? (similar shift times; within 7 days)\n"
                   "ប្តូរថ្ងៃឈប់ទៅ %s — ជាមួយអ្នកណា? (ម៉ោងវេនប្រហាក់ប្រហែល; ក្នុង 7 ថ្ងៃ)"
                % (day_label(d), day_label(d))), InlineKeyboardMarkup(rows)


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
    return _hdr(p, "Give OT — how much?\nអនុញ្ញាត OT — ប៉ុន្មានម៉ោង?"), InlineKeyboardMarkup(rows)


def ot_staff_pick(p: dict, minutes: int) -> tuple[str, InlineKeyboardMarkup]:
    rows = [_back_row("att:ot:give")]
    rows += [[InlineKeyboardButton(r["canonical_name"], callback_data="att:ot:s:%d:%d" % (minutes, r["id"]))]
             for r in staff_all("active") if r.get("org") == "TWB" and r.get("canonical_name") != "Tyty"][:35]
    label = ("%dmin" % minutes) if minutes < 60 else ("%gh" % (minutes / 60))
    return _hdr(p, "Give %s OT — to whom?\nអនុញ្ញាត OT %s — ឱ្យអ្នកណា?" % (label, label)), \
        InlineKeyboardMarkup(rows)


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
        InlineKeyboardMarkup([_back_row(),
                              [InlineKeyboardButton("▶️ Simulate the check-in messages",
                                                    callback_data="att:cis")]])


def ci_sim_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        _back_row("att:ci"),
        [InlineKeyboardButton("① T−10min — pre-reminder", callback_data="att:cis:pre")],
        [InlineKeyboardButton("② T0 — shift-start prompt", callback_data="att:cis:start")],
        [InlineKeyboardButton("③ T+5min — free-minutes message", callback_data="att:cis:plus5")],
        [InlineKeyboardButton("④ 🎯 Arm: judge my next live location", callback_data="att:cis:arm")],
        [InlineKeyboardButton("⑤ Shift end — check-out request", callback_data="att:cis:out")],
        [InlineKeyboardButton("⑥ +10min — did-you-leave-early ask", callback_data="att:cis:out2")],
    ]
    return _hdr(p, "▶️ Check-in simulator — each button sends the REAL message exactly as %s would "
                   "receive it (to you only). ④ makes your next shared live location be judged as "
                   "their check-in (geofence + early/late vs their %s start)."
                % (p.get("call_name") or p["canonical_name"], p.get("work_start") or "?")), \
        InlineKeyboardMarkup(rows)


def _ci_msg_pre(p: dict) -> str:
    ws = to_min(p.get("work_start"))
    t = fmt12(ws) if ws is not None else "?"
    return ("Your shift starts in 10 minutes (%s). Check in by sharing your live location.\n"
            "វេនការងាររបស់អ្នកនឹងចាប់ផ្តើមក្នុង 10 នាទីទៀត (%s)។ សូមចុះវត្តមានដោយចែករំលែក"
            "ទីតាំងបន្តផ្ទាល់។\n\n"
            "Arrive 5 minutes early and you earn +10 points ⭐\n"
            "មកដល់មុន 5 នាទី អ្នកនឹងទទួលបាន +10 points ⭐" % (t, t))


def _ci_msg_start() -> tuple[str, InlineKeyboardMarkup]:
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🕘 I'm late · ខ្ញុំមកយឺត", callback_data="att:late")],
        [InlineKeyboardButton("📍 How to check in · របៀបចុះវត្តមាន", callback_data="att:ci")],
    ])
    return ("Your shift just started. Please share your live location to check in.\n"
            "វេនការងាររបស់អ្នកទើបតែចាប់ផ្តើមហើយ។ សូមចែករំលែកទីតាំងបន្តផ្ទាល់ ដើម្បីចុះវត្តមាន។\n\n"
            "Running late? Tap below.\nកំពុងមកយឺតមែនទេ? សូមចុចខាងក្រោម។"), kb


_CI_MSG_PLUS5 = ("We give everyone 5 free late minutes 😊 More than 5 — every late minute counts: "
                 "as pay-back time, and minus points. The sooner you tell us, the fewer points it "
                 "costs. See you soon!\n"
                 "យើងផ្ដល់ឱ្យគ្រប់គ្នា 5 នាទីអនុគ្រោះសម្រាប់ការមកយឺត 😊 បើលើសពី 5 នាទី រាល់នាទីយឺត"
                 "ទាំងអស់នឹងត្រូវរាប់៖ ជាម៉ោងសងវិញ និងដកពិន្ទុ។ ប្រាប់យើងកាន់តែឆាប់ ពិន្ទុដែលត្រូវដក"
                 "កាន់តែតិច។ ជួបគ្នាឆាប់ៗ!")

_CI_MSG_OUT = ("Shift over — share your live location to check out.\n"
               "វេនចប់ហើយ — សូមចែករំលែកទីតាំងបន្តផ្ទាល់ ដើម្បីចុះវត្តមានចេញ។")

_CI_MSG_OUT2 = ("Did you leave early? If not, share your location to check out.\n"
                "អ្នកចេញមុនម៉ោងមែនទេ? បើមិនមែន សូមចែករំលែកទីតាំងបន្តផ្ទាល់ ដើម្បីចុះវត្តមានចេញ។")


def my_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    exp = ", ".join(p.get("expertise") or []) or "-"
    return _hdr(p, "📋 My schedule · កាលវិភាគខ្ញុំ\n"
                   "Shift · វេន: %s–%s\nDay off · ថ្ងៃឈប់: %s\nExpertise · ជំនាញ: %s\n\n"
                   "AL left · AL នៅសល់: %s days\n"
                   "Payback debt · ជំពាក់ម៉ោងសងវិញ: 0 min 🚧\n"
                   "OT bank · OT សន្សំ: 0h 🚧\n"
                   "Upcoming AL · AL ខាងមុខ: 🚧 (reads al_requests next build)"
                % (p.get("work_start") or "?", p.get("work_end") or "?",
                   p.get("day_off") or "?", exp, p.get("al_left", "?"))), \
        InlineKeyboardMarkup([_back_row("att:am")])


def persona_picker(page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    staff = [r for r in staff_all("active")]
    chunk = staff[page * 8:(page + 1) * 8]
    rows = [[InlineKeyboardButton("📅 Dry-run today's check-in messages (whole roster)",
                                  callback_data="att:dr:go")]] if page == 0 else []
    rows += [[InlineKeyboardButton("%s (%s)" % (r["canonical_name"], r.get("org") or "?"),
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

async def handle_location_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """TEST-ONLY location handler — OWNER ONLY (staff pins/locations stay unanswered until the
    real check-in build). Static pin -> the final bilingual template; live location -> geofence
    readout so the owner can test the 200m zone from anywhere."""
    msg = update.message or update.edited_message
    if not msg or not msg.location or update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    # EDITED location = live-share lifecycle (movement updates + the final "stopped sharing" edit,
    # which no longer carries live_period). NEVER the pin template; quiet in test mode.
    # (Real build: the stop-edit is the "location went off" signal for left-early/check-out.)
    if update.edited_message:
        return
    loc = msg.location
    if getattr(loc, "live_period", None):
        from gm_bot.attendance import TWB_LAT, TWB_LNG, haversine_m
        dist = haversine_m(loc.latitude, loc.longitude, TWB_LAT, TWB_LNG)
        # ARMED check-in simulation: judge this live location as the persona's check-in
        if context.user_data.get("att_ci_armed"):
            context.user_data["att_ci_armed"] = False
            p = _persona(context)
            ws = to_min(p.get("work_start")) if p else None
            if p and ws is not None:
                if dist > 200:
                    await msg.reply_text(
                        "You're not at the shop yet — it will count when you arrive.\n"
                        "អ្នកមិនទាន់នៅហាងទេ — ចុះវត្តមាននឹងរាប់ពេលអ្នកមកដល់។\n"
                        "[test: %dm from TWB]" % round(dist))
                    return
                rel = (_now_min() - ws) % 1440
                early = 1440 - rel if rel > 720 else 0
                late = rel if rel <= 720 else 0
                if early >= 5:
                    await msg.reply_text(
                        "Checked in ✓ — %d min early. +10 points ⭐\n"
                        "ចុះវត្តមានរួច ✓ — មុន %d នាទី។ +10 points ⭐" % (early, early))
                elif late <= 5:
                    await msg.reply_text("Checked in ✓\nចុះវត្តមានរួច ✓")
                else:
                    await msg.reply_text(
                        "Checked in ✓ — %d min late (counts as pay-back).\n"
                        "ចុះវត្តមានរួច ✓ — យឺត %d នាទី (រាប់ជាម៉ោងសងវិញ)។\n\n"
                        "Why were you late?\nហេតុអ្វីបានជាអ្នកមកយឺត?" % (late, late))
                return
        await msg.reply_text(
            "🧪 [TEST] Live location received ✓\nDistance from TWB: %dm — %s"
            % (round(dist), "INSIDE the 200m zone ✅" if dist <= 200 else "outside the zone ❌"))
        return
    # static pin (always a NEW message) — the locked bilingual response
    await msg.reply_text(
        "Sending a pin does not count as check-in to work.\n"
        "ការផ្ញើទីតាំងជា Pin មិនរាប់ជាការចុះវត្តមានចូលធ្វើការទេ។\n\n"
        "Do this instead:\nសូមធ្វើតាមនេះវិញ៖\n\n"
        "Tap 📎 (Attach) → Location / ទីតាំង → Share Live Location / ចែករំលែកទីតាំងបន្តផ្ទាល់")


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

    if action == "dr":
        if len(data) > 2 and data[2] == "go":
            events = compute_day_events(_today())
            context.user_data["att_dr_events"] = events
            context.user_data["att_dr_i"] = 0
            await context.bot.send_message(
                update.effective_chat.id,
                "📅 Dry-run for %s — %d messages the engine would send today (skipping day-offs, "
                "AL, Tyty, Delis). Tap through:" % (day_label(_today()), len(events)))
        await _dryrun_next(update, context)
        return
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
            return await show(sick_family_fulltime(p, data[3], data[4]))
        if sub == "famf":
            return await show(sick_family_stub(p, data[3], data[4]))
        if sub == "famt":
            return await show(sick_family_time_grid(p, data[3], data[4], "from"))
        if sub == "famtf":
            return await show(sick_family_time_grid(p, data[3], data[4], "to", int(data[5])))
        if sub == "famtt":
            window = "%s → %s" % (fmt12(int(data[5])), fmt12(int(data[6])))
            return await show(sick_family_stub(p, data[3], data[4], window))
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
            return await show(death_days(p, data[3], data[4]))
        if sub == "deathn":
            return await show(death_stub(p, data[3], data[4], int(data[5])))
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
    if action == "cis":
        sub = data[2] if len(data) > 2 else ""
        chat_id = update.effective_chat.id
        if sub == "":
            return await show(ci_sim_menu(p))
        if sub == "pre":
            await context.bot.send_message(chat_id, _ci_msg_pre(p))
        elif sub == "start":
            text, kb = _ci_msg_start()
            await context.bot.send_message(chat_id, text, reply_markup=kb)
        elif sub == "plus5":
            await context.bot.send_message(chat_id, _CI_MSG_PLUS5)
        elif sub == "arm":
            context.user_data["att_ci_armed"] = True
            await context.bot.send_message(
                chat_id, "🎯 Armed — share a live location now and I'll judge it as %s's check-in."
                % (p.get("call_name") or p["canonical_name"]))
        elif sub == "out":
            await context.bot.send_message(chat_id, _CI_MSG_OUT)
        elif sub == "out2":
            await context.bot.send_message(chat_id, _CI_MSG_OUT2)
        return
    if action == "my":
        return await show(my_screen(p))
    # att:noop and anything unknown: stay put
