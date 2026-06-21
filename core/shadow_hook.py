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


def shadow_checkin(staff: dict, when_dt, live_state, live_late, live_early) -> None:
    """Run core.check_in for TWB on the SAME check-in event + record new-vs-live. Best-effort + isolated:
    any failure is swallowed and logged as [SHADOW] (live is never affected). No-op unless shadow_run=on."""
    if not shadow_enabled():
        return
    try:
        from core.attendance import check_in
        from core.shadow import compare_checkin
        ls = _STATE_MAP.get((live_state or "").strip(), live_state)
        res = check_in("twb", staff["id"], when_dt,
                       staff.get("work_start"), staff.get("work_end"), "Asia/Phnom_Penh")
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
