"""core.approvals — the pure APPROVAL-LADDER rule (channel-agnostic, config-driven). For a still-PENDING
approval request it decides the next action from elapsed time + re-pings already sent: re-ping the
non-responders, escalate to the owner, expire (the request's window has passed), or wait. The live
gm_bot job EXECUTES the action (delete-old + send-new ping, escalate DM, expire); this is the
shadow-parity-tested brain. Config comes from tenant_config.approval_rule(org, kind). (owner Jun 23)
"""


def reping_decision(created_at, now, pings_done: int, escalated: bool, cfg: dict,
                    window_passed: bool) -> str:
    """Return 'expire' | 'reping' | 'escalate' | 'wait'.
    - window passed + cfg.expire_when_window_passes → 'expire' (moot — e.g. the AL date is gone).
    - else if more re-pings are DUE (one every cfg.reping_hours, capped at cfg.reping_max) than have been
      sent → 'reping' (the job sends the next one to the non-responders, deleting their previous).
    - else if the max re-pings are done, not yet escalated, and cfg.escalate_to_owner_after_max → 'escalate'.
    - else 'wait'."""
    if window_passed and cfg.get("expire_when_window_passes"):
        return "expire"
    reping_hours = cfg.get("reping_hours", 6)
    reping_max = cfg.get("reping_max", 4)
    elapsed_h = (now - created_at).total_seconds() / 3600.0
    due = min(int(elapsed_h // reping_hours), reping_max) if reping_hours > 0 else 0
    if due > pings_done:
        return "reping"
    if pings_done >= reping_max and not escalated and cfg.get("escalate_to_owner_after_max"):
        return "escalate"
    return "wait"
