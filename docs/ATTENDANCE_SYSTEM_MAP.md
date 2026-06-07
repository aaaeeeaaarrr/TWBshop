# Attendance / AL / Lateness — Whole System Map

> Private-DM attendance system. All staff↔GM about attendance happens in **private DM**.
> Status: ✅ built · ⏳ pending build · 🔒 owner input. This is the master picture; full detail +
> every edge in **ATTENDANCE_SYSTEM_DETAILED.md** (the authoritative spec — if the two ever disagree,
> DETAILED wins).
> **CURRENT MODEL (session 28, 2026-06-07/08):** check-in-at-shift-start only (NO whole-shift tracking);
> fully BUTTON-DRIVEN private chat (any text → main menu; one button/row; every submenu starts "←Back";
> long labels never side-by-side). Design 100% decided; what remains is WIRING + dry-run sign-off.

---

## THE GOLDEN RULES (the spine everything obeys)
- **SCHEDULE answers "who should be where"; LOCATION only proves "who actually was."** Never use live
  location to decide availability/presence (it's check-in-only, often off) — that's always a schedule
  question. Location + the on-site senior's word = proof.
- **Four separate ledgers, never mixed:** LATE → time (payback) · NO-SHOW → money+bonus · LEAVE → AL days ·
  PATTERNS → points+call-outs. One misstep = one price in one currency.
- **Informing/declining is FREE; breaking a commitment costs.** (tell-us-early late is cheaper; decline OT
  is free, accept-then-no-show is penalized.)
- **Buttons never block; text-waits expire (30 min) and die on any tap.** Abandoned flows never deadlock.
- **Zero-API:** all flows = buttons + pure logic. AI only at the edges (group-redirect detect, call-outs,
  undated-papers, weekly digest). Telegram messages/edits are free; "API $" only ever = AI calls.
- **Every staff-facing string is bilingual EN + KH** (ChatGPT-verified). Dates/times/numbers stay Latin.
- **Reasons shown everywhere** (owner+seniors+Supervisors group) verbatim, EXCEPT family-death cause is
  owner+Tyty only. Frequencies learned → autonomous call-outs.

---

## LAYER 0 — Identity & schedule (foundation)
- **staff_registry** ✅ — canonical/call name, aliases, telegram uid(s), phone, status, org (TWB/Delis),
  is_senior, work_start/end, day_off, al_left, expertise, salary/bonus/first+second pay.
- 33 active, all uid-bound, all pressed Start. Tyty = co-owner exempt. Delis excluded (separate team).
- **Coverage requirements table** ✅ (owner interview) — front/kitchen 3–4 busy / 2–3 quiet; night bakery
  3 (4 Fri/Sat); bar ≥1 always; prep ≥2 (10–19h); cake = Thyda+Tyty. Roster verified = perfect week.

## LAYER 1 — Channels
- **Private DM** staff→GM, button menus: Check-in · Late · About Work (Rules + Give OT seniors) ·
  About Me (AL · Special Leave · Change day off · OT · My schedule).
- **Live location** = CHECK-IN at shift start (in 100m TWB zone). No continuous requirement; voluntary
  always-on silently stored (location_pings).
- **Group AL/lateness post** → GM replies tagging @twb_gm_bot "message me directly" (EN+KH), doesn't process.
- **Auto-welcome** ✅ — registered staff joining an internal group + not yet Started → in-group press-START
  nudge; unknown joiner → one-time owner note.

## LAYER 2 — Reading (AI only where needed)
- Haiku: group-redirect detect. Sonnet: clarification answer-judge ✅ + private call-out DM.
- Opus: group call-out · undated-papers advice · weekly digest. Understand-without-reply (plain msg
  resolves the most-recent open case). 👍 ack on understood non-problem replies.

## LAYER 3 — Logic (deterministic)
- Geofence ✅ 100m. Availability/coverage ✅ (schedule-based, excludes day-off + AL). Overlap incl
  overnight ✅. Lateness kind ✅. Approval counting (≥2 seniors) ⏳. AL ledger: deduct-when-date-passes ✅
  + monthly +1.5 accrual ⏳. Ripple check ⏳. ⚠️ outside-budget code is DEAD (whole-shift model dropped).

## LAYER 4 — Actions
- Lateness → Supervisors heads-up (name+time) + reason follows on arrival. AL → senior cards (✅/❌ +
  availability + reason) → 2✅ → Supervisors notice (range + reason + day-off + back-at-work). Check-in →
  T−10/T0/T+5 prompts (each carries [I'm late] while undeclared) + check-out (06:00→+10→+30 close).
  Call-outs → Sonnet DM + Opus group, CC owner+Tyty.

## LAYER 5 — Records & learning
- Tables: al_requests (+deducted_days), al_approvals, lateness_records, attendance_sessions,
  gm_report_docs; ⏳ gm_flow_state (state persistence), payback_wallets, points_events, location_pings.
- Weekly digest ✅. Dossiers + frequency call-outs ⏳. Points CATALOGUED, PENDING owner activation.

---

## THE SUB-SYSTEMS

### CHECK-IN (shift start) ✅design
T−10 pre-reminder (how-to + +10 early ⭐ + [I'm late]) → T0 prompt (if not in zone) → T+5 free-minutes
message → live location in 100m = checked in (✓; +10 if >5 min early). ≤5 min late = free; >5 = all
minutes count. Check-out at shift end (one leave-early ask, then silent close + digest flag). Sick = type
anything → Special Leave (no Sick button by design).

### LATE → PAYBACK (time only — never AL) ✅design
Tap Late → time buttons → reason (typed, declare-time) → Supervisors heads-up + reason. Arrival by
location. Owe = minutes → payback SLOTS at the shop's neediest before/after-shift times (next 7 days +
1 day-off option), partials allowed, +10 if early, mini-shift treatment. Ignore ladder: daily line at
check-in → day-3 "pick before tomorrow or I'll pick for you" → day-4 auto-book → skip×2 = bonus not
earned + digest. Legitimate-leave days FREEZE the clock; no-show/day-off days count. No-show = 1 day's
pay + bonus not earned + −2/min points (never added to debt).

### ANNUAL LEAVE (days 0–90; 0–6 = short-notice priced) ✅design
Balance in header. Dates (≥7d free; <7d ⚠ costs points). Full day / hours (15-min). Reason. → senior
cards (≥2 ✅, dynamic timers). Approved → Supervisors notice. Hours-AL = fractional. Cancel via My
schedule (refund un-taken). Negative AL only via Special Leave.

### SPECIAL LEAVE (law-based) ✅design
Sick (Me = take-a-pill ladder, payback if paperless, papers→owner card w/ Opus advice + part-duty +
recovery ask + retroactive reversal; Family child/spouse/parent = 7-day pool, papers optional) · Marriage
(own 3d/child 1d, 30+ days ahead) · Family death (Child/Parent/Spouse law-tier 3–7d + Sibling/Grandparent
compassion 1d→owner upgrade; relation nameable; photos→owner+Tyty) · Wife birth 2d. AL→negative ok for
marriage/death/birth, never salary. Papers only ever to owner+Tyty.

### OT — GIVE OT / TIME BANK (no money) ✅design
Senior grants: [⚡Now]/[📅Later] → (Now = present-by-SCHEDULE) → duration → why ("for the owners") →
OWNER approve (ignore=approved; reject-before asks reason + memos both; reject-after still pays). NOW-OT
consent [✅/❌] (15min→senior reminds); proof = location∩window + granting-senior confirm. FUTURE-OT =
accept→work slot. Accepted = commitment (no-show penalized). Banks (cap 14h) → buyback at fattest-coverage
times, reward-tone reminders. Tyty/Delis excluded.

### CHANGE DAY-OFF (within 7 days) ⏳design+build (needs dry-run)
Pick new day (own day-off weekday hidden) → swap partner (similar shift, coverage-safe) → reason →
PARTNER first (✅ or silence=no swap) → 2 seniors → both schedules update + Supervisors notice.

### COVERAGE GUARDRAIL + RIPPLE ✅calc
Warns before an AL/swap/day-off opens an expertise gap; any approved change re-validates future plans
(payback slots, availability, OT bookings). Hiring-needs analyzer (future): table → hire profile.

---

## OPEN BUILD ITEMS (design done — these are wiring)
1. **State persistence (gm_flow_state)** — #1; no flow lives only in RAM.
2. Real ladders behind the shell: check-in jobs → Late+payback → AL approvals → swap → Give OT → slips.
3. Monthly AL accrual (+1.5). Interactive My-schedule dashboard. Voice/photo reason capture.
4. Points engine (raw events now; values + activation later, owner-tuned).
5. Per-flow dry-runs + owner role-play sign-off → staged go-live (no live-location requirement until
   owner explains + all Started — already met).

## STANDING REMINDERS 🔒
- Delis geofence method (staff live in building) — revisit when Delis integrated.
- Points→bonus link deferred (aim: threshold earns bonus) — after observing real behavior.
- Leftover phone numbers for privacy-hidden staff; promote nothing — listener stays OUT of senior rooms.
