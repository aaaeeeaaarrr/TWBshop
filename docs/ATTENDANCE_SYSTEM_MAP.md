# Attendance / AL / Lateness — Whole System Map

> Private-DM attendance system. All staff↔GM about attendance happens in **private DM**.
> Status: ✅ built · ⏳ pending · 🔒 gated on owner input. Tweak freely — this is the master picture.
> **v2 (owner spec 2026-06-04, session 28):** whole-shift live tracking DROPPED → **check-in at shift
> start** only (live location in 200m zone). If staff voluntarily keep location on → **secretly collect**.
> Private chat is now fully **BUTTON-DRIVEN** (any text → main menu, one button per row, every submenu
> starts with "←Back"). New flows: Late ladder + payback/AL/salary settlement, **Emergency AL** (1×/30
> days), **Change day off** (2 seniors + swap-partner approval, same week). Early >5min = +10 pts;
> −1/min (informed before) / −2/min (informed after) — ALL points PENDING owner review (raw events stored,
> points derived later). No-show = −1 AL, else 2 days pay. Full detail: ATTENDANCE_SYSTEM_DETAILED.md.

---

## THE 6 LAYERS (everything flows top→bottom)

### LAYER 0 — Identity & Schedule (the foundation)
- **staff_registry** ✅ — who is staff, active/ex-staff, telegram user_id(s), aliases, call-name.
- **Schedules** (per staff) ⏳🔒 — work_start/end, day_off, AL-left, org (TWB/Delis), is_senior, **expertise** (cashier/service/kitchen/bar/bakery). Schema ✅; data comes from the owner CSV → importer ⏳.
- **Rules baked in:** Delis = separate team (excluded for now); **Tyty = co-owner, exempt from all rules**; ex-staff & non-staff get no engagement.

### LAYER 1 — Channels (how info arrives)
- **Private DM** staff→GM — BUTTON-DRIVEN menus (Late / AL / Emergency AL / Change day off / Check in). ⏳
- **Live location** = CHECK-IN at shift start only (no continuous requirement); voluntary always-on feeds
  are silently stored (location_pings). ⏳
- **Group messages** → if anyone posts AL/lateness in a group, GM replies *"Please tell {name} to message me directly"* and does nothing else. ⏳

### LAYER 2 — Reading (AI that understands the message)
- **Haiku** parses: AL request (days/hours + reason), lateness (duration + which shift). ⏳
- **Sonnet** judges "does this reply resolve the open question?" (the answer-judge). ✅ (exists)
- **Understand-without-reply** ⏳ — resolve an open case from a **plain message** (no Telegram threaded reply needed). Applies to ALL cases (lateness, AL, finance/receipt clarifications).

### LAYER 3 — Logic & Decisions (deterministic — NO AI in anything that matters)
- **Geofence** ✅ — haversine, 200m from TWB.
- **Availability** ✅ — who's working a window on a day, excluding day-off **and anyone on AL that day**.
- **Coverage / expertise check** ✅(calc) — are all 5 skills covered each hour; would an AL/day-off open a gap.
- **Lateness kind** ✅ — before-shift vs already-started.
- **Approval counting** ⏳ — ≥2 of the chosen seniors.
- **AL ledger** ⏳ — deduct on approval; accrual +1.5/mo arrears.
- **Outside-budget** ✅ — 30 min/shift allowance.

### LAYER 4 — Actions & Notifications (what the GM does)
- **👍 acknowledgement** ⏳ — react 👍 when GM registers a reply that is NOT a concern (so staff know they were heard). NO 👍 if it's a problem/concern. 👍 never replaces a real reply/escalation.
- Lateness → **Supervisors group post** (for that shift) + private follow-up "have you arrived?".
- AL → **senior approval DMs** (✅/❌ + availability picture) → on 2 approvals, collapse & re-notify tagging voters → **Supervisors plain notice** (no details) if approved; seniors-only if rejected.
- Location → check-in reminders, "left early?", "what are you doing outside?".

### LAYER 5 — Records & Learning
- Tables ✅: al_requests, al_approvals, lateness_records, attendance_sessions.
- **Weekly attendance digest** ✅ — now FED by these tables (not group keyword scanning).
- **Coverage guardrail** ⏳ — warn before approving an AL/day-off that opens an expertise gap.
- **Points** ⏳(later) — negative for short-notice AL / repeat lates; positive recognition (existing system).

---

## THE 4 SUB-SYSTEMS (mapped through the layers)

### 1) LATENESS (private)
DM "late 30 min" → **Haiku** duration → **logic** next-shift vs started ("ok, but warn earlier next time")
→ record → **post to Supervisors** for that shift → at +30 past start: "Have you arrived? Share location."
→ frequency tracked → reminders → (later) negative points. **No approval.**

### 2) ANNUAL LEAVE (private)
DM AL days/hours (+reason; **Haiku** asks if missing) → **logic** builds the availability picture per AL day
(who's in at her hours, excluding day-offs & people on AL) → DM each **senior** ✅/❌ + that picture
→ **≥2 approve** → old DMs collapse, fresh DM to seniors tagging who voted → approved: **Supervisors** get
plain AL days/times (no who's-available, no who-approved); rejected: seniors only → **ledger** deducts AL.
Coverage guardrail warns if it opens a skill gap. **DELIS = separate pool when enabled.**

### 3) CHECK-IN ATTENDANCE (private, shift start — v2)
At shift start, no live location in the 200m zone → "Your shift started — share live location to check in.
Late? Tap below." → in-zone live location = checked in ✓ (+10 pts if >5 min early, PENDING). No continuous
tracking required; voluntary always-on location silently collected. **Not for Delis yet.**

### 4) COVERAGE GUARDRAIL (cross-cutting, from expertise + schedules)
Standing weekly skill-coverage map → proactively warns before an AL/day-off creates a missing-expertise hour.
(Bakery treated as production, not hourly customer coverage.)

---

## OLD SYSTEM → REMOVED vs KEPT

| Old piece | Fate |
|---|---|
| Group **lateness ladder** (senior reports → GM asks payback → escalate) | ❌ REMOVED (already silenced) → private lateness |
| Group **leave-questioning** + "Quick check… AL?" nudges (the spam) | ❌ REMOVED (already silenced) → private AL |
| **leave_clarify** clarification topic + its nudges | ❌ REMOVED → AL has its own flow/tables |
| Group **attendance keyword/semantic** scan (Supervisors/Management) | ❌ REMOVED → "DM me" redirect |
| **Staff registry + ex-staff** offboarding | ✅ KEPT (this whole thing sits on it) |
| **Clarification ladder** for report_math + receipt_clarity | ✅ KEPT (finance/receipt only) + gets understand-without-reply & 👍 |
| **Weekly attendance digest** | ✅ KEPT, now fed by the new private tables |
| **Finance brain, Stock, waste/mistake concerns, policy replies, proposals/points, receipts** | ✅ KEPT (unrelated) |

**Net effect:** the GM stops policing attendance *in groups* (no more spam/misunderstanding). Groups only get
**clean outcome notices** (a lateness for the shift; an approved AL). All the back-and-forth moves to private DM,
understood whether or not it's a threaded reply, acknowledged with 👍.

---

## OPEN TWEAK POINTS (where you can adjust)
1. Live location: whole-shift (current) vs check-in + spot-checks.
2. AL approvals: exactly 2 (current) vs majority; who the seniors are 🔒.
3. Lateness → post every one to Supervisors (current) vs only repeat offenders.
4. Outside-zone allowance: 30 min/shift; the "ask" thresholds.
5. Negative-points rules (later): short-notice AL %, repeat-late counts, grace for rare cases.
6. Geofence radius: 200 m.
7. New-staff day-offs 🔒; replacement senior when Met leaves (you said: not needed).
