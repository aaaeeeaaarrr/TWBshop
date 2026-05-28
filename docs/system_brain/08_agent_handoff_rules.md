# 08 — Agent Handoff Rules

This file defines what any new coding agent (Codex, a new Claude session, a contractor) may and may not do when working on this codebase. Read before touching any module.

This file will become `AGENTS.md` at the root when the system is handed off for review or refactoring.

---

## What this system is

Not a hiring app. Not a bot. One operating intelligence layer over a Phnom Penh bakery.

Hiring, staff Telegram behavior, attendance, trial outcomes, salary, POS cashier activity, customer orders, and supplier pricing are all connected because they are connected in real life. Do not optimize one module in isolation. A change to the hiring scoring rubric may affect how trial outcomes are interpreted. A change to the ops_messages schema may break evidence references in hiring assessments.

Read `docs/system_brain/00_operating_philosophy.md` before writing any code.

---

## What you MAY do

- Fix bugs in existing logic
- Add tests (pure unit tests preferred; DB-required tests clearly marked)
- Add new questions to the quiz bank via idempotent migrations
- Add new fields to existing tables via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- Improve error handling, logging, and timeout behavior in the bots
- Refactor within a single module without changing its public interface
- Add new modules in the correct location following the existing repo structure

---

## What you MUST NOT do

### People and identity
- **Never merge two person records** without explicit `confidence = 'confirmed'` evidence. Phan Piseth (Seth), Piseth Vinal (Hikaru), and Mr Pisey (SAM kitchen) are three different people. The alias table exists precisely because names overlap.
- **Never auto-resolve an alias to a candidate** using only a name-similarity heuristic. Always require a confirming source (self-introduction, unambiguous supervisor reference, or explicit owner confirmation).
- **Never delete a `hiring_candidates` row** or a `hiring_feedback_points` row without explicit owner instruction. Evidence records are permanent unless explicitly retracted.

### Salary and privacy
- **Never include E-T2 answers in any group-facing output.** E-T2 contains salary history and is marked `answer_sensitivity = 'owner_only'`.
- **Always call `filter_shareable_answers()` before sending any answer dict to a group chat or management summary.**
- **Never add a new question that captures salary, compensation, debt, or personal finances** without also adding its ID to `OWNER_ONLY_QUESTION_IDS` in `hire_bot/questions.py` and writing a test.
- **Supervisor/senior/chef salary is owner-only.** It must never appear in any Telegram group message, bot output, or scheduled report. If unsure about a person's tier, treat as owner-only.

### Hiring bot behavior
- **Never make hiring questions AI-generated at runtime.** Questions are seeded from the DB. The rubric is curated. AI is used for scoring analysis, not for generating questions on the fly.
- **Never bypass the confirmation gate** in any ordering or session flow. The gate is not optional.
- **Never skip trigger evaluation.** E-T1, E-T2, and E-T3 are rule-based and evaluated once after `PART_E_ALWAYS[-1]`. Do not evaluate earlier (inputs not yet available) or skip (structured answers are authoritative).
- **Never hardcode a question ID like "E-A5" in bot logic.** Use `PART_E_ALWAYS[-1]` or equivalent so Part E sequence changes do not require bot code changes.

### Schema and migrations
- **Every schema change must be a versioned migration** in `migrations/`, named `YYYY_MM_DD_description.sql`.
- **Every migration must be idempotent.** Use `ON CONFLICT DO UPDATE`, `ADD COLUMN IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS`, and conditional `DO $$ ... IF EXISTS ... $$` blocks for renames.
- **Never modify the DB schema directly on the server.** Run the migration file.
- **Never drop a column or table** without an explicit instruction from the owner. Renaming is acceptable with a migration.
- **After any schema change, warn** that the migration needs to be run on the server before pushing related code.

### Secrets and credentials
- **Never commit secrets.py to the main repo.** It lives in `twbshop-secrets` only.
- **Never hardcode any API key, token, connection string, or password** anywhere outside `secrets.py`.
- **Never print or log** DATABASE_URL, ANTHROPIC_API_KEY, BOT_TOKEN, or any other credential.

### AI usage
- **All Claude API calls go through `shared/ai_client.py`.** No module imports the `anthropic` SDK directly.
- **AI is used for analysis, not for live decisions.** The bot never asks AI what question to send next or whether to approve a session.
- **When ANTHROPIC_API_KEY is empty, the system must degrade gracefully,** not crash. The free-first architecture rule is permanent.

---

## Before touching these files specifically

| File | Why it's sensitive |
|------|--------------------|
| `hire_bot/questions.py` | Contains PART_E_ALWAYS, trigger logic, OWNER_ONLY_QUESTION_IDS. Changes here affect bot flow, tests, and privacy enforcement simultaneously. |
| `hire_bot/sessions.py` | DB transaction layer. SELECT FOR UPDATE prevents double-resume. record_answer has check-before-insert. Do not simplify these — they prevent race conditions in real candidate sessions. |
| `hire_bot/scorer.py` | Phase 2 contradiction detection logic is intentionally narrow. "Wrong tick + bad written = consistent failure, not contradiction" is the correct behavior. Do not flag consistent failures. |
| `migrations/` | All migrations must be idempotent. Test by re-running on the server before committing. |
| `shared/ai_client.py` | The only file that imports anthropic SDK. Changing this affects all AI features across all bots. |
| `config.py` | Contains chat_ids for all monitored groups. Getting a chat_id wrong sends messages to the wrong group. |

---

## Test expectations

- Part E trigger logic: `tests/test_part_e.py` — 35 tests, no DB required, must all pass before any Part E change is merged
- Scoring logic: `tests/test_hire_scorer.py` — run with `python3 tests/test_hire_scorer.py` (not pytest; requires DB on server)
- Run `python3 -m pytest tests/test_part_e.py -v` on the server after any deployment

---

## What "production ready" means here

A feature is production-ready when:
1. It has unit tests covering its core logic
2. The migration is idempotent and has been re-run successfully on the server
3. Salary and privacy filters have been applied where applicable
4. The bot degrades gracefully if an API call fails
5. The owner has run at least one manual test of the happy path

"It passed tests locally" is not production-ready.
