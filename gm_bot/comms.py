"""gm_bot.comms — staff comms-responsiveness escalation (owner: 'the GM complains when staff ignore the group').

DETERMINISTIC, not a text guess. The listener (a real Telegram account in the groups) already RECEIVES who-was-
@-mentioned, who-replied-to-whom, and the real sender id — we now STORE them on ops_messages. So 'a staffer was
@-mentioned (or replied-to) and posted NOTHING after, for longer than the window' is a FACT, matched by Telegram
user id. The gm job feeds these structured messages in and does the sending; this module is the pure brain + the
message templates.

GATED OFF (gm_state comms_escalation_live) until the owner enables it — it nudges real staff: walk it in test-mode
first and review the wording. Honest scope: GROUP MESSAGES only. A 1-to-1 Telegram CALL between two staff is
invisible to the listener (not a party to it); real cellular calls need a phone app — both out of scope here.
"""
from __future__ import annotations
from collections import defaultdict

NUDGE_MIN = 30        # addressed + unanswered this long → a gentle DM to the staffer
ESCALATE_MIN = 90     # still unanswered this long → flag the senior group


def find_unanswered(messages: list, staff_ids: set, now, window_min: int = NUDGE_MIN) -> list:
    """messages: [{id, chat_id, sender_id, text, sent_at(datetime), mentioned_ids:[int], reply_to_sender_id}]
    across the monitored groups, time-ASCending. staff_ids: the Telegram ids we track. Returns the overdue
    cases — a tracked staffer was ADDRESSED (@-mentioned, or someone replied to their message) and posted
    NOTHING in that chat afterward, with the window elapsed: [{chat_id, staff_id, msg_id, text, sent_at,
    age_min}]. Deterministic (Telegram user ids); one case per (message, addressed staffer)."""
    posted = defaultdict(list)                       # (chat_id, staff tg id) -> [sent_at] of their own posts
    for m in messages:
        if m.get("sender_id"):
            posted[(m["chat_id"], m["sender_id"])].append(m["sent_at"])
    out = []
    for m in messages:
        addressed = {mid for mid in (m.get("mentioned_ids") or []) if mid in staff_ids}
        if m.get("reply_to_sender_id") in staff_ids:
            addressed.add(m["reply_to_sender_id"])
        addressed.discard(m.get("sender_id"))        # a staffer addressing themselves isn't 'unanswered'
        for sid in addressed:
            answered = any(t > m["sent_at"] for t in posted.get((m["chat_id"], sid), ()))
            age = (now - m["sent_at"]).total_seconds() / 60.0
            if not answered and age >= window_min:
                out.append({"chat_id": m["chat_id"], "staff_id": sid, "msg_id": m.get("id"),
                            "text": (m.get("text") or "")[:160], "sent_at": m["sent_at"], "age_min": int(age)})
    return out


def stage_for(age_min: int, nudged: bool, escalated: bool,
              nudge_min: int = NUDGE_MIN, escalate_min: int = ESCALATE_MIN) -> str:
    """Next action due for an overdue case: 'nudge' (DM the staffer, once), 'escalate' (flag the senior group,
    once), or 'none'. Nudge FIRST (a wrong nudge is gentle); the louder group-flag waits for escalate_min."""
    if age_min >= escalate_min and not escalated:
        return "escalate"
    if nudge_min <= age_min < escalate_min and not nudged:
        return "nudge"
    return "none"


def nudge_text(name: str) -> str:
    """Gentle DM to the staffer. (Owner: review/adjust this wording in the test-mode walk before go-live.)"""
    return ("🤍 %s — someone's waiting on a reply in the group. Could you take a look when you get a moment?\n"
            "🤍 %s — មានគេកំពុងរង់ចាំចម្លើយនៅក្នុងក្រុម។ សូមជួយមើលនៅពេលទំនេរ។" % (name, name))


def escalation_text(name: str, group_label: str, age_min: int) -> str:
    """Flag to the senior group when a case is still unanswered after escalate_min."""
    return ("⚠️ FYI: %s hasn't replied in %s for ~%d min.\n"
            "⚠️ FYI: %s មិនទាន់ឆ្លើយតបក្នុង %s អស់រយៈពេល ~%d នាទីទេ។"
            % (name, group_label, age_min, name, group_label, age_min))
