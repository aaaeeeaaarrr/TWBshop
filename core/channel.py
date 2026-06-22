"""core.channel — the channel-agnostic command spine (platform principle #1, docs/PLATFORM_VISION.md).

The brain holds NO channel code. A channel adapter (Telegram, web, app, …) translates its native event
into a neutral (command, params) and calls handle(); the core runs; the adapter renders the neutral
result however that channel likes. This is the single surface the onboarding wizard and every new channel
plug into — "Telegram? web? both?" becomes config, not code. Per-tenant settings arrive in `params`
(the adapter loads them from the tenant config; defaults = TWB's).
"""
from core.attendance import check_in, check_out, verdict


def handle(org_id: str, command: str, params: dict) -> dict:
    """Execute a channel-neutral command. `params` is a plain dict — never a Telegram/HTTP object. Returns
    a neutral result dict {ok: bool, ...} the calling adapter renders. Unknown command / missing param =
    a clean error, never an exception across the channel boundary."""
    try:
        if command == "verdict":                       # pure query — no DB
            st, late, early = verdict(params["when"], params["start_dt"],
                                      params.get("tz", "Asia/Phnom_Penh"),
                                      params.get("grace_min", 5), params.get("early_bonus_min", 5))
            return {"ok": True, "state": st, "minutes_late": late, "minutes_early": early}
        if command == "check_in":
            r = check_in(org_id, params["staff_id"], params["when"], params["work_start"],
                         params["work_end"], params.get("tz", "Asia/Phnom_Penh"),
                         grace_min=params.get("grace_min", 5),
                         early_bonus_min=params.get("early_bonus_min", 5))
            return {"ok": True, **r}
        if command == "check_out":
            r = check_out(org_id, params["staff_id"], params["when"], params["work_start"],
                          params["work_end"], params.get("tz", "Asia/Phnom_Penh"))
            return {"ok": True, **r}
        return {"ok": False, "error": "unknown command: %s" % command}
    except KeyError as e:
        return {"ok": False, "error": "missing param: %s" % (e.args[0] if e.args else e)}
