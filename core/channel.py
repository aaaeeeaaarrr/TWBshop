"""core.channel — the channel-agnostic command spine (platform principle #1, docs/PLATFORM_VISION.md).

The brain holds NO channel code. A channel adapter (Telegram, web, app, …) translates its native event
into a neutral (command, params) and calls handle(); the core runs; the adapter renders the neutral
result however that channel likes. This is the single surface the onboarding wizard and every new channel
plug into — "Telegram? web? both?" becomes config, not code. Per-tenant settings arrive in `params`
(the adapter loads them from the tenant config; defaults = TWB's).
"""
from core.attendance import check_in, check_out, verdict


def _verdict_settings(org_id):
    from core.tenant_config import verdict_cfg   # lazy — keeps the brain free of import-time coupling
    return verdict_cfg(org_id)


def handle(org_id: str, command: str, params: dict, config: dict = None) -> dict:
    """Execute a channel-neutral command. `params` is a plain dict — never a Telegram/HTTP object. The
    tenant's verdict CONFIG (grace/early threshold) is applied automatically (loaded for `org_id`, or pass
    `config`={grace_min, early_bonus_min} to skip the DB); `params` may override per-call. Returns
    {ok: bool, ...} the adapter renders. Unknown command / missing param = a clean error, never an
    exception across the channel boundary."""
    v = config if config is not None else _verdict_settings(org_id)   # the verdict settings
    grace = params.get("grace_min", v.get("grace_min", 5))
    early = params.get("early_bonus_min", v.get("early_bonus_min", 5))
    tz = params.get("tz", "Asia/Phnom_Penh")
    try:
        if command == "verdict":
            st, late, early_m = verdict(params["when"], params["start_dt"], tz, grace, early)
            return {"ok": True, "state": st, "minutes_late": late, "minutes_early": early_m}
        if command == "check_in":
            r = check_in(org_id, params["staff_id"], params["when"], params["work_start"],
                         params["work_end"], tz, grace_min=grace, early_bonus_min=early)
            return {"ok": True, **r}
        if command == "check_out":
            r = check_out(org_id, params["staff_id"], params["when"], params["work_start"],
                          params["work_end"], tz)
            return {"ok": True, **r}
        return {"ok": False, "error": "unknown command: %s" % command}
    except KeyError as e:
        return {"ok": False, "error": "missing param: %s" % (e.args[0] if e.args else e)}
