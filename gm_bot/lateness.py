"""
Lateness / pay-back escalation ladder — pure decision logic + text builders.

When a senior reports a staff member late/absent without a pay-back day, the GM
asks the senior when. The ladder then:
  - senior asked, no answer after 30 min  -> ask the whole group (reply to the case)
  - group asked, no answer after 24 h      -> private message to the owner

Pure functions only — no DB, no Telegram, no AI. The job in bot.py drives it.
Mention strings (which may contain HTML tg://user links) are passed in by the caller.
"""
from __future__ import annotations

from datetime import datetime, timedelta

GROUP_ASK_AFTER = timedelta(minutes=30)
ESCALATE_AFTER  = timedelta(hours=24)

# Case status values
AWAITING_PAYBACK = "awaiting_payback"   # GM asked the reporting senior
GROUP_ASKED      = "group_asked"        # GM asked the whole group
RESOLVED         = "resolved"
ESCALATED        = "escalated"


def decide_lateness_action(status: str,
                           asked_senior_at: datetime | None,
                           asked_group_at: datetime | None,
                           now: datetime) -> str:
    """Decide the next ladder step for one open case.

    Returns one of:
      'ask_group' -> 30 min elapsed since the senior was asked; ask the whole group
      'escalate'  -> 24 h elapsed since the group was asked; tell the owner
      'wait'      -> nothing due yet
      'none'      -> already resolved/escalated
    """
    if status in (RESOLVED, ESCALATED, "closed"):
        return "none"
    if status == AWAITING_PAYBACK:
        if asked_senior_at is not None and (now - asked_senior_at) >= GROUP_ASK_AFTER:
            return "ask_group"
        return "wait"
    if status == GROUP_ASKED:
        if asked_group_at is not None and (now - asked_group_at) >= ESCALATE_AFTER:
            return "escalate"
        return "wait"
    return "wait"


# ── Message builders ──────────────────────────────────────────────────────────
# reporter_mention / late_mention are pre-formatted strings (may contain HTML
# tg://user mentions). Send these with parse_mode=HTML.

def ask_senior_text(reporter_mention: str, late_mention: str) -> str:
    return "%s when will %s pay back the missed time?" % (reporter_mention, late_mention)


def ask_group_text(late_mention: str) -> str:
    return "Does anyone know when %s will be paying back the missed time?" % late_mention


def escalation_text(chat_title: str, late_name: str,
                    reporter_name: str | None, case_excerpt: str | None) -> str:
    """Owner DM when 24 h pass with no pay-back day."""
    lines = [
        "⏰ Pay-back unanswered (24h)",
        "Group: %s" % (chat_title or "?"),
        "Late: %s" % (late_name or "?"),
    ]
    if reporter_name:
        lines.append("Reported by: %s" % reporter_name)
    lines.append("No pay-back day was given by the senior or the group.")
    if case_excerpt:
        lines.append("Original: %s" % case_excerpt[:200])
    return "\n".join(lines)
