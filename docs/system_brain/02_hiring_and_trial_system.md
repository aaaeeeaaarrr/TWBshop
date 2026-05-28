# 02 — Hiring and Trial System

## The full pipeline

```
Application → Bot invite → 111-question quiz → Part E hiring facts
→ Auto-scoring → Semantic contradiction check → Risk profile
→ Human review → Hire decision
→ Trial period → Trial outcome recorded
→ Feedback loop into rubric
```

Each stage produces structured data. The goal is that by the end of a trial, the system has enough linked evidence to answer: did the quiz predict what actually happened?

## The 111-question quiz (Parts A–D)

Four parts, administered sequentially through the Telegram bot with disappearing questions:

| Part | Type | Questions | What it measures |
|------|------|-----------|-----------------|
| A | Yes / No / Not sure (tick) | 60 | Attitude and values across 6 sections: schedule, honesty, customer, quiet-time ethic, team, commitment |
| B | Single-choice scenario | 22 | How they reason through realistic work situations |
| C | Written scenarios | 22 | Free-text judgment, quality of thought, vocabulary |
| D | Ranking + written | 5 | Prioritization instinct, situational reading, self-reflection |

Part A is the tick section. Part C and D are the written section. Contradictions between them are the detection signal: someone who ticks "I always tell my manager about mistakes" but writes "I would fix it quietly and not make it a big deal" is showing a gap between what they know is expected and what they actually do.

The quiz is bilingual (English + Khmer) throughout. Candidates can answer in either language.

## Part E — Hiring facts

Comes after all 111 questions. Not scored — factual collection.

**Always asked (7 questions):**

| ID | Question | Why |
|----|----------|-----|
| E-A1a | Can you start within 3 days? (structured Yes/No/Not sure) | Structured start-gate — replaced keyword guessing. B or C fires E-T3. |
| E-A1 | Exact start date (free text) | Records the specific date; E-A1a already determined the delay signal |
| E-A2 | 30-day availability: which days and hours | Flags blackouts, recurring blocks, schedule conflicts |
| E-A3a | Currently studying? (Yes/No) | Yes fires E-T1 |
| E-A3b | Currently working elsewhere? (Yes/No) | Yes fires E-T2 |
| E-A4 | Known leave/exams/travel next 30 days (free text) | Exam keywords also fire E-T1 |
| E-A5 | Transport and backup plan (free text) | Reliability signal; no backup = risk |

**Conditional triggers (evaluated once after E-A5):**

| ID | Fires when | What it asks |
|----|-----------|-------------|
| E-T1 | E-A3a=Yes OR exam keywords in E-A4 | How many days advance notice for a schedule conflict from exams? (structured choice) |
| E-T2 | E-A3b=Yes | Last working day, employer told?, full salary breakdown (marked owner_only) |
| E-T3 | E-A1a=B/C OR delay keywords in E-A1 | Why can't you start within 3 days? What would help? |

**Always last:**
- E-Final: In your own words, what should management see from you in your first 3 days? (free text, stored for trial comparison)

Trigger state is persisted to `hiring_quiz_attempts.part_e_triggered` (text[]) immediately after evaluation, so bot restarts do not lose state.

## Scoring — three phases

**Phase 1 — Auto-grade (rule-based):**
Every answer with a defined rubric gets `is_correct` and a `score_summary`. Part A yes/no questions are graded against expected answers. Part B single-choice has a correct answer. Part C and D free-text answers get rubric tags. No AI in Phase 1. Run synchronously after quiz completion.

**Phase 2 — Semantic contradiction detection:**
Checks 7 defined contradiction pairs: one Part A tick paired with one Part C or D written answer. Contradiction = tick is CORRECT (candidate knows the right answer) but written answer shows the opposite behavior. This is the liar signal. Consistent failures (wrong tick + bad written) are NOT flagged — they represent honest poor fit, not deception.

Current pairs: A2-Q13/C-Q8, A4-Q34/C-Q12, A4-Q38/C-Q12, A5-Q42/C-Q11, A6-Q58/C-Q16, A6-Q51/D3, and one written/written pair C-Q3/C-Q8.

**Phase 3 — Risk profile:**
Category-level risk assessment: schedule, honesty, quiet_time, experience, commitment. Each can be clean / weak / red_flag. Category overrides: A2-Q13 contradiction → honesty=weak. A2-Q20 wrong → experience=red_flag. Both schedule questions wrong → schedule=red_flag.

## Legacy paper assessments

Before the bot was live, staff were assessed via paper questionnaires reviewed in ChatGPT. These are imported into the same schema using per-person import scripts:

| Person | candidate_id | assessment_id | Status |
|--------|-------------|---------------|--------|
| Vannary | 24 | 2 | Complete — 14 findings, evidence hashed |
| Seth (Phan Piseth) | 27 | 5 | Complete — 6 findings, 12 message refs |
| Norin | TBD | TBD | Pending — 24-point bilingual feedback not yet imported |

The import pattern: paste structured ChatGPT output here → import script creates candidate + assessment + findings + evidence rows in one pass. The goal is a generic importer after 2–3 more person-specific scripts.

## Trial system

After hire, a trial period captures whether the quiz predictions were right:

- `trial_outcomes` table: stores trial result, supervisor notes, quiet_time_behavior, schedule_story_match
- `quiet_time_behavior` — did they actually work during quiet periods without being told, as their quiz predicted?
- `schedule_story_match` — did their stated availability (Part E) match their actual attendance?
- E-Final answer is stored for comparison: what they said management would see vs what management actually saw

The trial outcome links back to `assessment_id` and `attempt_id`. Over time, this creates a rubric validation loop: which quiz questions actually predicted trial outcomes? Which did not? The rubric should evolve.

## Verbal retest flags

Some questions are marked `requires_verbal_retest = TRUE`. These are questions where the tick position is ambiguous (the sheet can slip), or where confirmation in person is needed before escalating a finding. Vannary's A2-Q13 is the standing example: marked risk_critical but confirmation requires the verbal retest question before escalating.

Verbal retest questions are stored in `hiring_feedback_points.interpretation` for the specific finding.

## Follow-up questions

After scoring, the system selects up to 5 follow-up questions based on triggered risk categories. These are sent through the bot as free-text questions after the 111 main questions. The selection logic is in `hire_bot/followups.py`. Follow-ups are bilingual. Eligibility blockers (e.g. honesty=red_flag) get sent before softer probes.
