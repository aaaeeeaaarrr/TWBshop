# GM bot — interaction map: Brain vs AI (and which model)

> Audit of every GM interaction. **Brain** = pure deterministic logic, no AI, free. **AI** = a Claude
> call (costs money). Models are exactly what's in `shared/ai_client.py` today. When `ANTHROPIC_API_KEY`
> is empty, every AI feature auto-falls back to keyword/manual.

**Models in use (GM):**
| Tag | Model | Used for (rough) |
|----|-------|-------|
| 🟢 Brain | — (logic) | all attendance flows, geofence, schedules, slots, ladders |
| 🔵 Haiku 4.5 | `claude-haiku-4-5-20251001` | cheap classify/extract from text or photos |
| 🟡 Sonnet 4.6 | `claude-sonnet-4-6` (= `CLAUDE_MODEL`) | judgement, OCR reads, warm private replies |
| 🟠 Opus 4.7 | `claude-opus-4-7` | self-improvement proposals + the weekly digest |
| 🔴 Opus 4.8 | `claude-opus-4-8` | highest-stakes: the group call-out wink + medical papers |

---

## A. Attendance system (staff pressing buttons) — BRAIN unless noted
Zero-API by design. The whole private button world runs on logic:
- 🟢 **Check-in / check-out** — geofence (100m), early/late verdict, per-minute scheduler, auto-checkout.
- 🟢 **Late → pay-back** — time buttons, need-ranked slots, ignore-ladder (warn/auto-book).
- 🟢 **Annual Leave** — request, dates/hours, 2-senior approval, balance guard, deduction.
- 🟢 **OT / shift-redefine** — propose, approve, banking, the shield, buyback.
- 🟢 **Day-off swap** — partner-first, then seniors.
- 🟢 **My Schedule** — balances, booked/upcoming indicators.
- 🟢 **Coverage guardrail / ripple** — availability + the "two bakers" rule.
- 🟢 **Group-redirect** (Supervisors) — keyword match, rotating wording. *(zero-API)*
- 🟢 **Auto-welcome / roll-call** — keyword + registry.
- 🟢 **Points** — raw events recorded; values dormant until you activate them.

**AI edges of attendance (rare, only where judgement/vision is needed):**
- 🔴 **Medical paper read** (sick papers → owner card: hospital/doctor/dates/rest-days/part-duty) — Opus 4.8, vision.
- 🟠 **Weekly attendance digest** — Opus 4.7. *(this is the one you flagged to re-source for live)*
- 🟡 **Call-out — private DM** (warm "Mondays have been hard lately") — Sonnet 4.6.
- 🔴 **Call-out — group wink** (never names, light to everyone) — Opus 4.8.

## B. Group-comms monitoring (the GM reading chats) — AI
This is the **old / parallel source** that staff button-presses will replace once live:
- 🔵 **Lateness detection from a group message** — Haiku 4.5.
- 🔵 **Pay-back day extraction** from a message — Haiku 4.5.
- 🔵 **Leave-request detection** from a group message — Haiku 4.5.
- 🔵 **Concern / issue detection** (staffing, safety, etc.) — Haiku 4.5.
- 🟡 **Clarification-answer judge** (did the reply actually answer?) — Sonnet 4.6.
- 🔵 **Compose a short reply** to a concern — Haiku 4.5.
- 🟡 **Staff-message check** (live message risk scan) — Sonnet 4.6.

## C. GM self-improvement proposals — AI
- 🟠 **Generate proposals** from accumulated concerns — Opus 4.7.
- 🟠 **Refine a proposal** (with your feedback / conflict-resolve) — Opus 4.7.

## D. Finance / REPORT tracking
- 🟢→🟡 **Daily report parse** — regex/rules first; **Sonnet 4.6** only as fallback when rules miss.
- 🔵 **Receipt photo** (amount + clarity check) — Haiku 4.5.

## E. Stock
- 🔵 **Classify a stock photo** (is this a stock sheet?) — Haiku 4.5.
- 🟡 **Read a stock sheet** (OCR the counts) — Sonnet 4.6.

---

## The headline for go-live
- The **entire staff-facing attendance experience is Brain (free).** AI shows up only at four edges:
  medical papers, the weekly digest, and the two call-out channels.
- Section **B is the bit that shifts**: today the GM spends Haiku/Sonnet *guessing* attendance facts from
  group chatter; once live, those facts come from buttons (Brain), and the AI there becomes mostly
  redundant — so live attendance is *cheaper*, not more expensive.
