# 01 — People and Staff Model

## Three categories of people

**Candidates** — applicants going through the hiring process. They may become staff; they may not. Their quiz answers, Part E facts, and any paper assessment findings are stored even before they are hired. If they are hired and later assessed, their candidate record links to both the quiz attempt and the ops-side assessment.

**Staff** — current employees. They appear in Telegram group messages, payroll records, photo submissions, attendance reports, and supervisor notes. They may also have a quiz attempt if they were hired after the hiring bot was live, or a paper-based assessment if imported from historical review.

**Supervisors and management** — senior staff who report on others. Their messages are the primary source for attendance findings (lateness, payback, no-shows). They are also subject to the system's own assessment — a supervisor's reliability in reporting, accuracy, and response time is tracked.

## Entity isolation is critical

The same real name can appear in different spellings, abbreviations, or nicknames across different groups and time periods. The system must never merge two distinct people because their names look similar.

Three known people who must never be merged:

| Person | Real name | Also known as | Role |
|--------|-----------|---------------|------|
| Seth | Phan Piseth | Seth 🫵, Mr Piseth, Mr pisey (SAM PHARM typo), Mr Sith (typo) | Day-shift service, existing staff |
| Hikaru | Piseth Vinal | Hikaru | Night bakery staff |
| Mr Pisey (SAM) | Unknown | Mr Pisey | SAM kitchen side, different operation |

"Piseth" and "Pisey" appear from multiple senders referring to multiple people. Confidence level (confirmed / likely / inferred) must be recorded on every alias. Do not assume.

## Staff identity aliases table

`staff_identity_aliases` stores the mapping between a real person and every form their name appears in:

- `candidate_id` — links to `hiring_candidates`
- `alias_text` — the string as it appeared (e.g. "Mr pisey", "Seth 🫵")
- `telegram_sender_name` — the Telegram display name of whoever wrote the message (for context: "SAM PHARM" often wrote "pisey")
- `chat_id` — which group the alias was seen in
- `confidence` — `confirmed` (self-introduction or explicit reference), `likely` (strong match, one alternate explanation exists), `inferred` (probable but no direct evidence)
- `confirmed_by` — which ops_messages row, or which person, confirmed the identity

When analyzing ops messages, always resolve aliases before drawing conclusions. A message about "Mr pisey" late is ambiguous; the same message in the Supervisors group about the day-shift service team, cross-referenced with the date and context, becomes likely = Seth.

## Salary tiers and visibility

Two tiers with different visibility rules:

**Tier 1 — Regular new staff:** Salary can be discussed in the management group. Storing and sharing is acceptable.

**Tier 2 — Supervisors, seniors, chefs, and above:** Salary is owner-only. Must never appear in any Telegram group message, any management summary, or any bot output to a group chat. The `answer_sensitivity = 'owner_only'` flag in `hiring_quiz_questions` covers E-T2 (salary breakdown during hiring). The `filter_shareable_answers()` function in `questions.py` enforces this at the code level.

This rule does not change based on context. If unsure which tier someone belongs to, treat as owner-only.

## Key tables

| Table | Purpose |
|-------|---------|
| `hiring_candidates` | One row per person, regardless of how many assessments or quiz attempts they have |
| `staff_identity_aliases` | Name/alias resolution with confidence scoring |
| `hiring_quiz_attempts` | One row per quiz session (a candidate may have multiple if they resume or retry) |
| `hiring_assessments` | Paper-based or ops-evidence assessments, separate from the quiz bot |
| `hiring_feedback_points` | Individual findings from any assessment (structured, linked to evidence) |

## The candidate → staff transition

When a candidate is hired, they do not get a new row in a separate staff table. The `hiring_candidates` record is the persistent identity. Their trial outcome is recorded against their assessment. Their ops-side Telegram behavior links to the same `candidate_id` via `staff_identity_aliases`. Over time, a single person accumulates:

- Quiz answers (if bot-hired)
- Paper assessment findings (if legacy or supplemental)
- Ops message evidence (attendance, behavior, supervisor reports)
- Trial outcome (pass/fail/conditional, with notes)
- Salary tier and history (owner-only layer)

This is the intended end state. Not all of it is built yet. The schema is designed to hold it.
