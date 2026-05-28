# 07 — Current Open Questions

This file tracks decisions not yet made, work not yet done, and things the system does not yet know. Update it as things resolve. Delete rows when resolved — do not leave "completed" items here as a log; that belongs in CLAUDE.md.

**Maintenance rule:** If you are reading this file and a row is resolved, delete it now. Do not add a "completed" column or leave dead rows. This file should always reflect only what is currently open. A file that never shrinks is not being maintained.

---

## Hiring system — blocking for live use

| # | Question | What's needed | Status |
|---|----------|--------------|--------|
| 1 | HIRE_BOT_TOKEN not in secrets | Owner provides the BotFather token; add to twbshop-secrets repo | **Waiting on owner** |
| 2 | End-to-end fake candidate run not done | After token added: run full flow, trigger all 3 Part E triggers, confirm follow-ups, end screen, owner notify, resume | Planned |
| 3 | Salary data E-T2 not tested in group output | No group-facing hiring reports exist yet; test when first report is built | Future |

---

## Hiring system — pending assessments

| # | Person | What's missing | Status |
|---|--------|----------------|--------|
| 4 | Norin | 24-point bilingual feedback not imported into hiring_feedback_points | Pending — no import script yet |
| 5 | 47 draft feedback_points | source_ref and evidence_status = draft_unlinked; need to be linked to quiz question IDs | Pending |
| 6 | Future questionnaire imports | ChatGPT export ZIP with hiring bot questionnaire answers not yet extracted | Waiting on ZIP |
| 7 | Generic importer | After 2–3 person-specific scripts, build one standard-block importer | Future |

---

## Hiring system — scoring and reporting

| # | Question | What's needed | Status |
|---|----------|--------------|--------|
| 8 | Phase 2 async scoring not wired | After complete_session(), kick off detect_semantic_contradictions + build_risk_profile as background job | Not built |
| 9 | Trial outcome loop not started | No trial_outcomes rows exist yet; first hire under the bot system hasn't happened | Future |
| 10 | Rubric validation loop | Do quiz predictions match trial outcomes? Needs 5+ trial outcomes before meaningful | Long term |

---

## Staff and people

| # | Question | What's needed | Status |
|---|----------|--------------|--------|
| 11 | Staff real names for aliases | Real names needed for: Cat, Nakk, NY, O, Pew, Me Me, Boss TT, Chan Oun, Roth, por Khmer Bruce PP | **Waiting on owner** |
| 12 | Seth accountability conversation | Formal conversation not yet held; assessment findings should be updated with outcome | Pending |
| 13 | Vannary evidence storage | 12 photos hashed, on owner's PC (local_to_pc). Move to cloud or server when convenient | Pending |

---

## Ops intelligence

| # | Question | What's needed | Status |
|---|----------|--------------|--------|
| 14 | 383 concern cards unreviewed | Owner reviews in GM chat, taps buttons; /review for missed ones | **In progress** |
| 15 | Supplier price extraction | run_extract_prices.py on server | In progress |
| 16 | Facebook Messenger export | Sara Bologna account export pending; needed for customer history | Waiting on export |
| 17 | Alias resolution is manual | No automated NLP on ops_messages to detect who a message is about | Future |
| 18 | Attendance pattern digest | Automated weekly surfacing of who appeared most in supervisor reports | Future |

---

## Customer and B2B

| # | Question | What's needed | Status |
|---|----------|--------------|--------|
| 19 | Customer reactivation | Extract names and phones from WOC DELIVERY PICTURES photos | Not started |
| 20 | B2B bot rollout | 24+ active B2B customer groups identified; bot not added to any of them yet | Not started |

---

## Infrastructure

| # | Question | What's needed | Status |
|---|----------|--------------|--------|
| 21 | POS direction | Which system? API or file export? Which roles have access? | Not decided |
| 22 | Bakong/KHQR | Merchant QR registration pending — need passport (on other PC) | Blocked |
| 23 | Centralized group-report builder | filter_shareable_answers() is currently opt-in; should be enforced in one shared function | Future — build with first hiring report |

---

## Architectural questions not yet answered

**How does the system handle a staff member who was hired before the bot, has a paper assessment, and later does a bot quiz?**
The schema supports it (separate attempt_id and assessment_id on the same candidate_id), but the report merger is not built. What does a combined view look like? Which source takes precedence?

**When does a trial outcome update a risk profile?**
If someone's quiz predicted schedule=red_flag but they passed the trial with perfect attendance, should the risk profile be revised? Currently nothing writes back to the quiz scoring. The rubric is static.

**What is the escalation path when a finding becomes a formal HR action?**
The system records findings and evidence. But who is notified when a finding reaches a threshold? What does "Seth: formal accountability conversation" look like as a system event, not just a CLAUDE.md note?

**How does the system know when an alias is wrong?**
If "Mr pisey" (SAM PHARM) turns out to be a different person than Seth, a finding may be wrongly attributed. There is no correction mechanism today. Future: findings should have a `disputed` flag and a correction log.
