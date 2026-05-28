# 05 — Salary Privacy Rules

## The rule

**Two tiers. No exceptions.**

| Tier | Who | Salary visibility |
|------|-----|------------------|
| Regular new staff | Entry-level, service staff, bakers at standard rate | Can be discussed in the management Telegram group. Storing and sharing acceptable. |
| Supervisor, senior, chef, and above | Anyone with team responsibility or above-standard pay | Owner-only. Never in any group chat. Never in any bot message to a group. Never in any summary sent to management. |

If there is any doubt about which tier someone belongs to — treat as owner-only.

## Why this rule exists

Salary information shared in a group creates comparison, resentment, and attrition. The Telegram management group has multiple senior staff as members. If a supervisor's salary appears there — even in a bot summary — it immediately becomes visible to peers who may have different rates. This is not a hypothetical risk; it is the reason the rule was created.

## Where salary data enters the system

**Hiring bot — E-T2:**
When a candidate answers Yes to "Are you currently working elsewhere?" (E-A3b), the bot fires E-T2: last working day, whether employer was told, and a full salary breakdown (base + bonus + food allowance + hours + days). This is marked `answer_sensitivity = 'owner_only'` in `hiring_quiz_questions`.

**Legacy paper assessments:**
Some paper assessments include salary history or current pay rate. These are imported into `hiring_feedback_points` with appropriate severity and must never be included in any group-facing output.

**Trial outcomes:**
If a trial outcome record includes agreed salary, that is owner-only if the person is Tier 2.

## How the system enforces this

**At the question level:**
`hiring_quiz_questions.answer_sensitivity` column — value is `'owner_only'` for E-T2, `'normal'` for everything else.

**At the code level:**
`OWNER_ONLY_QUESTION_IDS` in `hire_bot/questions.py` — a frozenset of question IDs whose answers must not appear in shared output. Currently: `{"E-T2"}`.

`filter_shareable_answers(answers_dict)` in `hire_bot/questions.py` — strips owner_only questions from any answer dict before the dict is used in a group-facing context. This function must be called by every future report builder. It is not optional.

**At the test level:**
Five tests in `tests/test_part_e.py` cover: E-T2 in the owner-only set, filter removes E-T2, filter passes non-sensitive answers unchanged, empty input, all-sensitive input.

## The gap — opt-in enforcement

The current enforcement is opt-in: `filter_shareable_answers()` only works if every future report builder remembers to call it. There is no automatic exclusion at the DB layer.

The correct long-term fix is centralized group-report generation: one function that all bots call to produce any summary that goes to a group chat. That function calls `filter_shareable_answers()` internally, so there is no way to accidentally bypass it.

This should be built when the first hiring report is generated for the management group. Do not build individual report generators in each bot — build one shared report builder in `shared/`.

## What "owner-only" means in practice

Owner-only data goes to:
- `config.OWNER_TELEGRAM_ID` (the owner's personal Telegram account)
- Files on the server that only the owner accesses
- The raw DB (which only the owner can query)

Owner-only data never goes to:
- Any group chat (including management, supervisors, or any staff group)
- Any scheduled bot job that posts to a group
- Any summary, digest, or report sent to a group
- Any Telegram message sent by the bot to anyone other than the owner

## Adding new owner-only questions in the future

If a new question is added to the hiring bot that captures salary, debt, personal financial situation, or anything similarly sensitive:
1. Set `answer_sensitivity = 'owner_only'` in the DB seed (migration)
2. Add the question ID to `OWNER_ONLY_QUESTION_IDS` in `hire_bot/questions.py`
3. Add a test confirming it is excluded from `filter_shareable_answers()`

These three steps must happen together. A DB seed without a code update is not sufficient.
