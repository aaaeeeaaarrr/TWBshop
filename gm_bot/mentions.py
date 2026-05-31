"""Staff mention formatting for GM messages.

Owner rule: whenever the GM tags a staff member, show the name we call them by
next to the account tag — EXCEPT when the call-name already matches the account's
display name, in which case show only the tag.

The tag is a Telegram inline mention (`tg://user?id=<uid>`), which pings the person
and works even when they have no public @username. Send these with parse_mode=HTML.

Pure string helpers; the call-name comes from config, the uid is resolved at the
call site (see gm_get_staff_uid in shared.database).
"""
from __future__ import annotations

import html
import re

import config


def _norm(s: str | None) -> str:
    """Lowercased alphanumerics only — for comparing a call-name to a display name."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def format_mention(uid: int | None, display_name: str, call_name: str | None) -> str:
    """Return an HTML mention string.

    'Seth <a href="tg://user?id=1">Seth 🫵</a>'  when a distinct call-name is known
    '<a href="tg://user?id=1">Norin</a>'          when the call-name == display name
    'Dara'                                          when uid is unknown (plain, escaped)
    """
    display = (display_name or "Staff").strip()
    safe = html.escape(display)
    tag = '<a href="tg://user?id=%s">%s</a>' % (uid, safe) if uid else safe
    if call_name and _norm(call_name) and _norm(call_name) != _norm(display):
        return "%s %s" % (html.escape(call_name), tag)
    return tag


def mention(uid: int | None, display_name: str) -> str:
    """Convenience wrapper: look up the call-name from config, then format."""
    return format_mention(uid, display_name, config.call_name_for(display_name))
