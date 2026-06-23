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


def shadow_settle(staff: dict, shift_date, normal_len, pb_before, reason,
                  live_worked, live_ot_banked, live_pb_cleared) -> None:
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
            record_settle_info("twb", staff["id"], live,
                               "payback-slot ext-worked settle not modeled in core yet (roadmap #5)")
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
