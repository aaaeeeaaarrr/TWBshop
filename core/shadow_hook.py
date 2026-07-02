"""core.shadow_hook — the SAFE bridge that runs the new platform core BESIDE the live bot.

Two hard guarantees so the shadow can never be confused with, or harm, the live system:
  1. ISOLATION: the whole thing is wrapped so it can NEVER raise into the live flow and NEVER reach the
     user/Telegram. A shadow bug can only ever break SHADOW data (its own throwaway tables) — never live.
  2. ATTRIBUTION: every line goes to the dedicated 'shadow' logger, tagged [SHADOW]. So in the journal/logs
     a [SHADOW] line = the NEW system; anything without it = the original live system. (`grep SHADOW`.)

Gated by gm_state 'shadow_run' (OFF by default) → deploy inert, flip ON to start collecting comparisons.
TWBshop is tenant org_id 'twb'. The new core writes ONLY to its own tables (shifts / attendance_events /
shadow_comparisons) — it touches NOTHING the live system owns.
"""
import logging

logger = logging.getLogger("shadow")   # dedicated → filter with `grep SHADOW` / journalctl

# live uses 'ontime'; the new core uses 'on_time' — normalize so a vocab diff isn't a false mismatch.
_STATE_MAP = {"ontime": "on_time", "on_time": "on_time", "late": "late", "early": "early"}


def shadow_enabled() -> bool:
    try:
        from shared.database import gm_get_state
        return gm_get_state("shadow_run") == "on"
    except Exception:
        return False


def shadow_checkin(staff: dict, when_dt, live_state, live_late, live_early, resolved_start_min=None) -> None:
    """Run core.check_in for TWB on the SAME check-in event + record new-vs-live. Best-effort + isolated:
    any failure is swallowed and logged as [SHADOW] (live is never affected). No-op unless shadow_run=on.
    `resolved_start_min`: live's REDEFINE-aware start (from resolve_day) — pass it so the shadow judges
    vs the same moved start live used (the redefine port; verified to take agreement to ~100%). Falls
    back to the base work_start when not given."""
    if not shadow_enabled():
        return
    try:
        from core.attendance import check_in
        from core.shadow import compare_checkin
        ls = _STATE_MAP.get((live_state or "").strip(), live_state)
        ws = staff.get("work_start")
        if resolved_start_min is not None:
            sm = int(resolved_start_min) % 1440
            ws = "%02d:%02d" % (sm // 60, sm % 60)   # redefine-aware start (end-move doesn't affect check-in)
        res = check_in("twb", staff["id"], when_dt, ws, staff.get("work_end"), "Asia/Phnom_Penh")
        agree = compare_checkin("twb", staff["id"], ls, live_late, live_early, res)
        who = staff.get("call_name") or staff.get("canonical_name") or staff["id"]
        if agree:
            logger.info("[SHADOW] check-in AGREE — %s", who)
        else:
            logger.warning("[SHADOW] check-in MISMATCH — %s | live=(%s,late=%s,early=%s) new=%s",
                           who, ls, live_late, live_early, res)
    except Exception:
        # the entire reason this is here: a shadow problem must be visible AS shadow, and harmless to live
        logger.exception("[SHADOW] check-in hook failed — LIVE UNAFFECTED")


def _resolved_window(staff: dict, day_iso: str):
    """Live's redefine-aware window for the day as ('HH:MM','HH:MM'), or None (not working / no
    resolver / any failure → the caller falls back to the base window). The check-in hook feeds
    resolve_day's start, so the checkout MUST resolve the same way or the pair lands on two
    instances (the s59c mispair class: Nak's 20:56 come-early slots, Thyda's 06:00 ones)."""
    try:
        from gm_bot.attendance_ui import resolve_day
        r = resolve_day(staff, day_iso)
        if not r.get("working") or r.get("start_min") is None or r.get("end_min") is None:
            return None
        sm, em = int(r["start_min"]) % 1440, int(r["end_min"]) % 1440
        return "%02d:%02d" % (sm // 60, sm % 60), "%02d:%02d" % (em // 60, em % 60)
    except Exception:
        return None


def shadow_checkout(staff_id: int, at_iso: str, staff: dict = None, shift_date: str = None) -> None:
    """Feed the live CHECK-OUT into the platform core so its session loop COMPLETES (flowcheck's first
    prod catch, 2026-07-03: the feed was check-in-only — platform sessions could never reach their next
    step, and core can't self-derive worked-minutes at cut-over without checkouts). EVENT FEED ONLY —
    the money comparison already rides shadow_settle; the event is idempotent (UNIQUE(shift_id,type)).
    Hooked inside shared.database.att_check_out = the ONE live checkout write (auto · manual · closer ·
    sim), so no path can be missed. Same guarantees as shadow_checkin: best-effort, isolated, [SHADOW]-
    tagged, no-op unless shadow_run=on; ALSO no-op in attendance test mode (sim checkouts are role-play).
    `shift_date` (the session's business day) lets the hook bind via the RESOLVED window — the same
    resolution the check-in hook fed — so a redefined/come-early day pairs onto ONE instance and a
    checkout past a redefine-extended end still binds (A2, 2026-07-03; was the KNOWN LIMIT).
    `staff` injectable for tests."""
    if not shadow_enabled():
        return
    try:
        from datetime import datetime

        from shared.database import gm_get_state, staff_all
        if gm_get_state("attendance_test_mode") == "true":
            return
        if staff is None:
            staff = next((s for s in staff_all("active") if s["id"] == staff_id), None)
        if not staff:
            logger.info("[SHADOW] checkout skipped — staff %s not in the active registry", staff_id)
            return
        from core.attendance import check_out
        when = datetime.fromisoformat(at_iso) if isinstance(at_iso, str) else at_iso
        win = _resolved_window(staff, shift_date) if shift_date else None
        res = check_out("twb", staff_id, when, staff.get("work_start"), staff.get("work_end"),
                        "Asia/Phnom_Penh", windows=[win] if win else None)
        who = staff.get("call_name") or staff.get("canonical_name") or staff_id
        if res.get("bound"):
            logger.info("[SHADOW] checkout fed — %s (shift %s, worked %s min%s)", who,
                        res.get("shift_id"), res.get("worked_min"),
                        ", duplicate" if res.get("duplicate") else "")
        else:
            logger.info("[SHADOW] checkout unbound — %s (%s)", who, res.get("reason"))
    except Exception:
        logger.exception("[SHADOW] checkout hook failed — LIVE UNAFFECTED")


def shadow_settle(staff: dict, shift_date, normal_len, pb_before, reason,
                  live_worked, live_ot_banked, live_pb_cleared, ext_worked=None) -> None:
    """Run core's checkout-SETTLE math on the SAME real redefine checkout + record core-vs-live (the
    money split: OT banked / payback cleared). Best-effort + fully isolated; no-op unless shadow_run=on.
    `live_worked` is the worked-minutes live computed (used as the shared input so a ±1 worked-rounding
    nuance can't masquerade as a settle-logic mismatch). A PAYBACK-SLOT repays via an ext-worked window
    core doesn't model yet (roadmap #5) → recorded informational (never a false cut-over alarm)."""
    if not shadow_enabled():
        return
    try:
        from core.shadow import compare_settle, record_settle_info
        who = staff.get("call_name") or staff.get("canonical_name") or staff["id"]
        live = {"worked": int(live_worked), "ot_banked": int(live_ot_banked),
                "pb_cleared": int(live_pb_cleared), "reason": reason or "redefine"}
        if (reason or "") == "payback slot":
            # roadmap #5 CLOSED: core now scores a payback-slot settle (the EXTENSION worked clears the
            # debt FIRST; a slot never banks OT). COMPARE when live passed the ext_worked it measured;
            # fall back to informational only if it didn't (so a ±1 worked-rounding nuance can't masquerade).
            if ext_worked is not None:
                from core.settle import settle_payback_slot
                out = settle_payback_slot(int(ext_worked), int(pb_before or 0))
                new = {"worked": int(live_worked), "ot_banked": out["ot_banked"], "pb_cleared": out["pb_cleared"]}
                agree = compare_settle("twb", staff["id"], live, new, source="live")
                logger.info("[SHADOW] settle (payback-slot) %s — %s", "AGREE" if agree else "MISMATCH", who)
            else:
                record_settle_info("twb", staff["id"], live, "payback-slot settle: no ext_worked provided")
                logger.info("[SHADOW] settle (payback-slot, informational) — %s", who)
            return
        from core.settle import settle_shift
        out = settle_shift(int(live_worked), int(normal_len or 0), int(pb_before or 0),
                           bank_min=0, bank_cap_min=10**9)   # uncapped → parity with live's gm_bot.ot.settle_shift
        new = {"worked": int(live_worked), "ot_banked": out["ot_banked"], "pb_cleared": out["pb_cleared"]}
        agree = compare_settle("twb", staff["id"], live, new, source="live")
        if agree:
            logger.info("[SHADOW] settle AGREE — %s", who)
        else:
            logger.warning("[SHADOW] settle MISMATCH — %s | live=%s new=%s", who, live, new)
    except Exception:
        logger.exception("[SHADOW] settle hook failed — LIVE UNAFFECTED")
