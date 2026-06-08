# Attendance TEST-MODE harness — "test once, alone, for real" (owner spec, session 29)

> GOAL (owner): test the WHOLE attendance system ONCE, from the owner's own Telegram,
> playing every role and receiving every message, with REAL working buttons — and zero
> staff contact, zero real-data corruption. Go-live must need NO second test, and staff
> must never meet a dead button. Owner: precision over convenience; do not skip bits.

## The one switch
`gm_state.attendance_test_mode` ('true'/absent). Independent of `attendance_live`.
- **test_mode ON**: the real flow runs, but every outbound message is REDIRECTED to the
  OWNER, labeled `[→ {role}: {name}]`, with working buttons the owner taps as that role.
  Every DB row written is tagged `is_test=TRUE`. Real aggregate balances are NEVER mutated.
- **test_mode OFF (live)**: identical code; messages go to the real recipients; rows are real.
- Precedence: a flow runs if `attendance_live` OR `attendance_test_mode` (so the owner can
  exercise everything while staff stay untouched — test_mode never messages a real staffer).

## Data isolation (built — session 29 foundation)
- `is_test BOOLEAN DEFAULT FALSE` on: al_requests, al_approvals, lateness_records,
  payback_debts, payback_bookings, no_show_records, special_leaves, sick_cases, ot_grants,
  ot_buyback, dayoff_overrides, dayoff_swaps, points_events, attendance_sessions, location_pings.
- `database.set_att_test(bool)` sets a process global `_ATT_TEST`; every attendance INSERT
  helper stamps `is_test=_ATT_TEST`. Safe because test_mode runs owner-only (attendance_live
  is OFF in test → no concurrent real traffic).
- **Live reads filter `is_test=FALSE`.** Test reads (My Schedule etc. while in test) include
  test rows so the owner sees state change.
- **Balance overlay (no real mutation):** al_deduct / OT-bank adjust are NO-OPS when _ATT_TEST.
  Displayed balance = real value − Σ(test deductions) / + Σ(test grants), computed live.
- `attendance_testreset()` → `DELETE WHERE is_test=TRUE` from every table (exact, reversible).
  `attendance_test_counts()` → outstanding test rows per table.

## Routing layer (to build)
`_att_send(context, to_uid, role_label, to_name, text, kb=None)` — the SINGLE chokepoint for
every staff/senior/group message in the attendance system.
- test_mode: send to OWNER, text prefixed `[→ {role_label}: {to_name}]`, kb buttons kept
  functional (owner taps as that role).
- live: send to `to_uid` (or the group chat id) with the kb.
Replace EVERY `context.bot.send_message(senior/requester/SUPERVISORS …)` in the attendance
orchestration with `_att_send`. (Owner-card sends already go to the owner — leave as-is.)

## Actor-identity override (to build)
In test_mode, when the owner taps a card addressed to a role (e.g. a senior approval ✅),
the callback must treat the actor as THAT role, not the owner. Encode the intended actor in
the callback (the card already carries req_id; senior identity = whichever senior the card was
"sent" to — in test we let the owner stand in for ANY required senior, counting distinct
synthetic senior ids so quorum of 2 can be reached by the owner tapping twice as "senior 1"
then "senior 2"). Same pattern for partner agree, staff consent (Yes/Can't), come/rest.

## Owner commands (to build)
- `/testmode on` → set attendance_test_mode true, set_att_test(True), confirm + show how it works.
- `/testmode off` → false, set_att_test(False).
- `/testreset` → attendance_testreset(); report rows deleted.
- `/teststatus` → attendance_test_counts() + current mode.
- Persona: reuse the /test persona picker; "act as" sets the current test actor.

## Flows to wire through routing + is_test + overlay (the checklist — do ALL)
1. [ ] AL: submit_al_request, _al_approval_callback (actor override), _al_finalize (deduct overlay,
       Supervisors notice via _att_send), cancel.
2. [ ] Late → payback: late_declare, payback offer/booking, ladder job messages, no-show.
3. [ ] Check-in: prompts, verdict, check-out, left-zone (all via _att_send; sessions is_test).
4. [ ] Give OT: submit_ot_grant, owner card, NOW consent, FUTURE invite, banking (overlay),
       buyback booking, reminders.
5. [ ] Day-off swap: submit_swap (partner card), senior cards, apply overrides, notices.
6. [ ] Sick: declare ladder, papers → owner card, part-duty, family-sick + nudges.
7. [ ] Marriage / Death / Birth: book_*, notices, compassion upgrade.
8. [ ] Staff entry (real 7b): non-owner text/Start → real menu acting as themselves → submit_*
       via flow_state. In test_mode the owner-as-persona drives the same entry.

## Go-live (after the single owner test signs off)
1. `/testreset` (clear all test rows). 2. `/testmode off`. 3. brief staff. 4. send the greeting
(gm_greeting_FINAL) + attach the persistent 📋 Menu button. 5. `attendance_live='true'`.
No re-test needed: live uses the same code paths the owner already exercised; only the
recipient address and is_test flag differ.

## Status
- ✅ session 29: is_test on all tables + testreset/test_counts (deployed, verified in prod).
- ⏳ routing layer, actor override, owner commands, flow wiring (1–8), staff entry.
