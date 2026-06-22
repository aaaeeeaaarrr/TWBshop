"""core.channel — the channel-agnostic command spine (platform principle #1, docs/PLATFORM_VISION.md).

The brain holds NO channel code. A channel adapter (Telegram, web, app, …) translates its native event
into a neutral (command, params) and calls handle(); the core runs; the adapter renders the neutral
result however that channel likes. This is the single surface the onboarding wizard and every new channel
plug into — "Telegram? web? both?" becomes config, not code. Per-tenant settings arrive in `params`
(the adapter loads them from the tenant config; defaults = TWB's).
"""
from core.attendance import check_in, check_out, verdict


def _load_config(org_id):
    from core.tenant_config import get_config   # lazy — keeps the brain free of any import-time coupling
    return get_config(org_id)


def handle(org_id: str, command: str, params: dict, config: dict = None) -> dict:
    """Execute a channel-neutral command. `params` is a plain dict — never a Telegram/HTTP object. The
    tenant's CONFIG (grace/thresholds) is applied automatically (loaded for `org_id`, or pass `config`
    to skip the DB); `params` may override per-call. Returns {ok: bool, ...} the adapter renders. Unknown
    command / missing param = a clean error, never an exception across the channel boundary."""
    cfg = config if config is not None else _load_config(org_id)
    grace = params.get("grace_min", cfg.get("grace_min", 5))
    early = params.get("early_bonus_min", cfg.get("early_bonus_min", 5))
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
