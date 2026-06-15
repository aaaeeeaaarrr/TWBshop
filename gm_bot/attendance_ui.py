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
                             al_leave_days_set, staff_absent_dates, dayoff_override_for)

_DOW = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_DOW_NAME = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
_PP = ZoneInfo("Asia/Phnom_Penh")
SHORT_NOTICE_PT_PER_MIN = 0.1   # owner, session 28: AL days within 7 days cost −0.1 pt/min (ACTIVE since Jun 11)


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


def _decision(working, reason, source_id=None, start_min=None, end_min=None, normal_len=None) -> dict:
    return {"working": working, "reason": reason, "source_id": source_id,
            "start_min": start_min, "end_min": end_min, "normal_len": normal_len}


def _day_context(iso_days: list[str]) -> dict:
    """Batch-fetch everything resolve_day needs for the whole roster across `iso_days`, ONE query each,
    so the per-minute scheduler doesn't fire ~5 queries per staff-day. is_test-scoped. Redefines reuse
    the existing batch `shift_changes_active_map` (latest-wins per staff-date)."""
    import json as _json
    from datetime import date as _d, timedelta as _td
    from shared.database import _db, shift_changes_active_map
    flag = att_test_on()
    want = set(iso_days)
    al: dict = {}
    sick: dict = {}
    special: dict = {}
    overrides: dict = {}
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_id, days FROM al_requests WHERE status='approved' AND is_test=%s",
                        (flag,))
            for r in cur.fetchall():
                try:
                    al.setdefault(r["staff_id"], set()).update(set(_json.loads(r["days"] or "[]")) & want)
                except Exception:
                    pass
            cur.execute("SELECT staff_id, the_date FROM sick_cases WHERE the_date = ANY(%s::date[]) "
                        "AND is_test=%s AND status <> 'cancelled'", (iso_days, flag))
            for r in cur.fetchall():
                sick.setdefault(r["staff_id"], set()).add(str(r["the_date"]))
            cur.execute("SELECT staff_id, start_date, days FROM special_leaves WHERE is_test=%s", (flag,))
            for r in cur.fetchall():
                try:
                    base = _d.fromisoformat(str(r["start_date"]))
                    for i in range(max(int(r["days"] or 1), 1)):
                        iso = (base + _td(days=i)).isoformat()
                        if iso in want:
                            special.setdefault(r["staff_id"], set()).add(iso)
                except Exception:
                    pass
            cur.execute("SELECT staff_id, the_date, kind FROM dayoff_overrides "
                        "WHERE the_date = ANY(%s::date[]) AND is_test=%s", (iso_days, flag))
            for r in cur.fetchall():
                overrides[(r["staff_id"], str(r["the_date"]))] = r["kind"]
    return {"al": al, "sick": sick, "special": special, "overrides": overrides,
            "redefines": shift_changes_active_map(iso_days)}


def resolve_day(p: dict, day_iso: str, ctx: dict | None = None) -> dict:
    """THE single source of truth for "what is this person doing on day_iso" — every reader (attendance
    prompts, no-show sweep, lateness verdict, settle, /audit) must use this ONE resolver so they can't
    drift (see docs/SCHEDULE_RESOLUTION_MODEL.md). Returns {working, reason, source_id, start_min,
    end_min, normal_len}. Pass `ctx` (from `_day_context`) to batch; else it self-fetches. is_test-scoped.

    Precedence (highest first):
      1. approved AL · active sick · special-leave span → AWAY (leave is PROTECTED — beats a redefine;
         a redefine takes an AL day only via the confirmed-revoke path that refunds it, after which the
         AL is no longer 'approved' and step 2 wins legitimately);
      2. senior/auto shift-redefine (latest-wins)       → WORKING at the redefined [start,end] (beats a
         day-off — a "change-day" moves the shift onto a normally-off day);
      3. day-off swap override                          → 'off'=AWAY · 'work'=WORKING (normal times);
      4. weekly day-off                                 → AWAY;  5. normal schedule → WORKING.
    """
    import json as _json
    from datetime import date as _d, timedelta as _td
    sid = p["id"]
    d = _d.fromisoformat(day_iso)
    al_id = sick_id = special_id = None
    if ctx is not None:
        al_hit = day_iso in ctx["al"].get(sid, set())
        sick_hit = day_iso in ctx["sick"].get(sid, set())
        special_hit = day_iso in ctx["special"].get(sid, set())
        rd = ctx["redefines"].get((sid, day_iso))
        sc = {"start_min": rd[0], "end_min": rd[1], "normal_len": None, "id": None} if rd else None
        ov = ctx["overrides"].get((sid, day_iso))
    else:
        from shared.database import _db, shift_change_active
        flag = att_test_on()
        al_hit = sick_hit = special_hit = False
        ov = None
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, days FROM al_requests WHERE staff_id=%s AND status='approved' "
                            "AND is_test=%s", (sid, flag))
                for r in cur.fetchall():
                    try:
                        if day_iso in _json.loads(r["days"] or "[]"):
                            al_hit, al_id = True, r["id"]
                    except Exception:
                        pass
                cur.execute("SELECT id FROM sick_cases WHERE staff_id=%s AND the_date=%s AND is_test=%s "
                            "AND status <> 'cancelled' LIMIT 1", (sid, day_iso, flag))
                r = cur.fetchone()
                if r:
                    sick_hit, sick_id = True, r["id"]
                cur.execute("SELECT id, start_date, days FROM special_leaves WHERE staff_id=%s "
                            "AND is_test=%s", (sid, flag))
                for r in cur.fetchall():
                    try:
                        base = _d.fromisoformat(str(r["start_date"]))
                        if base <= d < base + _td(days=max(int(r["days"] or 1), 1)):
                            special_hit, special_id = True, r["id"]
                    except Exception:
                        pass
                cur.execute("SELECT kind FROM dayoff_overrides WHERE staff_id=%s AND the_date=%s "
                            "AND is_test=%s", (sid, day_iso, flag))
                ovr = cur.fetchone()
                ov = ovr["kind"] if ovr else None
        sc = shift_change_active(sid, day_iso)
    # ── single precedence block (both modes) ──
    if al_hit:
        return _decision(False, "al", al_id)
    if sick_hit:
        return _decision(False, "sick", sick_id)
    if special_hit:
        return _decision(False, "special", special_id)
    if sc:
        return _decision(True, "redefine", sc.get("id"), sc.get("start_min"), sc.get("end_min"),
                         sc.get("normal_len"))
    if ov == "off":
        return _decision(False, "swap_off")
    if ov == "work":
        return _decision(True, "swap_work", None, to_min(p.get("work_start")), to_min(p.get("work_end")))
    if _DOW_NAME.get((p.get("day_off") or "")[:3].title()) == d.weekday():
        return _decision(False, "day_off")
    return _decision(True, "normal", None, to_min(p.get("work_start")), to_min(p.get("work_end")))


def compute_day_events(target: date) -> list[tuple[int, str, str, str, str]]:
    """All would-be check-in messages for one date, whole active TWB roster, chronological.
    Each event is anchored to its SHIFT-START date: it appears on `target` only if the person
    actually worked that shift (start date not their day-off, not on approved AL) — so an
    overnight 6am check-out exists only when YESTERDAY was a working day.
    Returns (minute_of_day, staff_name, label, message_text, shift_start_iso) — the last is the
    date the shift STARTED, which is the attendance_sessions / shift_changes key: an overnight
    checkout fires today but must be written under yesterday's session (bakers are 9pm–6am)."""
    # ONE resolver (resolve_day) decides who's working each day — leave (AL/sick/special) is PROTECTED
    # above a redefine, sick is honoured, and reads are is_test-scoped (docs/SCHEDULE_RESOLUTION_MODEL).
    # A shift's events land on `target` only if its START date is target−1 (overnight tail), target, or
    # target+1 (a pre-midnight T−10). Batch the whole roster's context once for the per-minute scheduler.
    cand_days = [target - timedelta(days=1), target, target + timedelta(days=1)]
    ctx = _day_context([d.isoformat() for d in cand_days])

    events = []
    for p in staff_all("active"):
        if p.get("org") != "TWB" or p.get("canonical_name") == "Tyty":
            continue
        name = p.get("call_name") or p["canonical_name"]
        for shift_start_day in cand_days:
            dec = resolve_day(p, shift_start_day.isoformat(), ctx=ctx)
            if not dec["working"]:
                continue   # away (AL / sick / special / swap-off / day-off) → no shift events
            # a redefine retimes the prompts; normal/swap-work keep the staffer's own times (as before)
            if dec["reason"] == "redefine":
                ws_ov = dec["start_min"]
                len_ov = (dec["end_min"] - dec["start_min"]) % 1440
            else:
                ws_ov = len_ov = None
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
           "មកដល់មុន 5 នាទី ប្អូននឹងទទួលបាន +10 points ⭐")


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
               "មកដល់មុន 5 នាទី ប្អូននឹងទទួលបាន +10 points ⭐\n\n"
               "(then: the 12h-before reminder → the slot runs as a mini-shift)"),
    "pslot": ("→ tapping a 1-hour slot books the partial:",
              "Booked ✓ — Mon 09/06, 7:30pm–8:30pm.\nបានកក់រួច ✓ — Mon 09/06, 7:30pm–8:30pm។\n"
              "Come 5 minutes early and you earn +10 points ⭐\n"
              "មកដល់មុន 5 នាទី ប្អូននឹងទទួលបាន +10 points ⭐\n\n"
              "You still owe 30 min — pick another time anytime.\n"
              "ប្អូននៅត្រូវសង 30 min — អាចជ្រើសពេលបន្ថែមនៅពេលណាក៏បាន។"),
    "appr": ("→ your ✅ counts (1/2) — when the 2nd senior approves:",
             "Approved by Rath and Vannary.\nអនុម័តដោយ Rath និង Vannary។\n\n"
             "(requester gets her ✓ message; Supervisors get the plain notice — steps ③+⑤)"),
    "rej": ("→ your ❌ DECIDES instantly (owner: one rejection is enough):",
            "Your AL for Tue 23/06 → Thu 25/06 wasn't approved.\n"
            "AL របស់ប្អូនសម្រាប់ Tue 23/06 → Thu 25/06 មិនបានអនុម័តទេ។\n\n"
            "(requester only — with WHICH request; your typed reason follows; NOTHING to the group)"),
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
         "“Davy will be ~30 min late for today's shift.\n"
         "Davy នឹងមកយឺតប្រហែល ~30 min សម្រាប់វេនថ្ងៃនេះ។\n"
         "Reason · មូលហេតុ៖ moto broke”",
         None),
        ("② arrival watch — declared time passed, no location yet (repeats 4× every 15 min)",
         "Are you there yet?\nមកដល់ហើយឬនៅ?\n" + _CI_HOWTO, None),
        ("③ they arrive (location) — verdict only; reason already given at declare (silent arrivers asked now)",
         "(check-in verdict = Dry-run 1 steps ④–⑥, already approved. A SILENT arriver who never declared "
         "is asked 'Why were you late?' here instead.)", None),
        ("④ payback slot picker (right after the reason; no AL option — late = time)",
         "You owe 90 min. Pick when to work it off — these are the times we need you most:\n"
         "ប្អូននៅត្រូវសង 90 min។ សូមជ្រើសពេលធ្វើសង — ពេលទាំងនេះហាងត្រូវការប្អូនបំផុត៖",
         _slots_kb()),
        ("⑤ booked confirmation (self-picked or auto) — always encouraging",
         "Booked ✓ — Mon 09/06, 7:30pm–9pm.\nបានកក់រួច ✓ — Mon 09/06, 7:30pm–9pm។\n" + _PLUS10,
         None),
        ("⑥ 12h-before reminder (any booked event)",
         "Reminder — your payback time is tomorrow: 7:30pm–9pm.\n"
         "រំលឹក — ម៉ោងសងវិញរបស់អ្នកគឺថ្ងៃស្អែក៖ 7:30pm–9pm។\n" + _PLUS10 + "\n" + _CI_HOWTO,
         None),
        ("⑦ a booked slot EXTENDS the shift (the redefine engine — no separate machinery)",
         "(booking auto-redefines that day's shift: T−10 fires at the NEW start, lateness is "
         "judged vs the NEW start, and checkout settles the extra minutes straight into the "
         "debt — partial credit automatic. A day-off slot = a window within their own shift "
         "hours; every worked minute credits.)", None),
        ("⑧ partial credit — worked 60 of 90 min",
         "You paid back 60 min ✓ — 30 min stays on your balance.\n"
         "អ្នកបានសង 60 min ✓ — នៅសល់ 30 min ក្នុង balance របស់អ្នក។", None),
        ("⑨ unbooked debt — the daily line at check-in (never hourly)",
         "Checked in ✓ — you still owe 90 min, pick a time:\n"
         "ចុះវត្តមានរួច ✓ — ប្អូននៅត្រូវសង 90 min, សូមជ្រើសពេល៖", _slots_kb()),
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


_DEMO_AL_LABEL = "① the SENIOR's approval card — the REAL card render (tap the 👁 toggle!)"


def _demo_al_card(p: dict, show_cov: bool) -> tuple[str, InlineKeyboardMarkup]:
    """Dry-run 3 ①: rendered by the REAL _al_card builder so body/layout/toggle can NEVER drift
    from what seniors actually receive (owner, Jun 11 — the hand-written preview had drifted:
    no toggle, different formatting). Approve/Not-approve demo their outcomes; the 👁 toggle
    edits in place exactly like the real card."""
    from gm_bot.bot import _al_card
    d1 = _today() + timedelta(days=12)
    req = {"id": 0, "staff_id": p["id"], "days": [(d1 + timedelta(days=i)).isoformat()
                                                  for i in range(3)],
           "hours_start": None, "hours_end": None, "reason": "family trip", "status": "pending"}
    body, _real_kb = _al_card(req, p, audience="senior", sen_id=0, show_cov=show_cov)
    tog = ("🙈 Hide who's working · លាក់អ្នកធ្វើការ" if show_cov
           else "👁 Show who's working · បង្ហាញអ្នកធ្វើការ")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve · អនុម័ត", callback_data="att:drs:appr")],
        [InlineKeyboardButton("❌ Not approve — explain · មិនអនុម័ត — ពន្យល់", callback_data="att:drs:rej")],
        [InlineKeyboardButton(tog, callback_data="att:drs:alcov:%d" % (0 if show_cov else 1))],
    ])
    return body, kb


_DEMO_SW_LABELS = {
    "partner": "① staff requests a swap → the PARTNER is asked FIRST (real card — tap the 👁!)",
    "senior": "④ seniors' approval card (real card, same-week rule) → 2 ✅ apply · ONE ❌ rejects",
}


def _demo_swap_card(p: dict, audience: str, show_cov: bool) -> tuple[str, InlineKeyboardMarkup]:
    """Dry-run 6 swap cards via the REAL _swap_card builder (same no-drift guarantee), with demo
    buttons; the 👁 toggle (BOTH affected days) edits in place like the real one."""
    from gm_bot.bot import _swap_card
    partner = next((r for r in staff_all("active") if r.get("org") == "TWB"
                    and r["id"] != p["id"] and r.get("canonical_name") != "Tyty"), p)
    sw = {"id": 0, "req_off_date": (_today() + timedelta(days=3)).isoformat(),
          "partner_off_date": (_today() + timedelta(days=5)).isoformat(),
          "reason": "clinic",
          "partner_ok": True if audience == "senior" else None,
          "status": "partner_ok" if audience == "senior" else "pending"}
    body, _real_kb = _swap_card(sw, p, partner, audience=audience, show_cov=show_cov)
    tog = ("🙈 Hide who's working · លាក់អ្នកធ្វើការ" if show_cov
           else "👁 Show who's working · បង្ហាញអ្នកធ្វើការ")
    rows = ([[InlineKeyboardButton("✅ I agree · ខ្ញុំយល់ព្រម", callback_data="att:drs:noop")],
             [InlineKeyboardButton("✋ No — explain · ទេ — ពន្យល់", callback_data="att:drs:noop")]]
            if audience == "partner" else
            [[InlineKeyboardButton("✅ Approve · អនុម័ត", callback_data="att:drs:noop")],
             [InlineKeyboardButton("❌ Not approve — explain · មិនអនុម័ត — ពន្យល់", callback_data="att:drs:noop")]])
    rows.append([InlineKeyboardButton(tog, callback_data="att:drs:swcov:%s:%d"
                                      % (audience, 0 if show_cov else 1))])
    return body, InlineKeyboardMarkup(rows)


def build_catalogue3(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 3: ANNUAL LEAVE — request → approval → notice, every variant we now support."""
    al_body, al_kb = _demo_al_card(p, False)
    return [
        (_DEMO_AL_LABEL, al_body, al_kb),
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
        ("⑥ after 2 ✅ (ONE ❌ would reject instantly) — the refreshed recap to all seniors",
         "Approved by Rath and Vannary.\nអនុម័តដោយ Rath និង Vannary។", None),
        ("⑦ to the requester — approved + new balance",
         "Your AL for Tue 23/06 → Thu 25/06 is approved ✓. You have 4.5 AL days left. 🤍\n"
         "AL របស់ប្អូនសម្រាប់ Tue 23/06 → Thu 25/06 បានអនុម័តហើយ ✓។ ប្អូននៅសល់ AL 4.5 ថ្ងៃទៀត 🤍",
         None),
        ("⑧ to the requester — ONE ❌ decides (owner) · says WHICH request · reason follows; nothing to the group",
         "Your AL for Tue 23/06 → Thu 25/06 wasn't approved.\n"
         "AL របស់ប្អូនសម្រាប់ Tue 23/06 → Thu 25/06 មិនបានអនុម័តទេ។", None),
        ("⑨ SUPERVISORS notice — FULL-DAY (ENGLISH-only, owner Jun 11; locked format)",
         "Meng on leave: Tue 23/06 → Thu 25/06.\n"
         "Reason: family trip\n"
         "Normal day off: Friday\n"
         "Back at work: Sat 27/06, 9pm.", None),
        ("⑩ SUPERVISORS notice — HOURS-AL (ENGLISH-only; shows the window + same-day return)",
         "Meng on leave: Tue 23/06 → Thu 25/06 (9pm–12am each day).\n"
         "Reason: family trip\n"
         "Normal day off: Friday\n"
         "Back at work: 12am each of those days (rest of shift as normal).", None),
        ("⑪ cancelling an AL — refund confirmation",
         "Your AL for Tue 23/06 is cancelled ✓ — 1 day(s) returned.\n"
         "AL របស់អ្នកសម្រាប់ Tue 23/06 ត្រូវបានលុបចោលហើយ ✓ — 1 ថ្ងៃបានត្រឡប់ចូលវិញ។", None),
    ]


def build_catalogue4(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 4: SICK — own-sick anti-fake ladder, papers, part-duty, family-sick. Full."""
    cant_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💪 I can come · ខ្ញុំអាចមក", callback_data="att:drs:noop")],
        [InlineKeyboardButton("🛌 Rest today · សម្រាកថ្ងៃនេះ", callback_data="att:drs:noop")]])
    return [
        ("① Sick → Me: the anti-fake opener (try to come, see how you feel)",
         "Sorry to hear 😟 Take some medicine and come try — see how you feel at work. "
         "What time can you come?\n"
         "សោកស្តាយណាស់ 😟 សូមលេបថ្នាំ ហើយមកសាកធ្វើការមើល។ អ្នកអាចមកម៉ោងប៉ុន្មាន?",
         _ill(["9:30pm", "10pm", "10:30pm"], ["📝 Really can't — explain · មិនអាចមក — ពន្យល់"])),
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
         "Saved ✓ — your sick day is confirmed. Get well 🤍\n"
         "រក្សាទុករួច ✓ — ថ្ងៃឈឺរបស់អ្នកបានបញ្ជាក់ហើយ។ សូមឱ្យឆាប់ជាសះស្បើយ 🤍", None),
        ("⑥ owner offers PART-DUTY → staff invited back for light work (+15 ⭐, no pressure)",
         "Feeling a little better? If you're up to it, there's light work today (+15 points ⭐) — "
         "only if you truly feel able 🤍\n"
         "ធូរស្បើយបន្តិចហើយឬនៅ? បើអ្នកមានកម្លាំង អាចមកធ្វើការងារស្រាលៗថ្ងៃនេះបាន (+15 points ⭐) — "
         "តែបើអ្នកពិតជាអាចធ្វើបានប៉ុណ្ណោះ 🤍", cant_kb),
        ("⑦ came on light duty → the Supervisors-group memo + the staff welcome",
         "[→ Supervisors group] Davy is coming on LIGHT DUTY today — please give easy/seated work only.\n"
         "Davy នឹងមកធ្វើ LIGHT DUTY ថ្ងៃនេះ — សូមឱ្យធ្វើតែការងារងាយៗ/អង្គុយប៉ុណ្ណោះ។\n\n"
         "[→ Davy] Thank you for coming in 🤍 light duty only — a senior will point you to seated/easy work.\n"
         "អរគុណដែលមកជួយ 🤍 ធ្វើតែការងារស្រាលៗប៉ុណ្ណោះ — បងៗនឹងណែនាំការងារអង្គុយ ឬការងារងាយៗឱ្យអ្នក។", None),
        ("⑧ chose to rest instead",
         "Rest well 🤍 get better.\nសម្រាកឱ្យបានល្អ 🤍 ឆាប់ជាសះស្បើយ។", None),
        ("⑨ each night while out → return check (never papers/pay-back); the answer goes to Supervisors",
         "I hope you're feeling better now 🤍 Are you coming in tomorrow?\n"
         "សង្ឃឹមថាប្អូនធូរស្បើយហើយ 🤍 ស្អែកប្អូនមកធ្វើការមែនទេ?",
         _ill(["✅ Coming in tomorrow · ស្អែកមកធ្វើការ"],
              ["📝 Still resting — explain · សម្រាកបន្ត — ពន្យល់"],
              ["⏰ Coming in today at… · ថ្ងៃនេះមកម៉ោង…"])),   # = the real buttons, bilingual
        ("⑩ FAMILY-sick day → SUPERVISORS GROUP informed (no approval gate; burns 1 of 7 yearly days). "
         "No night nudge — a family-sick entry is one day/window; to add another the staffer re-requests.",
         "FYI: Kimying takes sick leave for their child today.\n"
         "FYI: Kimying សុំច្បាប់ឈឺសម្រាប់កូនថ្ងៃនេះ។", None),
        ("⑪ [→ OWNER] paperless-sick FREQUENCY dossier (pattern, not a single day)",
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
        ("② marriage approved → the AL engine's confirmation (marriage rides the AL approval flow)",
         "Your AL for Mon 14/07 → Wed 16/07 is approved ✓. You have 4.5 AL days left. 🤍\n"
         "AL របស់ប្អូនសម្រាប់ Mon 14/07 → Wed 16/07 បានអនុម័តហើយ ✓។ ប្អូននៅសល់ AL 4.5 ថ្ងៃទៀត 🤍", None),
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
        ("⑨ a death-context PHOTO (within a week of the leave) → condolence only, NO AI, "
         "forwarded to owner+Tyty alone (photos welcome — never discouraged)",
         "We're so sorry for your loss 🤍\n"
         "យើងសូមចូលរួមរំលែកទុក្ខចំពោះការបាត់បង់នេះ 🤍", None),
        ("⑩ WIFE giving birth (2 days) + the Supervisors notice",
         "Congratulations! 👶 2 days of leave, Tue 09/06 → Wed 10/06.\n"
         "អបអរសាទរ! 👶 សម្រាក 2 ថ្ងៃ, Tue 09/06 → Wed 10/06។\n\n"
         "[→ SUPERVISORS] Davy on leave Tue 09/06 → Wed 10/06 (wife giving birth).\n"
         "Davy ឈប់សម្រាក Tue 09/06 → Wed 10/06 (ប្រពន្ធសម្រាលកូន)។", None),
    ]


def build_catalogue7(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 6 (swap): partner asked FIRST, then 2 seniors, same-week rule. The partner and
    senior cards render via the REAL _swap_card builder (no drift, real 👁 toggle)."""
    pa_body, pa_kb = _demo_swap_card(p, "partner", False)
    return [
        (_DEMO_SW_LABELS["partner"], pa_body, pa_kb),
        ("② partner agrees → goes to the seniors",
         "✅ You agreed — sent to seniors.\n"
         "✅ ប្អូនបានយល់ព្រមហើយ — បានផ្ញើទៅបងៗ។", None),
        ("③ partner declines OR stays silent → swap doesn't happen, seniors never bothered",
         "Your day-off swap (Wed 10/06 ↔ Fri 12/06) wasn't accepted by your partner.\n"
         "អ្នកដែលត្រូវប្តូរជាមួយ មិនបានយល់ព្រមលើការប្តូរថ្ងៃឈប់ (Wed 10/06 ↔ Fri 12/06) របស់ប្អូនទេ។",
         None),
        (_DEMO_SW_LABELS["senior"],) + _demo_swap_card(p, "senior", False),
        ("⑤ approved → SUPERVISORS notice",
         "Day-off swap: Davy off Fri 12/06, Mealea off Wed 10/06.\n"
         "ប្តូរថ្ងៃឈប់៖ Davy ឈប់ Fri 12/06, Mealea ឈប់ Wed 10/06។", None),
        ("⑥ approved → to the requester",
         "Your day-off swap is approved ✓\nការប្តូរថ្ងៃឈប់របស់អ្នកបានអនុម័តហើយ ✓", None),
        ("⑦ ONE senior ❌ rejects (owner) → to the requester + partner, with the dates",
         "The day-off swap (Wed 10/06 ↔ Fri 12/06) wasn't approved.\n"
         "ការប្តូរថ្ងៃឈប់ (Wed 10/06 ↔ Fri 12/06) មិនបានអនុម័តទេ។", None),
    ]


def build_catalogue8(p: dict) -> list[tuple[str, str, InlineKeyboardMarkup | None]]:
    """Dry-run 8: CROSS-CUTTING — acks, group redirect, autonomous call-outs, welcome."""
    return [
        ("① ⚠ PLANNED (not built yet) — 👍 ACK for normal (non-problem) replies",
         "Got it 👍 thank you.\nបានហើយ 👍 អរគុណ។\n(a reply that IS a problem gets a real answer, never a 👍)",
         None),
        ("② GROUP REDIRECT — the GM REPLIES to their message IN THE GROUP, tagging them by uid "
         "(never typing a name → no misspelling risk)",
         "[replying to Davy's message in the Supervisors group]\n"
         "@Davy — AL, sick and days off only count when you tell me directly. Open @twb_gm_bot, "
         "or it won't be recorded 🙂\n"
         "@Davy — AL, ឈឺ និងថ្ងៃឈប់ នឹងរាប់បានតែពេលប្អូនប្រាប់ខ្ញុំផ្ទាល់។ សូមបើក @twb_gm_bot "
         "បើមិនដូច្នេះ វានឹងមិនត្រូវបានកត់ត្រាទេ 🙂\n"
         "(one of 5 rotating wordings · once per person per 30 min)", None),
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
    """Today's who/when — grouped by SHIFT PATTERN, one block per group (owner, Jun 11: the
    per-minute listing was 'too long and messy'). OWNER-ONLY preview (Dry-run 1's last step) —
    in live operation each staffer receives only their own few lines, at their own times."""
    from collections import defaultdict
    ev = compute_day_events(target)
    per: dict = defaultdict(list)          # name → [(minute, kind)]
    for minute, name, label, _text, _sd in ev:
        per[name].append((minute, label.split(" ")[0]))
    groups: dict = defaultdict(list)       # identical event-pattern → [names]
    for name, evs in per.items():
        groups[tuple(sorted(evs))].append(name)
    lines = ["📅 Today's plan (%s) — %d sends · %d staff · %d shift groups."
             % (day_label(target), len(ev), len(per), len(groups)),
             "(Owner-only preview. Each staffer gets ONLY their own lines, at these times.)"]
    for evs, names in sorted(groups.items(), key=lambda kv: kv[0][0][0]):
        names.sort()
        shown = ", ".join(names[:6]) + ((" +%d more" % (len(names) - 6)) if len(names) > 6 else "")
        lines.append("")
        lines.append("👥 %s" % shown)
        lines.append("   " + " · ".join("%s %s" % (k, fmt12(m)) for m, k in evs))
    return "\n".join(lines)


async def _dryrun_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # legacy shim — old messages' buttons (pre-stateless) land here after any restart
    await context.bot.send_message(update.effective_chat.id,
        "⚠ The bot was updated since this dry-run started — its place was lost. "
        "Open /test and tap the dry-run again (new runs survive updates).")


_DR_INTROS = {
    "go":  "🧪 Dry-run 1 — CHECK-IN, every message + today's who/when. %d steps:",
    "go2": "🧪 Dry-run 2 — LATE + PAYBACK lifecycle. %d steps:",
    "go3": "🧪 Dry-run 3 — ANNUAL LEAVE, every variant. %d steps:",
    "go4": "🧪 Dry-run 4 — SICK (anti-fake ladder, papers, part-duty, family). %d steps:",
    "go5": "🧪 Dry-run 5 — MARRIAGE · FAMILY DEATH · WIFE BIRTH. %d steps:",
    "go7": "🧪 Dry-run 6 — DAY-OFF SWAP (partner first, then seniors). %d steps:",
    "go8": "🧪 Dry-run 7 — ACKS · GROUP REDIRECT · CALL-OUTS · WELCOME. %d steps:",
}


def _dr_sample(context) -> dict | None:
    return _persona(context) or next(
        (r for r in staff_all("active") if to_min(r.get("work_start")) is not None
         and r.get("org") == "TWB" and r.get("canonical_name") != "Tyty"), None)


def _dr_events(key: str, sample: dict):
    """Build a dry-run's steps FRESH on every tap — STATELESS by design: the step number rides
    in the button (att:dr:n:{key}:{i}), so a bot restart/deploy mid-walkthrough can never lose
    the owner's place again (Jun 11: deploys wiped user_data → 'stopped at random steps' and
    dead buttons)."""
    if key == "go":
        return build_catalogue(sample) + [("📅 schedule summary", schedule_summary(_today()), None)]
    return {"go2": build_catalogue2, "go3": build_catalogue3, "go4": build_catalogue4,
            "go5": build_catalogue5, "go6": build_catalogue7, "go7": build_catalogue7,
            "go8": build_catalogue8}.get(key, build_catalogue8)(sample)


async def _dryrun_send(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       key: str, i: int) -> None:
    sample = _dr_sample(context)
    if sample is None:
        return
    events = _dr_events(key, sample)
    chat_id = update.effective_chat.id
    if i >= len(events):
        await context.bot.send_message(chat_id, "✅ Dry-run finished — %d possibilities walked."
                                       % len(events))
        return
    label, text, kb = events[i]
    # Buttons: att:drs:* DEMO their consequence — suffixed :{key}:{i} so even the demos are
    # restart-proof; anything else becomes Next (a dry-run can never trigger live actions).
    nxt = "att:dr:n:%s:%d" % (key, i + 1)
    rows = []
    if kb:
        for r in kb.inline_keyboard:
            rows.append([InlineKeyboardButton(b.text, callback_data="%s:%s:%d"
                                              % (b.callback_data, key, i))
                         if (b.callback_data or "").startswith("att:drs:")
                         else InlineKeyboardButton(b.text, callback_data=nxt) for b in r])
    if i + 1 < len(events):
        rows.append([InlineKeyboardButton("Next ▶ (%d/%d)" % (i + 2, len(events)),
                                          callback_data=nxt)])
    # real-builder card bodies carry HTML (<b> dates) — render them as the staff would see them
    await context.bot.send_message(chat_id, "🧪 %s\n────────────\n%s" % (label, text),
                                   reply_markup=InlineKeyboardMarkup(rows) if rows else None,
                                   parse_mode="HTML" if "<b>" in text else None)


# ---------------------------------------------------------------- shell state

def _persona(context) -> dict | None:
    sid = context.user_data.get("att_persona")
    if sid is None:
        return None
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    if rec is None:
        return None
    rec = dict(rec)
    if att_test_on():
        # test mode never mutates the real al_left column → overlay the simulated test deductions so the
        # schedule view + over-balance gates match the approval messages during a walk (display only).
        try:
            from shared.database import al_effective_left
            rec["al_left"] = al_effective_left(rec["id"])
        except Exception:
            pass
    if context.user_data.get("att_live_self"):
        rec["_live"] = True   # a real staffer driving their own menu (not the owner shell)
    return rec


def _is_live(context) -> bool:
    """True when a real staffer is driving their OWN menu (live), not the owner role-play shell."""
    return bool(context.user_data.get("att_live_self"))


def _armed(context) -> bool:
    """A terminal fires the REAL submit_* when the owner is in test mode OR a live staffer is
    driving. Otherwise (test off, owner just browsing) terminals show a read-only preview stub."""
    return att_test_on() or _is_live(context)


def _supersede_prev_pend(context, update) -> None:
    """Prompt-supersession honesty (multi-menu fix, piece 2). There is ONE typed-text pend slot per
    uid, so arming a NEW reason prompt silently OVERWRITES an older armed one — and whatever the
    staffer then types lands in the new flow even though the old prompt still looks alive (the
    cross-wiring today-bug: an AL excuse recorded as a swap-decline reason). Before the overwrite,
    edit the OLD prompt in place so it says it was replaced — no typed reason can vanish into the
    wrong flow invisibly. Best-effort (fire-and-forget); the dead-tap guard backs it up. Mode-agnostic:
    reads whichever slot holds the old pend (user_data in owner-test, flow_state when live)."""
    try:
        uid = update.effective_user.id
        old = context.user_data.get("att_test_pending")
        if not old:
            from shared.database import flow_load
            fs = flow_load(uid)
            old = (fs.get("data") or {}) if fs and fs.get("flow") == "att_pending" else None
        if not old:
            return
        pc, pm = old.get("_prompt_chat"), old.get("_prompt_msg")
        if not (pc and pm):
            return
        # never relabel the very message we are about to re-arm onto (same-message re-entry)
        q = getattr(update, "callback_query", None)
        msg = getattr(q, "message", None) if q is not None else None
        cur_id = getattr(msg, "message_id", None) if msg is not None else None
        if cur_id is not None and cur_id == pm:
            return
        app = getattr(context, "application", None)
        if app is None:
            return

        async def _edit():
            try:
                await context.bot.edit_message_text(
                    "↩ Replaced — answer the newer prompt below\n"
                    "↩ បានជំនួសហើយ — សូមឆ្លើយសំណួរថ្មីខាងក្រោម",
                    chat_id=pc, message_id=pm)
            except Exception:
                pass

        app.create_task(_edit())
    except Exception:
        pass


def _arm_pending(context, update, pend: dict) -> None:
    """Stash the pending reason/'go' for the next typed message. Owner test → user_data (ephemeral);
    live staffer → flow_state (DB, restart-safe), per docs/ATTENDANCE_TEST_MODE.md item 8.
    Also captures the reason-PROMPT message coords so the dispatcher can edit it in place into an
    'awaiting approval' card once the reason is typed (only when the flow set pend['_summary'])."""
    _supersede_prev_pend(context, update)   # honesty: relabel any prompt this one overwrites
    _menu_release(context)   # P1: this menu just became a prompt — don't let the singleton collapse it
    uid = update.effective_user.id
    q = getattr(update, "callback_query", None)
    msg = getattr(q, "message", None) if q is not None else None
    if msg is not None:
        chat_id = getattr(msg, "chat_id", None)
        msg_id = getattr(msg, "message_id", None)
        if chat_id is not None and msg_id is not None:
            pend["_prompt_chat"] = chat_id
            pend["_prompt_msg"] = msg_id
    # sick_me rides the bounded 10/20/30 reason ladder (owner, Jun 11) — armed_at + a 35-min
    # window so the nudge job can finish before expiry; other flows keep the 15-min default.
    if pend.get("flow") == "sick_me":
        from gm_bot.finance import PP_TZ
        pend.setdefault("armed_at", datetime.now(PP_TZ).isoformat())
        pend.setdefault("nudges", 0)
        ttl = 35
    else:
        ttl = 30   # owner Jun 13: lifted 15→30 so busy hands rarely hit expiry (F3)
    # A2/A3 (Fable): tag this pend with a per-user monotonic nonce so a tap-confirm card carries the
    # identity of the flow it was built for — a stale/superseded card (different nonce) can't submit
    # the current pend, and a double-tap (no pend) is recognised. _confirm_prompt reads att_go_nonce.
    _seq = int(context.user_data.get("att_go_seq", 0)) + 1
    context.user_data["att_go_seq"] = _seq
    pend["_go_nonce"] = str(_seq)
    context.user_data["att_go_nonce"] = str(_seq)
    if att_test_on():
        context.user_data["att_test_pending"] = pend
    else:
        flow_save(uid, "att_pending", "reason", pend, ttl_min=ttl)


def _arm_prompt(p: dict, context, base: str, back: str, extra_rows=None):
    """Unified prompt for an armed terminal. Neutral copy works for BOTH live (routes to the real
    seniors/Supervisors) and test; test adds an owner coaching suffix. (KH pending for new lines.)
    `extra_rows`: button rows placed ABOVE the back row (e.g. a Show-who's-working toggle)."""
    line = base
    if att_test_on():
        line += "\n🧪 (test — every reply/card routes to you; /testreset to wipe when done.)"
    rows = list(extra_rows or [])
    rows.append(_cancel_row())   # armed prompt → Cancel disarms; a plain Back would leave a ghost pend
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
    _nonce = context.user_data.get("att_go_nonce", "")   # A2/A3: ties this card to its pend
    return _hdr(p, line), InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I confirm · ខ្ញុំបញ្ជាក់", callback_data="att:go:%s" % _nonce)],
        _cancel_row(),   # armed confirm → Cancel disarms (a plain Back would leave a ghost pend)
    ])


def _hdr(p: dict, line: str = "") -> str:
    if p.get("_live"):
        head = "👤 %s" % (p.get("call_name") or p["canonical_name"])
    else:
        head = "🧪 TEST — acting as %s (%s)" % (p["canonical_name"], p.get("call_name") or "-")
    return head + ("\n\n" + line if line else "")


def _back_row(target: str = "att:menu") -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton("← Back · ត្រឡប់ក្រោយ", callback_data=target)]


def _cancel_row() -> list[InlineKeyboardButton]:
    """Armed prompts use this INSTEAD of a plain Back (multi-menu fix F5/Law 6): a harmless Back on a
    reason prompt leaves the pend armed, so a later stray message becomes a ghost submission. Cancel
    DISARMS the pend, then returns to a clean menu — the only safe exit from an armed input state."""
    return [InlineKeyboardButton("✕ Cancel · បោះបង់", callback_data="att:cancel")]


def _stale_screen(p: dict):
    """Law 1c (F4/F10): a button on an OLD screen whose selection stash was reset (new menu opened, or
    a restart) must read empty and ask to start again — never act on wrong/empty data or crash."""
    return (_hdr(p, "⏳ This screen is old — please open the menu to start again.\n"
                    "⏳ ផ្ទាំងនេះចាស់ហើយ — សូមបើក menu ដើម្បីចាប់ផ្តើមម្តងទៀត។"),
            InlineKeyboardMarkup([[InlineKeyboardButton("📋 Open menu · បើក menu",
                                                        callback_data="att:menu")]]))


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
    from shared.database import payback_open_debt, ot_pending_extension_min
    rows = [_back_row()]
    try:
        debt = payback_open_debt(p["id"])
        debt_min = debt["balance"] if debt else 0
        pending_ext = ot_pending_extension_min(p["id"], _today().isoformat())
        remaining = max(0, debt_min - max(0, pending_ext))
    except Exception:
        remaining = 0
    if remaining > 0:
        rows.append([InlineKeyboardButton("📅 Book pay-back time · កក់ម៉ោងសងវិញ",
                                          callback_data="att:pb:offer")])
    rows += [
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
    rows.append([InlineKeyboardButton("📝 Really can't — explain · មិនអាចមក — ពន្យល់",
                                      callback_data="att:sp:mecant")])   # typed reason → Supervisors
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
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menunew")]])


def sick_me_cant(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    txt = _hdr(p,
               "OK — rest well 🤍 If you see a doctor, send me a photo of the papers.\n"
               "បានហើយ — សម្រាកឱ្យបានល្អ 🤍 បើអ្នកបានទៅជួបពេទ្យ សូមផ្ញើរូបថតឯកសារពេទ្យមកខ្ញុំ។\n\n"
               "(Provisional: the missed shift becomes pay-back time unless papers arrive within 3 days.\n"
               "Papers → real sick day: no pay-back, no points, AL untouched.)")
    return txt, InlineKeyboardMarkup([_back_row("att:sp:me"), _walk_btn("sickme"),
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menunew")]])


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
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menunew")]])


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
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menunew")]])


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
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menunew")]])


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
                              [InlineKeyboardButton("🏠 Main menu", callback_data="att:menunew")]])


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
             "“បានកក់រួច ✓ — មកដល់មុន 5 នាទី ប្អូននឹងទទួលបាន +10 points ⭐”" % nm, None),
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
             _ill(["✅ Approve · អនុម័ត", "❌ Not approve — explain · មិនអនុម័ត — ពន្យល់"])),
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
             % (nm, nm), _ill(["✅ I agree · ខ្ញុំយល់ព្រម", "✋ No — explain · ទេ — ពន្យល់"])),
            ("[→ %s] “You agreed — sending to seniors.”  (partner silence/❌ = swap doesn't happen, "
             "%s told, seniors never bothered.)" % (nm, nm), None),
            ("[→ EVERY senior] approval card (same week rule) → 2 ✅ applies dated overrides.",
             _ill(["✅ Approve · អនុម័ត", "❌ Not approve — explain · មិនអនុម័ត — ពន្យល់"])),
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
        rows.append([InlineKeyboardButton("🏠 Main menu — flow complete ✓", callback_data="att:menunew")])
    return _hdr(p, "Step %d of %d — the flow continues:\n\n%s" % (idx + 1, n, text)), \
        InlineKeyboardMarkup(rows)


def about_work_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    # Rules for everyone; Give OT seniors only; later: Stocks + other checks (owner)
    rows = [
        _back_row(),
        [InlineKeyboardButton("📜 Rules · ច្បាប់ហាង", callback_data="att:rules")],
    ]
    if p.get("is_senior"):
        rows.append([InlineKeyboardButton("🗓 Staff Changes (1 time) · ប្តូរកាលវិភាគ (1 ដង)",
                                          callback_data="att:sc1")])
        rows.append([InlineKeyboardButton("🗓 Staff Changes (forever) · ប្តូរកាលវិភាគ (រហូត)",
                                          callback_data="att:scfv")])
    return _hdr(p, "🧰 About Work"), InlineKeyboardMarkup(rows)


def staff_changes_menu(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Senior 'Staff Changes (1 time)' (owner, Jun 15) → A1 Change time +OT, or A2 Change day off (move).
    Replaces the old mixed 'Give OT / change shift'. → docs/SCHEDULE_CHANGES_REDESIGN.md."""
    rows = [
        _back_row("att:aw"),
        [InlineKeyboardButton("⏱ Change time +OT · ប្តូរម៉ោង +OT", callback_data="att:scp:staff")],
        [InlineKeyboardButton("📅 Change day off · ប្តូរថ្ងៃឈប់", callback_data="att:sc2")],
    ]
    return _hdr(p, "🗓 Staff Changes (1 time) — pick one.\n"
                   "ប្តូរកាលវិភាគ (1 ដង) — ជ្រើសមួយ។"), InlineKeyboardMarkup(rows)


def _coming_soon(p: dict, what: str, back: str) -> tuple[str, InlineKeyboardMarkup]:
    return _hdr(p, "🚧 %s — coming next.\n🚧 %s — នឹងមានពេលក្រោយ។" % (what, what)), \
        InlineKeyboardMarkup([_back_row(back)])


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
                                      [InlineKeyboardButton("🏠 Main menu", callback_data="att:menunew")]])


AL_TODAY_GATE_MIN = 30   # the gate arms this many minutes BEFORE shift start (owner, Jun 11)


def al_today_allowed(p: dict) -> bool:
    """OWNER RULE (Jun 11): from 30 min BEFORE shift start onward, same-day AL exists only if
    they CHECKED IN (early or late) — otherwise the today button isn't even shown. Why: without
    it, a no-show launders itself into an innocent AL day (dodging the 1-day-pay no-show
    penalty), and an oversleeper dodges the late ladder by tapping 'AL from now' from bed.
    Earlier than start−30, today is requestable as normal (short-notice costs apply)."""
    ws = to_min(p.get("work_start"))
    if ws is None:
        return True
    if _now_min() < ws - AL_TODAY_GATE_MIN:     # well before today's shift
        return True
    from shared.database import att_get_session
    sess = att_get_session(p["id"], _today().isoformat()) or {}
    return bool(sess.get("checked_in_at"))


def _al_charged_with_coexist(p: dict, picked, doff, nw) -> list[str]:
    """The days an AL request actually CHARGES, for the picker preview: the normal charged set PLUS any
    A2 comp-work day — a day-off weekday a move turned into a real work day (8b). Makes the picker's
    count + 'Day off = No AL used' line match the real deduction (which already adds these back). Falls
    back to the plain charged set if the lookup can't run."""
    from gm_bot import al as alm
    charged = set(alm.al_charged_days(picked, doff, nw))
    try:
        from shared.database import al_coexist_days
        charged |= al_coexist_days(p["id"], list(picked))
    except Exception:
        pass
    return sorted(charged)


def _al_over_balance(p: dict, amount: float) -> str | None:
    """The owner's EARLY gate (Jun 11): not-enough-AL fires right after the day/time pick —
    BEFORE the reason prompt (the dispatch check stays as the final net). Plain-AL flows only;
    special leaves (marriage/death/birth) may go negative by design and never come through here."""
    bal = p.get("al_left")
    if bal is None or float(amount) <= float(bal):
        return None
    return ("⚠ You only have %g AL day(s) left, but this request needs %g.\n"
            "Please choose a smaller amount — you can request up to %g.\n"
            "⚠ ប្អូននៅសល់ AL តែ %g ថ្ងៃប៉ុណ្ណោះ ប៉ុន្តែសំណើនេះត្រូវប្រើ %g ថ្ងៃ។\n"
            "សូមជ្រើសចំនួនតិចជាងនេះ — ប្អូនអាចស្នើបានច្រើនបំផុត %g ថ្ងៃ។"
            % (float(bal), float(amount), float(bal),
               float(bal), float(amount), float(bal)))


def al_screen(p: dict, picked: set[str], page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    al_left = p.get("al_left")
    start = _today() + timedelta(days=page * 28)
    days = [start + timedelta(days=i) for i in range(28)]
    near_cut = _today() + timedelta(days=6)
    today_iso = _today().isoformat()
    # 8b-1 (owner, Jun 16): only offer days she ACTUALLY WORKS — hide her real day-offs, swapped-away days,
    # and days she already has leave. Kills the pointless "0 AL on an off-day". Batched (one _day_context).
    try:
        ctx = _day_context([d.isoformat() for d in days])
    except Exception:
        ctx = None
    btns = []
    for d in days:
        iso = d.isoformat()
        if iso == today_iso and not al_today_allowed(p):
            continue                     # shift started, never checked in → no AL-today button
        try:
            if not resolve_day(p, iso, ctx).get("working"):
                continue                 # she's away/off that day → not an AL day (fail-open on error)
        except Exception:
            pass
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
    rows.append([InlineKeyboardButton("🏠 Main menu", callback_data="att:menunew")])
    return _hdr(p, detail), InlineKeyboardMarkup(rows)


# Emergency AL was REMOVED by the owner (session 28) — weird emergencies go via points (TBD).
# The old emergency_screen/emergency_dates + att:em branch were unreachable dead code, deleted
# session 30. (Short-notice AL — _near_days / SHORT_NOTICE_PT_PER_MIN — is a SEPARATE thing, kept.)


def _real_dayoff_dates(staff: dict, start: date, n_days: int = 21) -> list:
    """WF5/WF9b: a staff's REAL upcoming day-off occurrences — their weekly day-off weekday, MINUS
    any date that already carries a dayoff_override (a date already involved in a swap is not free to
    trade again). Honours overrides instead of trusting the static weekday blindly."""
    from gm_bot import payback as pb
    dates = pb.dayoff_dates_ahead(staff.get("day_off"), set(), start, n_days)
    return [d for d in dates if dayoff_override_for(staff["id"], d.isoformat()) is None]


def dayoff_partners(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    """WF5 partner-swap ENTRY — pick WHO to trade day-offs with FIRST (no arbitrary day). Candidates =
    active TWB staff with a DIFFERENT day off (something to trade) and similar shift hours."""
    ws = to_min(p.get("work_start"))
    my_off = (p.get("day_off") or "")[:3].title()
    cands = []
    for r in staff_all("active"):
        if r["id"] == p["id"] or r.get("org") != "TWB" or r.get("canonical_name") == "Tyty":
            continue
        if (r.get("day_off") or "")[:3].title() == my_off:
            continue   # same day off → nothing to trade
        rs = to_min(r.get("work_start"))
        if rs is None or ws is None:
            continue
        diff = min((rs - ws) % (24 * 60), (ws - rs) % (24 * 60))
        if diff <= 180:  # starts within 3h of each other = "similar/close shift times"
            cands.append(r)
    rows = [_back_row("att:am")]
    rows += [[InlineKeyboardButton(staff_btn_label(c), callback_data="att:do:p:%d" % c["id"])]
             for c in staff_sort(cands)[:8]]
    return _hdr(p, "Swap day off — pick WHO to trade with (a different day off, similar shift times). "
                   "You'll then choose a date-pairing.\n"
                   "ប្តូរថ្ងៃឈប់ — ជ្រើសអ្នកដែលប្អូនចង់ប្តូរជាមួយ (ថ្ងៃឈប់ខុសគ្នា, ម៉ោងវេនប្រហាក់ប្រហែល)។ "
                   "បន្ទាប់មក ប្អូននឹងជ្រើសគូថ្ងៃ។\n"
                   "Your day off · ថ្ងៃឈប់របស់ប្អូន៖ %s" % (p.get("day_off") or "?")), \
        InlineKeyboardMarkup(rows)


def dayoff_swap_pairs(p: dict, partner_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """WF5: the valid day-off swap pairings with the chosen partner. A pairing = (your real upcoming
    day off, their real upcoming day off) ≤ 6 days apart — a TRUE trade (you take their day off, they
    take yours), coverage-neutral by construction. Callback encodes the engine's two dates directly:
    att:do:pair:{partner}:{req_off=their date you take}:{partner_off=your date they take}."""
    from gm_bot import payback as pb
    partner = next((s for s in staff_all("active") if s["id"] == partner_id), None)
    if not partner:
        return _hdr(p, "That partner isn't available — pick again."), \
            InlineKeyboardMarkup([_back_row("att:do")])
    pn = partner.get("call_name") or partner["canonical_name"]
    start = _today() + timedelta(days=1)
    my_dates = _real_dayoff_dates(p, start)          # r = your day off (partner ends up off here)
    par_dates = _real_dayoff_dates(partner, start)   # q = their day off (you end up off here)
    pairs = pb.swap_pairings(my_dates, par_dates, max_gap=6, cap=6)
    rows = [_back_row("att:do")]
    for r, q in pairs:
        # you take THEIR day off q (you off q) · they take YOURS r (they off r)
        lbl = "🔁 you off %s · %s off %s" % (day_label(q), pn, day_label(r))
        rows.append([InlineKeyboardButton(
            lbl, callback_data="att:do:pair:%d:%s:%s" % (partner_id, q.isoformat(), r.isoformat()))])
    if not pairs:
        return _hdr(p, "No close day-off pairing with %s in the next 3 weeks (need ≤6 days apart, a "
                       "different day off, and neither date already swapped).\n"
                       "គ្មានគូថ្ងៃឈប់ជិតគ្នាជាមួយ %s ក្នុង 3 សប្តាហ៍ខាងមុខទេ។" % (pn, pn)), \
            InlineKeyboardMarkup([_back_row("att:do")])
    return _hdr(p, "Swap with %s — pick a pairing. You take their day off, they take yours "
                   "(≤ 6 days apart, coverage stays even).\n"
                   "ប្តូរជាមួយ %s — ជ្រើសគូថ្ងៃមួយ។ ប្អូនយកថ្ងៃឈប់របស់គាត់ គាត់យកថ្ងៃឈប់របស់ប្អូន "
                   "(ខុសគ្នាមិនលើស 6 ថ្ងៃ)។" % (pn, pn)), InlineKeyboardMarkup(rows)


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


def _sc_reason_prompt(p: dict, context, sid: int, tdidx: int, start: int, end: int,
                      shift_sum: str, show_cov: bool):
    """The senior's reason prompt for a shift redefine, with the 👁 who's-working toggle (owner,
    Jun 11: both parties must see who covers the NEW times — it helps them decide). Coverage is
    computed live for the redefined window on that date."""
    line = shift_sum
    if show_cov:
        try:
            from gm_bot.bot import _sc_coverage_lines
            rec = next((r for r in staff_all("active") if r["id"] == sid), None)
            cov = _sc_coverage_lines(rec, (_today() + timedelta(days=tdidx)).isoformat(),
                                     start, end) if rec else ""
        except Exception:
            cov = ""
        if cov:
            line += "\n\n👥 Working those hours · អ្នកធ្វើការពេលនោះ:\n" + cov
    line += ("\n\n📝 Type the reason — your next message sends it "
             "to them for approval.\n📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើទៅពួកគាត់ ដើម្បីសុំការយល់ព្រម។")
    tog = ("🙈 Hide who's working · លាក់អ្នកធ្វើការ" if show_cov
           else "👁 Show who's working · បង្ហាញអ្នកធ្វើការ")
    extra_rows = [[InlineKeyboardButton(tog, callback_data="att:scp:cov:%d:%d:%d:%d:%d"
                                        % (sid, tdidx, start, end, 0 if show_cov else 1))]]
    return _arm_prompt(p, context, line, "att:scp:staff", extra_rows=extra_rows)


def sc_staff_pick(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Change time +OT (A1) — pick the staffer."""
    rows = [_back_row("att:sc1")]
    rows += [[InlineKeyboardButton(staff_btn_label(r), callback_data="att:scp:d:%d" % r["id"])]
             for r in staff_sort(_sc_pool())][:35]
    return _hdr(p, "Change time +OT — for whom?\nប្តូរម៉ោង +OT — សម្រាប់អ្នកណា?"), \
        InlineKeyboardMarkup(rows)


def _sc_workdays(sid: int, n: int = 30) -> list[tuple[int, date]]:
    """The next n WORKING days for this staffer (their day-off weekday excluded), today first, within
    a 30-day horizon (owner, Jun 15: seniors plan weeks ahead). Returns (dayidx_from_today, date)."""
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    off = _DOW_NAME.get(((rec or {}).get("day_off") or "")[:3].title())
    out = []
    for i in range(0, 31):
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
    # A1 (owner, Jun 15): change-time+OT only — straight to the START ladder (no Change-time/Change-day
    # mode step). Moving a day off is now the separate A2 "Change day off" flow.
    rows += grid([InlineKeyboardButton(day_label(d), callback_data="att:scp:ss:%d:%d" % (sid, i))
                  for i, d in _sc_workdays(sid)], 2)
    return _hdr(p, "Change %s's shift — which work day? (next 30 days)\n"
                   "ប្តូរវេនរបស់ %s — ថ្ងៃធ្វើការណា? (30 ថ្ងៃខាងមុខ)" % (nm, nm)), \
        InlineKeyboardMarkup(rows)


def sc_start(p: dict, sid: int, tdidx: int) -> tuple[str, InlineKeyboardMarkup]:
    """START ladder for the target day (tdidx = days from today). Today drops past times.
    A shift RUNNING today never reaches this ladder — its start is locked (spec 'today edges'),
    so any route here (incl. Back from the end ladder) bounces to the locked mode screen."""
    from gm_bot import ot as ot_mod
    if tdidx == 0:
        run = _sc_running(sid)
        if run and run[0] == 0:
            return sc_end(p, sid, 0, run[1])   # running today → start locked, only extend the end
    rec, d, ws, we, is_off, nm = _ot_receiver(sid, tdidx)
    normal_len = (shift_len_min(rec.get("work_start"), rec.get("work_end")) or 0) if rec else 0
    earliest = _now_min() if tdidx == 0 else 0
    rows = [_back_row("att:scp:d:%d" % sid)]
    # A1 (owner, Jun 15): one-tap "Normal times" applies their standard shift and SKIPS the end ladder
    # (straight to confirm). Shown only when the normal start hasn't already passed today.
    if ws is not None and normal_len and ws >= earliest:
        end_abs = ws + normal_len
        rows.append([InlineKeyboardButton(
            "⏱ Normal times %s–%s · ម៉ោងធម្មតា" % (fmt12(ws), fmt12(we % 1440)),
            callback_data="att:scp:cf:%d:%d:%d:%d" % (sid, tdidx, ws, end_abs))])
    rows += grid([InlineKeyboardButton(fmt12(s), callback_data="att:scp:st:%d:%d:%d" % (sid, tdidx, s))
                  for s in ot_mod.start_options(earliest_min=earliest)], 4)
    return _hdr(p, "%s — START time? (or ⏱ Normal times above)\n"
                   "%s — ម៉ោងចាប់ផ្តើម? (ឬ ⏱ ម៉ោងធម្មតាខាងលើ)" % (day_label(d), day_label(d))), \
        InlineKeyboardMarkup(rows)


def sc_end(p: dict, sid: int, tdidx: int, start: int) -> tuple[str, InlineKeyboardMarkup]:
    """END ladder: normal end (no tag) then each hour beyond carries +NPB (clears debt) then +MOT."""
    from gm_bot import ot as ot_mod
    from gm_bot import payback as pb_mod
    from shared.database import payback_open_debt, ot_pending_extension_min
    rec, d, ws, we, is_off, nm = _ot_receiver(sid, tdidx)
    normal_len = (shift_len_min(rec.get("work_start"), rec.get("work_end")) or 0) if rec else 0
    debt = payback_open_debt(sid)
    raw = max(0, debt["minutes_owed"] - debt["minutes_paid"]) if debt else 0
    # UNBOOKED payback only (owner, Jun 15): debt already covered by approved upcoming redefines/slots
    # must NOT count toward this extension's +PB tag, or the same hour is credited twice.
    try:
        pend = ot_pending_extension_min(sid, (_today() + timedelta(days=tdidx)).isoformat())
    except Exception:
        pend = 0
    pb = pb_mod.unbooked(raw, pend)
    normal_end = start + normal_len
    # never offer a total beyond the 18h/day cap (owner, Jun 15) — bound the ladder by day_ext_cap so the
    # picker can't create an over-cap change the audit would flag.
    max_extra = min(ot_mod.MAX_EXTRA_HOURS * 60, pb_mod.day_ext_cap(normal_len))
    btns = []
    for extra in range(0, max_extra + 1, 60):
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


# ===== A2: Change day off — a real MOVE (off X · work comp-day Y). docs/SCHEDULE_CHANGES_REDESIGN.md.
# Reuses the whole shift_change submit/approve/card machinery — it just adds paired_off_date (=X) to the
# 'shift' pending; on staff approval, X is set OFF atomically with the Y redefine. Callbacks under att:a2:
def a2_staff_pick(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    """A2 step 1 — pick the staffer whose day off is moving."""
    rows = [_back_row("att:sc1")]
    rows += [[InlineKeyboardButton(staff_btn_label(r), callback_data="att:a2:x:%d" % r["id"])]
             for r in staff_sort(_sc_pool())][:35]
    return _hdr(p, "Change day off — for whom?\nប្តូរថ្ងៃឈប់ — សម្រាប់អ្នកណា?"), \
        InlineKeyboardMarkup(rows)


def a2_offday_pick(p: dict, sid: int) -> tuple[str, InlineKeyboardMarkup]:
    """A2 step 2 — pick the day the staffer will be OFF (X): a working day within 30 days."""
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    nm = (rec or {}).get("call_name") or (rec or {}).get("canonical_name") or "?"
    rows = [_back_row("att:sc2")]
    rows += grid([InlineKeyboardButton(day_label(d), callback_data="att:a2:c:%d:%d" % (sid, i))
                  for i, d in _sc_workdays(sid)], 2)
    return _hdr(p, "%s — which day should they be OFF? (next 30 days)\n"
                   "%s — ត្រូវឱ្យឈប់ថ្ងៃណា? (30 ថ្ងៃខាងមុខ)" % (nm, nm)), InlineKeyboardMarkup(rows)


def a2_compday_pick(p: dict, sid: int, xidx: int) -> tuple[str, InlineKeyboardMarkup]:
    """A2 step 3 — pick the comp WORK day (Y): one of the staffer's day-offs within 7 days of X that
    they'll work INSTEAD (so total days worked is unchanged). Override-aware (WF9b)."""
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    nm = (rec or {}).get("call_name") or (rec or {}).get("canonical_name") or "?"
    X = _today() + timedelta(days=xidx)
    cands = [d for d in _real_dayoff_dates(rec, X - timedelta(days=7), n_days=15)
             if abs((d - X).days) <= 7 and d != X and d >= _today()]
    if not cands:
        return _hdr(p, "No day off for %s within 7 days of %s (or already changed).\n"
                       "គ្មានថ្ងៃឈប់សម្រាប់ %s ក្នុង 7 ថ្ងៃនៃ %s ទេ។"
                    % (nm, day_label(X), nm, day_label(X))), \
            InlineKeyboardMarkup([_back_row("att:a2:x:%d" % sid)])
    rows = [_back_row("att:a2:x:%d" % sid)]
    for y in cands:
        yidx = (y - _today()).days
        rows.append([InlineKeyboardButton("%s · their day off" % day_label(y),
                     callback_data="att:a2:ss:%d:%d:%d" % (sid, xidx, yidx))])
    return _hdr(p, "%s off %s — which day-off will they WORK instead? (within 7 days)\n"
                   "%s ឈប់ %s — ត្រូវឱ្យមកធ្វើការជំនួសថ្ងៃឈប់ណា? (ក្នុង 7 ថ្ងៃ)"
                % (nm, day_label(X), nm, day_label(X))), InlineKeyboardMarkup(rows)


def a2_start(p: dict, sid: int, xidx: int, yidx: int) -> tuple[str, InlineKeyboardMarkup]:
    """A2 step 4 — START time for the comp work day Y, with the one-tap Normal-times shortcut."""
    from gm_bot import ot as ot_mod
    rec, d, ws, we, is_off, nm = _ot_receiver(sid, yidx)
    normal_len = (shift_len_min(rec.get("work_start"), rec.get("work_end")) or 0) if rec else 0
    rows = [_back_row("att:a2:c:%d:%d" % (sid, xidx))]
    if ws is not None and normal_len:
        end_abs = ws + normal_len
        rows.append([InlineKeyboardButton(
            "⏱ Normal times %s–%s · ម៉ោងធម្មតា" % (fmt12(ws), fmt12(we % 1440)),
            callback_data="att:a2:cf:%d:%d:%d:%d:%d" % (sid, xidx, yidx, ws, end_abs))])
    rows += grid([InlineKeyboardButton(fmt12(s),
                  callback_data="att:a2:st:%d:%d:%d:%d" % (sid, xidx, yidx, s))
                  for s in ot_mod.start_options()], 4)
    return _hdr(p, "%s (their day off) — START time? (or ⏱ Normal times)\n"
                   "%s (ថ្ងៃឈប់របស់គាត់) — ម៉ោងចាប់ផ្តើម? (ឬ ⏱ ម៉ោងធម្មតា)"
                % (day_label(d), day_label(d))), InlineKeyboardMarkup(rows)


def a2_end(p: dict, sid: int, xidx: int, yidx: int, start: int) -> tuple[str, InlineKeyboardMarkup]:
    """A2 step 5 — END time for Y: the +PB/+OT ladder (UNBOOKED pb, combined tag). Confirm carries
    BOTH dates (att:a2:cf:{sid}:{xidx}:{yidx}:{start}:{end})."""
    from gm_bot import ot as ot_mod
    from gm_bot import payback as pb_mod
    from shared.database import payback_open_debt, ot_pending_extension_min
    rec, d, ws, we, is_off, nm = _ot_receiver(sid, yidx)
    normal_len = (shift_len_min(rec.get("work_start"), rec.get("work_end")) or 0) if rec else 0
    debt = payback_open_debt(sid)
    raw = max(0, debt["minutes_owed"] - debt["minutes_paid"]) if debt else 0
    try:
        pend = ot_pending_extension_min(sid, d.isoformat())
    except Exception:
        pend = 0
    pbm = pb_mod.unbooked(raw, pend)
    normal_end = start + normal_len
    # 18h/day cap (owner, Jun 15): bound the ladder so the picker can't create an over-cap change.
    max_extra = min(ot_mod.MAX_EXTRA_HOURS * 60, pb_mod.day_ext_cap(normal_len))
    btns = []
    for extra in range(0, max_extra + 1, 60):
        end_abs = normal_end + extra
        pb_cleared, ot_m = ot_mod.split_ot_pb(extra, pbm)
        tag = ot_mod._ext_tag(pb_cleared, ot_m)
        label = fmt12(end_abs % 1440) + ((" " + tag) if tag else "")
        btns.append(InlineKeyboardButton(label,
                    callback_data="att:a2:cf:%d:%d:%d:%d:%d" % (sid, xidx, yidx, start, end_abs)))
    rows = [_back_row("att:a2:ss:%d:%d:%d" % (sid, xidx, yidx))] + grid(btns, 2)
    return _hdr(p, "%s — END time? (start %s)\n%s — ម៉ោងបញ្ចប់?"
                % (day_label(d), fmt12(start), day_label(d))), InlineKeyboardMarkup(rows)


def _a2_summ(sid: int, xidx: int, yidx: int, start: int, end: int) -> str:
    """The 'Day-off move — OFF X, works Y' summary line shared by the A2 reason prompt + its toggle +
    the armed pend's _summary (so all three stay identical)."""
    rec = next((r for r in staff_all("active") if r["id"] == sid), None)
    normal_len = (shift_len_min(rec.get("work_start"), rec.get("work_end")) or 0) if rec else 0
    extra = max(0, end - (start + normal_len))
    X = (_today() + timedelta(days=xidx)).isoformat()
    Y = (_today() + timedelta(days=yidx)).isoformat()
    rnm = (rec or {}).get("call_name") or (rec or {}).get("canonical_name") or "the staffer"
    ot_txt = (" (+%dh OT)" % (extra // 60)) if extra else ""
    return ("Day-off move — %s: OFF %s, works %s %s-%s%s.\n"
            "ប្តូរថ្ងៃឈប់ — %s៖ ឈប់ %s, មកធ្វើការ %s %s-%s%s។"
            % (rnm, day_label(date.fromisoformat(X)), day_label(date.fromisoformat(Y)),
               fmt12(start), fmt12(end % 1440), ot_txt,
               rnm, day_label(date.fromisoformat(X)), day_label(date.fromisoformat(Y)),
               fmt12(start), fmt12(end % 1440), ot_txt))


def _a2_reason_prompt(p: dict, context, sid: int, xidx: int, yidx: int, start: int, end: int,
                      show_cov: bool):
    """A2 day-off-move reason prompt with a BOTH-DAYS 👁 who's-working toggle (owner, Jun 15: the
    senior moving a day off must see who works the new OFF day X AND the comp day Y before sending)."""
    line = _a2_summ(sid, xidx, yidx, start, end)
    if show_cov:
        try:
            from gm_bot.bot import _sc_cov_block
            rec = next((r for r in staff_all("active") if r["id"] == sid), None)
            X = (_today() + timedelta(days=xidx)).isoformat()
            Y = (_today() + timedelta(days=yidx)).isoformat()
            blk = _sc_cov_block(rec, Y, start, end, X) if rec else ""
        except Exception:
            blk = ""
        if blk:
            line += "\n\n" + blk
    line += ("\n\n📝 Type the reason — your next message sends it to them for approval.\n"
             "📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើទៅពួកគាត់ ដើម្បីសុំការយល់ព្រម។")
    tog = ("🙈 Hide who's working · លាក់អ្នកធ្វើការ" if show_cov
           else "👁 Show who's working · បង្ហាញអ្នកធ្វើការ")
    extra_rows = [[InlineKeyboardButton(tog, callback_data="att:a2:cov:%d:%d:%d:%d:%d:%d"
                                        % (sid, xidx, yidx, start, end, 0 if show_cov else 1))]]
    return _arm_prompt(p, context, line, "att:sc2", extra_rows=extra_rows)


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
            "មកដល់មុន 5 នាទី ប្អូននឹងទទួលបាន +10 points ⭐") % (t, t)


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
    # Cancel AL button — shows whenever there are future cancelable days (Jun 11, both modes)
    cancelable = [(d, rid) for d, rid in upcoming
                  if d > today_iso or (d == today_iso and not _shift_running(p))]
    if cancelable:
        rows.append([InlineKeyboardButton("✕ Cancel AL · បោះបង់ AL",
                                          callback_data="att:my:allist")])
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


def al_cancel_list(p: dict) -> tuple[str, InlineKeyboardMarkup]:
    """List of upcoming approved AL days the staffer can cancel — one button per day.
    Tapping opens the confirmation screen (att:my:alconfirm)."""
    import json as _json
    from shared.database import _db   # (was missing in this scope → list silently came back empty)
    today_iso = _today().isoformat()
    cancelable = []
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # only deduct-at-approval rows carry a refundable frozen map; a legacy (no-map) row
                # can't be refunded by al_cancel_and_refund, so never offer it a (silently no-op) ✕
                cur.execute("""SELECT id, days, kind, hours_start, hours_end FROM al_requests
                               WHERE staff_id=%s AND status='approved' AND is_test=%s
                               AND deducted_map IS NOT NULL""",
                            (p["id"], att_test_on()))
                for r in cur.fetchall():
                    for d in _json.loads(r["days"] or "[]"):
                        if d < today_iso:
                            continue
                        if d == today_iso and _shift_running(p):
                            continue
                        cancelable.append((d, r["id"], r["kind"],
                                           r.get("hours_start"), r.get("hours_end")))
    except Exception:
        pass
    cancelable.sort()
    rows = [_back_row("att:my")]
    for d, rid, kind, hs, he in cancelable:
        lbl = day_label(date.fromisoformat(d))
        if kind == "hours" and hs and he:
            lbl += " %s–%s" % (hs, he)
        rows.append([InlineKeyboardButton("✕ %s" % lbl,
                                          callback_data="att:my:alconfirm:%s:%d" % (d, rid))])
    if not cancelable:
        return _hdr(p, "No upcoming AL to cancel.\nគ្មាន AL ខាងមុខដែលអាចបោះបង់បានទេ។"), \
            InlineKeyboardMarkup(rows)
    return _hdr(p, "Which AL day do you want to cancel?\nប្អូនចង់បោះបង់ AL ថ្ងៃណា?"), \
        InlineKeyboardMarkup(rows)


def al_cancel_confirm(p: dict, iso: str, rid: int) -> tuple[str, InlineKeyboardMarkup]:
    """Confirmation screen: shows the day details and asks the staffer to confirm before cancelling.
    Confirm → att:my:cancel (actual cancel). Back → att:my:allist."""
    import json as _json
    from shared.database import _db   # (was missing in this scope → details silently fell back)
    kind, hs, he, refund = "days", None, None, None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT kind, hours_start, hours_end, deducted_map FROM al_requests "
                            "WHERE id=%s", (rid,))
                r = cur.fetchone()
                if r:
                    kind, hs, he = r["kind"], r.get("hours_start"), r.get("hours_end")
                    dm = r.get("deducted_map") or {}
                    refund = dm.get(iso)   # the EXACT frozen amount (None on a legacy row)
    except Exception:
        pass
    lbl = day_label(date.fromisoformat(iso))
    detail = ("%s %s–%s" % (lbl, hs, he)) if (kind == "hours" and hs and he) else lbl
    # S4: show the amount that will ACTUALLY return — fraction for hours-AL, 0 for a day-off day
    if refund is None or refund == 1:
        ret_en, ret_kh = "1 day", "AL 1 ថ្ងៃ"
    elif refund == 0:
        ret_en, ret_kh = "no AL (this day costs none)", "មិនដក AL (ថ្ងៃនេះមិនអស់ AL)"
    else:
        ret_en, ret_kh = "%g AL" % refund, "AL %g" % refund
    body = ("Are you sure you want to cancel your AL on %s?\n"
            "This will return %s to your AL balance.\n\n"
            "ប្អូនពិតជាចង់បោះបង់ AL នៅ %s មែនទេ?\n"
            "វានឹងដាក់ %s ត្រឡប់ចូល balance របស់ប្អូនវិញ។"
            % (detail, ret_en, detail, ret_kh))
    rows = [
        [InlineKeyboardButton("✅ Yes, cancel it · បោះបង់",
                              callback_data="att:my:cancel:%s:%d" % (iso, rid))],
        [InlineKeyboardButton("← Back · ត្រឡប់ក្រោយ",
                              callback_data="att:my:allist")],
    ]
    return _hdr(p, body), InlineKeyboardMarkup(rows)


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


async def _menu_claim(context, msg) -> None:
    """P1 menu singleton: register `msg` as the CURRENT nav menu and collapse the PREVIOUS one (if a
    different message) to a 'continues below' pointer with its buttons removed — so a staffer can't
    drive two live menus that share one user_data (the cross-contamination root). Best-effort; the
    dead-tap guard backs it up. Only NAV menus are ever claimed; the moment a menu becomes a prompt,
    _menu_release unregisters it, so an awaiting prompt/card is NEVER collapsed."""
    if msg is None:
        return
    new = (getattr(msg, "chat_id", None), getattr(msg, "message_id", None))
    if new[0] is None or new[1] is None:
        return
    old = context.user_data.get("att_menu_msg")
    if old and tuple(old) != new:
        try:
            await context.bot.edit_message_text(
                "⤵ Menu continues below · menu បន្តនៅខាងក្រោម",
                chat_id=old[0], message_id=old[1])
        except Exception:
            pass   # too old / already a prompt / deleted → dead-tap guard is the backstop
    context.user_data["att_menu_msg"] = new


def _menu_release(context) -> None:
    """The current menu message became a prompt/awaiting-card — unregister it so the singleton never
    collapses a message that's now waiting for input (P1 + Law 2)."""
    try:
        context.user_data.pop("att_menu_msg", None)
    except Exception:
        pass


_SELECTION_STASHES = ("att_al_cov", "att_do_day", "att_do_cov", "att_al_from", "att_al_page",
                      "att_ci_armed")


def reset_selection(context) -> None:
    """Clear EVERY per-flow selection stash (not just the AL day-set). Called on a fresh menu AND on
    flow completion/cancel — otherwise a leftover att_al_picked/att_do_day/att_al_from makes the F8
    mid-pick guard fire forever on later typed text (Fable A1: a near-every-staffer dead-end loop)."""
    context.user_data["att_al_picked"] = set()
    for _k in _SELECTION_STASHES:
        context.user_data.pop(_k, None)


async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only: open the role-play shell."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    if update.effective_chat.type != "private":
        return
    context.user_data["att_live_self"] = False   # owner is role-playing, not a live staffer
    text, kb = persona_picker(0)
    sent = await update.message.reply_text(text, reply_markup=kb)
    await _menu_claim(context, sent)


async def open_live_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, rec: dict) -> None:
    """LIVE entry: a real active staffer opens their OWN attendance menu (gated upstream by
    attendance_live). Persona is LOCKED to themselves; the owner role-play shell is unaffected."""
    context.user_data["att_persona"] = rec["id"]
    context.user_data["att_live_self"] = True
    # multi-menu fix (piece 3): a fresh menu starts a clean slate. Opening a new menu must not let a
    # half-done flow's stashes (from an older, now-stale menu sharing this same user_data) leak into it.
    reset_selection(context)
    text, kb = main_menu(_persona(context))
    sent = await update.message.reply_text(text, reply_markup=kb)
    await _menu_claim(context, sent)   # P1: collapse any older menu this one supersedes


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """All att:* buttons. The owner drives the role-play shell; a real staffer drives their OWN
    menu — persona LOCKED to themselves, and only when attendance_live is on."""
    query = update.callback_query
    uid = update.effective_user.id
    if uid != config.OWNER_TELEGRAM_ID:
        from gm_bot.bot import _attendance_live
        if not _attendance_live():
            # F12: when the master switch is OFF (e.g. a rollback), every staff tap used to die
            # silently → "boss it's broken". Tell them it's paused, don't leave a dead button.
            await query.answer("🔧 Attendance is paused for maintenance — please talk to your senior."
                               " · ប្រព័ន្ធវត្តមានកំពុងផ្អាកដើម្បីថែទាំ — សូមនិយាយជាមួយបងៗ។", show_alert=True)
            return
        rec = staff_get_by_uid(uid)
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
        # dry-run sample buttons demonstrate their consequence (owner: ladders must continue).
        # Sent buttons carry a :{key}:{step} suffix (stateless — restart-proof).
        what = data[2] if len(data) > 2 else ""
        if what == "noop":            # acknowledge-style buttons (OK / I agree …) just advance
            if len(data) >= 5:
                return await _dryrun_send(update, context, data[3], int(data[4]) + 1)
            return await _dryrun_next(update, context)   # legacy (pre-stateless message)
        if what in ("alcov", "swcov"):    # the 👁 toggle — edits in place, like the real card
            p2 = _dr_sample(context)
            if p2 is None:
                return
            if what == "alcov":           # att:drs:alcov:{flag}[:key:i]
                label, (body, kb2) = _DEMO_AL_LABEL, _demo_al_card(p2, data[3] == "1")
                key, di = (data[4], int(data[5])) if len(data) >= 6 else (None, 0)
            else:                         # att:drs:swcov:{aud}:{flag}[:key:i]
                label = _DEMO_SW_LABELS.get(data[3], "")
                body, kb2 = _demo_swap_card(p2, data[3], data[4] == "1")
                key, di = (data[5], int(data[6])) if len(data) >= 7 else (None, 0)
            rows2 = [[InlineKeyboardButton(b.text, callback_data="%s:%s:%d"
                                           % (b.callback_data, key, di))
                      if key and (b.callback_data or "").startswith("att:drs:") else b
                      for b in r] for r in kb2.inline_keyboard]
            if key:
                total = len(_dr_events(key, p2))
                if di + 1 < total:
                    rows2.append([InlineKeyboardButton(
                        "Next ▶ (%d/%d)" % (di + 2, total),
                        callback_data="att:dr:n:%s:%d" % (key, di + 1))])
            try:
                await query.edit_message_text("🧪 %s\n────────────\n%s" % (label, body),
                                              reply_markup=InlineKeyboardMarkup(rows2),
                                              parse_mode="HTML")
            except Exception:
                pass
            return
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
        sub = data[2] if len(data) > 2 else ""
        if sub in _DR_INTROS or sub == "go6":
            key = "go7" if sub == "go6" else sub
            sample = _dr_sample(context)
            if sample is None:
                await query.answer("No staff with shifts found")
                return
            await context.bot.send_message(update.effective_chat.id,
                                           _DR_INTROS[key] % len(_dr_events(key, sample)))
            await _dryrun_send(update, context, key, 0)
            return
        if sub == "n":                      # stateless step — survives any restart/deploy
            await _dryrun_send(update, context, data[3], int(data[4]))
            return
        await _dryrun_next(update, context)   # legacy 'next' from pre-stateless messages
        return
    if action == "pick":
        return await show(persona_picker(0))
    if action == "pickp":
        return await show(persona_picker(int(data[2])))
    if action == "persona":
        context.user_data["att_persona"] = int(data[2])
        reset_selection(context)
        return await show(main_menu(_persona(context)))

    p = _persona(context)
    if not p:
        return await show(persona_picker(0))

    if action == "menu":
        reset_selection(context)   # A1: full reset, not just att_al_picked (else F8 guard traps later text)
        await show(main_menu(p))
        await _menu_claim(context, query.message)   # P1: this edited message is now the current menu
        return
    if action == "menunew":
        # Law 8 / owner pt#1: a TERMINAL/ended message holds useful details — its "🏠 Main menu" must
        # open a NEW message, never edit OVER the record. (Nav screens keep att:menu = edit in place.)
        reset_selection(context)   # A1: full reset
        text, kb = main_menu(p)
        try:
            sent = await query.message.reply_text(text, reply_markup=kb)
            await _menu_claim(context, sent)   # P1: the new menu collapses any older one
        except Exception:
            await show((text, kb))   # fallback: edit in place if we can't post a new message
        return
    if action == "cancel":
        # F5/Law 6: the exit from an armed prompt MUST disarm the pend, or a later stray message
        # becomes a ghost submission. Clear both stores (test user_data + live flow_state), reset the
        # selection stashes, and return to a clean menu.
        context.user_data.pop("att_test_pending", None)
        try:
            from shared.database import flow_clear
            flow_clear(uid)
        except Exception:
            pass
        reset_selection(context)
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
                from gm_bot.bot import _who_kh
                return await show(_confirm_prompt(p, context,
                    "Family sick (%s) — full day. · គ្រួសារឈឺ (%s) ពេញមួយថ្ងៃ។"
                    % (data[3], _who_kh(data[3])), "att:sp:sick"))
            return await show(sick_family_stub(p, data[3], data[4]))
        if sub == "famt":
            return await show(sick_family_time_grid(p, data[3], data[4], "from"))
        if sub == "famtf":
            return await show(sick_family_time_grid(p, data[3], data[4], "to", int(data[5])))
        if sub == "famtt":
            window = "%s → %s" % (fmt12(int(data[5])), fmt12(int(data[6])))
            # WF2 (owner): the TIMES path must mirror the full-day path — a CONFIRM before booking (a
            # mis-tapped time button shouldn't book silently), and it must ACTUALLY file the case (the
            # old famtt only showed a "✓" stub and never booked). Unarmed = preview/walk → stub.
            if _armed(context):
                _arm_pending(context, update,
                    {"flow": "sick_fam", "persona_id": p["id"], "who": data[3], "date": data[4],
                     "window": window})
                from gm_bot.bot import _who_kh
                return await show(_confirm_prompt(p, context,
                    "Family sick (%s) — %s. · គ្រួសារឈឺ (%s) — %s។"
                    % (data[3], window, _who_kh(data[3]), window), "att:sp:sick"))
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
            mins = int(data[3])
            if _armed(context):
                # declare-Late-FIRST (owner Jun 13): the MOMENT they pick the minutes, RECORD the
                # declaration (so split-late credits the cheaper 'informed' rate even if no reason
                # follows) and tell Supervisors NOW (so someone always knows). The reason arrives
                # later as an addendum + is attached to this same record.
                from gm_bot.attendance import to_min
                from shared.database import late_declare as _late_declare
                _ws = to_min(p.get("work_start"))
                _late_declare(p["id"], _today().isoformat(),
                              (_ws + mins) if _ws is not None else mins, "")
                try:
                    from gm_bot.bot import _att_send
                    _nm = p.get("call_name") or p["canonical_name"]
                    await _att_send(context, None, "Supervisors group", "",
                        "%s will be ~%s late for today's shift (reason to follow).\n"
                        "%s នឹងមកយឺត ~%s សម្រាប់វេនថ្ងៃនេះ (មូលហេតុនឹងមកតាមក្រោយ)។"
                        % (_nm, _hm(mins), _nm, _hm(mins)), group=True)
                except Exception:
                    pass
                _arm_pending(context, update,
                    {"flow": "late", "persona_id": p["id"], "mins": mins, "_declared": True})
                # WF1 (owner): no staffer-facing "Supervisors notified ✓" line — go straight to the
                # reason. The Supervisors GROUP heads-up above still fires; the staffer just doesn't
                # get told they were reported.
                return await show(_arm_prompt(p, context,
                    "📝 Type your reason (added to the heads-up). Share your live location when you "
                    "arrive and I'll work out the payback.\n"
                    "📝 សរសេរមូលហេតុ (បន្ថែមលើដំណឹង)។ ពេលមកដល់ សូមចែករំលែកទីតាំងផ្ទាល់ "
                    "ខ្ញុំនឹងគណនាម៉ោងសងវិញ។",
                    "att:late"))
            return await show(late_picked(p, mins))
        return await show(late_screen(p))
    if action == "al":
        picked = context.user_data.setdefault("att_al_picked", set())
        if len(data) > 2:
            sub = data[2]
            if sub == "cov":   # toggle who's-working on the reason prompt (from the stashed selection)
                st = context.user_data.get("att_al_cov")
                if not st:     # F10: stash reset under an old prompt → don't blank the request summary
                    return await show(_stale_screen(p))
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
                if not picked:   # F4: stale grid (stash reset) → don't file a 0-day ghost AL
                    return await show(_stale_screen(p))
                return await show(al_fullday_or_time(p, picked))
            if sub == "full":
                if not picked:   # F4: stale grid (stash reset) → don't file a 0-day ghost AL
                    return await show(_stale_screen(p))
                from gm_bot import al as alm
                doff = p.get("day_off")
                nw = staff_absent_dates(p["id"])                # other AL / special leave / swaps
                charged = _al_charged_with_coexist(p, picked, doff, nw)   # incl. A2 comp-work days (8b)
                span = alm.al_span_label(picked, doff, nw)       # from → to, bridging ANY absence
                over = _al_over_balance(p, float(len(charged)))
                if over:                                          # owner: gate BEFORE the reason
                    return await show((_hdr(p, over),
                                       InlineKeyboardMarkup([_back_row("att:al")])))
                near = _near_days(set(charged))
                detail = ("Full-day AL: %s — %d AL day(s).\nAL ពេញមួយថ្ងៃ៖ %s — %d ថ្ងៃ។"
                          % (span, len(charged), span, len(charged)))
                if len(charged) != len(picked):
                    detail += "\nDay off = No AL used · ថ្ងៃឈប់ = មិនដក AL"
                if near:
                    sl = shift_len_min(p.get("work_start"), p.get("work_end")) or 0
                    pts = round(SHORT_NOTICE_PT_PER_MIN * sl * len(near))
                    detail += ("\n⚠ %d short-notice day(s) → −%d points (−0.1/min)."
                               "\n⚠ %d ថ្ងៃស្នើជិតពេល → −%d points (−0.1/min)។"
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
                if f is None or not picked:   # F4: stale time grid (stash reset) → don't crash/ghost
                    return await show(_stale_screen(p))
                t = int(data[3])
                from gm_bot import al as alm
                _picked = sorted(picked)
                _doff, _nw = p.get("day_off"), staff_absent_dates(p["id"])
                _span = alm.al_span_label(_picked, _doff, _nw)
                _charged = _al_charged_with_coexist(p, _picked, _doff, _nw)   # incl. A2 comp-work (8b)
                _sl = shift_len_min(p.get("work_start"), p.get("work_end")) or 0
                _total = round(alm.fractional_al(f, t, _sl) * len(_charged), 2)
                over = _al_over_balance(p, _total)
                if over:                                          # owner: gate BEFORE the reason
                    return await show((_hdr(p, over),
                                       InlineKeyboardMarkup([_back_row("att:al")])))
                detail = ("AL: %s · %s–%s = %g AL.\nAL៖ %s · %s–%s = %g AL។"
                          % (_span, fmt12(f), fmt12(t), _total, _span, fmt12(f), fmt12(t), _total))
                if len(_charged) != len(_picked):
                    detail += "\nDay off = No AL used · ថ្ងៃឈប់ = មិនដក AL"
                near = _near_days(picked)
                if near:
                    window = t - f
                    pts = round(SHORT_NOTICE_PT_PER_MIN * window * len(near))
                    detail += ("\n⚠ %d short-notice day(s) → −%d points (−0.1/min)."
                               "\n⚠ %d ថ្ងៃស្នើជិតពេល → −%d points (−0.1/min)។"
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
            st = context.user_data.get("att_do_cov")
            if not st:     # F10: stash reset under an old swap prompt → don't blank the summary
                return await show(_stale_screen(p))
            flag = bool(int(data[3])) if len(data) > 3 else False
            return await show(_swap_prompt(p, context, st.get("base", ""), st.get("partner_id"),
                                           st.get("req_off"), st.get("partner_off"), flag))
        if len(data) > 2 and data[2] == "p":
            # WF5: partner picked FIRST → show the valid date-pairings (no arbitrary day anymore)
            return await show(dayoff_swap_pairs(p, int(data[3])))
        if len(data) > 2 and data[2] == "pair":
            # att:do:pair:{partner}:{req_off}:{partner_off} — req_off = THEIR day off you take (you
            # end up off), partner_off = YOUR day off they take (they end up off). Coverage-neutral.
            if len(data) < 6:
                return await show(_stale_screen(p))   # malformed/stale pairing button
            partner_id, req_off, partner_off = int(data[3]), data[4], data[5]
            if _armed(context):
                partner = next((s for s in staff_all("active") if s["id"] == partner_id), None)
                pn = (partner or {}).get("call_name") or (partner or {}).get("canonical_name", "partner")
                ro, po = date.fromisoformat(req_off), date.fromisoformat(partner_off)
                _swap_sum = ("Day-off swap with %s — you take their day off %s, they take yours %s."
                             % (pn, day_label(ro), day_label(po)))
                _swap_kh = ("ប្តូរថ្ងៃឈប់ជាមួយ %s — ប្អូនយកថ្ងៃឈប់របស់គាត់ %s, គាត់យកថ្ងៃឈប់របស់ប្អូន %s។"
                            % (pn, day_label(ro), day_label(po)))
                _arm_pending(context, update,
                    {"flow": "swap", "persona_id": p["id"], "partner_id": partner_id,
                     "req_off_date": req_off, "partner_off_date": partner_off,
                     "_summary": _swap_sum})
                return await show(_swap_prompt(p, context, "%s\n%s" % (_swap_sum, _swap_kh),
                                               partner_id, req_off, partner_off, False))
            return await show(al_stub(p, "Day-off swap pairing picked. (Partner agrees FIRST, then "
                                         "2 seniors approve.)\n"
                                         "បានជ្រើសគូថ្ងៃឈប់ហើយ។ (ដៃគូយល់ព្រមមុន បន្ទាប់មកបង 2 នាក់។)",
                                         walk="swap"))
        return await show(dayoff_partners(p))
    if action == "walk":
        # att:walk:{name}:{idx} — owner steps through the rest of a ladder to the end
        if len(data) > 2 and data[2] == "noop":
            return  # illustrative preview button — already answered, do nothing
        if len(data) > 3:
            return await show(walk_card(p, data[2], int(data[3])))
        return await show(main_menu(p))
    if action == "ot":          # personal OT bank view (Give OT lives under att:scp:)
        return await show(ot_screen(p))
    if action == "sc1":         # Staff Changes (1 time) menu → A1 change-time / A2 change-day-off
        return await show(staff_changes_menu(p))
    if action == "scfv":        # Staff Changes (forever) — Phase 2+ (all-senior + owner approval)
        return await show(_coming_soon(p, "Staff Changes (forever)", "att:aw"))
    if action == "sc2":         # A2 Change day off (a real move) — pick the staffer
        return await show(a2_staff_pick(p))
    if action == "a2":          # A2 Change-day-off picker: x (off-day) → c (comp-day) → ss/st → cf
        sub = data[2] if len(data) > 2 else ""
        if sub == "x":
            return await show(a2_offday_pick(p, int(data[3])))
        if sub == "c":
            return await show(a2_compday_pick(p, int(data[3]), int(data[4])))
        if sub == "ss":
            return await show(a2_start(p, int(data[3]), int(data[4]), int(data[5])))
        if sub == "st":
            return await show(a2_end(p, int(data[3]), int(data[4]), int(data[5]), int(data[6])))
        if sub == "cf":
            # att:a2:cf:{sid}:{xidx}:{yidx}:{start}:{end} → arm a 'shift' pending carrying paired_off
            sid, xidx, yidx, start, end = (int(data[3]), int(data[4]), int(data[5]),
                                           int(data[6]), int(data[7]))
            if _armed(context):
                rec = next((r for r in staff_all("active") if r["id"] == sid), None)
                normal_len = (shift_len_min(rec.get("work_start"), rec.get("work_end")) or 0) if rec else 0
                X = (_today() + timedelta(days=xidx)).isoformat()
                Y = (_today() + timedelta(days=yidx)).isoformat()
                _arm_pending(context, update,
                    {"flow": "shift", "persona_id": p["id"], "staff_id": sid, "when_date": Y,
                     "start_min": start, "end_min": end, "normal_len": normal_len,
                     "paired_off_date": X, "_summary": _a2_summ(sid, xidx, yidx, start, end)})
                return await show(_a2_reason_prompt(p, context, sid, xidx, yidx, start, end,
                                                    show_cov=False))
            return await show(a2_staff_pick(p))
        if sub == "cov":
            # att:a2:cov:{sid}:{xidx}:{yidx}:{start}:{end}:{flag} — the A2 reason prompt's both-days
            # 👁 toggle. The pend is already armed at cf; this only re-renders the prompt.
            sid, xidx, yidx, start, end, flag = (int(data[3]), int(data[4]), int(data[5]),
                                                 int(data[6]), int(data[7]), int(data[8]))
            return await show(_a2_reason_prompt(p, context, sid, xidx, yidx, start, end,
                                                show_cov=bool(flag)))
    if action == "scp":   # session 31: unified Give-OT / shift-redefine picker
        sub = data[2] if len(data) > 2 else ""
        if sub == "staff":
            return await show(sc_staff_pick(p))
        if sub == "d":
            return await show(sc_day_pick(p, int(data[3])))
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
                # 1a (owner): extending the CURRENTLY-running shift (start LOCKED to the running start)
                # needs no extra senior approval; any other change does. Detect it here.
                _run = _sc_running(sid)
                is_ext = bool(_run and _run[0] == tdidx and _run[1] == start)
                _shift_sum = ("Shift change — %s %s-%s%s for %s."
                              % (day_label(_today() + timedelta(days=tdidx)), fmt12(start),
                                 fmt12(end % 1440), (" (+%dh OT)" % (extra // 60)) if extra else "", rnm))
                _arm_pending(context, update,
                    {"flow": "shift", "persona_id": p["id"], "staff_id": sid,
                     "when_date": (_today() + timedelta(days=tdidx)).isoformat(),
                     "start_min": start, "end_min": end, "normal_len": normal_len,
                     "is_extension": is_ext, "_summary": _shift_sum})
                return await show(_sc_reason_prompt(p, context, sid, tdidx, start, end,
                                                    _shift_sum, show_cov=False))
            return await show(sc_staff_pick(p))
        if sub == "cov":
            # att:scp:cov:{sid}:{tdidx}:{start}:{end}:{flag} — the prompt's 👁 toggle (owner,
            # Jun 11: the SENIOR deciding new times must see who's working them). The armed
            # pending stays untouched — this only re-renders the prompt.
            sid, tdidx, start, end, flag = (int(data[3]), int(data[4]), int(data[5]),
                                            int(data[6]), int(data[7]))
            rec = next((r for r in staff_all("active") if r["id"] == sid), None)
            normal_len = (shift_len_min(rec.get("work_start"), rec.get("work_end")) or 0) if rec else 0
            extra = max(0, end - (start + normal_len))
            rnm = (rec or {}).get("call_name") or "the staffer"
            _shift_sum = ("Shift change — %s %s-%s%s for %s."
                          % (day_label(_today() + timedelta(days=tdidx)), fmt12(start),
                             fmt12(end % 1440), (" (+%dh OT)" % (extra // 60)) if extra else "", rnm))
            return await show(_sc_reason_prompt(p, context, sid, tdidx, start, end,
                                                _shift_sum, show_cov=bool(flag)))
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
        if len(data) > 2 and data[2] == "allist":
            return await show(al_cancel_list(p))
        if len(data) > 2 and data[2] == "alconfirm":
            iso, rid = data[3], int(data[4])
            return await show(al_cancel_confirm(p, iso, rid))
        if len(data) > 2 and data[2] == "cancel":
            iso, rid = data[3], int(data[4])
            from shared.database import al_cancel_and_refund
            today_iso = _today().isoformat()
            # cutoff (window-aware): block past dates, and today's once the shift/window has started
            if iso < today_iso or (iso == today_iso and _shift_running(p)):
                await query.answer("Too late to cancel — that day has already started · "
                                   "យឺតពេលបោះបង់ហើយ — ថ្ងៃនោះបានចាប់ផ្តើមហើយ", show_alert=True)
                return await show(my_screen(p))
            # per-date cancel: pop ONLY this day + refund the EXACT frozen amount, atomically (S1).
            # None ⇒ nothing to refund (double-tap / not approved / past) → just refresh, no FYI.
            res = al_cancel_and_refund(rid, p["id"], iso, today_iso=today_iso)
            if res is not None and res[0] > 0:   # >0 only: a 0-cost day-off day = not a "back to work"
                from gm_bot.bot import _att_send
                nmx = p.get("call_name") or p["canonical_name"]
                dlbl = date.fromisoformat(iso).strftime("%a %d/%m")
                await _att_send(context, None, "Supervisors group", "",
                    "FYI: %s cancelled AL on %s — back to work that day.\n"
                    "FYI: %s បានលុបចោល AL ថ្ងៃ %s — នឹងមកធ្វើការវិញ។" % (nmx, dlbl, nmx, dlbl), group=True)
            return await show(my_screen(p))
        return await show(my_screen(p))
    # att:noop and anything unknown: stay put
