# GM Subsystems — full status

*(Moved out of CLAUDE.md. One-line statuses stay in CLAUDE.md; full text here.)*

## REPORT Finance Tracking (GM bot) — LIVE
TWB REPORT group (chat_id in Connectivity). Business day 06:00→06:00; ~16:00 mid + ~05:00 final report.
GM parses each report, recomputes the drawer (600 + cash in − cash out; Over/Lost = count − expected),
flags Lost>$2 in-group + opens a clarification, DMs owner anomalies. FX margin (4000 riel=$1) → a small
"Over" is EXPECTED, never flag. Level-1 reconciliation LIVE (cash sheet / POS / ABA vs report).
OPEN (remind owner): #1 overexpense-carryover model (deficit carried to next day off the $600 float —
owner wants cleaner). Sales-anomaly framework built; activates once years of FB Messenger reports import.
Full decoded format + resolved decisions → docs/HISTORY.md.

---

## Supervisors / Management — Lateness · AL · Tagging — mostly BUILT
Global staff tagging: config.STAFF_CALL_NAME + call_name_for() + _staff_mention (call-name + tg://user
ping). Group lateness ladder BUILT but SILENCED (config.GM_ATTENDANCE_GROUP_ACTIVE=False) — all
attendance moved to the private-DM system (below). AL math + accrual (+1.5/mo arrears) PENDING owner
seeding balances. Full owner spec + build detail → docs/HISTORY.md.

---

## Delivery System (WOC) — SHELVED
Mine the WOC delivery-photo archive into structured data (customers/phones/orders/food catalog/prices).
Parked by owner; pilot validated (~$500–800 full-year API). ⚠ Grab/Foodpanda privacy-law flag on
customer numbers. Full design + pilot findings → docs/HISTORY.md.

---

## Staff Registry · Ex-staff Offboarding · Paperless /stock — BUILT
staff_registry (canonical/call/aliases/uids/status/schedule/salary). /exstaff or plain owner DM → confirm
card → mark ex_staff (history kept) + ban from internal groups WHERE the bot is admin (currently
mark+report only — promote an admin account to enable auto-kick). Paperless /stock overhaul + the
143-item order CSV import are PENDING. Full spec → docs/HISTORY.md.

---

## Private-DM Attendance Overhaul — LIVE (since 2026-06-16)
Button-driven private-DM attendance: check-in (live-location geofence) · late+payback (time-bank) ·
AL + senior approval · Special Leave (sick/marriage/death/birth) · day-off swap · Give-OT time-bank ·
points · no-shows · payroll. Replaces the silenced group ladder. Full spec → docs/ATTENDANCE_SYSTEM_DETAILED.md
+ docs/ATTENDANCE_SYSTEM_MAP.md. Test harness → docs/ATTENDANCE_TEST_MODE.md.

---

## STRATEGIC — POS convergence (owner, session 27)
> Owner is building a separate UNIVERSAL CLOUD POS (cloud source-of-truth + local-PC backup so ops don't
> break when internet is down). Endgame: fold tested features (stock, attendance, GM brain) into the POS.
> DECISION: stock staff-entry starts on **AppSheet** as a THROWAWAY/BRIDGE front-end (validate workflow fast),
> NOT the destination. GUARDRAILS: (1) keep OUR Postgres the SOURCE OF TRUTH — sync AppSheet→Postgres; the
> brain (order list, minimums, suppliers, points) stays in our code, AppSheet is just a data-entry skin →
> migration = swap front-end only, no rebuild. (2) Shape the data model to POS inventory needs (item id,
> unit, count, min, order_qty, supplier, counted_by, timestamp). FUTURE: when POS basics exist, cross-
> reference BOTH repos (add POS as a 2nd working dir / share its design) to design the convergence with both
> codebases in hand. Keep everything TWBshop-side POS-friendly meanwhile. Custom-own beats AppSheet long-term
> because inventory IS a POS module and offline-sync is the same hard problem the POS must solve.

---

## GM Backlog & Roadmap
The remaining GM "shop-brain" roadmap (finance brain · attendance brain · stock/ops brain · cross-group
knowledge brief · added ideas) → docs/ROADMAP.md (reference only, not an auto-run task list).

---

## Operations Intelligence System — mostly BUILT (Phase 3)
Telethon listener + historical import + AI analysis tiers + hiring bot are built/live. Original Phase-3
plan → docs/HISTORY.md.

---

