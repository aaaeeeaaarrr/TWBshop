# 00 — Operating Philosophy

## What this system is

This is not a collection of bots. It is one operating intelligence layer over a Phnom Penh bakery operation. The individual bots — retail ordering, B2B wholesale, GM monitoring, hiring — are access points into that layer, not separate products.

The owner cannot be physically present everywhere at once. The system is the owner's eyes, memory, and judgment — extended across Telegram groups, hiring conversations, staff behavior, supplier pricing, customer orders, and trial outcomes. Everything feeds into a shared database. Nothing is siloed.

## The Telegram channel is the operating layer

Staff, supervisors, suppliers, and customers all already live in Telegram. They do not use email. They do not use a web portal. The system meets them where they are. New tools do not get their own interface — they extend what already exists in Telegram.

This constraint is a feature, not a limitation. It means zero adoption cost for staff and zero training for customers. It also means the system can observe real behavior — what people actually type in group chats — rather than only what they fill in on forms.

## Free-first architecture

Every feature must work without any API call before any API call is added. The bot handles orders, tracks stock, and routes concerns using rule-based logic. AI (Claude API) is an upgrade layer, not the foundation. If the API key is empty, the system degrades gracefully — it does not break.

This is not a cost-control policy. It is an architectural principle. Systems that depend on AI from the start become untestable and fragile. Systems that add AI on top of solid rule-based logic stay predictable.

## No silent guessing

The system never silently interprets an ambiguous input and acts on it. Every order is restated and confirmed before saving. Every candidate is asked a structured question rather than having keywords scraped from a free-text answer. Every photo concern is reviewed by a human before being flagged as a real issue.

The confirmation gate is the safety mechanism. It is not optional and it is never bypassed for convenience.

## Schema changes are migrations

Every change to the database is a versioned, idempotent SQL migration in `migrations/`. No schema is ever modified directly on the server. Migrations use `ON CONFLICT DO UPDATE` or `IF NOT EXISTS` or conditional `DO $$` blocks so they can be re-run safely. The migration file is the single source of truth for what the DB should look like.

## Secrets live in one place

All credentials, connection strings, and tokens live in `secrets.py`, which is in a separate private repo (`twbshop-secrets`) and never committed to the main repo. If a credential appears anywhere else in the codebase, it must be moved before the next commit.

## The system grows toward interconnection

The long-term goal is that a candidate's quiz answers connect to their Telegram group behavior, trial performance, payroll tier, POS cashier accuracy, mistake history, and attendance record — in one queryable dataset. Each new module is built with that connection in mind. A hiring question about punctuality and a supervisor's attendance report in the ops messages table are about the same thing. The system should know that.
