"""
Clarification escalation ladder — pure decision logic + text builders.

When the GM asks something in a group (a math correction "Explain", or a receipt
clarity question), it opens a clarification. This module decides, on each tick,
whether to nudge, escalate to the owner, or wait — and detects when staff say
they are still checking (so we back off).

Pure functions only — no DB, no Telegram. The job in bot.py drives it.

Ladder (owner's spec):
  - No answer after 10 min  -> nudge in the group; repeat every 10 min
  - Staff say "we're checking" -> back off, next nudge in 30 min
  - No real clarification within 2 h -> escalate to owner
"""

from __future__ import annotations

from datetime import datetime, timedelta

NUDGE_INTERVAL_OPEN     = timedelta(minutes=10)
NUDGE_INTERVAL_CHECKING = timedelta(minutes=30)
ESCALATE_AFTER          = timedelta(hours=2)

# Phrases that mean "give us time, we're looking" — back off to the slow cadence.
_CHECKING_PHRASES = [
    "checking", "check now", "i check", "we check", "will check",
    "give us time", "give me time", "give time", "one moment", "moment",
    "wait", "hold on", "let me see", "let me check", "looking", "look now",
    "verify", "verifying", "recount", "count again", "counting", "re check", "recheck",
    # Khmer
    "ពិនិត្យ", "មើល", "រង់ចាំ", "កំពុង",
]


def is_checking_phrase(text: str | None) -> bool:
    """True if the message says they are still checking (not a real answer)."""
    if not text:
        return False
    t = text.strip().lower()
    if not t:
        return False
    return any(p in t for p in _CHECKING_PHRASES)


def decide_ladder_action(
    status: str,
    created_at: datetime,
    now: datetime,
    next_action_at: datetime | None,
) -> tuple[str, datetime | None]:
    """
    Decide what to do for one clarification.

    Returns (action, new_next_action_at) where action is:
      'nudge'    -> send a reminder in the group, schedule next at returned time
      'escalate' -> inform the owner; clarification is done
      'wait'     -> nothing due yet; keep the same next_action_at
      'none'     -> already resolved/escalated; ignore
    """
    if status in ("answered", "escalated", "closed"):
        return ("none", None)

    if now - created_at >= ESCALATE_AFTER:
        return ("escalate", None)

    if next_action_at is None or now >= next_action_at:
        interval = NUDGE_INTERVAL_CHECKING if status == "checking" else NUDGE_INTERVAL_OPEN
        return ("nudge", now + interval)

    return ("wait", next_action_at)


# ── Message builders (plain ASCII for safe display anywhere) ────────────────────

def nudge_text(topic: str, nudge_count: int) -> str:
    """A gentle, escalating reminder. nudge_count is how many have already been sent."""
    base = {
        "report_math": "Still need this corrected, please.",
        "receipt_clarity": "Still need this clarified, please.",
    }.get(topic, "Still waiting on this, please.")
    if nudge_count >= 3:
        return base + " Please reply now or it will be sent to the owner."
    return base


def escalation_text(topic: str, group_name: str, sender_name: str | None,
                    question_text: str, answer_text: str | None) -> str:
    """The owner DM when a clarification times out or an answer doesn't resolve it."""
    who = sender_name or "Staff"
    head = "No clarification after 2h" if not answer_text else "Clarification may not add up"
    lines = [
        f"⏰ {head}",
        f"Group: {group_name}",
        f"Topic: {topic}",
        f"Asked: {question_text}",
    ]
    if answer_text:
        lines.append(f"{who} replied: {answer_text}")
    else:
        lines.append(f"{who} has not replied.")
    return "\n".join(lines)
