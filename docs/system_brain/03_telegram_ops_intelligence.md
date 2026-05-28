# 03 — Telegram Ops Intelligence

## The groups and what they contain

| Group | chat_id | What happens there | Messages imported |
|-------|---------|-------------------|------------------|
| Stock Checks | -1003952029131 | Staff photo submissions: workstation, fridge, stock sheets. GM bot is a member and monitors photos. | 5,276 (Nov 2025 – May 2026) |
| Supervisors TWB | -4980513319 | Supervisor attendance reports: lateness, payback, no-shows, excuses. Primary source for staff behavior evidence. | 323 (Jun 2025 – May 2026) |
| Management | (confirmed) | Owner-level decisions, policy, salary discussions, escalations. | 538 (May 2023 – May 2026) |
| COMMS & Transfers | (confirmed) | Inter-location coordination, delivery, stock transfers. | Monitored |
| TWB REPORT | -5136886404 | Daily expense receipts submitted as photos. GM bot checks clarity and replies in-thread. | Active |

The GM bot is a **member** of all groups. It reads messages and photos silently, except in TWB REPORT where it replies in-thread on unclear receipts.

## The ops_messages table

All messages from all monitored groups flow into `ops_messages`:

```
id          bigint     — internal primary key (used as ops_message_row_id in evidence refs)
message_id  bigint     — Telegram's own message_id (used for in-thread replies)
chat_id     bigint     — which group
sender_id   bigint     — Telegram user ID
sender_name text       — Telegram display name at time of message
text        text       — message content
media_type  text       — photo, document, etc.
sent_at     timestamptz
```

`id` and `message_id` are different columns. This has caused confusion. `id` is the row's internal PK used in foreign key references. `message_id` is Telegram's number used when the bot needs to reply to a specific message.

## Telethon listener

The listener runs as the owner's Telegram account (not a bot), so it can read message history in any group the owner is a member of. It streams all new messages into `ops_messages` in real time. Historical groups were imported via one-time scripts.

The listener is separate from the GM bot. The GM bot acts (posts, replies). The listener only reads.

## GM bot behavior

The GM bot (`run_gm_bot.py`, systemd: `twbshop-gm`) does three things:

**1. Photo analysis — concerns:**
Every photo posted in Stock Checks triggers AI vision analysis. If the photo shows something concerning (dirty workstation, low stock, wrong setup), the GM bot:
- Creates a concern record in `gm_concerns`
- Sends a concern card to the owner's private chat with [✓ All good] / [🚨 Real issue] / [📚 Teach bot] buttons
- [✓ All good] closes the concern
- [🚨 Real issue] flags it for tracking
- [📚 Teach bot] adds a suppression rule to `gm_rules` so similar photos are ignored in future

The `/review` command resends any concern that was sent but never had a button tapped.

**2. Receipt checking — TWB REPORT:**
Every photo in the REPORT group is analyzed for clarity: is the total amount readable? Are the line items visible? If unclear, the GM bot replies in-thread (using Telethon for thread replies, not Bot API — regular groups have a message ID mismatch between MTProto and Bot API). Past clarification Q&As are stored in `receipt_clarifications` and injected into the AI prompt as few-shot examples.

**3. Proposals and approvals:**
The `/check` command triggers AI clustering of accumulated concerns into improvement proposals. Proposals are reviewed by the owner with [Approve] / [Skip] / [✏️ Refine] buttons. Approved proposals go into `/approved`. The `/points` command shows a monthly leaderboard. Refinement uses Claude Opus with stacked note history and conflict detection.

## Staff behavior evidence from ops messages

The Supervisors group is the richest source of real staff behavior data. Supervisors report lateness, payback hours, no-shows, and excuses in natural language. The system does not parse these automatically — they are imported manually into `hiring_feedback_points` linked to specific `ops_messages` rows via `hiring_assessment_message_refs`.

Each evidence link stores:
- `ops_message_row_id` — the `ops_messages.id` of the specific message
- `telegram_message_id` — Telegram's `message_id` for display/linking
- `finding_id` — which specific finding this message supports
- `confidence` — confirmed / likely / inferred
- `notes` — the exact quoted text and interpretation

One message can support multiple findings (Seth's May 27 Met Solina message supports both "no_show_exam_claim" and "rotating_excuse_pattern"). The UNIQUE constraint is `(assessment_id, finding_id, chat_id, ops_message_row_id)` — per finding, not per message.

## Staff alias resolution in ops messages

Supervisors do not use real names consistently. "Mr Piseth," "pisey," "Sith," and "Seth" have all appeared in the Supervisors group for the same person. Before drawing conclusions from an ops message, resolve the sender name and subject name through `staff_identity_aliases`.

SAM PHARM is a recurring sender whose messages refer to people on the SAM side of the kitchen. When SAM PHARM writes "Mr pisey," it may refer to SAM's own Mr Pisey, not to Seth. Cross-reference date, context, and known incidents before assigning confidence.

## What is not yet automated

- Alias resolution is manual. There is no NLP running on `ops_messages` to auto-detect who a message is about.
- Attendance pattern detection is manual. Finding "Seth was late 4 times in 3 months" requires a human looking at the data.
- The long-term goal is a weekly digest that surfaces patterns automatically: who appeared most in supervisor reports, what types of incidents, cross-referenced with quiz predictions.

## The connection to hiring

When a staff member has a quiz attempt and also appears in ops messages, the two records can be linked:
- Their `candidate_id` appears in `staff_identity_aliases` with their Telegram name
- Their `ops_messages` rows are findable by matching `sender_name` or `sender_id` against the alias table
- Their `hiring_feedback_points` can reference specific `ops_messages` rows as evidence

Seth is the first full example: candidate_id=27, assessment_id=5, 6 findings, 12 message refs, 5 aliases. The quiz predicted reliability risk. The ops messages confirmed it with dated, supervisor-sourced evidence.
