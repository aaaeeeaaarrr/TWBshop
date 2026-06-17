"""Runtime guard: refuse to start a live Telegram/Telethon poller off production.

WHY (the double-poller hazard): two simultaneous long-polls on ONE bot token make
Telegram hand each update to only one of them — so a stray local/dev poller silently
*steals* live updates from the production server (a missed gm check-in, a lost order).
One Telethon user-session likewise cannot be used by two clients at once.

GUARD: only a process that explicitly declares itself the production poller may start.
The server's systemd units set ``TWBSHOP_POLL_OK=1``. Any other machine must use a
DEV bot token and opt in with ``ALLOW_LOCAL_POLLING=1`` — never the live token.

This is mechanical (a hard exit), not a doc note, because it must protect the live
system even when a run_*.py script is launched outside Claude Code.
"""
import os
import sys


def assert_polling_allowed(service: str) -> None:
    """Exit unless this machine is authorized to poll a live token."""
    if os.environ.get("TWBSHOP_POLL_OK", "").strip() == "1":
        return  # the production server (its systemd units set this)
    if os.environ.get("ALLOW_LOCAL_POLLING", "").strip() == "1":
        return  # deliberate local opt-in — use a DEV token, never the live one
    sys.exit(
        "\n  REFUSING to start the %s poller on this machine.\n"
        "  TWBSHOP_POLL_OK is not set, so this is not the production server.\n"
        "  Two pollers on one token make Telegram DROP live updates (lost check-ins/orders).\n"
        "  • Production server: systemd sets TWBSHOP_POLL_OK=1 (never triggers there).\n"
        "  • Local loop: use a DEV bot token and set ALLOW_LOCAL_POLLING=1.\n"
        % service
    )
