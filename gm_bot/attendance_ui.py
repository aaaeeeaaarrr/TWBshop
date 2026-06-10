"""Attendance main-menu — owner role-play SHELL + LIVE staff entry (one set of menus, no fork).

TWO drivers, the SAME menus / callbacks / submit_* (Rule 1 — no behavior fork):
  - OWNER role-play shell via /test: the owner picks a PERSONA and walks every ladder; every
    message routes to the owner ([→ role] previews); rows are is_test-tagged. Active whenever
    attendance_test_mode is on.
  - LIVE staff entry: a real ACTIVE TWB staffer opens their OWN menu — persona LOCKED to
    themselves, never another. GATED by attendance_live; submit_* route to the real recipients
    via bot._att_send. Reason capture uses flow_state (DB, restart-safe).

⚠️ SAFETY: when attendance_live is OFF and test mode is OFF, this module messages NO ONE but the
owner — the live branch is gated (callback rejects non-owners unless _attendance_live()), and the
owner branch only ever edits the owner's own message. Pure helpers at the top are unit-tested in
tests/test_attendance_ui.py; live entry in tests/test_attendance_live_entry.py.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from gm_bot.attendance import to_min, overlaps
from shared.database import (staff_all, att_test_on, staff_get_by_uid, flow_save,
                             al_leave_days_set, staff_absent_dates)

_DOW = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_DOW_NAME = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
_PP = ZoneInfo("Asia/Phnom_Penh")
SHORT_NOTICE_PT_PER_MIN = 0.1   # owner, session 28: AL days within 7 days cost −0.1 pt/min (pending)


def _today() -> date:
    return datetime.now(_PP).date()


def _now_min() -> int:
    n = datetime.now(_PP)
    return n.hour * 60 + n.minute


def _hm(minutes) -> str:
    """Readable duration for staff (no dividing by 60): '4h', '4h 30m', '45m', '0h'."""
    minutes = int(round(minutes or 0))
    if minutes <= 0:
        return "0h"
    h, m = divmod(minutes, 60)
    return ("%dh %dm" % (h, m)) if (h and m) else (("%dh" % h) if h else ("%dm" % m))


def _shift_running(p: dict) -> bool:
    ws = to_min(p.get("work_start"))
    ln = shift_len_min(p.get("work_start"), p.get("work_end")) if ws is not None else None
    if ws is None or ln is None:
        return False
    return (_now_min() - ws) % 1440 < ln


def _present_now(r: dict, grace_min: int = 60) -> bool:
    """For ⚡ Now OT: is this staffer present RIGHT NOW — on shift, or ended their shift within the
    last `grace_min` minutes — so a senior can give them OT now? Schedule-based (the right proxy
    before attendance_live); excludes day-off-today and AL-today."""
    ws = to_min(r.get("work_start"))
    ln = shift_len_min(r.get("work_start"), r.get("work_end")) if ws is not None else None
    if ws is None or ln is None:
        return False
    elapsed = (_now_min() - ws) % 1440        # minutes since today's shift start (wraps overnight)
    if elapsed >= ln + grace_min:             # not started yet, or ended > grace ago
        return False
    today = _today()
    off = _DOW_NAME.get((r.get("day_off") or "")[:3].title())
    if off is not None and today.weekday() == off:
        return False
    try:
        if today.isoformat() in al_leave_days_set(r["id"]):
            return False
    except Exception:
        pass
    return True


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


def fmt12s(hhmm) -> str:
    """'21:00' -> '9pm' (am/pm everywhere — owner: never show 24h to staff)."""
    m = to_min(hhmm)
    return fmt12(m) if m is not None else "?"


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

def staff_day_events(p: dict, ws_override: int | None = None,
                     len_override: int | None = None) -> list[tuple[int, int, str]]:
    """The check-in message schedule for ONE shift: (day_offset_from_shift_START, minute, label).
    End-of-shift events on an overnight shift carry offset +1 (they land the NEXT calendar day);
    a pre-reminder for a just-after-midnight start carries −1. Pure — the launch scheduler's brain.
    A redefined shift (session 31) passes ws_override (start minute-of-day) + len_override (worked
    length) so the day's prompts fire at the REDEFINED times instead of the normal schedule."""
    ws = ws_override if ws_override is not None else to_min(p.get("work_start"))
    if len_override is not None:
        ln = len_override
    else:
        ln = shift_len_min(p.get("work_start"), p.get("work_end")) if ws is not None else None
    if ws is None or ln is None:
        return []
    raw = [
        (ws - 10, "T−10 pre-reminder"),
        (ws, "T0 start prompt (only if not checked in)"),
        (ws + 5, "T+5 free-minutes message (only if still not checked in)"),
        (ws + ln, "check-out request"),
        (ws + ln + 10, "leave-early ask (only if no check-out)"),
        (ws + ln + 20, "leave-early ask (only if no check-out)"),
        (ws + ln + 40, "leave-early ask (only if no check-out)"),
    ]
    return [(m // 1440, m % 1440, label) for m, label in raw]


def compute_day_events(target: date) -> list[tuple[int, str, str, str, str]]:
    """All would-be check-in messages for one date, whole active TWB roster, chronological.
    Each event is anchored to its SHIFT-START date: it appears on `target` only if the person
    actually worked that shift (start date not their day-off, not on approved AL) — so an
    overnight 6am check-out exists only when YESTERDAY was a working day.
    Returns (minute_of_day, staff_name, label, message_text, shift_start_iso) — the last is the
    date the shift STARTED, which is the attendance_sessions / shift_changes key: an overnight
    checkout fires today but must be written under yesterday's session (bakers are 9pm–6am)."""
    import json as _json

    from shared.database import _db
    al_days: dict[int, set[str]] = {}
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_id, days FROM al_requests WHERE status='approved'")
            for r in cur.fetchall():
                try:
                    al_days.setdefault(r["staff_id"], set()).update(_json.loads(r["days"] or "[]"))
                except Exception:
                    pass

    from shared.database import dayoff_override_for, shift_changes_active_map

    def works_on(p: dict, day: date) -> bool:
        # dated day-off override (a swap) wins over the normal weekday rule
        ov = dayoff_override_for(p["id"], day.isoformat())
        if ov == "off":
            return False
        if ov == "work":
            return day.isoformat() not in al_days.get(p["id"], set())
        if _DOW_NAME.get((p.get("day_off") or "")[:3].title()) == day.weekday():
            return False
        return day.isoformat() not in al_days.get(p["id"], set())

    # A shift's events can land on `target` only if its START date is target−1 (overnight tail),
    # target (same day) or target+1 (a pre-midnight T−10). Resolve any redefine per (staff, start day):
    # an APPROVED redefine fires the day's prompts at the REDEFINED [start,end] and makes the person
    # "work" that day even if it's normally their day-off (a change-day moved the shift there).
    cand_days = [target - timedelta(days=1), target, target + timedelta(days=1)]
    redefines = shift_changes_active_map([d.isoformat() for d in cand_days])

    events = []
    for p in staff_all("active"):
        if p.get("org") != "TWB" or p.get("canonical_name") == "Tyty":
            continue
        name = p.get("call_name") or p["canonical_name"]
        for shift_start_day in cand_days:
            ov = redefines.get((p["id"], shift_start_day.isoformat()))
            if not works_on(p, shift_start_day) and ov is None:
                continue
            ws_ov = ov[0] if ov else None
            len_ov = (ov[1] - ov[0]) if ov else None
            for day_offset, minute, label in staff_day_events(p, ws_ov, len_ov):
                if shift_start_day + timedelta(days=day_offset) != target:
                    continue
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
                events.append((minute, name, label, text, shift_start_day.isoformat()))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def build_catalogue(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Every DISTINCT message the check-in system can send — once each (owner, session 28:
    same template goes to every staff, so one of each possibility is the whole test)."""
    t0_text, t0_kb = _ci_msg_start()
    return [
        ("① T−10 pre-reminder", _ci_msg_pre(p), _kb_im_late()),
        ("② T0 shift-start prompt (only if not checked in)", t0_text, t0_kb),
        ("③ T+5 free-minutes (only if still not checked in)", _CI_MSG_PLUS5, None),
        ("④ check-in verdict — EARLY ⭐", _V_EARLY % (12, 12), None),
        ("⑤ check-in verdict — ON TIME", _V_ONTIME, None),
        ("⑥ check-in verdict — LATE → reason ask", _V_LATE % (25, 25), None),
        ("⑦ live location shared but still far", _V_FAR, None),
        ("⑧ static pin sent instead", _PIN_RESPONSE, None),
        ("⑨ shift-end check-out request", _CI_MSG_OUT, None),
        ("⑩ +10min leave-early ask (only if no check-out)", _CI_MSG_OUT2, None),
        ("⑪ checked out ✓ — shift closed", _CO_DONE, None),   # the LIVE constant — can't drift
        # (former ⑫⑬ — "left zone mid-shift" + "outside too long / 30-min allowance" — DELETED
        # session 32: both belong to the DROPPED whole-shift-tracking model. v2 is check-in-only:
        # stopping a share mid-shift gets SILENCE; the leave-early ask fires only at checkout.)
    ]


_PLUS10 = ("Come 5 minutes early and you earn +10 points ⭐\n"
           "មកដល់មុន 5 នាទី អ្នកនឹងទទួលបាន +10 points ⭐")


def _slots_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Mon 09/06 7:30pm-9pm", callback_data="att:drs:slot")],
        [InlineKeyboardButton("Tue 10/06 6-7:30am", callback_data="att:drs:slot")],
        [InlineKeyboardButton("Thu 11/06 (ថ្ងៃឈប់) 11:30pm-1am", callback_data="att:drs:slot")],
        [InlineKeyboardButton("Pay 1 hour only · សងតែ 1h", callback_data="att:drs:part")],
    ])


_DRS = {
    "slot": ("→ tapping a full slot books it:",
             "Booked ✓ — Mon 09/06, 7:30pm–9pm.\nបានកក់រួច ✓ — Mon 09/06, 7:30pm–9pm។\n"
             + "Come 5 minutes early and you earn +10 points ⭐\n"
               "មកដល់មុន 5 នាទី អ្នកនឹងទទួលបាន +10 points ⭐\n\n"
               "(then: the 12h-before reminder → the slot runs as a mini-shift)"),
    "pslot": ("→ tapping a 1-hour slot books the partial:",
              "Booked ✓ — Mon 09/06, 7:30pm–8:30pm.\nបានកក់រួច ✓ — Mon 09/06, 7:30pm–8:30pm។\n"
              "Come 5 minutes early and you earn +10 points ⭐\n"
              "មកដល់មុន 5 នាទី អ្នកនឹងទទួលបាន +10 points ⭐\n\n"
              "You still owe 30 min — pick another time anytime.\n"
              "អ្នកនៅត្រូវសង 30 min — អាចជ្រើសពេលបន្ថែមនៅពេលណាក៏បាន។"),
    "appr": ("→ your ✅ counts (1/2) — when the 2nd senior approves:",
             "Approved by Rath and Vannary.\nអនុម័តដោយ Rath និង Vannary។\n\n"
             "(requester gets her ✓ message; Supervisors get the plain notice — steps ③+⑤)"),
    "rej": ("→ your ❌ counts — if a 2nd senior also rejects:",
            "Your AL request wasn't approved.\nសំណើ AL របស់អ្នកមិនបានអនុម័តទេ។\n\n"
            "(requester only; seniors get the recap; NOTHING goes to the group)"),
    "take": ("→ tapping a buyback slot books the rest:",
             "Booked ✓ — Tue 10/06, 2pm–3pm.\nបានកក់រួច ✓ — Tue 10/06, 2pm–3pm។\n"
             "OT bank របស់អ្នក៖ 3.5h\n\n"
             "(then: the 12h-before reminder; no check-in — it's rest, not work)"),
}


def _kb_part_slots() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Mon 09/06 7:30pm-8:30pm", callback_data="att:drs:pslot")],
        [InlineKeyboardButton("Tue 10/06 6-7am", callback_data="att:drs:pslot")],
        [InlineKeyboardButton("Thu 11/06 (ថ្ងៃឈប់) 11:30pm-12:30am", callback_data="att:drs:pslot")],
    ])


def build_catalogue2(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 2: the LATE + PAYBACK lifecycle — every distinct message, once.
    Bilingual finals (batch-33, session 28)."""
    return [
        ("① late declared — pick time → REASON typed at declare-time → confirm + group heads-up WITH reason",
         "Noted — see you ~9:30pm 🤍\nកត់ចំណាំហើយ — ជួបគ្នា ~9:30pm 🤍\n\n"
         "[TEST PREVIEW → SUPERVISORS group, reason INCLUDED at declare-time]\n"
         "“Davy will be ~30 min late for the 9pm shift today. Reason: moto broke.\n"
         "Davy នឹងមកយឺតប្រហែល ~30 min សម្រាប់វេន 9pm ថ្ងៃនេះ។ មូលហេតុ៖ moto broke”",
         None),
        ("② arrival watch — declared time passed, no location yet (repeats 4× every 15 min)",
         "Are you there yet?\nមកដល់ហើយឬនៅ?\n" + _CI_HOWTO, None),
        ("③ they arrive (location) — verdict only; reason already given at declare (silent arrivers asked now)",
         "(check-in verdict = Dry-run 1 steps ④–⑥, already approved. A SILENT arriver who never declared "
         "is asked 'Why were you late?' here instead.)", None),
        ("④ payback slot picker (right after the reason; no AL option — late = time)",
         "You owe 90 min. Pick when to work it off — these are the times we need you most:\n"
         "អ្នកនៅត្រូវសង 90 min។ សូមជ្រើសពេលធ្វើម៉ោងសងវិញ — ពេលទាំងនេះហាងត្រូវការអ្នកបំផុត៖",
         _slots_kb()),
        ("⑤ booked confirmation (self-picked or auto) — always encouraging",
         "Booked ✓ — Mon 09/06, 7:30pm–9pm.\nបានកក់រួច ✓ — Mon 09/06, 7:30pm–9pm។\n" + _PLUS10,
         None),
        ("⑥ 12h-before reminder (any booked event)",
         "Reminder — your payback time is tomorrow: 7:30pm–9pm.\n"
         "រំលឹក — ម៉ោងសងវិញរបស់អ្នកគឺថ្ងៃស្អែក៖ 7:30pm–9pm។\n" + _PLUS10 + "\n" + _CI_HOWTO,
         None),
        ("⑦ the slot itself = mini-shift (T−10, check-in, early ⭐) — same templates as Dry-run 1",
         "(reused — a payback slot greets, checks in and rewards exactly like a shift)", None),
        ("⑧ partial credit — worked 60 of 90 min",
         "You paid back 60 min ✓ — 30 min stays on your balance.\n"
         "អ្នកបានសង 60 min ✓ — នៅសល់ 30 min ក្នុង balance របស់អ្នក។", None),
        ("⑨ unbooked debt — the daily line at check-in (never hourly)",
         "Checked in ✓ — you still owe 90 min, pick a time:\n"
         "ចុះវត្តមានរួច ✓ — អ្នកនៅត្រូវសង 90 min, សូមជ្រើសពេល៖", _slots_kb()),
        ("⑩ day 3 — the warning",
         "Pick before tomorrow, or I'll pick for you.\n"
         "សូមជ្រើសមុនថ្ងៃស្អែក។ បើអ្នកមិនទាន់ជ្រើសទេ ខ្ញុំនឹងជ្រើសជូនអ្នក។", _slots_kb()),
        ("⑪ day 4 — auto-booked",
         "I booked you Mon 09/06, 7:30pm–9pm (you didn't choose).\n"
         "ខ្ញុំបានកក់ពេលឱ្យអ្នក Mon 09/06, 7:30pm–9pm (ព្រោះអ្នកមិនបានជ្រើស)។\n" + _PLUS10 + "\n\n"
         "[TEST PREVIEW → SUPERVISORS group]\n“Davy pays back Mon 09/06, 7:30pm–9pm.\n"
         "Davy ធ្វើម៉ោងសងវិញ Mon 09/06, 7:30pm–9pm។”", None),
        ("⑫ skipped the assigned slot — re-booked ONCE",
         "You missed your payback time — new time: Tue 10/06, 6–7:30am.\n"
         "អ្នកខកខានម៉ោងសងវិញ — ពេលថ្មី៖ Tue 10/06, 6–7:30am។", None),
        ("⑬ skipped twice — bonus consequence + owner digest",
         "[TEST PREVIEW → OWNER digest]\n"
         "“Davy skipped 2 assigned payback slots (90 min open since Jun 7) — next bonus not earned. "
         "This is a person-problem now.”  ← staff see the bonus line on the May#2 slip, never mid-month",
         None),
        ("⑭ no-show day (never arrived at all) — the hardest message, tone matters",
         "You missed your whole shift yesterday. One day's pay is deducted, and this month's bonus "
         "is not earned. If something serious happened, please tell me.\n"
         "អ្នកខកខានវេនទាំងមូលម្សិលមិញ។ ប្រាក់ឈ្នួល 1 ថ្ងៃនឹងត្រូវដក ហើយលក្ខខណ្ឌ Bonus ខែនេះមិនបានសម្រេចទេ។ "
         "បើមានរឿងធ្ងន់ធ្ងរមែន សូមប្រាប់ខ្ញុំ។", None),
    ]


def build_catalogue3(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 3: ANNUAL LEAVE — request → approval → notice, every variant we now support."""
    appr_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve · អនុម័ត", callback_data="att:drs:appr")],
        [InlineKeyboardButton("❌ Not approve · មិនអនុម័ត", callback_data="att:drs:rej")],
    ])
    return [
        ("① the SENIOR's approval card (every senior gets it privately — even on their day off)",
         "Meng requests AL: Tue 23/06 → Thu 25/06 (full day). Reason: family trip\n"
         "Meng ស្នើ AL: Tue 23/06 → Thu 25/06 (ពេញមួយថ្ងៃ)។ មូលហេតុ៖ family trip\n\n"
         "Working those hours: Davy, Nak, Sey\nអ្នកធ្វើការពេលនោះ៖ Davy, Nak, Sey", appr_kb),
        ("② SHORT-NOTICE request (within 7 days) — costs points, computed total shown",
         "⚠ Short notice (within 7 days) — about −54 points for a full day (−0.1/min).\n"
         "⚠ ស្នើជិតពេល (ក្នុង 7 ថ្ងៃ) — ប្រហែល −54 points សម្រាប់ពេញមួយថ្ងៃ (−0.1/min)។", None),
        ("③ HOURS-AL (part of a day)",
         "Hours AL: 9pm → 12am (3h of a 9h shift = 0.3 AL).\n"
         "AL តាមម៉ោង៖ 9pm → 12am (3h ក្នុងវេន 9h = 0.3 AL)។", None),
        ("④ FROM-NOW (today, mid-shift) — 1 senior can let them leave, 2nd ratifies after",
         "Asking to leave from now. One senior ✅ lets them go; a 2nd confirms after.\n"
         "សុំចេញពីពេលនេះ។ បង 1 នាក់ ✅ អាចអនុញ្ញាតឱ្យចេញបាន; បងទី 2 បញ្ជាក់តាមក្រោយ។", None),
        ("⑤ NOT ENOUGH balance — the STAFFER is told to pick a smaller amount (never reaches seniors)",
         "⚠ You only have 1.5 AL day(s) left, but this request needs 3.\n"
         "Please choose a smaller amount — you can request up to 1.5.\n"
         "⚠ ប្អូននៅសល់ AL តែ 1.5 ថ្ងៃប៉ុណ្ណោះ ប៉ុន្តែសំណើនេះត្រូវប្រើ 3 ថ្ងៃ។\n"
         "សូមជ្រើសចំនួនតិចជាងនេះ — ប្អូនអាចស្នើបានច្រើនបំផុត 1.5 ថ្ងៃ។", None),
        ("⑥ after 2 ✅ — the refreshed recap to all seniors",
         "Approved by Rath and Vannary.\nអនុម័តដោយ Rath និង Vannary។", None),
        ("⑦ to the requester — approved + new balance",
         "Your AL for Tue 23/06 → Thu 25/06 is approved ✓. You have 4.5 AL days left. 🤍\n"
         "AL របស់ប្អូនសម្រាប់ Tue 23/06 → Thu 25/06 បានអនុម័តហើយ ✓។ ប្អូននៅសល់ AL 4.5 ថ្ងៃទៀត 🤍",
         None),
        ("⑧ to the requester — not approved (seniors-only recap, nothing to the group)",
         "Your AL request wasn't approved.\nសំណើ AL របស់អ្នកមិនបានអនុម័តទេ។", None),
        ("⑨ SUPERVISORS notice — FULL-DAY (locked format: leave + day-off + back-at-work)",
         "Meng on leave: Tue 23/06 → Thu 25/06 (3 days).\n"
         "Meng ឈប់សម្រាក៖ Tue 23/06 → Thu 25/06 (3 ថ្ងៃ)។\n"
         "Reason: family trip\nមូលហេតុ៖ family trip\n"
         "Normal day off: Friday 26/06.\nថ្ងៃឈប់ធម្មតា៖ Friday 26/06។\n"
         "Back at work: Saturday 27/06, 9pm.\nត្រឡប់មកធ្វើការ៖ Saturday 27/06, 9pm។", None),
        ("⑩ SUPERVISORS notice — HOURS-AL (return time that same day)",
         "Meng on leave 9pm–12am on Tue 23/06, Wed 24/06, Thu 25/06.\n"
         "Meng ឈប់សម្រាក 9pm–12am នៅ Tue 23/06, Wed 24/06, Thu 25/06។\n"
         "Back at work: 12am each of those nights (rest of shift as normal).\n"
         "ត្រឡប់មកធ្វើការ 12am រាល់យប់នោះ (ម៉ោងនៅសល់នៃវេនធ្វើធម្មតា)។", None),
        ("⑪ cancelling an AL — refund confirmation",
         "Your AL for Tue 23/06 is cancelled ✓ — 1 day(s) returned.\n"
         "AL របស់អ្នកសម្រាប់ Tue 23/06 ត្រូវបានលុបចោលហើយ ✓ — 1 ថ្ងៃបានត្រឡប់ចូលវិញ។", None),
    ]


def build_catalogue4(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 4: SICK — own-sick anti-fake ladder, papers, part-duty, family-sick. Full."""
    cant_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💪 I can come · ខ្ញុំអាចមក", callback_data="att:drs:noop")],
        [InlineKeyboardButton("🛌 Rest today · សម្រាកថ្ងៃនេះ", callback_data="att:drs:noop")]])
    nudge_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Again tomorrow · ស្អែកទៀត", callback_data="att:drs:noop")],
        [InlineKeyboardButton("👍 Better · ធូរស្បើយហើយ", callback_data="att:drs:noop")]])
    return [
        ("① Sick → Me: the anti-fake opener (try to come, see how you feel)",
         "Sorry to hear 😟 Take some medicine and come try — see how you feel at work. "
         "What time can you come?\n"
         "សោកស្តាយណាស់ 😟 សូមលេបថ្នាំ ហើយមកសាកធ្វើការមើល។ អ្នកអាចមកម៉ោងប៉ុន្មាន?",
         _ill(["9:30pm", "10pm", "10:30pm"], ["🛌 I really can't come today · ថ្ងៃនេះមកមិនបាន"])),
        ("② Sick → Me: 'I really can't come today' → rest + papers ask",
         "OK — rest well 🤍 If you see a doctor, send me a photo of the papers.\n"
         "បានហើយ — សម្រាកឱ្យបានល្អ 🤍 បើអ្នកបានទៅជួបពេទ្យ សូមផ្ញើរូបថតឯកសារពេទ្យមកខ្ញុំ។\n"
         "(paperless = pay-back from now; doctor's papers within 2 days cancel it)", None),
        ("③ papers photo arrives → instant ack (goes to OWNER + Tyty ONLY)",
         "Got your papers ✓ sending to the owner.\n"
         "បានទទួលឯកសាររបស់អ្នក ✓ កំពុងផ្ញើទៅម្ចាស់ហាង។", None),
        ("④ [→ OWNER + Tyty card] Opus reads the paper → owner taps the decision",
         "🩺 Davy — sick papers. Opus: Calmette Hospital · likely flu · 2 days · not contagious.\n"
         "(the photo is forwarded right under this card; never shown to any group)",
         _ill(["✓ Accept (cover 2d)"], ["1d", "2d", "3d"], ["💺 Offer part-duty"],
              ["Skip → nightly nudges"])),
        ("⑤ owner accepts → real sick day, debt+points wiped, AL UNTOUCHED",
         "Saved ✓ — your sick day is confirmed, nothing owed. Get well 🤍\n"
         "រក្សាទុករួច ✓ — ថ្ងៃឈឺរបស់អ្នកបានបញ្ជាក់ហើយ មិនមានអ្វីត្រូវសងទេ។ សូមឱ្យឆាប់ជាសះស្បើយ 🤍", None),
        ("⑥ owner offers PART-DUTY → staff invited back for light work (+15 ⭐, no pressure)",
         "Feeling a little better? If you're up to it, there's light work today (+15 points ⭐) — "
         "only if you truly feel able 🤍\n"
         "ធូរស្បើយបន្តិចហើយឬនៅ? បើអ្នកមានកម្លាំង អាចមកធ្វើការងារស្រាលៗថ្ងៃនេះបាន (+15 points ⭐) — "
         "តែបើអ្នកពិតជាអាចធ្វើបានប៉ុណ្ណោះ 🤍", cant_kb),
        ("⑦ came on light duty → the Supervisors-group memo + the staff welcome",
         "[→ Supervisors group] Davy is coming on LIGHT DUTY today — easy/seated work only.\n"
         "Davy នឹងមកធ្វើ LIGHT DUTY ថ្ងៃនេះ — សូមឱ្យធ្វើតែការងារងាយៗ/អង្គុយប៉ុណ្ណោះ។\n\n"
         "[→ Davy] Thank you for coming 🤍 light duty only — a senior will point you to easy work.\n"
         "អরគុណដែលមកជួយ 🤍 ធ្វើតែការងារស្រាលៗប៉ុណ្ណោះ — បងៗនឹងណែនាំការងារងាយៗឱ្យអ្នក។", None),
        ("⑧ chose to rest instead",
         "Get well 🤍 rest today.\nសូមឱ្យឆាប់ជាសះស្បើយ 🤍 សម្រាកថ្ងៃនេះ។", None),
        ("⑨ each night while out → return check (never papers/pay-back); the answer goes to Supervisors",
         "Hi 🤍 are you well enough to come in tomorrow? Let us know.\n"
         "សួស្តី 🤍 ស្អែកអ្នកអាចមកធ្វើការបានទេ? សូមប្រាប់ពួកយើងផង។",
         _ill(["✅ Coming in tomorrow"], ["🛌 Still resting"], ["⏰ Coming in today at…"])),
        ("⑩ FAMILY-sick day → seniors informed (no approval gate; burns 1 of 7 yearly days)",
         "FYI: Kimying takes sick leave for her child today.\n"
         "FYI: Kimying សុំច្បាប់ឈឺសម្រាប់កូនរបស់គាត់ថ្ងៃនេះ។", None),
        ("⑪ FAMILY-sick night nudge (12h before next shift) — one-tap re-book",
         "Is your child better? If you need tomorrow off too, tell me now.\n"
         "តើកូនរបស់អ្នកធូរស្បើយហើយឬនៅ? បើត្រូវការឈប់ថ្ងៃស្អែកទៀត សូមប្រាប់ខ្ញុំឥឡូវនេះ។", nudge_kb),
        ("⑫ [→ OWNER] paperless-sick FREQUENCY dossier (pattern, not a single day)",
         "Davy: 3rd paperless sick in 30 days (all Mondays). Pattern flag for your review.\n"
         "(owner-only — English; staff never see this)", None),
    ]


def _buyback_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Tue 10/06 2pm-3pm", callback_data="att:drs:take")],
        [InlineKeyboardButton("Wed 11/06 8pm-9pm", callback_data="att:drs:take")],
        [InlineKeyboardButton("Take 1 hour only · សម្រាកតែ 1h", callback_data="att:drs:take")]])


def build_catalogue5(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 5: MARRIAGE · FAMILY DEATH (2 tiers) · WIFE BIRTH. All AL-funded, never salary."""
    upgrade_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Upgrade to 3 days · បន្ថែមដល់ 3 ថ្ងៃ", callback_data="att:drs:noop")]])
    return [
        ("① OWN marriage (3 days) → routes through senior approval (planned 30+ days ahead)",
         "💍 Your marriage: 3 days, Mon 14/07 → Wed 16/07. From AL (can go below zero, never salary).\n"
         "💍 រៀបការរបស់អ្នក៖ 3 ថ្ងៃ, Mon 14/07 → Wed 16/07។", None),
        ("② marriage approved → warm confirmation",
         "Your marriage leave is approved ✓ Mon 14/07 → Wed 16/07. Congratulations! 🤍\n"
         "ច្បាប់រៀបការរបស់ប្អូនបានអនុម័តហើយ ✓ Mon 14/07 → Wed 16/07។ អបអរសាទរ! 🤍", None),
        ("③ CHILD's marriage (1 day)",
         "👰 Child's marriage: 1 day on Sat 19/07.\n👰 រៀបការកូន៖ 1 ថ្ងៃ នៅ Sat 19/07។", None),
        ("④ FAMILY DEATH — law tier (child/parent/spouse): instant, NO approval, 3–7 days",
         "We're very sorry for your loss 🤍 3 days of leave, Tue 09/06 → Thu 11/06. No approval needed.\n"
         "យើងសូមចូលរួមរំលែកទុក្ខចំពោះការបាត់បង់នេះ 🤍 សម្រាក 3 ថ្ងៃ, Tue 09/06 → Thu 11/06។ "
         "មិនចាំបាច់រង់ចាំការអនុម័តទេ។", None),
        ("⑤ death SUPERVISORS notice — relation MAY be named (masking dropped, owner)",
         "Davy on leave Tue 09/06 → Thu 11/06 (death of parent).\n"
         "Davy ឈប់សម្រាក Tue 09/06 → Thu 11/06 (មរណភាព ឪពុក/ម្តាយ)។", None),
        ("⑥ death COMPASSION tier (sibling/grandparent): 1 day instant, zero questions",
         "We're very sorry for your loss 🤍 1 day of leave today. No approval needed.\n"
         "យើងសូមចូលរួមរំលែកទុក្ខចំពោះការបាត់បង់នេះ 🤍 ថ្ងៃនេះប្អូនអាចសម្រាក 1 ថ្ងៃបានភ្លាមៗ។ មិនចាំបាច់រង់ចាំការអនុម័តទេ។",
         None),
        ("⑦ [→ OWNER] compassion case → one-tap upgrade if it warrants",
         "Davy reported a sibling's death — gave 1 day (compassion). Upgrade?", upgrade_kb),
        ("⑧ owner upgraded → staff told",
         "Your leave is extended to 3 days 🤍\n"
         "ច្បាប់សម្រាករបស់អ្នកត្រូវបានបន្ថែមដល់ 3 ថ្ងៃហើយ 🤍", None),
        ("⑨ a death-context PHOTO arrives → condolence only, NO AI, owner+Tyty only",
         "You don't need to send anything — we're so sorry for your loss 🤍\n"
         "អ្នកមិនចាំបាច់ផ្ញើអ្វីទេ — យើងសូមចូលរួមរំលែកទុក្ខចំពោះការបាត់បង់នេះ 🤍", None),
        ("⑩ WIFE giving birth (2 days) + the Supervisors notice",
         "👶 Congratulations! 2 days of leave, Tue 09/06 → Wed 10/06.\n"
         "អបអរសាទរ! 👶 សម្រាក 2 ថ្ងៃ, Tue 09/06 → Wed 10/06។\n\n"
         "[→ SUPERVISORS] Davy on leave Tue 09/06 → Wed 10/06 (wife giving birth).\n"
         "Davy ឈប់សម្រាក Tue 09/06 → Wed 10/06 (ប្រពន្ធសម្រាលកូន)។", None),
    ]


def build_catalogue7(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 7: DAY-OFF SWAP — partner asked FIRST, then 2 seniors, same-week rule."""
    agree_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I agree · ខ្ញុំយល់ព្រម", callback_data="att:drs:noop")],
        [InlineKeyboardButton("✋ No · ទេ", callback_data="att:drs:noop")]])
    return [
        ("① staff requests a swap → the PARTNER is asked FIRST (their veto is cheapest)",
         "Davy wants to swap day off: Davy takes Wed off, you take Fri — same week. Reason: clinic\n"
         "Davy ស្នើសុំប្តូរថ្ងៃឈប់ជាមួយអ្នក៖ Davy ឈប់ថ្ងៃពុធ, អ្នកឈប់ថ្ងៃសុក្រ — ក្នុងសប្តាហ៍ដដែល។ "
         "មូលហេតុ៖ clinic", agree_kb),
        ("② partner agrees → goes to the seniors",
         "✅ You agreed — sent to seniors.\n"
         "✅ ប្អូនបានយល់ព្រមហើយ — បានផ្ញើទៅបងៗ។", None),
        ("③ partner declines OR stays silent → swap doesn't happen, seniors never bothered",
         "Your day-off swap wasn't accepted by your partner.\n"
         "អ្នកដែលត្រូវប្តូរជាមួយ មិនបានយល់ព្រមលើការប្តូរថ្ងៃឈប់របស់អ្នកទេ។", None),
        ("④ seniors' approval card (same-week rule) → 2 ✅ applies the dated swap",
         "Day-off swap: Davy ↔ Mealea. Reason: clinic\n"
         "ប្តូរថ្ងៃឈប់៖ Davy ↔ Mealea។ មូលហេតុ៖ clinic",
         _ill(["✅ Approve · អនុម័ត", "❌ Not approve · មិនអនុម័ត"])),
        ("⑤ approved → SUPERVISORS notice",
         "Day-off swap: Davy off Fri 12/06, Mealea off Wed 10/06.\n"
         "ប្តូរថ្ងៃឈប់៖ Davy ឈប់ Fri 12/06, Mealea ឈប់ Wed 10/06។", None),
        ("⑥ approved → to the requester",
         "Your day-off swap is approved ✓\nការប្តូរថ្ងៃឈប់របស់អ្នកបានអនុម័តហើយ ✓", None),
        ("⑦ seniors rejected → to the requester",
         "The day-off swap wasn't approved.\nការប្តូរថ្ងៃឈប់មិនបានអនុម័តទេ។", None),
    ]


def build_catalogue8(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 8: CROSS-CUTTING — acks, group redirect, autonomous call-outs, welcome."""
    return [
        ("① 👍 ACK — a normal (non-problem) reply gets a thumbs-up so they know they were heard",
         "Got it 👍 thank you.\nបានហើយ 👍 អរគុណ។\n(a reply that IS a problem gets a real answer, never a 👍)",
         None),
        ("② GROUP REDIRECT — someone posts leave/late in a group → GM nudges them private",
         "— AL, sick and days off only count when you tell me directly. Open @twb_gm_bot, or it "
         "won't be recorded 🙂\n"
         "— AL, ឈឺ និងថ្ងៃឈប់ នឹងរាប់បានតែពេលប្អូនប្រាប់ខ្ញុំផ្ទាល់។ សូមបើក @twb_gm_bot "
         "បើមិនដូច្នេះ វានឹងមិនត្រូវបានកត់ត្រាទេ 🙂\n"
         "(one of 5 rotating variants — the GM never repeats the same line back-to-back)", None),
        ("③ CALL-OUT — private DM when a pattern shows (warm, by name, Sonnet-written)",
         "Hi Davy — we noticed Mondays have been hard lately (3 of your last 4 lates). "
         "Everything okay? Let's fix Mondays together. 🤍\n(AI-written bilingual at send time; CC to owners)",
         None),
        ("④ CALL-OUT — the GROUP version (never names anyone, Opus-written, said once)",
         "Friendly reminder: we track lateness patterns and reasons. Some Mondays have been "
         "popular lately 😉\n(AI-written bilingual; the GM says it once and goes quiet)", None),
        ("⑤ WELCOME — the one-time greeting + the always-on 📋 Menu button",
         "👋 Hi team! I'm the GM — your new helper. Message me anytime and I'll open your menu; "
         "the 📋 Menu button stays at the bottom for you.\n(full bilingual greeting in gm_greeting_FINAL)",
         None),
    ]


def schedule_summary(target: date) -> str:
    """Today's who/when in ONE message — the schedule math, compressed."""
    from collections import defaultdict
    ev = compute_day_events(target)
    by: dict = defaultdict(list)
    for minute, name, label, _text, _sd in ev:
        by[(minute, label.split(" ")[0])].append(name)
    lines = ["📅 Today's actual schedule (%s) — %d sends, same texts as above:"
             % (day_label(target), len(ev))]
    for (minute, kind), names in sorted(by.items()):
        lines.append("%s %s ×%d: %s" % (fmt12(minute), kind, len(names), ", ".join(names)))
    return "\n".join(lines)


async def _dryrun_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    events = context.user_data.get("att_dr_events") or []
    i = context.user_data.get("att_dr_i", 0)
    chat_id = update.effective_chat.id
    if i >= len(events):
        await context.bot.send_message(chat_id, "✅ Dry-run finished — %d possibilities walked."
                                       % len(events))
        return
    label, text, kb = events[i]
    context.user_data["att_dr_i"] = i + 1
    # a choice button ADVANCES the dry-run (shows the consequence) — never a dead tap
    rows = []
    if kb:
        for r in kb.inline_keyboard:
            rows.append([InlineKeyboardButton(b.text, callback_data="att:dr:next") for b in r])
    if i + 1 < len(events):
        rows.append([InlineKeyboardButton("Next ▶ (%d/%d)" % (i + 2, len(events)),
                                          callback_data="att:dr:next")])
    await context.bot.send_message(chat_id, "🧪 %s\n────────────\n%s" % (label, text),
                                   reply_markup=InlineKeyboardMarkup(rows) if rows else None)


# ---------------------------------------------------------------- shell state

def _persona(context) -> dict | None:
    sid = context.user_data.get("att_persona")
    if sid is None:
        return None
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    if rec is not None and context.user_data.get("att_live_self"):
        rec = dict(rec)
        rec["_live"] = True   # a real staffer driving their own menu (not the owner shell)
    return rec


def _is_live(context) -> bool:
    """True when a real staffer is driving their OWN menu (live), not the owner role-play shell."""
    return bool(context.user_data.get("att_live_self"))


def _armed(context) -> bool:
    """A terminal fires the REAL submit_* when the owner is in test mode OR a live staffer is
    driving. Otherwise (test off, owner just browsing) terminals show a read-only preview stub."""
    return att_test_on() or _is_live(context)


def _arm_pending(context, update, pend: dict) -> None:
    """Stash the pending reason/'go' for the next typed message. Owner test → user_data (ephemeral);
    live staffer → flow_state (DB, restart-safe), per docs/ATTENDANCE_TEST_MODE.md item 8.
    Also captures the reason-PROMPT message coords so the dispatcher can edit it in place into an
    'awaiting approval' card once the reason is typed (only when the flow set pend['_summary'])."""
    uid = update.effective_user.id
    q = getattr(update, "callback_query", None)
    msg = getattr(q, "message", None) if q is not None else None
    if msg is not None:
        chat_id = getattr(msg, "chat_id", None)
        msg_id = getattr(msg, "message_id", None)
        if chat_id is not None and msg_id is not None:
            pend["_prompt_chat"] = chat_id
            pend["_prompt_msg"] = msg_id
    if att_test_on():
        context.user_data["att_test_pending"] = pend
    else:
        flow_save(uid, "att_pending", "reason", pend, ttl_min=15)


def _arm_prompt(p: dict, context, base: str, back: str, extra_rows=None):
    """Unified prompt for an armed terminal. Neutral copy works for BOTH live (routes to the real
    seniors/Supervisors) and test; test adds an owner coaching suffix. (KH pending for new lines.)
    `extra_rows`: button rows placed ABOVE the back row (e.g. a Show-who's-working toggle)."""
    line = base
    if att_test_on():
        line += "\n🧪 (test — every reply/card routes to you; /testreset to wipe when done.)"
    rows = list(extra_rows or [])
    rows.append(_back_row(back))
    return _hdr(p, line), InlineKeyboardMarkup(rows)


def _al_prompt(p: dict, context, detail: str, days: list, hs, he, show_cov: bool):
    """The AL reason prompt carrying a persistent 👁/🙈 Show-who's-working toggle, computed LIVE from
    the in-progress selection (no request exists yet). The stash drives the toggle re-render."""
    context.user_data["att_al_cov"] = {"detail": detail, "days": list(days), "hs": hs, "he": he}
    line = detail
    if show_cov:
        try:
            from gm_bot.bot import _al_availability_lines
            cov = _al_availability_lines(p, days, hs, he)
        except Exception:
            cov = ""
        if cov:
            _lab = ("Working those hours · អ្នកធ្វើការពេលនោះ" if hs
                    else "Working those days · អ្នកធ្វើការពេលនោះ")
            line += "\n\n👥 %s:\n%s" % (_lab, cov)
    line += ("\n\n📝 Type the reason — your next message submits the AL request for senior approval.\n"
             "📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើសំណើ AL ទៅបងៗ ដើម្បីសុំការអនុម័ត។")
    lbl, flag = (("🙈 Hide who's working · លាក់អ្នកធ្វើការ", 0) if show_cov
                 else ("👁 Show who's working · បង្ហាញអ្នកធ្វើការ", 1))
    extra = [[InlineKeyboardButton(lbl, callback_data="att:al:cov:%d" % flag)]]
    return _arm_prompt(p, context, line, "att:al", extra_rows=extra)


def _swap_both_days_lines(p: dict, partner_id, req_off: str, partner_off: str) -> str:
    """BOTH affected days for a day-off swap: who works the requester's off date (requester away)
    and the partner's off date (partner away). Plain text (the prompt isn't HTML)."""
    try:
        from gm_bot.bot import _al_availability_lines
        partner = next((s for s in staff_all("active") if s["id"] == partner_id), None)
        parts = []
        l1 = _al_availability_lines(p, [req_off])                 # requester off → who covers
        if l1:
            parts.append(l1)
        if partner:
            l2 = _al_availability_lines(partner, [partner_off])   # partner off → who covers
            if l2:
                parts.append(l2)
        return "\n".join(parts)
    except Exception:
        return ""


def _swap_prompt(p: dict, context, base: str, partner_id, req_off: str, partner_off: str,
                 show_cov: bool):
    """The day-off-swap reason prompt with a persistent both-days Show-who's-working toggle, computed
    LIVE from the picked dates (no swap record yet). The stash drives the toggle re-render."""
    context.user_data["att_do_cov"] = {"base": base, "partner_id": partner_id,
                                       "req_off": req_off, "partner_off": partner_off}
    line = base
    if show_cov:
        cov = _swap_both_days_lines(p, partner_id, req_off, partner_off)
        if cov:
            line += "\n\n👥 Working those days · អ្នកធ្វើការពេលនោះ:\n%s" % cov
    line += ("\n\n📝 Type the reason — your partner agrees first, then the seniors approve.\n"
             "📝 សរសេរមូលហេតុ — ដៃគូត្រូវយល់ព្រមមុន បន្ទាប់មកបងៗអនុម័ត។")
    lbl, flag = (("🙈 Hide who's working · លាក់អ្នកធ្វើការ", 0) if show_cov
                 else ("👁 Show who's working · បង្ហាញអ្នកធ្វើការ", 1))
    extra = [[InlineKeyboardButton(lbl, callback_data="att:do:cov:%d" % flag)]]
    return _arm_prompt(p, context, line, "att:do", extra_rows=extra)


def _confirm_prompt(p: dict, context, base: str, back: str):
    """For NO-reason flows: show a tappable '✅ I confirm' button instead of asking them to type
    'go'. Tapping fires att:go → the real submit_* (same pending as the reason flows)."""
    line = base
    if att_test_on():
        line += "\n🧪 (test — routes to you; /testreset to wipe.)"
    return _hdr(p, line), InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I confirm · ខ្ញុំបញ្ជាក់", callback_data="att:go")],
        _back_row(back),
    ])


def _hdr(p: dict, line: str = "") -> str:
    if p.get("_live"):
        head = "👤 %s" % (p.get("call_name") or p["canonical_name"])
    else:
        head = "🧪 TEST — acting as %s (%s)" % (p["canonical_name"], p.get("call_name") or "-")
    return head + ("\n\n" + line if line else "")


def _back_row(target: str = "att:menu") -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton("← Back · ត្រឡប់ក្រោយ", callback_data=target)]


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
    ]
    if not p.get("_live"):
        rows.append([InlineKeyboardButton("🎭 Switch persona", callback_data="att:pick")])
    line = ("What would you like to do? · តើអ្នកចង់ធ្វើអ្វី?" if p.get("_live")
            else "Main menu — what they see when they type anything:")
    return _hdr(p, line), InlineKeyboardMarkup(rows)


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
               "(Missed time becomes pay-back, same as informed late. Doctor papers later wipe it.)"
               % (t, t, p.get("call_name") or p["canonical_name"], t))
    return txt, InlineKeyboardMarkup([_back_row("att:sp:me"), _walk_btn("sickme"),
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def sick_me_cant(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    txt = _hdr(p,
               "OK — rest well 🤍 If you see a doctor, send me a photo of the papers.\n"
               "បានហើយ — សម្រាកឱ្យបានល្អ 🤍 បើអ្នកបានទៅជួបពេទ្យ សូមផ្ញើរូបថតឯកសារពេទ្យមកខ្ញុំ។\n\n"
               "(Provisional: the missed shift becomes pay-back time unless papers arrive within 3 days.\n"
               "Papers → real sick day: no pay-back, no points, AL untouched.)")
    return txt, InlineKeyboardMarkup([_back_row("att:sp:me"), _walk_btn("sickme"),
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
    txt = ("Sick leave for your %s — %s\nច្បាប់ឈឺសម្រាប់%s — %s\n"
           "Full day or part of the day?\nសុំឈប់ពេញមួយថ្ងៃ ឬសុំឈប់តាមម៉ោង?"
           % (who, d, _WHO_KH.get(who, who), d))
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
                   "Take care 🤍\nថែទាំឱ្យបានល្អ 🤍"
                % (who, d, window, _WHO_KH.get(who, who), d, window)), \
        InlineKeyboardMarkup([_back_row("att:sp:sick"), _walk_btn("sickfam"),
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
                       "must be planned 30+ days ahead)\n"
                       "👰 រៀបការកូនរបស់អ្នក — ថ្ងៃណា? (1 ថ្ងៃ; ត្រូវស្នើមុន 30+ ថ្ងៃ)"), \
            InlineKeyboardMarkup(rows)
    # own marriage: dates start at day 31 (owner rule — plan 30+ days ahead)
    rows = _date_grid_rows("att:sp:mard", _today() + timedelta(days=31), 28, "att:sp:mar")
    return _hdr(p, "💍 Your marriage — first day of leave? (3 days; "
                   "must be planned 30+ days ahead)\n"
                   "💍 រៀបការរបស់អ្នក — ថ្ងៃចាប់ផ្តើមសម្រាក? (3 ថ្ងៃ; ត្រូវស្នើមុន 30+ ថ្ងៃ)"), \
        InlineKeyboardMarkup(rows)


def marriage_stub(p: dict, iso: str, child: bool) -> tuple[str, InlineKeyboardMarkup]:
    d = date.fromisoformat(iso)
    if child:
        detail = ("👰 Child's marriage: 1 day on %s.\n👰 រៀបការកូន៖ 1 ថ្ងៃ នៅ %s។"
                  % (day_label(d), day_label(d)))
    else:
        d3 = day_label(d + timedelta(days=2))
        detail = ("💍 Your marriage: 3 days, %s → %s.\n💍 រៀបការរបស់អ្នក៖ 3 ថ្ងៃ, %s → %s។"
                  % (day_label(d), d3, day_label(d), d3))
    return _hdr(p, detail + "\nFrom AL — balance can go below zero, never from salary. "
                            "Senior approval like a normal AL."), \
        InlineKeyboardMarkup([_back_row("att:sp:mar"), _walk_btn("marriage"),
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def death_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = [
        _back_row("att:sp"),
        [InlineKeyboardButton("My child · កូនខ្ញុំ", callback_data="att:sp:deathw:child")],
        [InlineKeyboardButton("My parent · ឪពុក/ម្តាយខ្ញុំ", callback_data="att:sp:deathw:parent")],
        [InlineKeyboardButton("My spouse · ប្តី/ប្រពន្ធខ្ញុំ", callback_data="att:sp:deathw:spouse")],
        [InlineKeyboardButton("My sibling · បងប្អូនបង្កើតខ្ញុំ", callback_data="att:sp:deathw:sibling")],
        [InlineKeyboardButton("My grandparent · ជីតា/ជីដូនខ្ញុំ", callback_data="att:sp:deathw:grandparent")],
    ]
    return _hdr(p, "🕊 We're very sorry. Who passed away?\n"
                   "🕊 យើងសូមចូលរួមរំលែកទុក្ខ។ តើអ្នកណាទទួលមរណភាព?"), InlineKeyboardMarkup(rows)


def death_dates(p: dict, who: str) -> tuple[str, InlineKeyboardMarkup]:
    rows = _date_grid_rows("att:sp:deathd:%s" % who, _today(), 8, "att:sp:death")
    return _hdr(p, "🕊 First day of leave?\n🕊 ថ្ងៃចាប់ផ្តើមសម្រាក?"), InlineKeyboardMarkup(rows)


def death_days(p: dict, who: str, iso: str) -> tuple[str, InlineKeyboardMarkup]:
    # law tier (child/parent/spouse): choose 3–7 once. compassion tier (sibling/grandparent):
    # 1 day granted instantly, owner may upgrade — no picker (handled in callback → death_stub 1).
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
                   "“%s on leave %s → %s (death of %s).”\n%s\n"
                   "(From AL — balance can go below zero, never from salary. Need more later? Just open "
                   "Special Leave again.)"
                % (days, day_label(d), dn, days, day_label(d), dn,
                   p.get("call_name") or p["canonical_name"], day_label(d), dn, who,
                   ("🤍 If you need more time, just open Special Leave again — we're here for you.\n"
                    "🤍 បើអ្នកត្រូវការពេលថែមទៀត គ្រាន់តែបើក Special Leave ម្តងទៀត — យើងនៅជាមួយអ្នក។"
                    if days == 1 else "✓ booked · បានកក់រួច"))), \
        InlineKeyboardMarkup([_back_row("att:sp:death"), _walk_btn("death"),
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def birth_dates(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    rows = _date_grid_rows("att:sp:birthd", _today(), 8, "att:sp")
    return _hdr(p, "👶 Congratulations! First day of leave? (2 days)\n"
                   "👶 អបអរសាទរ! ថ្ងៃចាប់ផ្តើមសម្រាក? (2 ថ្ងៃ)"), InlineKeyboardMarkup(rows)


def birth_stub(p: dict, iso: str) -> tuple[str, InlineKeyboardMarkup]:
    d = date.fromisoformat(iso)
    d2 = day_label(d + timedelta(days=1))
    return _hdr(p, "👶 2 days of leave, %s → %s.\nFrom AL — balance can go below zero, never from "
                   "salary."
                % (day_label(d), d2)), \
        InlineKeyboardMarkup([_back_row("att:sp"),
                              _walk_btn("birth"),
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


# ───────────────────────── FLOW WALKTHROUGHS ─────────────────────────
# Each stub above stops at the staff's last tap. These walkthroughs let the OWNER
# (in /test) step through EVERY message that follows — senior cards, group notices,
# final staff confirmation — so the whole ladder is visible end-to-end. Preview only:
# cross-audience messages are tagged [→ X]; nothing is sent or written. New staff-facing
# lines marked "(KH pending)" feed the next ChatGPT batch.

_WALK_BACK = {"late": "att:late", "al": "att:al", "swap": "att:do", "sickme": "att:sp:me",
              "sickfam": "att:sp:sick", "marriage": "att:sp:mar", "death": "att:sp:death",
              "birth": "att:sp"}


def _ill(*rows) -> InlineKeyboardMarkup:
    """Illustrative buttons for a preview pick-step — visual only (att:walk:noop)."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(lbl, callback_data="att:walk:noop")
                                 for lbl in row] for row in rows])


def _walk_btn(name: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton("▶️ See the rest of this flow", callback_data="att:walk:%s:0" % name)]


def _walk_steps(p: dict, name: str) -> list[tuple[str, InlineKeyboardMarkup | None]]:
    """Each step = (message text, illustrative keyboard or None). Pick-steps carry REAL
    buttons (visual only) so the preview looks exactly like what staff/seniors will tap."""
    nm = p.get("call_name") or p["canonical_name"]
    ws = fmt12(to_min(p.get("work_start"))) if to_min(p.get("work_start")) is not None else "your start"
    if name == "late":
        return [
            ("[→ SUPERVISORS group, at declare-time WITH reason]\n"
             "“%s will be ~15 min late for tonight's shift. Reason: moto broke.”" % nm, None),
            ("[→ %s, arrival watch — fires at the declared time, repeats 4× every 15 min "
             "until location confirms]\n"
             "“Are you there yet? Open Live Location.”\n"
             "“អ្នកមកដល់ហើយឬនៅ? សូមបើកទីតាំងបន្តផ្ទាល់។”" % nm, None),
            ("[→ %s, when location enters the zone — TRUTH = location, not what was said]\n"
             "“Arrived 9:18pm — 13 min late. That becomes 13 min pay-back time.”\n"
             "“មកដល់ 9:18pm — យឺត 13 នាទី។ នេះនឹងត្រូវរាប់ជា 13 នាទី ម៉ោងសងវិញ។”" % nm, None),
            ("[→ %s] payback slot picker (no AL option — late = time):\n"
             "“Pick when to pay back your 13 minutes — the best times for the shop, next 7 days:”\n"
             "“ជ្រើសពេលមកសង 13 នាទីរបស់ប្អូន — ពេលដែលល្អសម្រាប់ហាង ក្នុង 7 ថ្ងៃខាងមុខ:”" % nm,
             _ill(["Fri 06/06 7:30–7:43pm"], ["Sat 07/06 5:47–6:00am"], ["Pay 1 hour only · សងតែ 1h"])),
            ("[→ %s] booked ✓ — runs like a mini-shift (T−10, check-in, +10 if early):\n"
             "“Booked ✓ — Fri 06/06 7:30–7:43pm. Come 5 minutes early and you earn +10 points ⭐”\n"
             "“បានកក់រួច ✓ — មកដល់មុន 5 នាទី អ្នកនឹងទទួលបាន +10 points ⭐”" % nm, None),
            ("[→ SUPERVISORS group]\n“%s pays back Fri 06/06, 7:30–7:43pm.”\n\n"
             "✓ Lateness ladder complete." % nm, None),
        ]
    if name in ("al", "marriage"):
        what = "marriage leave (3 days)" if name == "marriage" else "AL"
        kh_ok = ("ច្បាប់រៀបការរបស់ប្អូនអនុម័តហើយ ✓ Tue 23/06។ អបអរសាទរ! 🤍" if name == "marriage"
                 else "AL របស់ប្អូនអនុម័តហើយ ✓ Tue 23/06។ ប្អូននៅសល់ AL 6.5 ថ្ងៃទៀត។ 🤍")
        return [
            ("[→ %s] “Reason? (you type it)” → reason captured verbatim, attached to the request." % nm,
             None),
            ("[→ EVERY senior, privately] approval card:\n"
             "“%s requests %s — Tue 23/06 (full day). Reason: family trip.\n"
             "Working that day: Dara, Sok, Mealea (day-off: Pisey; on AL: Vann).”" % (nm, what),
             _ill(["✅ Approve · អនុម័ត", "❌ Not approve · មិនអនុម័ត"])),
            ("[→ requester] “Senior 1 approved ✓ (1/2)…” (silent until the 2nd vote).", None),
            ("[→ all seniors] the cards collapse → fresh DM tagging who approved. "
             "2 ✅ = approved (2 ❌ = seniors-only recap, requester told no).", None),
            ("[→ SUPERVISORS group, reason INCLUDED]\n"
             "“%s on leave Tue 23/06 (family trip). Normal day off: Fri. Back at work: Wed 24/06, %s.”"
             % (nm, ws), None),
            ("[→ %s] “Your %s is approved ✓ Tue 23/06. AL balance: 6.5 days 🤍”\n“%s”\n\n"
             "✓ Approval ladder complete (AL deducted; marriage may go below zero, never salary)."
             % (nm, what, kh_ok), None),
        ]
    if name == "swap":
        return [
            ("[→ %s] “Reason? (you type it)” → captured." % nm, None),
            ("[→ the PARTNER, privately — their veto is asked FIRST (cheapest)]\n"
             "“%s wants to swap day off: you take Wed off, %s takes Fri — same week. Reason: clinic.”"
             % (nm, nm), _ill(["✅ I agree · ខ្ញុំយល់ព្រម", "✋ No · ទេ"])),
            ("[→ %s] “You agreed — sending to seniors.”  (partner silence/❌ = swap doesn't happen, "
             "%s told, seniors never bothered.)" % (nm, nm), None),
            ("[→ EVERY senior] approval card (same week rule) → 2 ✅ applies dated overrides.",
             _ill(["✅ Approve · អនុម័ត", "❌ Not approve · មិនអនុម័ត"])),
            ("[→ SUPERVISORS group]\n“Day-off swap: %s off Fri, partner off Wed.”" % nm, None),
            ("[→ %s] “Your day-off swap is approved ✓”\n"
             "“ការប្តូរថ្ងៃឈប់របស់អ្នកបានអនុម័តហើយ ✓”\n\n✓ Swap ladder complete." % nm, None),
        ]
    if name == "sickme":
        return [
            ("[→ %s] “If you see a doctor, send me a photo of the papers.” → (staff sends a photo)" % nm,
             None),
            ("[→ OWNER + Tyty ONLY — never a group, never other seniors]\n"
             "“🩺 %s — sick papers. Opus: Calmette Hospital · likely flu · 2d · not contagious.”\n"
             "(the photo is forwarded right under this card)" % nm,
             _ill(["✓ Accept (cover 2d)"], ["1d", "2d", "3d"], ["💺 Offer part-duty"],
                  ["Skip → nightly nudges"])),
            ("[→ owner taps ✓ Accept 2d] → debt + points wiped, real sick day, AL UNTOUCHED.", None),
            ("[→ %s] “Saved ✓ — your sick day is confirmed, nothing owed. Get well 🤍”\n"
             "“រក្សាទុករួច ✓ — ថ្ងៃឈឺរបស់អ្នកបានបញ្ជាក់ហើយ មិនមានអ្វីត្រូវសងទេ។ សូមឱ្យឆាប់ជាសះស្បើយ 🤍”"
             % nm, None),
            ("[→ %s, if part-duty offered] “Feeling a little better? There's light work today (+15 ⭐) "
             "— only if you truly feel able 🤍”\n\n"
             "✓ Sick-papers ladder complete. (Paperless = pay-back from declaration; accepted papers "
             "within 2 days cancel it. Nightly return-check asks if they're back, not about papers.)"
             % nm, _ill(["💪 I can come · ខ្ញុំអាចមក", "🛌 Rest today · សម្រាកថ្ងៃនេះ"])),
        ]
    if name == "sickfam":
        return [
            ("[→ SUPERVISORS group] “%s's family member is sick — off today (no approval needed).”" % nm,
             None),
            ("[→ %s, 12h before the next shift] one-tap re-book nudge:\n"
             "“Is your child better? If you need tomorrow off too, tell me now.\n"
             "តើកូនរបស់អ្នកធូរស្បើយហើយឬនៅ? បើត្រូវការឈប់ថ្ងៃស្អែកទៀត សូមប្រាប់ខ្ញុំឥឡូវនេះ។”\n\n"
             "✓ Family-sick ladder complete (each day burns 1 of the 7 yearly special-leave days)." % nm,
             _ill(["Again tomorrow · ស្អែកទៀត", "👍 Better · ធូរស្បើយហើយ"])),
        ]
    if name == "death":
        return [
            ("[→ SUPERVISORS group] “%s on leave (death of parent).” (relation may be named)" % nm, None),
            ("[→ OWNER, compassion tier only] “%s reported a sibling's death — gave 1 day (compassion).”"
             % nm, _ill(["Upgrade to 3 days · បន្ថែមដល់ 3 ថ្ងៃ"])),
            ("[→ %s, if owner upgrades] “Your leave is extended to 3 days 🤍”\n\n"
             "✓ Death-leave ladder complete (no approval ever; AL may go below zero, never salary)." % nm,
             None),
        ]
    if name == "birth":
        return [
            ("[→ SUPERVISORS group] “%s on leave 2 days (wife giving birth).”" % nm, None),
            ("[→ %s] “Congratulations! 👶 2 days of leave booked.”\n"
             "“អបអរសាទរ! 👶 សម្រាក 2 ថ្ងៃ បានកក់រួច។”\n\n✓ Wife-birth ladder complete." % nm, None),
        ]
    return []


def walk_card(p: dict, name: str, idx: int) -> tuple[str, InlineKeyboardMarkup]:
    steps = _walk_steps(p, name)
    if not steps:
        return main_menu(p)
    idx = max(0, min(idx, len(steps) - 1))
    n = len(steps)
    text, step_kb = steps[idx]
    back = ("att:walk:%s:%d" % (name, idx - 1)) if idx > 0 else _WALK_BACK.get(name, "att:menu")
    # a choice button ADVANCES to its consequence (the next step) — never a dead tap
    nxt = ("att:walk:%s:%d" % (name, idx + 1)) if idx < n - 1 else "att:menu"
    rows = []
    if step_kb:
        for r in step_kb.inline_keyboard:
            rows.append([InlineKeyboardButton(b.text, callback_data=nxt) for b in r])
    rows.append(_back_row(back))
    if idx < n - 1:
        rows.append([InlineKeyboardButton("▶️ Next step (%d/%d)" % (idx + 2, n),
                                          callback_data="att:walk:%s:%d" % (name, idx + 1))])
    else:
        rows.append([InlineKeyboardButton("🏠 Main menu — flow complete ✓", callback_data="att:menu")])
    return _hdr(p, "Step %d of %d — the flow continues:\n\n%s" % (idx + 1, n, text)), \
        InlineKeyboardMarkup(rows)


def about_work_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    # Rules for everyone; Give OT seniors only; later: Stocks + other checks (owner)
    rows = [
        _back_row(),
        [InlineKeyboardButton("📜 Rules · ច្បាប់ហាង", callback_data="att:rules")],
    ]
    if p.get("is_senior"):
        rows.append([InlineKeyboardButton("➕ Give OT / change shift", callback_data="att:scp:staff")])
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
                "• No-show = ដកប្រាក់ឈ្នួល 1 ថ្ងៃ ហើយលក្ខខណ្ឌ Bonus លើកនេះមិនបានសម្រេច។\n\n"
                "• AL: free when asked 7+ days ahead. Within 7 days is possible — it costs points.\n"
                "• AL៖ ស្នើមុន 7+ ថ្ងៃ = មិនដក Points។ ក្នុង 7 ថ្ងៃ អាចស្នើបាន — តែដក Points។\n\n"
                "• Special Leave (sick, marriage, family death, birth): see the menu — money is never "
                "taken for these.\n"
                "• ច្បាប់ពិសេស (ឈឺ, រៀបការ, មរណភាពគ្រួសារ, ប្រពន្ធសម្រាលកូន)៖ សូមមើលក្នុង menu — "
                "មិនដកប្រាក់ខែសម្រាប់រឿងទាំងនេះទេ។\n\n"
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
               "Noted — arriving ~%s (%d min late).\n"
               "កត់ចំណាំហើយ — មកដល់ប្រហែល ~%s (យឺត %d min)។\n"
               "Why? (you type the reason)\nហេតុអ្វី? (សូមវាយប្រាប់ហេតុផល)\n\n"
               "[TEST PREVIEW → SUPERVISORS group, with the reason]\n"
               "“%s will be ~%d min late for the %s shift today. Reason: …”\n\n"
               "Then on arrival (location): if >5 min late → PAYBACK slots (time only — never AL)."
               % (fmt12(ws + offset), offset, fmt12(ws + offset), offset,
                  p.get("call_name") or p["canonical_name"], offset, fmt12(ws)))
    return txt, InlineKeyboardMarkup([_back_row("att:late"), _walk_btn("late"),
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")]])


def al_screen(p: dict, picked: set[str], page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    al_left = p.get("al_left")
    start = _today() + timedelta(days=page * 28)
    days = [start + timedelta(days=i) for i in range(28)]
    near_cut = _today() + timedelta(days=6)
    btns = []
    for d in days:
        iso = d.isoformat()
        mark = "✅ " if iso in picked else ""
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
    return _hdr(p, "You have %s AL days left.\n"
                   "អ្នកនៅសល់ AL %s ថ្ងៃ។\n"
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


def al_stub(p: dict, detail: str, walk: str = "al") -> tuple[str, InlineKeyboardMarkup]:
    rows = [_back_row()]
    if walk:
        rows.append(_walk_btn(walk))
    rows.append([InlineKeyboardButton("🏠 Main menu", callback_data="att:menu")])
    return _hdr(p, detail), InlineKeyboardMarkup(rows)


# Emergency AL was REMOVED by the owner (session 28) — weird emergencies go via points (TBD).
# The old emergency_screen/emergency_dates + att:em branch were unreachable dead code, deleted
# session 30. (Short-notice AL — _near_days / SHORT_NOTICE_PT_PER_MIN — is a SEPARATE thing, kept.)


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
    rows += [[InlineKeyboardButton(staff_btn_label(c), callback_data="att:do:p:%d" % c["id"])]
             for c in staff_sort(cands)[:8]]
    d = date.fromisoformat(iso)
    return _hdr(p, "Swap day-off for %s — with whom? (similar shift times; within 7 days)\n"
                   "ប្តូរថ្ងៃឈប់ទៅ %s — ជាមួយអ្នកណា? (ម៉ោងវេនប្រហាក់ប្រហែល; ក្នុង 7 ថ្ងៃ)"
                % (day_label(d), day_label(d))), InlineKeyboardMarkup(rows)


def ot_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    # everyone's personal OT view — Give OT lives under About Work (seniors).
    # Live bank + buyback slots are shown in 📋 My schedule (att:my).
    return _hdr(p, "OT is given by your seniors when the shop needs extra hours — when you have hours "
                   "banked, I'll show you the best times to take them back.\n"
                   "OT ត្រូវបានអនុញ្ញាតដោយបងៗ/អ្នកគ្រប់គ្រង ពេលហាងត្រូវការម៉ោងបន្ថែម។ "
                   "ពេលអ្នកមានម៉ោង OT សន្សំទុក ខ្ញុំនឹងបង្ហាញពេលដែលអ្នកអាចសម្រាកសងម៉ោងវិញបាន។\n\n"
                   "👉 Your live OT bank is in 📋 My schedule.\n"
                   "👉 OT bank បច្ចុប្បន្នរបស់អ្នកនៅក្នុង 📋 កាលវិភាគរបស់ខ្ញុំ។"), \
        InlineKeyboardMarkup([_back_row("att:am"),
                              [InlineKeyboardButton("📋 My schedule · កាលវិភាគ", callback_data="att:my")]])


# ===== Session 31: UNIFIED Give-OT / shift-redefine picker (see docs/OT_DESIGN.md) =====
# staff → work-day → [Change time | Change day] → start ladder → end ladder (+PB/+OT) → reason →
# submit_shift_change. OT is emergent = end beyond (start + normal length). Callbacks under att:scp:.
def _sc_pool():
    return [r for r in staff_all("active") if r.get("org") == "TWB" and r.get("canonical_name") != "Tyty"]


def sc_staff_pick(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Give OT / change a shift — pick the staffer."""
    rows = [_back_row("att:aw")]
    rows += [[InlineKeyboardButton(staff_btn_label(r), callback_data="att:scp:d:%d" % r["id"])]
             for r in staff_sort(_sc_pool())][:35]
    return _hdr(p, "Give OT / change a shift — for whom?\nឱ្យ OT / ប្តូរវេន — ឱ្យអ្នកណា?"), \
        InlineKeyboardMarkup(rows)


def _sc_workdays(sid: int, n: int = 7) -> list[tuple[int, date]]:
    """The next n WORKING days for this staffer (their day-off weekday excluded), today first.
    Returns (dayidx_from_today, date)."""
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    off = _DOW_NAME.get(((rec or {}).get("day_off") or "")[:3].title())
    out = []
    for i in range(0, 21):
        d = _today() + timedelta(days=i)
        if off is None or d.weekday() != off:
            out.append((i, d))
        if len(out) >= n:
            break
    return out


def _sc_running(sid: int):
    """If the staffer is MID-SHIFT right now → (tdidx, eff_start_min, shift_date_iso) of the RUNNING
    shift, else None. Overnight-aware: tdidx may be -1 (a 9pm–6am baker at 2am is running YESTERDAY's
    shift — a date today's work-day list can't express). Redefine-aware: an approved shift_change for
    the date supplies the effective [start,len] (and makes a day-off day count as working).
    Powers the 'extend the running shift' entry — spec 'today edges': a start that already happened
    is LOCKED; the only time action on a running shift is extending its end."""
    from shared.database import shift_change_active
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    if not rec:
        return None
    now = _now_min()
    off = _DOW_NAME.get((rec.get("day_off") or "")[:3].title())
    for tdidx in (0, -1):
        d = _today() + timedelta(days=tdidx)
        sc = None
        try:
            sc = shift_change_active(sid, d.isoformat())
        except Exception:
            pass
        if sc and sc.get("start_min") is not None and sc.get("end_min") is not None:
            ws, ln = int(sc["start_min"]) % 1440, int(sc["end_min"]) - int(sc["start_min"])
        else:
            if off is not None and d.weekday() == off:
                continue
            try:
                if d.isoformat() in al_leave_days_set(sid):
                    continue
            except Exception:
                pass
            ws = to_min(rec.get("work_start"))
            ln = shift_len_min(rec.get("work_start"), rec.get("work_end"))
        if ws is None or not ln:
            continue
        if tdidx == 0:
            running = ws <= now < ws + ln          # started today, not yet past the end
        else:
            running = (1440 - ws) + now < ln       # overnight tail: started yesterday, still inside
        if running:
            return tdidx, ws, d.isoformat()
    return None


def sc_day_pick(p: dict, sid: int) -> tuple[str, InlineKeyboardMarkup]:
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    nm = (rec or {}).get("call_name") or (rec or {}).get("canonical_name") or "?"
    rows = [_back_row("att:scp:staff")]
    run = _sc_running(sid)
    if run:
        # the running shift may have started YESTERDAY (overnight) — this button is the only way to
        # reach that date; start is locked → straight to the END ladder (att:scp:st routes to sc_end)
        tdidx, ws_eff, _iso = run
        rows.append([InlineKeyboardButton(
            "⚡ Extend the shift running NOW (started %s) · បន្ថែមវេនដែលកំពុងដំណើរការ" % fmt12(ws_eff),
            callback_data="att:scp:st:%d:%d:%d" % (sid, tdidx, ws_eff))])
    rows += grid([InlineKeyboardButton(day_label(d), callback_data="att:scp:m:%d:%d" % (sid, i))
                  for i, d in _sc_workdays(sid)], 2)
    return _hdr(p, "Change %s's shift — which work day?\nប្តូរវេនរបស់ %s — ថ្ងៃធ្វើការណា?" % (nm, nm)), \
        InlineKeyboardMarkup(rows)


def sc_mode(p: dict, sid: int, didx: int) -> tuple[str, InlineKeyboardMarkup]:
    """Retime/extend THIS day (Change time → straight to the start ladder), or move it to a day off
    (Change day → pick a day off, then the start ladder). MID-SHIFT today (spec 'today edges'): the
    start already happened → it is LOCKED to the real start and the only time action is extending the
    end (straight to the end ladder); Change day stays available for future re-planning."""
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    nm = (rec or {}).get("call_name") or (rec or {}).get("canonical_name") or "?"
    d = _today() + timedelta(days=didx)
    run = _sc_running(sid) if didx == 0 else None
    if run and run[0] == 0:
        rows = [
            _back_row("att:scp:d:%d" % sid),
            [InlineKeyboardButton("⏱ Extend the end (started %s) · បន្ថែមម៉ោងចប់" % fmt12(run[1]),
                                  callback_data="att:scp:st:%d:0:%d" % (sid, run[1]))],
            [InlineKeyboardButton("📅 Change day · ប្តូរថ្ងៃ", callback_data="att:scp:cd:%d:%d" % (sid, didx))],
        ]
        return _hdr(p, "%s is MID-SHIFT (started %s) — the start is locked. Extend the end, "
                       "or move a day?\n%s កំពុងធ្វើវេន (ចាប់ផ្តើម %s) — ម៉ោងចាប់ផ្តើមផ្លាស់ប្តូរមិនបានទេ។ "
                       "បន្ថែមម៉ោងចប់ ឬប្តូរថ្ងៃ?"
                    % (nm, fmt12(run[1]), nm, fmt12(run[1]))), InlineKeyboardMarkup(rows)
    rows = [
        _back_row("att:scp:d:%d" % sid),
        [InlineKeyboardButton("⏱ Change time · ប្តូរម៉ោង", callback_data="att:scp:ss:%d:%d" % (sid, didx))],
        [InlineKeyboardButton("📅 Change day · ប្តូរថ្ងៃ", callback_data="att:scp:cd:%d:%d" % (sid, didx))],
    ]
    return _hdr(p, "%s — %s. Retime/extend, or move to a day off?\n"
                   "%s — %s។ ប្តូរម៉ោង/បន្ថែម ឬផ្លាស់ទៅថ្ងៃឈប់?" % (nm, day_label(d), nm, day_label(d))), \
        InlineKeyboardMarkup(rows)


def sc_dayoff_pick(p: dict, sid: int, didx: int) -> tuple[str, InlineKeyboardMarkup]:
    """Change DAY: move this shift to one of the staffer's nearest 2 day-offs (then the start ladder)."""
    from gm_bot import payback as pb
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    nm = (rec or {}).get("call_name") or (rec or {}).get("canonical_name") or "?"
    offs = pb.dayoff_dates_ahead((rec or {}).get("day_off"), set(), _today(), 21)[:2]
    rows = [_back_row("att:scp:m:%d:%d" % (sid, didx))]
    for od in offs:
        rows.append([InlineKeyboardButton(day_label(od) + " (off)",
                     callback_data="att:scp:ss:%d:%d" % (sid, (od - _today()).days))])
    msg = ("Move %s's shift to which day off?\nផ្លាស់វេនរបស់ %s ទៅថ្ងៃឈប់ណា?" % (nm, nm)) if offs \
        else ("No upcoming day off found for %s.\nគ្មានថ្ងៃឈប់ខាងមុខសម្រាប់ %s។" % (nm, nm))
    return _hdr(p, msg), InlineKeyboardMarkup(rows)


def sc_start(p: dict, sid: int, tdidx: int) -> tuple[str, InlineKeyboardMarkup]:
    """START ladder for the target day (tdidx = days from today). Today drops past times.
    A shift RUNNING today never reaches this ladder — its start is locked (spec 'today edges'),
    so any route here (incl. Back from the end ladder) bounces to the locked mode screen."""
    from gm_bot import ot as ot_mod
    if tdidx == 0:
        run = _sc_running(sid)
        if run and run[0] == 0:
            return sc_mode(p, sid, 0)
    rec, d, ws, we, is_off, nm = _ot_receiver(sid, tdidx)
    earliest = _now_min() if tdidx == 0 else 0
    rows = [_back_row("att:scp:d:%d" % sid)]
    rows += grid([InlineKeyboardButton(fmt12(s), callback_data="att:scp:st:%d:%d:%d" % (sid, tdidx, s))
                  for s in ot_mod.start_options(earliest_min=earliest)], 4)
    return _hdr(p, "%s — START time?\n%s — ម៉ោងចាប់ផ្តើម?" % (day_label(d), day_label(d))), \
        InlineKeyboardMarkup(rows)


def sc_end(p: dict, sid: int, tdidx: int, start: int) -> tuple[str, InlineKeyboardMarkup]:
    """END ladder: normal end (no tag) then each hour beyond carries +NPB (clears debt) then +MOT."""
    from gm_bot import ot as ot_mod
    from shared.database import payback_open_debt
    rec, d, ws, we, is_off, nm = _ot_receiver(sid, tdidx)
    normal_len = (shift_len_min(rec.get("work_start"), rec.get("work_end")) or 0) if rec else 0
    debt = payback_open_debt(sid)
    pb = max(0, debt["minutes_owed"] - debt["minutes_paid"]) if debt else 0
    normal_end = start + normal_len
    btns = []
    for extra in range(0, ot_mod.MAX_EXTRA_HOURS * 60 + 1, 60):
        end_abs = normal_end + extra
        pb_cleared, ot_m = ot_mod.split_ot_pb(extra, pb)
        tag = ot_mod._ext_tag(pb_cleared, ot_m)
        label = fmt12(end_abs % 1440) + ((" " + tag) if tag else "")
        btns.append(InlineKeyboardButton(label,
                    callback_data="att:scp:cf:%d:%d:%d:%d" % (sid, tdidx, start, end_abs)))
    # a locked/running start (extend-the-end, incl. yesterday's overnight tdidx=-1) must NOT offer
    # the start ladder on Back — a start that happened can't be re-picked (spec 'today edges')
    back_cb = ("att:scp:d:%d" % sid) if tdidx < 0 else ("att:scp:ss:%d:%d" % (sid, tdidx))
    rows = [_back_row(back_cb)] + grid(btns, 2)
    return _hdr(p, "%s — END time? (start %s)\n%s — ម៉ោងបញ្ចប់?" % (day_label(d), fmt12(start), day_label(d))), \
        InlineKeyboardMarkup(rows)


def _ot_receiver(sid: int, dayidx: int):
    """(record, date, shift_start, shift_end, is_dayoff, call_name) for the OT receiver."""
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    d = _today() + timedelta(days=dayidx)
    ws = to_min((rec or {}).get("work_start"))
    we = to_min((rec or {}).get("work_end"))
    off = _DOW_NAME.get(((rec or {}).get("day_off") or "")[:3].title())
    is_off = off is not None and d.weekday() == off
    nm = (rec or {}).get("call_name") or (rec or {}).get("canonical_name") or "?"
    return rec, d, ws, we, is_off, nm


def checkin_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    return _hdr(p, "Tap 📎 (Attach) → Location / ទីតាំង → Share Live Location / "
                   "ចែករំលែកទីតាំងបន្តផ្ទាល់\n\n"
                   "Shift: %s–%s"
                % (fmt12s(p.get("work_start")), fmt12s(p.get("work_end")))), \
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
        [InlineKeyboardButton("⑦ ✅ Simulate full checkout (settle + banking)",
                              callback_data="att:cisco:%d" % p["id"])],
    ]
    return _hdr(p, "▶️ Check-in simulator — each button sends the REAL message exactly as %s would "
                   "receive it (to you only). ④ makes your next shared live location be judged as "
                   "their check-in. ⑦ runs the REAL end-to-end checkout: ensures a check-in, checks "
                   "out at the shift end, settles OT vs their normal length, and sends the thank-you "
                   "— so you can walk Give-OT → approve → checkout → banking without going live."
                % (p.get("call_name") or p["canonical_name"])), \
        InlineKeyboardMarkup(rows)


def _ci_msg_pre(p: dict) -> str:
    ws = to_min(p.get("work_start"))
    t = fmt12(ws) if ws is not None else "?"
    return ("Your shift starts in 10 minutes (%s).\n"
            "វេនការងាររបស់អ្នកនឹងចាប់ផ្តើមក្នុង 10 នាទីទៀត (%s)។\n"
            + _CI_HOWTO + "\n\n"
            "Arrive 5 minutes early and you earn +10 points ⭐\n"
            "មកដល់មុន 5 នាទី អ្នកនឹងទទួលបាន +10 points ⭐") % (t, t)


def _kb_im_late() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕘 I'm late · ខ្ញុំមកយឺត", callback_data="att:late")],
    ])


def _ci_msg_start() -> tuple[str, InlineKeyboardMarkup]:
    # how-to is inline (the recognizable line) -> no separate How-to button needed
    kb = _kb_im_late()
    return ("Your shift just started — check in now.\n"
            "វេនការងាររបស់អ្នកទើបតែចាប់ផ្តើមហើយ — សូមចុះវត្តមាន។\n"
            + _CI_HOWTO + "\n\n"
            "Running late? Tap below.\nកំពុងមកយឺតមែនទេ? សូមចុចខាងក្រោម។"), kb


_CI_MSG_PLUS5 = ("We give everyone 5 free late minutes 😊 More than 5 — every late minute counts: "
                 "as pay-back time, and minus points. The sooner you tell us, the fewer points it "
                 "costs. See you soon!\n"
                 "យើងផ្ដល់ឱ្យគ្រប់គ្នា 5 នាទីអនុគ្រោះសម្រាប់ការមកយឺត 😊 បើលើសពី 5 នាទី រាល់នាទីយឺត"
                 "ទាំងអស់នឹងត្រូវរាប់៖ ជាម៉ោងសងវិញ និងដកពិន្ទុ។ ប្រាប់យើងកាន់តែឆាប់ ពិន្ទុដែលត្រូវដក"
                 "កាន់តែតិច។ ជួបគ្នាឆាប់ៗ!")

_CI_HOWTO = "📍 Tap 📎 (Attach) → Location / ទីតាំង → Share Live Location / ចែករំលែកទីតាំងបន្តផ្ទាល់"

# check-in verdicts — shared by the armed simulator and the dry-run catalogue (no drift)
_V_EARLY = ("Checked in ✓ — %d min early. +10 points ⭐\n"
            "ចុះវត្តមានរួច ✓ — មុន %d នាទី។ +10 points ⭐")
_V_ONTIME = "Checked in ✓\nចុះវត្តមានរួច ✓"
_V_LATE = ("Checked in ✓ — %d min late (counts as pay-back).\n"
           "ចុះវត្តមានរួច ✓ — យឺត %d នាទី (រាប់ជាម៉ោងសងវិញ)។\n\n"
           "Why were you late?\nហេតុអ្វីបានជាអ្នកមកយឺត?")
_V_FAR = ("You're not at the shop yet — it will count when you arrive.\n"
          "អ្នកមិនទាន់នៅហាងទេ — ចុះវត្តមាននឹងរាប់ពេលអ្នកមកដល់។")
_PIN_RESPONSE = ("Sending a pin does not count as check-in to work.\n"
                 "ការផ្ញើទីតាំងជា Pin មិនរាប់ជាការចុះវត្តមានចូលធ្វើការទេ។\n\n"
                 "Do this instead:\nសូមធ្វើតាមនេះវិញ៖\n\n"
                 "Tap 📎 (Attach) → Location / ទីតាំង → Share Live Location / ចែករំលែកទីតាំងបន្តផ្ទាល់")

_CI_MSG_OUT = ("Shift over — share your live location to check out.\n"
               "វេនចប់ហើយ — សូមចែករំលែកទីតាំងបន្តផ្ទាល់ ដើម្បីចុះវត្តមានចេញ។\n\n"
               + _CI_HOWTO)

_CI_MSG_OUT2 = ("Did you leave early? If not, share your location to check out.\n"
                "អ្នកចេញមុនម៉ោងមែនទេ? បើមិនមែន សូមចែករំលែកទីតាំងបន្តផ្ទាល់ ដើម្បីចុះវត្តមានចេញ។\n\n"
                + _CI_HOWTO)

# Sent on EVERY successful checkout — manual share-to-checkout AND silent auto-checkout (owner).
_CO_DONE = ("Checked out ✓ Thank you, have a nice day! 🤍\n"
            "ចុះវត្តមានចេញរួច ✓ អរគុណ សូមឱ្យថ្ងៃនេះល្អៗ 🤍")


def my_screen(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Live personal dashboard — real balances from the DB (AL, payback debt, OT bank, upcoming)."""
    import json as _json
    from shared.database import (_db, payback_open_debt, ot_bank_balance, ot_pending_extension_min)
    exp = ", ".join(p.get("expertise") or []) or "-"
    debt = payback_open_debt(p["id"])
    debt_min = debt["balance"] if debt else 0
    bank_min = ot_bank_balance(p["id"])
    # Agreed-but-not-yet-worked OT (approved upcoming redefines) settles at checkout: it clears
    # payback FIRST, the leftover banks. Partition it with NO double-count — the same hour is either
    # 'booked' against the debt OR 'upcoming' into the bank, never both:
    #   booked PB  = min(extension, debt)            → shown next to the debt
    #   upcoming OT = max(0, extension − debt)        → shown next to the bank (capped at 14h room)
    from gm_bot import ot as ot_mod
    pending_ext = ot_pending_extension_min(p["id"], _today().isoformat())
    booked_min = min(pending_ext, debt_min)
    upcoming_ot = min(max(0, pending_ext - debt_min), ot_mod.cap_room(bank_min))
    debt_txt = _hm(debt_min) + ((" (%s booked · កក់រួច)" % _hm(booked_min)) if booked_min else "")
    bank_txt = _hm(bank_min) + ((" (%s upcoming · នឹងចូល)" % _hm(upcoming_ot)) if upcoming_ot else "")
    # upcoming approved AL/special dates
    upcoming = []
    rows = [_back_row("att:am")]
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT id, days FROM al_requests
                               WHERE staff_id=%s AND status='approved' AND is_test=%s""",
                            (p["id"], att_test_on()))
                for r in cur.fetchall():
                    for d in _json.loads(r["days"] or "[]"):
                        if d >= _today().isoformat():
                            upcoming.append((d, r["id"]))
    except Exception:
        pass
    upcoming.sort()
    up_txt = ", ".join(day_label(date.fromisoformat(d)) for d, _ in upcoming) or "—"
    today_iso = _today().isoformat()
    # CANCEL buttons ONLY in the role-play (test) shell — the /test shell must never mutate REAL data.
    # (Real staff will cancel their own real ALs through the live staff entry, not here.)
    if att_test_on():
        for d, rid in upcoming[:6]:
            # only offer cancel for dates that haven't STARTED (future, or today before shift begins)
            if d < today_iso or (d == today_iso and _shift_running(p)):
                continue
            rows.append([InlineKeyboardButton("✕ Cancel AL · បោះបង់ AL %s" % day_label(date.fromisoformat(d)),
                                              callback_data="att:my:cancel:%s:%d" % (d, rid))])
    return _hdr(p, "📋 My schedule · កាលវិភាគខ្ញុំ\n"
                   "Shift · វេន: %s–%s\nDay off · ថ្ងៃឈប់: %s\nExpertise · ជំនាញ: %s\n\n"
                   "AL left: %s days\n"
                   "Payback debt: %s\n"
                   "OT bank: %s\n"
                   "Upcoming AL: %s"
                % (fmt12s(p.get("work_start")), fmt12s(p.get("work_end")),
                   p.get("day_off") or "?", exp, p.get("al_left", "?"),
                   debt_txt, bank_txt, up_txt)), \
        InlineKeyboardMarkup(rows)


def staff_btn_label(r: dict) -> str:
    """Staff-pick button text: 'POR — Chea Chaktopor' (the CAPSED call name first, owner session 32).
    No call name on record → just the canonical name."""
    cn = (r.get("call_name") or "").strip()
    return ("%s — %s" % (cn.upper(), r["canonical_name"])) if cn else r["canonical_name"]


def staff_sort(rows: list[dict]) -> list[dict]:
    """Alphabetical by the name we CALL them (call_name, falling back to canonical)."""
    return sorted(rows, key=lambda r: (r.get("call_name") or r.get("canonical_name") or "").lower())


def persona_picker(page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    staff = staff_sort([r for r in staff_all("active")
                        if r.get("org") == "TWB" and r.get("canonical_name") != "Tyty"])   # TWB only
    chunk = staff[page * 8:(page + 1) * 8]
    rows = [[InlineKeyboardButton("🧪 Dry-run 1: Check-in (full lifecycle)",
                                  callback_data="att:dr:go")],
            [InlineKeyboardButton("🧪 Dry-run 2: Late & payback lifecycle",
                                  callback_data="att:dr:go2")],
            [InlineKeyboardButton("🧪 Dry-run 3: Annual Leave (all variants)",
                                  callback_data="att:dr:go3")],
            [InlineKeyboardButton("🧪 Dry-run 4: Sick (papers, part-duty, family)",
                                  callback_data="att:dr:go4")],
            [InlineKeyboardButton("🧪 Dry-run 5: Marriage · Death · Birth",
                                  callback_data="att:dr:go5")],
            [InlineKeyboardButton("🧪 Dry-run 6: Day-off swap",
                                  callback_data="att:dr:go7")],
            [InlineKeyboardButton("🧪 Dry-run 7: Acks · redirect · call-outs · welcome",
                                  callback_data="att:dr:go8")]] if page == 0 else []
    # (labels renumbered 2026-06-11 — the old Dry-run 6 was the retired Now/Later OT model's
    # walkthrough; the Give-OT/shift-redefine flow is walked INTERACTIVELY, not as a script.
    # Callback ids stay go7/go8 — only the display numbers closed the gap.)
    rows += [[InlineKeyboardButton(staff_btn_label(r),
                                   callback_data="att:persona:%d" % r["id"])] for r in chunk]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀", callback_data="att:pickp:%d" % (page - 1)))
    if (page + 1) * 8 < len(staff):
        nav.append(InlineKeyboardButton("▶", callback_data="att:pickp:%d" % (page + 1)))
    if nav:
        rows.append(nav)
    head = ("🧪 TEST — pick who you want to act as.\n\n"
            "✅ REAL TEST: run /testmode on first — then every button is LIVE (real code), and every "
            "message (staff/senior/group) is routed to YOU. /teststatus · /testreset · /testmode off.\n"
            "⚡ The Dry-runs below are a READ-ONLY preview (they can lag the real flow) — use them for "
            "a quick look, but TRUST /testmode for the real test.")
    return head, InlineKeyboardMarkup(rows)


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
        from gm_bot.attendance import TWB_LAT, TWB_LNG, WORK_ZONE_RADIUS_M, haversine_m
        dist = haversine_m(loc.latitude, loc.longitude, TWB_LAT, TWB_LNG)
        # ARMED check-in simulation: judge this live location as the persona's check-in
        if context.user_data.get("att_ci_armed"):
            context.user_data["att_ci_armed"] = False
            p = _persona(context)
            ws = to_min(p.get("work_start")) if p else None
            if p and ws is not None:
                from gm_bot.checkin import verdict
                state, mins = verdict(_now_min(), ws, dist <= WORK_ZONE_RADIUS_M)
                in_zone = dist <= WORK_ZONE_RADIUS_M
                # RECORD it for real (test-tagged) only in test mode — same att_check_in code as
                # production. Never writes real data unless /testmode on (is_test stamped from the flag).
                from shared.database import att_test_on, att_record_ping, att_check_in
                if att_test_on() and state != "not_here":
                    today = _today().isoformat()
                    nowiso = datetime.now().isoformat()
                    att_record_ping(p["id"], loc.latitude, loc.longitude, in_zone, nowiso)
                    att_check_in(p["id"], today, nowiso, in_zone,
                                 mins if state == "late" else 0, mins if state == "early" else 0)
                if state == "not_here":
                    await msg.reply_text(_V_FAR + "\n[test: %dm from TWB]" % round(dist))
                elif state == "early":
                    await msg.reply_text(_V_EARLY % (mins, mins))
                elif state == "ontime":
                    await msg.reply_text(_V_ONTIME)
                else:
                    await msg.reply_text(_V_LATE % (mins, mins))
                return
        await msg.reply_text(
            "🧪 [TEST] Live location received ✓\nDistance from TWB: %dm — %s"
            % (round(dist), "INSIDE the %dm zone ✅" % WORK_ZONE_RADIUS_M if dist <= WORK_ZONE_RADIUS_M
               else "outside the zone ❌"))
        return
    # static pin (always a NEW message) — the locked bilingual response
    await msg.reply_text(_PIN_RESPONSE)


async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only: open the role-play shell."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    if update.effective_chat.type != "private":
        return
    context.user_data["att_live_self"] = False   # owner is role-playing, not a live staffer
    text, kb = persona_picker(0)
    await update.message.reply_text(text, reply_markup=kb)


async def open_live_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, rec: dict) -> None:
    """LIVE entry: a real active staffer opens their OWN attendance menu (gated upstream by
    attendance_live). Persona is LOCKED to themselves; the owner role-play shell is unaffected."""
    context.user_data["att_persona"] = rec["id"]
    context.user_data["att_live_self"] = True
    context.user_data["att_al_picked"] = set()
    text, kb = main_menu(_persona(context))
    await update.message.reply_text(text, reply_markup=kb)


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """All att:* buttons. The owner drives the role-play shell; a real staffer drives their OWN
    menu — persona LOCKED to themselves, and only when attendance_live is on."""
    query = update.callback_query
    uid = update.effective_user.id
    if uid != config.OWNER_TELEGRAM_ID:
        from gm_bot.bot import _attendance_live
        rec = staff_get_by_uid(uid) if _attendance_live() else None
        if not rec or rec.get("status") != "active" or rec.get("org") != "TWB":
            await query.answer()
            return
        # security: a live staffer can ONLY ever act as themselves
        context.user_data["att_persona"] = rec["id"]
        context.user_data["att_live_self"] = True
    await query.answer()
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else ""

    async def show(pair):
        text, kb = pair
        # The /test shell stays BILINGUAL — it previews exactly what staff see (owner, session 30).
        # Khmer is stripped only from the message BODIES routed to the owner (in bot._att_send).
        await query.edit_message_text(text, reply_markup=kb)

    if _is_live(context) and action in ("pick", "pickp", "persona"):
        return await show(main_menu(_persona(context)))   # live: locked to self

    if action == "drs":
        # dry-run sample buttons demonstrate their consequence (owner: ladders must continue)
        what = data[2] if len(data) > 2 else ""
        if what == "part":
            await context.bot.send_message(
                update.effective_chat.id,
                "→ partial chosen — 1-hour options at the shop's best times:",
                reply_markup=_kb_part_slots())
            return
        if what in _DRS:
            head, body = _DRS[what]
            await context.bot.send_message(update.effective_chat.id,
                                           "🧪 %s\n────────────\n%s" % (head, body))
            return
        return
    if action == "dr":
        if len(data) > 2 and data[2] in ("go", "go2", "go3", "go4", "go5", "go6", "go7", "go8"):
            sample = _persona(context) or next(
                (r for r in staff_all("active") if to_min(r.get("work_start")) is not None
                 and r.get("org") == "TWB" and r.get("canonical_name") != "Tyty"), None)
            if sample is None:
                await query.answer("No staff with shifts found")
                return
            if data[2] == "go":
                events = build_catalogue(sample) + [
                    ("📅 schedule summary", schedule_summary(_today()), None)]
                intro = "🧪 Dry-run 1 — CHECK-IN, every message + today's who/when. %d steps:"
            elif data[2] == "go2":
                events = build_catalogue2(sample)
                intro = "🧪 Dry-run 2 — LATE + PAYBACK lifecycle. %d steps:"
            elif data[2] == "go3":
                events = build_catalogue3(sample)
                intro = "🧪 Dry-run 3 — ANNUAL LEAVE, every variant. %d steps:"
            elif data[2] == "go4":
                events = build_catalogue4(sample)
                intro = "🧪 Dry-run 4 — SICK (anti-fake ladder, papers, part-duty, family). %d steps:"
            elif data[2] == "go5":
                events = build_catalogue5(sample)
                intro = "🧪 Dry-run 5 — MARRIAGE · FAMILY DEATH · WIFE BIRTH. %d steps:"
            elif data[2] == "go7":
                events = build_catalogue7(sample)
                intro = "🧪 Dry-run 6 — DAY-OFF SWAP (partner first, then seniors). %d steps:"
            else:
                events = build_catalogue8(sample)
                intro = "🧪 Dry-run 7 — ACKS · GROUP REDIRECT · CALL-OUTS · WELCOME. %d steps:"
            context.user_data["att_dr_events"] = events
            context.user_data["att_dr_i"] = 0
            await context.bot.send_message(update.effective_chat.id, intro % len(events))
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
            if _armed(context):
                _arm_pending(context, update,
                    {"flow": "sick_me", "persona_id": p["id"], "date": _today().isoformat()})
                return await show(_confirm_prompt(p, context,
                    "Sick — can't come to work today. · ឈឺ មកធ្វើការថ្ងៃនេះមិនបាន។",
                    "att:sp:me"))
            return await show(sick_me_cant(p))
        if sub == "sickf":
            return await show(sick_family_dates(p, data[3]))
        if sub == "famd":
            return await show(sick_family_fulltime(p, data[3], data[4]))
        if sub == "famf":
            if _armed(context):
                _arm_pending(context, update,
                    {"flow": "sick_fam", "persona_id": p["id"], "who": data[3], "date": data[4]})
                return await show(_confirm_prompt(p, context,
                    "Family sick (%s) — full day. · គ្រួសារឈឺ (%s) ពេញមួយថ្ងៃ។"
                    % (data[3], data[3]), "att:sp:sick"))
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
        if sub in ("mard", "marcd"):
            child = sub == "marcd"
            if _armed(context):
                _arm_pending(context, update,
                    {"flow": "marriage", "persona_id": p["id"], "start_date": data[3], "child": child})
                ndays = 1 if child else 3
                d0 = date.fromisoformat(data[3])
                dn = d0 + timedelta(days=ndays - 1)
                span = (d0.strftime("%a %d/%m") if ndays == 1
                        else "%s → %s" % (d0.strftime("%a %d/%m"), dn.strftime("%a %d/%m")))
                return await show(_confirm_prompt(p, context,
                    "Marriage leave (%d day%s) · ច្បាប់រៀបការ (%d ថ្ងៃ)\n"
                    "Date · កាលបริច្ឆេទ៖ %s\n\n"
                    "If you need more days, you can request AL.\n"
                    "បើត្រូវការច្រើនថ្ងៃ អ្នកអាចស្នើ AL បន្ថែម។"
                    % (ndays, "" if child else "s", ndays, span), "att:sp:mar"))
            return await show(marriage_stub(p, data[3], child=child))
        if sub == "death":
            return await show(death_menu(p))
        if sub == "deathw":
            return await show(death_dates(p, data[3]))
        if sub == "deathd":
            # compassion tier (sibling/grandparent) = 1 day instant + owner-upgrade; law tier picks 3–7
            from gm_bot.special import death_tier
            if death_tier(data[3]) == "compassion":
                if _armed(context):
                    _arm_pending(context, update,
                        {"flow": "death", "persona_id": p["id"], "who": data[3], "start_date": data[4]})
                    _d0 = date.fromisoformat(data[4])
                    return await show(_confirm_prompt(p, context,
                        "🤍 So sorry for your loss. · សូមរំលែកមរណទុក្ខ 🤍\n"
                        "Family death leave (1 day) · មរណភាពគ្រួសារ (1 ថ្ងៃ)\n"
                        "Date · កាលបริច្ឆេទ៖ %s" % _d0.strftime("%a %d/%m"), "att:sp:death"))
                return await show(death_stub(p, data[3], data[4], 1))
            return await show(death_days(p, data[3], data[4]))
        if sub == "deathn":
            if _armed(context):
                _arm_pending(context, update,
                    {"flow": "death", "persona_id": p["id"], "who": data[3], "start_date": data[4]})
                _nd = int(data[5])
                _d0 = date.fromisoformat(data[4]); _dn = _d0 + timedelta(days=_nd - 1)
                return await show(_confirm_prompt(p, context,
                    "🤍 So sorry for your loss. · សូមរំលែកមរណទុក្ខ 🤍\n"
                    "Family death leave (%d days) · មរណភាពគ្រួសារ (%d ថ្ងៃ)\n"
                    "Date · កាលបริច្ឆេទ៖ %s → %s"
                    % (_nd, _nd, _d0.strftime("%a %d/%m"), _dn.strftime("%a %d/%m")), "att:sp:death"))
            return await show(death_stub(p, data[3], data[4], int(data[5])))
        if sub == "birth":
            return await show(birth_dates(p))
        if sub == "birthd":
            if _armed(context):
                _arm_pending(context, update,
                    {"flow": "birth", "persona_id": p["id"], "start_date": data[3]})
                _d0 = date.fromisoformat(data[3]); _dn = _d0 + timedelta(days=1)
                return await show(_confirm_prompt(p, context,
                    "👶 Congratulations! · សូមអបអរសាទរ! 👶\n"
                    "Wife giving birth — leave (2 days) · ប្រពន្ធសម្រាលកូន (2 ថ្ងៃ)\n"
                    "Date · កាលបริច្ឆេទ៖ %s → %s"
                    % (_d0.strftime("%a %d/%m"), _dn.strftime("%a %d/%m")), "att:sp"))
            return await show(birth_stub(p, data[3]))
        return await show(special_menu(p))
    if action == "aw":
        return await show(about_work_menu(p))
    if action == "rules":
        return await show(rules_screen(p))
    if action == "late":
        if len(data) > 2 and data[2] == "o":
            if _armed(context):
                _arm_pending(context, update,
                    {"flow": "late", "persona_id": p["id"], "mins": int(data[3])})
                return await show(_arm_prompt(p, context,
                    "Late ~%d min. · មកយឺត ~%d នាទី។\n\n"
                    "📝 Type your reason — it sends the Supervisors a heads-up. Share your live "
                    "location when you arrive and I'll work out the payback.\n"
                    "📝 សរសេរមូលហេតុ — វាជូនដំណឹងដល់បងៗ។ ពេលមកដល់ សូមចែករំលែកទីតាំងផ្ទាល់ "
                    "ខ្ញុំនឹងគណនាម៉ោងសងវិញ។"
                    % (int(data[3]), int(data[3])), "att:late"))
            return await show(late_picked(p, int(data[3])))
        return await show(late_screen(p))
    if action == "al":
        picked = context.user_data.setdefault("att_al_picked", set())
        if len(data) > 2:
            sub = data[2]
            if sub == "cov":   # toggle who's-working on the reason prompt (from the stashed selection)
                st = context.user_data.get("att_al_cov") or {}
                flag = bool(int(data[3])) if len(data) > 3 else False
                return await show(_al_prompt(p, context, st.get("detail", ""), st.get("days", []),
                                             st.get("hs"), st.get("he"), flag))
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
                from gm_bot import al as alm
                doff = p.get("day_off")
                nw = staff_absent_dates(p["id"])                # other AL / special leave / swaps
                charged = alm.al_charged_days(picked, doff, nw)  # never charge a day they're away
                span = alm.al_span_label(picked, doff, nw)       # from → to, bridging ANY absence
                near = _near_days(set(charged))
                detail = ("Full-day AL: %s — %d AL day(s).\nAL ពេញមួយថ្ងៃ៖ %s — %d ថ្ងៃ។"
                          % (span, len(charged), span, len(charged)))
                if len(charged) != len(picked):
                    detail += "\nDay off = No AL used · ថ្ងៃឈប់ = មិនដក AL"
                if near:
                    sl = shift_len_min(p.get("work_start"), p.get("work_end")) or 0
                    pts = round(SHORT_NOTICE_PT_PER_MIN * sl * len(near))
                    detail += ("\n⚠ %d short-notice day(s) → −%d points (−0.1/min, pending activation)."
                               "\n⚠ %d ថ្ងៃស្នើជិតពេល → −%d points (−0.1/min, រង់ចាំបើកប្រើ)។"
                               % (len(near), pts, len(near), pts))
                if _armed(context):
                    _arm_pending(context, update,
                        {"flow": "al", "persona_id": p["id"], "kind": "days",
                         "days": sorted(picked), "hours_start": None, "hours_end": None,
                         "_summary": detail})
                    return await show(_al_prompt(p, context, detail, sorted(picked), None, None, False))
                return await show(al_stub(p, detail))
            if sub == "time":
                return await show(al_time_grid(p, "from", picked=picked))
            if sub == "f":
                context.user_data["att_al_from"] = int(data[3])
                return await show(al_time_grid(p, "to", int(data[3])))
            if sub == "t":
                f = context.user_data.get("att_al_from")
                t = int(data[3])
                from gm_bot import al as alm
                _picked = sorted(picked)
                _doff, _nw = p.get("day_off"), staff_absent_dates(p["id"])
                _span = alm.al_span_label(_picked, _doff, _nw)
                _charged = alm.al_charged_days(_picked, _doff, _nw)
                _sl = shift_len_min(p.get("work_start"), p.get("work_end")) or 0
                _total = round(alm.fractional_al(f, t, _sl) * len(_charged), 2)
                detail = ("AL: %s · %s–%s = %g AL.\nAL៖ %s · %s–%s = %g AL។"
                          % (_span, fmt12(f), fmt12(t), _total, _span, fmt12(f), fmt12(t), _total))
                if len(_charged) != len(_picked):
                    detail += "\nDay off = No AL used · ថ្ងៃឈប់ = មិនដក AL"
                near = _near_days(picked)
                if near:
                    window = t - f
                    pts = round(SHORT_NOTICE_PT_PER_MIN * window * len(near))
                    detail += ("\n⚠ %d short-notice day(s) → −%d points (−0.1/min, pending activation)."
                               "\n⚠ %d ថ្ងៃស្នើជិតពេល → −%d points (−0.1/min, រង់ចាំបើកប្រើ)។"
                               % (len(near), pts, len(near), pts))
                if _armed(context):
                    _arm_pending(context, update,
                        {"flow": "al", "persona_id": p["id"], "kind": "hours",
                         "days": sorted(picked),
                         "hours_start": "%02d:%02d" % (f // 60, f % 60),
                         "hours_end": "%02d:%02d" % (t // 60, t % 60),
                         "_summary": detail})
                    return await show(_al_prompt(p, context, detail, sorted(picked),
                        "%02d:%02d" % (f // 60, f % 60), "%02d:%02d" % (t // 60, t % 60), False))
                return await show(al_stub(p, detail))
        context.user_data["att_al_page"] = 0
        return await show(al_screen(p, picked, 0))
    if action == "do":
        if len(data) > 2 and data[2] == "cov":   # toggle both-days who's-working on the swap prompt
            st = context.user_data.get("att_do_cov") or {}
            flag = bool(int(data[3])) if len(data) > 3 else False
            return await show(_swap_prompt(p, context, st.get("base", ""), st.get("partner_id"),
                                           st.get("req_off"), st.get("partner_off"), flag))
        if len(data) > 2 and data[2] == "d":
            context.user_data["att_do_day"] = data[3]   # remember the chosen new day-off date
            return await show(dayoff_partners(p, data[3]))
        if len(data) > 2 and data[2] == "p":
            if _armed(context):
                req_off = context.user_data.get("att_do_day") or _today().isoformat()
                ro = date.fromisoformat(req_off)
                off_wd = _DOW_NAME.get((p.get("day_off") or "")[:3].title())
                partner_off = (ro + timedelta(days=(off_wd - ro.weekday())) if off_wd is not None
                               else ro + timedelta(days=1)).isoformat()
                _swap_sum = ("Day-off swap — your off %s ↔ partner off %s."
                             % (day_label(ro), day_label(date.fromisoformat(partner_off))))
                _arm_pending(context, update,
                    {"flow": "swap", "persona_id": p["id"], "partner_id": int(data[3]),
                     "req_off_date": req_off, "partner_off_date": partner_off,
                     "_summary": _swap_sum})
                _swap_kh = ("ប្តូរថ្ងៃឈប់ — ប្អូនឈប់ %s ↔ ដៃគូឈប់ %s។"
                            % (day_label(ro), day_label(date.fromisoformat(partner_off))))
                return await show(_swap_prompt(p, context, "%s\n%s" % (_swap_sum, _swap_kh),
                                               int(data[3]), req_off, partner_off, False))
            return await show(al_stub(p, "Day-off swap partner picked. (Partner approval FIRST, "
                                         "then 2 seniors — same week rule.)\n"
                                         "បានជ្រើសអ្នកប្តូរថ្ងៃឈប់ហើយ។ (ត្រូវឱ្យដៃគូយល់ព្រមមុន "
                                         "បន្ទាប់មកបង 2 នាក់ — ត្រូវនៅសប្តាហ៍ដដែល។)", walk="swap"))
        return await show(dayoff_screen(p))
    if action == "walk":
        # att:walk:{name}:{idx} — owner steps through the rest of a ladder to the end
        if len(data) > 2 and data[2] == "noop":
            return  # illustrative preview button — already answered, do nothing
        if len(data) > 3:
            return await show(walk_card(p, data[2], int(data[3])))
        return await show(main_menu(p))
    if action == "ot":          # personal OT bank view (Give OT lives under att:scp:)
        return await show(ot_screen(p))
    if action == "scp":   # session 31: unified Give-OT / shift-redefine picker
        sub = data[2] if len(data) > 2 else ""
        if sub == "staff":
            return await show(sc_staff_pick(p))
        if sub == "d":
            return await show(sc_day_pick(p, int(data[3])))
        if sub == "m":
            return await show(sc_mode(p, int(data[3]), int(data[4])))
        if sub == "cd":
            return await show(sc_dayoff_pick(p, int(data[3]), int(data[4])))
        if sub == "ss":
            return await show(sc_start(p, int(data[3]), int(data[4])))
        if sub == "st":
            return await show(sc_end(p, int(data[3]), int(data[4]), int(data[5])))
        if sub == "cf":
            # att:scp:cf:{sid}:{tdidx}:{start}:{end} → arm a shift-redefine pending → reason → submit
            sid, tdidx, start, end = int(data[3]), int(data[4]), int(data[5]), int(data[6])
            if _armed(context):
                rec = next((r for r in staff_all("active") if r["id"] == sid), None)
                normal_len = (shift_len_min(rec.get("work_start"), rec.get("work_end")) or 0) if rec else 0
                extra = max(0, end - (start + normal_len))
                rnm = (rec or {}).get("call_name") or "the staffer"
                _shift_sum = ("Shift change — %s %s-%s%s for %s."
                              % (day_label(_today() + timedelta(days=tdidx)), fmt12(start),
                                 fmt12(end % 1440), (" (+%dh OT)" % (extra // 60)) if extra else "", rnm))
                _arm_pending(context, update,
                    {"flow": "shift", "persona_id": p["id"], "staff_id": sid,
                     "when_date": (_today() + timedelta(days=tdidx)).isoformat(),
                     "start_min": start, "end_min": end, "normal_len": normal_len,
                     "_summary": _shift_sum})
                return await show(_arm_prompt(p, context,
                    "%s\n\n📝 Type the reason — your next message sends it "
                    "to them for approval.\n📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើទៅពួកគាត់ ដើម្បីសុំការអនុម័ត។"
                    % _shift_sum, "att:scp:staff"))
            return await show(sc_staff_pick(p))
        return await show(sc_staff_pick(p))
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
        if len(data) > 2 and data[2] == "cancel":
            if not att_test_on():
                await query.answer("Role-play shell — turn /testmode on. This never changes real data.",
                                   show_alert=True)
                return await show(my_screen(p))
            iso, rid = data[3], int(data[4])
            from shared.database import al_cancel_day, al_deduct
            today_iso = _today().isoformat()
            # cutoff (window-aware): block past dates, and today's once the shift/window has started
            if iso < today_iso or (iso == today_iso and _shift_running(p)):
                await query.answer("Too late to cancel — that day has already started · "
                                   "យឺតពេលលុបចោលហើយ — ថ្ងៃនោះបានចាប់ផ្តើមហើយ", show_alert=True)
                return await show(my_screen(p))
            # per-date cancel: drop ONLY this day, keep the rest of the request
            remaining, sid = al_cancel_day(rid, iso)
            if remaining >= 0:
                al_deduct(p["id"], -1)   # refund just the one cancelled day
                from gm_bot.bot import _att_send
                nmx = p.get("call_name") or p["canonical_name"]
                dlbl = date.fromisoformat(iso).strftime("%a %d/%m")
                await _att_send(context, None, "Supervisors group", "",
                    "FYI: %s cancelled AL on %s — back to work that day.\n"
                    "FYI: %s បានលុបចោល AL ថ្ងៃ %s — នឹងមកធ្វើការវិញ។" % (nmx, dlbl, nmx, dlbl), group=True)
            return await show(my_screen(p))
        return await show(my_screen(p))
    # att:noop and anything unknown: stay put
