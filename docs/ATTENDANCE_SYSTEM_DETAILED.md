# Attendance / AL / Lateness — DETAILED Step-by-Step

> Companion to ATTENDANCE_SYSTEM_MAP.md. Every step, branch, message, timer, and edge case.
> Tags: [Haiku] [Sonnet] [Logic] [Telegram]. Status: ✅ built · ⏳ pending · 🔒 owner input.
> Confirmed: 2 approvals · lateness→Supervisors group · 30min cumulative/shift · 200m · whole-shift location ·
> seniors set new-staff day-offs · Tyty exempt · Delis excluded for now.

---

## 0. FOUNDATION — identity & schedule
- **Source of truth = owner CSV** (not conversations). Importer rebuilds staff_registry from it:
  - person in CSV → active; person not in CSV → ex_staff; new person → added.
  - fields loaded: work_start/end, day_off, al_left, org (TWB/Delis), is_senior, expertise.
  - dual accounts merged to one record (Sao Visal); ex-staff dropped.
- **Per-person flags that change behaviour:**
  - `org=DELIS` → excluded from all GM attendance for now (separate team/pool later).
  - `is_senior=Y` → receives AL approval requests; cannot approve their own AL.
  - **Tyty (co-owner)** → fully exempt: no check-in, no lateness, no AL rules.
  - new staff with **no telegram id yet** → in registry but can't DM until added to a group.
- **Expertise** (cashier/service/kitchen/bar/bakery) stored per person → feeds availability + coverage.

## 1. WHO THE GM TALKS TO (the gate) ⏳
- Every private message: look up sender `uid` → staff_registry. [Logic]
  - **active staff** → engage.
  - **ex-staff / unknown uid** → no engagement (silent, or one-time "I can't help here").
  - **Delis** → not yet enabled.
- **Group redirect:** if any AL/lateness topic is posted in a group [Haiku/keyword detect]:
  - GM replies once: *"Please tell {name} to message me directly about this."* then stops.
  - does NOT process it as a case (forces the private channel).

## 2. CROSS-CUTTING FIXES (apply to every case) ⏳
- **Understand-without-reply:** when a chat has an OPEN case (lateness/AL/finance/receipt), any new message is
  checked as a possible answer [Haiku extract + Sonnet judge] — a plain message resolves it; no Telegram
  threaded reply required.
- **👍 acknowledgement:**
  - GM registers a reply that is NOT a concern → react 👍 on it (staff know they were heard). [Telegram react]
  - reply IS a problem/concern → **no 👍** (so it's not read as "all fine").
  - 👍 **never** replaces the GM's actual reply/escalation — it's only an ack.

## 3. LATENESS (private) ⏳
1. Staff DM: *"I'll be 30 min late."* → [Haiku] extract minutes + (optional) which day.
2. **Which shift?** [Logic] default = their **next shift**; unless that shift already started → "already started".
   - **before shift:** *"Noted — you'll be ~30 min late for your 1pm shift today. Thanks for telling us."* + 👍
   - **already started:** *"Ok. Please try to tell us before your start time next time."* + record.
   - **edge — today is their day off:** *"You're off today — did you mean a different day?"*
   - **edge — no shift today (not scheduled):** ask which day.
3. **Record** → lateness_records (minutes, for_shift). [Logic]
4. **Post to SUPERVISORS group:** *"Heads-up: {name} will be ~30 min late for the {shift} shift today."* [Telegram]
5. **Arrival check timer:** at (shift start + stated minutes) → DM staff *"Have you arrived? Share your location if you did."*
   - location shared & in zone → mark arrived, record real time, 👍. [Logic geofence]
   - still nothing → gentle re-ask; (later) counts toward frequency.
6. **Frequency:** repeated lateness in a window → remind the staff privately; (later) negative points.
7. **No approval needed** — lateness is informational, not a request.

## 4. ANNUAL LEAVE (private) ⏳
1. Staff DM the AL: full days OR a few hours, with a **reason**. → [Haiku] extract days/hours + reason.
   - **reason missing** → *"What's the reason for the AL?"* (wait for it).
   - **dates/hours unclear** → ask to confirm exact day(s)/time(s).
2. **Validations** [Logic]:
   - **balance:** enough `al_left`? if not → tell staff + flag owner; still let seniors decide.
   - **self-approval block:** if requester is a senior, they're excluded from approving their own.
   - **already-off:** if a requested day is their normal day-off, note it (no AL needed that day).
3. **Availability picture** [Logic] — for EACH AL day/window:
   - list staff working the requester's hours that day, **excluding** day-offs + anyone else on AL that day.
   - line per day, e.g. *"Tue Jun 3 — working her hours: Lina, Nak, Sony."* then next day, etc.
4. **Coverage guardrail** [Logic] — if the AL leaves an **expertise** uncovered at some hour, add a warning line
   to the senior message (bakery = production, judged on baking-hours, not hourly).
5. **Send to each SENIOR (private DM):** the request + reason + availability picture + **[✅ Approve] [❌ Not approve]**.
6. **Tally** → al_approvals. **On 2 ✅:** [Logic]
   - delete/collapse the pending DMs to all seniors. [Telegram]
   - fresh DM to all seniors: same details + *"Approved by {A} and {B}."* (tag them).
   - **SUPERVISORS group:** plain notice *"{name} on AL: {days/times}."* — NO availability, NO who-approved.
   - **deduct** the AL days/hours from `al_left`.
   - confirm to requester: *"Your AL for {days} is approved."* + 👍
7. **On 2 ❌ (rejected):**
   - collapse DMs → fresh DM to seniors *"Not approved by {A} and {B}."*
   - nothing to the Supervisors group.
   - tell requester: *"Your AL request wasn't approved."*
8. **Edge — split / no quorum:** if it never reaches 2 either way within a window → escalate to **owner** to decide.
9. **Owner override** any time. **Accrual** +1.5/mo arrears runs as a monthly job (from the seeded al_left).
10. **Delis** (when enabled) = its own seniors + its own availability pool; never mixed with TWB.

## 5. LIVE-LOCATION ATTENDANCE (whole shift) ⏳
1. **Check-in:** staff share **live location** with the GM at shift start = their time-attendance.
   - in 200m zone → *"Checked in ✓"* + 👍; record checked_in_at, in_zone. [Logic geofence]
   - shared but outside zone → *"You're not at the shop yet — share again when you arrive."*
2. **No check-in by start time** → DM reminder *"Your shift started — please share your live location to check in."*
   (in case they forgot). Repeat once; if still nothing, it shows as not-checked-in.
3. **During the shift** (GM watches live-location updates / edited messages) [Logic]:
   - **location stops / goes off** → *"Did you leave work early? If not, share your location again."*
   - **leaves the 200m zone** → start timing this excursion.
   - **cumulative time outside > 30 min** (across ALL trips this shift) → *"What are you doing outside the shop?"*
   - **returns to zone** → pause the outside-timer (keeps the running total).
4. **Shift end** → close the session; if location was off and they never returned → flag *left early?*.
5. **Telegram live-location reality:** a live period maxes ~8h → for longer shifts the GM reminds them to re-share.
   GPS drifts in dense areas → the 200m buffer absorbs it; very brief edge wobble isn't penalised.
6. **Delis** staff: not tracked yet.
- **(Alternative on file: SPOT-CHECKS)** — one-off check-in + random "share location now" pings instead of a
  continuous feed. Lighter, but gameable. Not chosen; kept as fallback.

## 6. COVERAGE GUARDRAIL (standing) ⏳
- Weekly skill map from expertise + schedules; warns BEFORE an AL/day-off opens an expertise hole.
- Used live inside AL approval (step 4.4); also available as an on-demand owner report.

## 7. RECORDS, DIGEST, POINTS
- Tables ✅: al_requests, al_approvals, lateness_records, attendance_sessions.
- **Weekly digest** ✅ now reads these (not group keyword scanning).
- **Points** ⏳ later: negative (short-notice AL, repeat lates, grace for rare) + positive recognition (existing).

---

## OUTPUTS BY DESTINATION (who sees what)
- **Private to staff:** all back-and-forth, acks (👍), arrival/location prompts, AL approve/reject result.
- **Private to each senior:** AL approval request + availability + the approved/rejected recap.
- **Supervisors GROUP (only clean outcomes):** lateness-for-the-shift notice; approved-AL plain notice.
- **Private to owner:** quorum stand-offs, balance shortfalls, coverage warnings, anything unusual.
- **Never in any group:** reasons, who-approved, availability details, the questioning back-and-forth.
