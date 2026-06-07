# Attendance / AL / Lateness — DETAILED Step-by-Step (v2, session 28 owner spec 2026-06-04)

> Companion to ATTENDANCE_SYSTEM_MAP.md. Every step, branch, message, timer, and edge case.
> Tags: [Haiku] [Sonnet] [Logic] [Telegram]. Status: ✅ built · ⏳ pending · 🔒 owner input.
> Confirmed: 2 senior approvals · 200m geofence · seniors set new-staff day-offs · Tyty exempt · Delis excluded.
> **v2 CHANGES (owner 2026-06-04):** whole-shift live location DROPPED → check-in-at-start model;
> entire private chat becomes BUTTON-DRIVEN; new flows: Late ladder w/ payback, Emergency AL,
> Change-day-off w/ partner approval; points catalogued but PENDING activation.

---

## 0. FOUNDATION — identity & schedule
- **Source of truth = owner CSV** (importer ✅ — registry rebuilt: 35 active, 5 seniors, 6 ex-staff).
- **Per-person flags:** `org=DELIS` excluded for now · `is_senior=Y` approves ALs (not their own) ·
  **Tyty co-owner = fully exempt** · staff with no telegram id can't DM until bound.
- **UID BINDING (step 0 before go-live):** current telegram_ids are seed-guessed from display names
  (imperfect for repeated names like 'Pisey'). First DM from an unknown/unverified uid → GM shows
  name-pick buttons ("Who are you?") → staff picks own name → owner confirms unusual/ambiguous binds.
  Recommended go-live: a roll-call ("everyone DM the GM bot once") binds the whole roster in a day.
- **Expertise** (cashier/service/kitchen/bar/bakery) per person → availability + coverage guardrail.
- **KHMER NAMING (owner, session 28):** LEFT name = surname, RIGHT name = given name. Call names = the
  right name, or a shortened tail of it when long (Chuch Pisey→Pisey, Doeun Rothanak→Nak, Tengmarim
  Chaktopor→Por, Khon Visalpisey→Sey). GM addresses staff by call_name / right name — never the surname
  alone. New staff default call name = right name (confirm with owner).
- **Salary + Bonus ✅ IMPORTED (session 28):** salary_usd + bonus_usd columns on staff_registry, loaded
  from owner's Salaries 2026 CSV — 33 staff (Met Solina none; resigning). OWNER-ONLY data: never in any
  group, never in repo files, DB only.
- **TWO-PAY STRUCTURE ✅ IMPORTED (owner, session 28):** first_pay_usd + second_pay_usd columns loaded
  (1st+2nd = salary+bonus, verified — only Tyty differs by his $200 overtime). **Pay model:** 1st of the
  following month = most of the salary; 15th = remainder + bonus. **ALL pay cuts come out of the FIRST
  pay.** 🔒 timing edge: a cut booked after the 1st but before the 15th → from the 2nd pay, or carried to
  next month's 1st pay? ⚠️ salary sheet has an unnamed row paying 155/40 — owner to identify.
- **PHONES ✅ partial (session 28, via listener get_entity):** 9 single-id staff phones auto-stored;
  Khon Visalpisey almost certainly = uid 768420022 (username VISALPISEY, phone 0963803229 — owner to
  confirm, then drop his other 4 ids); Rom Sopheaktra 6652936983 / Sen Vathanakthyda 7278651403 each have
  a phone-bearing candidate. Rest are privacy-hidden → owner adds Phone column to the CSV → listener
  import_contacts resolves phone→uid (also IDs Sao Visal, Thorn Kimheng, Tyty, Chuch Pisey).
- **BONUS MESSAGING RULE (owner, session 28 — LEGAL-SAFE wording required):** every time the GM mentions
  the bonus to staff it MUST auto-append the discretionary disclaimer, worded so the bonus can never be
  read as expected pay. One canonical string in config (single place to tune). PROPOSED 🔒:
  *"Reminder: the monthly bonus is a discretionary extra decided by management each month based on
  performance and conduct. It is not part of salary and is never guaranteed."* (+ Khmer under.)
  **WORDING APPROVED by owner session 28.**
- **bonus_eligible (per bonus-pay flag — UPDATED owner session 28):** events (2nd emergency AL in 30 days,
  no-show) void the **NEXT UNPAID bonus pay**. **LANGUAGE RULE:** never "lost the bonus" (implies
  entitlement) — always **"earned" / "not earned"**. **REVEAL = SURPRISE on the 2nd pay day (15th):** the
  payday slip shows *"Bonus: earned ✓ $X"* or *"Bonus: not earned — reason: …"*. No ongoing bonus-status
  messages (the at-action warning in the emergency flow is the only advance notice).
- **TYTY PAY RULE (owner):** $1,700 every month on the 1st — single payment, no split, no bonus logic.
- **Schedule CSV v3 ✅ IMPORTED (session 28):** 34 staff updated (day-offs now filled, AL balances,
  expertise, work times) + **4 planned ALs** booked as approved al_requests (Chun Chomruen Jun 5-7, Kiry
  Jun 4, Lim Soleng Jun 4, Sao Visal Jun 9/10/12) — engine deducts as each AL time starts. ⚠️ **Yorng
  Lyhouy auto-ex_staffed** (absent from CSV) — owner to confirm intentional. Still VERIFY multi-ID: Khon
  Visalpisey (5 ids), Rom Sopheaktra, Sen Vathanakthyda · MISSING id: Sao Visal, Tyty, Thorn Kimheng,
  Chuch Pisey → first-DM bind fixes all.
- **PHONE BINDING (owner idea session 28 — yes, adopted):** registry has a `phone` column ✅. Owner adds a
  Phone column to the schedule CSV → the LISTENER (Telethon) imports them as contacts and resolves
  phone → telegram user_id — this nails the multi-candidate/missing IDs without waiting for first DM.
  Tagging itself always uses the user_id (Telegram bots can't tag by phone); phone is the binding key.
- **Met Solina resigns 5 Jun 2026** → flip to ex_staff (seniors 5→4; 2-approval quorum unaffected).
- **PH (Public Holiday): SHELVED** — owner will explain the model later. Keep a placeholder day-type in the
  schedule model so AL/payback/day filters can exclude PH days when it lands.

## 1. WHO THE GM TALKS TO (the gate) ⏳
- Private message → uid lookup in staff_registry. [Logic]
  - active staff → engage · ex-staff/unknown → no engagement · Delis → not yet.
- **Group redirect (format confirmed owner session 28):** AL/lateness posted in any group → GM replies
  once, **tagging the GM bot itself** so it's one tap into the DM — English line + Khmer line, each
  carrying the tag:
  *"Please message @twb_gm_bot directly about this."*
  *"សូមផ្ញើសារទៅ @twb_gm_bot ដោយផ្ទាល់អំពីរឿងនេះ។"*
  Never processed as a case (forces the private channel).

## 2. BUTTON-DRIVEN PRIVATE CHAT (the new UX) ⏳ — owner spec session 28
- **ANY free text** the staff types (when GM is not explicitly waiting for a reason/answer) → GM responds
  with the MAIN MENU. Buttons stacked **one per row** (readable), labels padded to a uniform width so the
  menu renders wide. All labels bilingual (English / Khmer under or beside).
- **Every submenu's FIRST button = "←Back"** (always returns one level up).
- **GLOBAL BUTTON RULE (owner, session 28, from live truncation screenshot):** any button with a LONG label
  gets its OWN ROW — side-by-side only for short labels (dates, times, Yes/No, ✓/✗). Applies to ALL bots,
  not just attendance. (Live fix already applied: _exstaff_kb confirm card was truncating "Mark as left +
  remove".)
- **MAIN MENU (proposed set):**
  1. 🕐 Late / មកយឺត
  2. 🏖 Annual Leave (AL) / ច្បាប់ឈប់សម្រាក
  3. 🚨 Emergency AL / ច្បាប់បន្ទាន់
  4. 🔄 Change day off / ប្ដូរថ្ងៃឈប់
  5. ⏱ OT — **"GIVE OT" MODEL, TIME BANK, NO MONEY (owner FINAL v3, session 28).** Staff do NOT request
     OT. **SENIORS grant it**, owner approves, staff only choose when to take the hours back.
     - **SENIOR side — `Give OT` button (under About Work, seniors only):** duration buttons 30min→6h in
       30-min steps → pick the staff (name buttons; seniors can pick THEMSELVES — same flow) → **when:
       day buttons, then START-TIME buttons only** (duration already known → end auto-computed; same
       insight as payback placement). START-TIME CONSTRAINTS (owner, session 28): never show times inside
       the receiver's scheduled shift; only starts where start+duration ends BEFORE their next shift
       begins (gap between shifts; whole day if day-off) → **why: typed** (verbatim rule) → goes to the
       OWNER. FINAL why-prompt (owner+ChatGPT): *"Please type the reason why this OT is needed."* /
       *"សូមវាយបញ្ចូលហេតុផលថា ហេតុអ្វីបានជាត្រូវការ OT នេះ។"*
       **OT ON AN AL DAY (owner decision, session 28):** ALLOWED outside the leave window (AL already
       deducted, no refund — their choice), with a FLAG LINE on the owner card: *"Note: receiver is on AL
       this day ({window})."* **BLOCKED when overlapping the leave hours themselves** — one person can't
       be officially absent and working the same minutes (availability pictures lie to seniors, the
       Supervisors notice loses trust, check-in/left-early guards contradict, and hours-AL→OT overlap
       would launder the controlled AL ledger into the self-serve OT bank). AL cancelled after an OT
       grant that day → ripple check re-validates the OT booking (gap may have vanished).
     - **OWNER APPROVAL (always):** GM DMs owner the card — who gives, who gets, duration, when, why,
       receiver's current bank → [✅ Approve] / [❌ No]. Only on ✅ do the hours bank. **NO "stay-now" /
       pending state (owner final):** the grant→approve→bank chain is the whole system; the OT work itself
       happens on the senior's authority, the bot only records it.
     - **STAFF side — after owner approval:** staff gets the message: hours banked (*"+1h OT — your bank:
       3.5h"*) + **slot buttons to choose when to take the BUYBACK TIME** (owner's working name): business-
       safest times ONLY (fattest coverage, never hurting limited expertise — owner: no day-off-adjacency
       niceness, even for big banks), glued to their shift (come late / leave early), next 7 days, full
       amount first + partial `Take 1 hour only` buttons — exact inverse of §4.7. **NO senior approval for
       the take-back**; plain Supervisors notice when booked.
     - **IGNORED? Daily reminder, clean chat (owner):** if they don't pick, GM reminds ONCE A DAY, during
       their shift, **deleting the previous reminder message first** (no chat clutter), showing fresh
       slots for the next 7 days. Repeats until they choose.
     - **BANK CAP = 14 HOURS (owner):** a grant that would push the bank past 14h is trimmed/blocked at
       the Give-OT step (duration buttons beyond the remaining headroom hidden). No expiry — the daily
       reminder is the anti-stale mechanism.
     - **RESIGNATION with banked hours:** no fixed rule — GM asks the owner in a message at that moment
       (pay out or expire, case by case).
     - **SHIFT-CONTINUITY RULE (kept):** payback-before-shift + shift + OT-after-shift = ONE presence
       window — one check-in at the start, one check-out at the very end; check-in auto-satisfies if
       location already in zone. Check-out moves to the OT end when OT extends the shift.
     - **RULES:** open payback debt blocks Give-OT to that person (time settles debt first; debt-hours
       never banked). No OT-per-day ceiling (owner: not needed — the 6h-per-grant + 14h cap bound it).
       No payroll column — hours in, hours out.
  6. 📍 Check in / ចុះវត្តមាន (instructions to share live location)
  7. 📋 My schedule & AL balance / កាលវិភាគ & សមតុល្យ AL  *(self-service — shows ALL THREE balances:
     AL left, payback debt, OT bank; plus shift times, day off, upcoming approved ALs)*
- **AL BALANCE IN HEADERS (owner, session 28):** tapping AL or Emergency AL shows the balance in the
  message text ABOVE the buttons (*"You have 7.5 AL days left. Choose dates:"*) — replaces the monthly
  AL-statement DM idea. Monthly accrual stays silent.
- **ZERO-API PRINCIPLE:** every flow above is buttons + pure logic — no AI parsing, no per-message cost.
  The ONLY typed text is the reason fields (passed verbatim to seniors, not AI-read). Haiku is needed only
  for the group-redirect detection and understand-without-reply edges. (Telegram Bot API itself — messages,
  buttons, edits, reacts — is FREE; "API $" only ever means AI calls.)
- **ALWAYS-SHOW-REASON + OWNER-GATED CALL-OUTS (owner remodel, session 28):**
  1. Every recorded event (late, sick, AL, swap, OT, no-show) keeps its VERBATIM reason attached and
     VISIBLE on every owner/senior surface — approval cards, dossiers, digests, /whois, payroll notes —
     **AND in the SUPERVISORS GROUP notices (owner clarified session 28):** the approved-AL notice
     includes the reason; the lateness heads-up still goes out at declare-time (no reason exists yet)
     and **the reason is posted as a reply to it once given on arrival** ("Davy arrived 9:32pm —
     reason: moto broke"). EXCEPTION kept for dignity: family-death notices stay "(family)" — veto if
     you want the cause shown.
  2. FREQUENCIES learned over time at analysis-time ("traffic ×14 this month", "sick: 3rd Monday"),
     surfacing in the owner digest/dossiers.
  3. **CALL-OUT GATE: the GM NEVER confronts a staff member about a reason pattern on its own.**
     It messages the OWNER first with the dossier; only on the owner's explicit go (and his wording
     preference) does anything reach the person. Nice to their face, evidence to the owner, the bam
     is always a human decision.
- **BUTTONS NEVER BLOCK — TEXT-WAITS EXPIRE (owner "they do the opposite" rule, session 28):**
  exactly TWO text-wait kinds exist (late-reason ask; flow reason/why steps). A text-wait expires after
  **30 min** and dies instantly on ANY button tap — after that, typing → main menu as normal. Expired
  late-reason → recorded "(no reason given)" (digest signal); unsettled debts live in the deadline
  machinery, never blocking. Abandoned button-flows just sit in scroll-back (tap-time validation).
  Reason-step abandoned mid-request = a DRAFT: never sent to seniors, quietly expires after 24h.
  One text-wait at a time — a new flow's reason step replaces the old wait (last intention wins).
- ~~Settle-menu AL guard~~ SUPERSEDED same session: lateness has NO AL option at all (late = time,
  leave = AL, never mixed) — see §4.7 ignore-the-planner ladder.
- **👍 ACK RULES (updated session 28):**
  - **OWNER: ALWAYS 👍** any typed owner message the GM understood — no exceptions. (Born from the Lim
    Soleng case: owner typed "Yes she's finished", GM acted but never confirmed.) PLUS when an owner
    message resolves a pending card/action, GM sends an explicit confirmation of what it did
    (*"Done — Lim Soleng marked as left."*), not just the react.
  - **STAFF: 👍 only on replies that are NOT a concern/problem** (owner: never thumb up bad behaviour) —
    lateness notices, bad reports, complaints get the GM's real reply, no 👍. 👍 never replaces the GM's
    actual reply/escalation.
- **Free text exceptions:** when a flow is at its "give your reason" step, or an open case is awaiting an
  answer (understand-without-reply [Haiku extract + Sonnet judge]) → text is captured as the answer, not menu'd.
- **Later idea (not v1):** Haiku reads the typed text and pre-opens the right submenu with values prefilled
  (e.g. "late 10 min" → Late flow at the time step).
- **Date-picker pattern** (used by AL/Emergency/Day-off/Payback): dates in a grid (4–5 per row,
  `Mo 29/06` style), 30 days per page with `▶ Next 30` pager; multi-select = tap toggles ✓, then **Done**.
  (Telegram caps ~100 buttons/keyboard; 90 stacked single-row date buttons would be an endless scroll.)

## 3. CHECK-IN (replaces whole-shift tracking) ⏳ — owner spec session 28
1. **At shift start:** if no live location shows them inside the 200m zone → DM:
   *"Your shift just started. Please share your **live location** to check in. Running late? Tap below."*
   `[🕐 I'm late]` `[📍 How to check in]`  (owner's wording: "Are you late? If not, share live location
   to check in attendance" — refined above).
2. **Live location received & in zone** → *"Checked in ✓"* + 👍; record checked_in_at. [Logic geofence]
   - **static location pin** (one-shot, easily faked) — fires ANY time someone drops a pin. FINAL
     bilingual template (owner+ChatGPT, session 28):
     *"Sending a pin does not count as check-in to work."*
     *"ការផ្ញើទីតាំងជា Pin មិនរាប់ជាការចុះវត្តមានចូលធ្វើការទេ។"*
     *"Do this instead:"* / *"សូមធ្វើតាមនេះវិញ៖"*
     *"Tap 📎 (Attach) → Location / ទីតាំង → Share Live Location / ចែករំលែកទីតាំងបន្តផ្ទាល់"*
     Check-in screen itself is SHORT: the same slash-style instruction line + "Shift: HH:MM–HH:MM",
     no zone talk.
   - **GLOBAL HOW-TO RULE (owner, session 28):** EVERY message that asks for a location carries the ONE
     recognizable line (shared constant _CI_HOWTO): *"📍 Tap 📎 (Attach) → Location / ទីតាំង → Share Live
     Location / ចែករំលែកទីតាំងបន្តផ្ទាល់"* — it REPLACES wordy "please share your live location" sentences
     (shorter, not longer). Applied: T−10 pre-reminder, T0 prompt (whose separate How-to button was
     dropped — inline beats a tap), check-out request, leave-early ask, pin response, check-in screen.
     Build note: the Late flow's arrival-watch ("Are you there yet?") must use it too.
   - shared but outside zone → *"You're not at the shop yet — it will count when you arrive."* (keep watching)
3. **EARLY BIRD:** in zone >5 min before start → **+10 points** (points PENDING — record raw arrival time
   now, points computed later; see §9).
4. **NO continuous-tracking requirement.** Staff may stop sharing after check-in, no nagging.
5. **SECRET COLLECTION:** if staff voluntarily keep live location running → silently store every update
   (location_pings: uid, lat, lon, ts, in_zone). Never mention it to staff. Used as evidence for
   early-leave, outside-time, payback verification, lateness measurement.
6. **Check-in scheduling:** per-staff job at their work_start (Asia/Phnom_Penh; overnight shifts handled by
   overlaps()); skip if day-off / approved AL / Tyty / Delis / already checked in.
7. **CHECK-OUT (owner, session 28):** at work_end → DM *"Shift over — share your live location to check
   out."* If their live location has been ON since check-in (forgot it on / left it on) → auto-checked-out,
   no message needed (we know they were there to the last minute). **TIMING (session 28):** request at
   work_end → no response by **+10 min** → ONE gentle ask (*"Did you leave early? If not, share your
   location to check out."*) → still nothing by **+30 min** → case closes silently as no-check-out →
   digest flag with evidence (last ping / stop-edit time). Never more than 2 messages — check-out is
   evidence collection, not a chase. Skipped if rest-of-day leave was approved.
   **"DID YOU LEAVE EARLY" TIMING (clarified session 28):** the question fires ONLY at check-out time,
   NEVER mid-shift — stopping a voluntary live share mid-shift gets silence (their right; no continuous
   tracking). The stop-edit signal is silently RECORDED and upgrades the digest flag's evidence quality:
   "last seen in zone 2:30am, location stopped, no check-out" vs a bare "no check-out".
8. **CHECK-IN MESSAGE SEQUENCE (owner FINAL, session 28 — pre-reminder REVIVED with a job):**
   skipped entirely on day-off / AL / already-checked-in / Tyty / Delis.
   - **T−10 min:** pre-reminder — shift starts in 10 min, the 📍 how-to line, AND advertise the
     early-bird reward: arrive 5 min before start = **+10 points**. Carries the `[🕘 I'm late ·
     ខ្ញុំមកយឺត]` button (owner, session 28) — tapping it BEFORE start is exactly what earns the −1 rate.
   - **T0 (start):** still no in-zone location → the normal check-in prompt (+ I'm-late button).
   - **I'M-LATE BUTTON RULE (owner, session 28):** T−10, T0 AND T+5 each carry `[🕘 I'm late ·
     ខ្ញុំមកយឺត]` while NO lateness is declared for this shift — every nudge is another chance.
     **Once declared (time chosen): the remaining prompts are SUPPRESSED entirely** — the arrival watch
     at their declared time owns the timeline (no "check in now!" after they already told us 9:30).
   - **NO SICK BUTTON on check-in prompts (owner, session 28 — deliberate friction):** a Sick button at
     5:50am is an invitation. The genuinely sick TYPE anything → main menu → About Me → Special Leave →
     Sick. (Parked for later: Haiku intent-routing of typed "sick" straight to the ladder.)
   - **T+5 min:** still nothing → the NICE message — FINAL bilingual (owner+ChatGPT via khmer_inbox):
     *"We give everyone 5 free late minutes 😊 More than 5 — every late minute counts: as pay-back time,
     and minus points. The sooner you tell us, the fewer points it costs. See you soon!"*
     *"យើងផ្ដល់ឱ្យគ្រប់គ្នា 5 នាទីអនុគ្រោះសម្រាប់ការមកយឺត 😊 បើលើសពី 5 នាទី រាល់នាទីយឺតទាំងអស់នឹងត្រូវរាប់៖
     ជាម៉ោងសងវិញ និងដកពិន្ទុ។ ប្រាប់យើងកាន់តែឆាប់ ពិន្ទុដែលត្រូវដកកាន់តែតិច។ ជួបគ្នាឆាប់ៗ!"*
     (Exact rates −1/−2 live in the Rules screen, not in the nudge.)
   - **GRACE RULE (updates the old "strict from minute 1"):** late ≤5 min → totally free (no debt, no
     points). Late >5 min → **ALL minutes count from minute 1** (not minus 5) — debt = actual minutes;
     points rate by informed-before (−1) vs not (−2).

## 4. LATE (private, button flow) ⏳ — owner spec session 28
1. Staff taps **Late** (or gets the check-in prompt and taps `I'm late`).
2. **Time buttons** — increments after their shift start (example 9pm start):
   9:05, 9:10, 9:15, 9:20, 9:30, 9:45, 10:00, 10:15, 10:30, 11:00, 11:30, 12:00, then **every 30 min until
   2 hours before shift end**. (Offsets: +5,10,15,20,30,45,60,75,90,120, then +30 steps.) Generated from
   their schedule. NO "don't know yet" option (owner: the store team must know a time to manage around).
   Beyond the 2h-before-end cap = effectively absent → Emergency AL or no-show rules.
3. **Reason — asked ON ARRIVAL, FREE TEXT (owner reversed quick-reasons, session 28):** the second their
   location confirms arrival, GM asks *"Why were you late?"* (bilingual) — they TYPE the answer, stored
   verbatim. **MECHANICS (owner Qs, session 28):** NO reply/tag needed — private 1-on-1, the ask opens an
   awaiting-reason state and the next text IS the reason (menu-on-any-text is suspended while awaiting —
   no menu spam). First message → 👍 + the payback SLOT BUTTONS directly (no AL option — late = time);
   **further texts until a slot button is tapped (or ~10 min) APPEND to the stored reason** — Khmer
   burst-texting ("moto broke" / "on bridge" / "sorry boss") lands as ONE reason, no re-asks, no second 👍.
   Ignoring the slots → the ignore-the-planner ladder (§4.7). NO preset reason buttons anywhere ("a menu of excuses is a menu of permission" — presets
   would teach staff which excuses are acceptable; the reason never changes the penalty, so its only
   value is honest signal). Categorization happens at ANALYSIS time (digest/Opus-on-subscription), never
   at confession time. Why on arrival: they're rushing/driving at the Late tap.
4. **Posted to SUPERVISORS group instantly** — name + expected time (no reason exists yet at
   declare-time). **REMODEL (owner, session 28 late): once the reason is given on arrival, it is
   POSTED AS A REPLY to that heads-up** — Supervisors always end up seeing the why.
5. **Arrival watch:** at the selected time, if live location still doesn't show them at the premise →
   *"Are you there yet? Open Live Location."* — repeat **4× every 15 min** until location confirms.
6. **TRUTH = LOCATION:** late minutes are computed from when their live location enters the zone,
   NOT what they said.
7. **On arrival → straight to payback (owner FINAL, session 28): NO AL option for lateness — late costs
   TIME, leave costs AL, the currencies never mix.** After the reason, the GM goes directly to the
   payback slot buttons. AL/salary are NEVER touched automatically for lateness.
   - **Pay back → NEED-TARGETED SLOTS, SHIFT-ADJACENT ONLY (v4 FINAL, owner session 28):**
     NO auto-pay; NO slots far from their shift. Slots are **immediately BEFORE or AFTER their own shift**
     — except ONE day-off option (see below). [Logic, no AI — §8 engine scores expertise thinness.]
     - **Primary buttons = the FULL owed amount**, placed at the before/after-shift times that are BEST
       FOR THE SHOP within the **next 7 days** (owner final: slot window = 1 week; deadline stays 14 days
       — list refreshes daily). **RANKING (owner):** our most-need first; if needs are identical, the
       CLOSEST date wins the higher spot. **COMPACT LABELS (owner):** `Fri 06/06 7:30pm-9pm` — date +
       window only, never sentences (long text truncates on buttons).
     - **+ ONE DAY-OFF option:** their day off, at the time we need them most **within their regular shift
       hours** (a 9pm–6am person gets a night window on their day off, never a 5am call).
     - **Below those: partial buttons** `Pay 1 hour only` / `Pay 2 hours only` / … → each opens the same
       good before/after-shift (+day-off) times for that partial amount; remainder stays in the balance.
     - **Booked slots → plain Supervisors notice** (team expects them) — CONFIRMED owner session 28.
     - **Verification:** live location in zone during the slot; partial attendance = partial credit.
       **No payback-of-a-payback (owner confirmed).**
     - **Slot dynamics / stale open menus:** slots are computed when the menu is sent; validity is checked
       AT TAP TIME. Debtor B's already-open menu is left alone (no delete/resend) — if his tapped slot is
       still valid it just books (two debtors on one thin hour = fine); if something truly invalidated it
       (his own schedule changed), the tap is rejected gracefully and the SAME message's buttons are
       EDITED IN PLACE with fresh slots (Telegram edit_message_reply_markup — Bot API messaging/edits are
       FREE; only AI reads cost money).
     - **IGNORE-THE-PLANNER LADDER (owner FINAL, session 28 — replaces the 14-day auto-AL entirely;
       the debt NEVER auto-converts, time stays time):**
       · Day 0: debt born → slot buttons shown.
       · Every CHECK-IN while unbooked: ONE calm line + the slot buttons (*"Checked in ✓ — you still owe
         90 min, pick a time:"*) — daily cadence at a natural moment, never hourly hammering.
       · Day 3: warning + slots again: *"Pick before tomorrow, or I'll pick for you."* /
         *"សូមជ្រើសរើសមុនថ្ងៃស្អែក បើមិនទាន់ទេ ខ្ញុំនឹងជ្រើសរើសជូនអ្នក។"* (KH draft — next batch).
       · Day 4: **GM auto-books the shop's #1 need-slot** + notifies them + plain Supervisors notice.
       · Skipped the assigned slot → re-book ONCE → skipped again → **next bonus not earned** +
         the case lands in the owner digest as a person-problem.
       Ignoring stops being a strategy: the only way out of the debt is through it.
     - **PAYBACK SLOT = MINI-SHIFT (owner REVERSED the no-reward rule, session 28 — "encourage them,
       not just break them"):** a booked slot (self-picked OR auto-assigned) gets the FULL check-in
       treatment — T−10 pre-reminder (with the how-to + the +10 line), T0 prompt, location check-in —
       and **arriving 5+ min early to a payback slot EARNS the +10 points** like any shift.
     - **BOOKED CONFIRMATION always carries the encouragement line:** *"Booked ✓ — {slot}. Come 5
       minutes early and you earn +10 points ⭐"* + approved KH (+10 line reuses the approved T−10
       fragment មកដល់មុន 5 នាទី...).
     - **12-HOUR-BEFORE REMINDER for any booked attendance event** (payback slot, assigned slot, OT
       buyback): *"Reminder — your payback time is tomorrow: {slot}."* / KH draft *"រំលឹក — ម៉ោងសងវិញ
       របស់អ្នកគឺថ្ងៃស្អែក៖ {slot}។"* + the +10 line + the 📍 how-to (both already approved). Same
       quiet-hours slide rule as the family-sick nudge. (+10 applies to WORK slots — payback / granted
       OT work — not to taking buyback rest, where there's nothing to check into.)
     - "My schedule" menu shows the live balance; weekly digest lists open debts.
8. **NO-SHOW (FINAL, owner session 28):** never arrived during the whole shift (Late tapped or not) →
   **cut 1 DAY'S PAY** (internally: Cambodian law 1-for-1 — **NEVER mention the law to staff**; owner:
   staff should think less about the law unless it's against them) + the **next bonus pay is not earned**
   (bonus_eligible=false on the next unpaid bonus). AL is fully out of the no-show picture. Cut comes from
   the first UNPAID pay cycle — **if the month's 1st pay already went out, the cut carries to NEXT month's
   first pay** (owner: it's a pay of a different month). Owner-approval tap before any salary deduction is
   booked. Edge: arrived very late but before shift end = LATE (payback), not no-show. Owner-override
   always available (hospital cases etc.).
9. **POINTS (PENDING, §9):** informed BEFORE shift start → **−1 pt/min late**; informed AFTER start →
   **−2 pts/min late**; minutes from location, not claim.
10. **No approval needed** — lateness is informational + settlement, not a request.

## 5. ANNUAL LEAVE (private, button flow) ⏳ — owner spec session 28
1. Staff taps **AL**.
2. **If existing approved/pending ALs** → stacked buttons: `New AL?` + one `Cancel AL {date}` per AL
   (date only, no time). No existing ALs → straight to date picking.
   - **Cancel AL {date}** → confirm → release the booking, refund any deducted AL, collapse/refresh senior
     messages, notify Supervisors group if it had been announced. **Cutoff (owner): cannot cancel once the
     AL TIME has started** (the window, not the whole day).
3. **Date selection — UPDATED (owner, session 28 v2): days 0→90 INCLUDING TODAY.** Days 0–6 show a ⚠
   marker — selectable, allowed, but **SHORT-NOTICE PRICED: −0.1 points per AL minute on those days**
   (full 9h day ≈ −54 pts; pending points activation). The warning shows the COMPUTED TOTAL before
   confirming, never just the rate. Per-day evaluation: 8 days picked, 3 within the window → only those
   3 cost points. **This fully replaces Emergency AL** (no limiter, no bonus-warning ladder — the price +
   2-senior approval + digest visibility do the governing).
   - **TODAY while shift already running:** Full-day option HIDDEN (half-worked day); time picker's first
     button = **Now (exact current time)** and past times never shown — the gap before the request stays
     in the lateness machinery (no retro-excuses possible by construction).
   - **From-now requests inherit 1-SENIOR-TO-LEAVE** (from the old mid-shift emergency): seniors pinged
     instantly, one ✅ lets them go, second ratifies after.
   - **Compassion override:** on approval, owner/seniors can waive the short-notice points for genuine
     crises (points pending owner tuning anyway).
   - Lateness-vs-AL arbitrage is INTENTIONAL: asking properly (−0.1/min + AL + approval) is ~10× cheaper
     than being late (−1/−2/min + payback) — pushes people from surprising the team into proper requests.
   - ⚠ Rules-screen bullet "AL: ask 7+ days ahead" needs updating + retranslation (batch with next
     ChatGPT pass).
4. **Full day or Choose Time** → buttons. Choose Time → their work hours in **15-min buttons**
   (9:00am, 9:15am …), pick **from** then **to**.
5. **Reason** — bilingual ask (Khmer under).
6. **Validations [Logic]:** balance check (warn + flag owner if insufficient, seniors still decide) ·
   senior can't approve own AL · requested day is their day-off → note (no AL needed).
7. **Approval escalation (unchanged):** each senior gets DM: request + reason + **availability picture**
   per AL day/window (staff working those hours, excluding day-offs + others on AL) + coverage-guardrail
   warning if an expertise hour opens + `[✅ Approve]` `[❌ Not approve]`.
   **ALL SENIORS, ALWAYS (owner, session 28):** approval requests go to every senior even if they're on
   holiday / AL / off-hours — no reachability filtering; whoever answers, answers. (Kills the need for a
   senior-pool watch.)
   **On 2 ✅:** collapse senior DMs → fresh DM to all seniors tagging approvers → Supervisors group plain
   notice → deduct → confirm to requester + 👍.
   **SUPERVISORS APPROVED-AL NOTICE FORMAT (owner spec, session 28):**
   - line 1: *"{name} on leave {from} → {to}"* (or *"{hours} on {day1}, {day2}, …"* for hours-AL);
   - line 2: her NORMAL day off, mentioned whether or not she included it in the request
     (supervisors see the full absence picture, e.g. AL Wed–Thu + Fri day off = gone till Sat);
   - line 3 (separate): *"Back at work: {day}, {shift start time}"* — for hours-AL, the return TIME that
     same day (e.g. "back 12am each night, rest of shift as normal").
   Example full-day: *"Meng on leave Tue 23/06 → Thu 25/06 (3 days). Normal day off: Friday 26/06.
   Back at work: Saturday 27/06, 9pm."*
   Example hours (3 days, 9pm–12am of her 9pm–6am shift): *"Meng on leave 9pm–12am on Tue 23/06,
   Wed 24/06, Thu 25/06. Normal day off: Friday. Back at work: 12am each of those nights (works the
   rest of her shift); fully normal from Sat 27/06 9pm."* (deduction: 3×3h of 9h = 1.0 AL)
   **On 2 ❌:** collapse → seniors-only recap → tell requester.
   **Senior-response timers are DYNAMIC (owner question "what if the AL is after 23 hours?"):** timers
   scale to time-until-the-AL-starts — nudge silent seniors at min(12h, 25% of time-to-start), escalate to
   owner at min(24h, 50% of time-to-start). Emergency-today requests compress to minutes
   (nudge ~15min, owner ~45min). The decision always lands BEFORE the AL begins.
8. **FRACTIONAL DEDUCTION:** hours-based AL deducts proportionally — e.g. 10h shift, 3h AL → **0.3 AL**.
9. **Accrual** +1.5/mo arrears (monthly job, from seeded al_left). **Latest-wins amendments** via gm_leave_events
   supersede pattern (Backlog B).
10. ~~Advance-notice question~~ RESOLVED by §5.3: normal AL starts at day 7; anything sooner = Emergency AL.

## 6b. SPECIAL LEAVE (About Me → 🕊 Special Leave) — owner spec + Cambodian law, session 28 ⏳
> Legal basis: Labor Law Art. 169–171 + Prakas 267/2001 — special leave = up to 7 PAID days/yr for
> immediate-family events; deduct from AL if available, else make-up hours; NEVER salary.
- **Menu (reason FIRST):** 🤒 Sick → Me / My child / My spouse / My parent — **FAMILY-SICK = ONE DAY AT A
  TIME (owner, session 28):** date → Full day OR hours (15-min from→to; mid-shift → starts at Now, like
  AL); **NIGHT-BEFORE NUDGE replaces re-asking (owner, session 28):** after a family-sick day, GM nudges
  **12h before their next shift** (slid back to 20:00 the prior evening if it lands in the 21:30–08:00
  quiet window): FINAL bilingual: *"Is your {child} better? If you need tomorrow off too, tell me now. /
  តើ{child_kh}ធូរស្បើយហើយឬនៅ? បើត្រូវការឈប់ថ្ងៃស្អែកទៀត សូមប្រាប់ខ្ញុំឥឡូវនេះ។"* → TWO short
  buttons: `[Again tomorrow · ស្អែកទៀត]` (→ the standard Full-day/Choose-time screen) ·
  `[👍 Better · ធូរស្បើយហើយ]` (→ GM replies *"Great news — see you at {time} 🤍 /
  ដំណឹងល្អណាស់ — ជួបគ្នា {time} 🤍"*). Day-by-day control kept. (Batch-30 finals wired session 28:
  every staff-facing string in the shell is now FINAL bilingual.) Each day individually consumes the 7-day pool (internal counter — NEVER mention the
  pool/jargon to staff; confirmations stay minimal: "Sick leave for your child — Sa 07/06, full day ✓
  Take care 🤍"). ·
  💍 Marriage → My marriage /
  My child's marriage (**BOTH: dates hidden for first 30 days** — owner rule, weddings are planned) ·
  🕊 Family death → Child / Parent / Spouse → start date → **duration buttons 3–7 days, chosen ONCE at
  booking** (owner+session 28: no re-applying mid-funeral; need more later → just re-enter Special Leave) ·
  👶 Wife giving birth. **Death-photo reply FINAL bilingual:** *"You don't need to send anything — we're
  so sorry for your loss 🤍 / អ្នកមិនចាំបាច់ផ្ញើអ្វីទេ — យើងសូមចូលរួមរំលែកទុក្ខចំពោះការបាត់បង់នេះ 🤍"*.
  ALL Special Leave strings now FINAL bilingual in the shell (ChatGPT batch session 28, via khmer_inbox).
- **Funding:** taken from AL; for own marriage + death of child/parent/spouse (+ wife birth): if AL = 0 →
  **AL GOES NEGATIVE (only here), floor −7/yr, NEVER money**. Negative repaid by future +1.5/mo accrual;
  resignation with negative AL → shop absorbs (owner). 7-day/yr special-leave counter; beyond 7 → normal
  AL request. Defaults: marriage 3d · child's marriage 1d · wife birth 2d · death 3d (+extra via normal AL).
- **NO short-notice points EVER on special leave** (never charge grief). Approval: death = NO approval
  (instant acknowledgment + condolence + Supervisors notice) · sick = notify, no gate · marriage =
  normal AL approval (30+ days out by design). Evidence: death never asked · marriage = the 30-day rule ·
  sick = see below.
- **DEATH PHOTOS (owner question, session 28 — Khmer staff sometimes send photos of the deceased):**
  the death flow NEVER asks for any document or photo. If one arrives anyway in a death context:
  **NO AI ever touches it**, it is never forwarded anywhere (owner confirmed: not even to him), and the
  GM replies with condolence ONCE: *"You don't need to send anything — we're so sorry for your loss 🤍"*
  — further photos in the same case get only a quiet 🤍 reaction (no repeated text). File references are
  STORED SILENTLY on the case (never displayed; retrievable only if the owner explicitly asks later —
  dignity by default, audit on demand). Fraud risk is naturally low (funerals are community events;
  seniors know) — suspected abuse is a human conversation for the owner, not a verification flow.
- **🤒 SICK→ME — THE ANTI-FAKE LADDER (owner practice, session 28):**
  - GM: *"Sorry to hear 😟 Take some medicine and come try — see how you feel at work. What time can you
    come?"* → Late-style time buttons + `[🛌 I really can't come today]`.
  - **PAPERLESS SICK = INFORMED LATENESS, identical price** (payback debt at need-slots for ALL missed
    minutes incl. full day + −1/min when points activate) — "sick" carries ZERO discount, so only truth
    says it. Full-day claim → *"If you see a doctor, send me a photo of the papers."*
  - **Papers photo** (within ~3 days) → **AI VISION READ (owner, session 28 — one Sonnet/Haiku call per
    photo, rare event = pennies):** extract {is_medical_document, hospital/clinic name, address, phone,
    doctor name, patient name, document date, confidence, red_flags} → stored on the sick case AND into a
    growing `medical_providers` knowledge table (hospitals/doctors seen) → owner approval card shows the
    extraction + cross-checks (patient name ≈ staff name? date ≈ sick day? same doctor/clinic recurring
    across many staff? date looks edited?) → OWNER still taps the final ✅ (AI reads, never decides).
    On ✅: debt+points wiped, real sick day, **AL UNTOUCHED (owner + law: own certified sickness is sick
    leave, separate from AL — never deduct)**.
    Job legally protected up to ~6 months certified. 🔒 minor: papers-day paid or unpaid = owner policy
    (recommend paid — rare once paperless costs payback). OLD "suggest 0.5 AL" practice = DEAD.
  - **FREQUENCY DOSSIER (paperless only — nice until bam, owner):** flags → owner card with full history
    (dates, weekday, papers ratio, came-vs-full-day, debt status): 2-in-7d (burst) · 3-in-30d (drip,
    even spread) · 5-in-90d (chronic) · 3-of-last-4 same weekday ("every Monday") · 2-in-60d adjacent to
    day-off (bridge) · 2 within 2 days after payday (payday echo).
  - Family-sick (child/spouse/parent) untouched by the ladder — legal special-leave lane.
- **HIRE BOT (owner, session 28):** add intake health question — *"Is your health 100% for this job?"*
  `[Yes 100%]` / `[I want to explain]` + free text; stored on the candidate file (cross-checked later
  against sick dossiers).
- **Maternity NOT here** — 90d at half pay after 1yr service, own legal regime, case-by-case later.

## 6. EMERGENCY AL — ❌ REMOVED FROM MENU (owner, session 28 late): "sometimes some people have weird
## emergencies popping up" — a rigid 1×/30-days flow doesn't fit real life. Owner is bringing the POINTS
## system into this instead (discussion open — see §9). Design below KEPT for reference only; the
## main menu is now: Check in · Late · About Work (seniors: Give OT, later stocks/checks) · About Me
## (AL, Change day off, OT, My schedule). ⚠️ OPEN: with Emergency gone, days 0–6 have NO request path
## (normal AL starts at day 7) — resolve when the points discussion lands.
### (shelved design follows)
1. Staff taps **Emergency AL** → warning, bilingual:
   *"You can only do this once every 30 days. Do you understand?"*
   `[I fully understand]` `[No Emergency AL]` (second = back to main menu).
   - **Limiter (owner confirmed session 28):** only an **APPROVED** emergency consumes the 30 days; a
     rejected request burns nothing.
   - **2nd click within 30 days of the last approved one → NOT blocked, but a BONUS WARNING:**
     *"No bonus pay for taking many emergency AL leaves in 30 days. Last time you took emergency AL was
     {date}."* (bilingual) → stacked buttons `[I fully understand]` / `[No Emergency AL]`. Proceeding +
     approval ⇒ **bonus_eligible=false for the current month** (feeds the month-end payroll report).
   - **3rd click within 30 days of the last approved one → HARD BLOCK (owner, session 28):** message only,
     no flow: *"Not allowed — this would be your 3rd emergency AL within 30 days (last approved {date}).
     Next possible: {date+30}. If you miss your shift it counts as absence (1 day's pay)."* Absence line
     **CONFIRMED by owner** — transparency so nobody can claim "but I told the bot".
2. **Date** — multiple choice: `Today` + next **60 days** (grid+pager).
3. **Full day / Choose Time** → same 15-min from→to pattern.
4. **Reason** — bilingual.
5. **Approval escalation = same as AL** (2 seniors, availability picture, Supervisors notice, deduction).
   Suggest the senior DM is visibly marked 🚨 EMERGENCY for urgency.
6. Interplay with no-show: Emergency AL for TODAY must be requested **before shift start** to cancel that
   day's no-show exposure 🔒 (else staff could retro-excuse a no-show).
7. **MID-SHIFT EMERGENCY (proposed flow 🔒, expanded session 28 — "sometimes it's 2 hours then back"):**
   staff is AT work and suddenly needs time off NOW:
   - If currently inside their shift, the Emergency date step shows **`From now`** first. Then:
     `[Rest of my shift]` or `[I'll be back]` → duration buttons `30m / 1h / 1.5h / 2h / 3h`.
   - **"I'll be back" variant:** at now+duration → GM checks location / asks *"Are you back?"* — actual
     away time measured by location when available; back early = smaller deduction, back late = GM asks
     again and the real gap counts. Deduction stays **fractional** (2h of 10h = 0.2 AL).
   - Same warning/limiter/bonus-warning, same reason step.
   - **Approval can't physically block someone walking out**, so: GM instantly DMs seniors (🚨 marked,
     with availability) + plain notice; staff may leave once **ONE senior approves** (one is usually on
     shift) — 2nd approval ratifies after the fact. **CONFIRMED owner session 28: 1-senior-to-leave.**
   - Departure/return times = live location when on; check-out message skipped for rest-of-shift.
   - **ABUSE-FREE measures (the limiter + bonus hit do the heavy lifting; these add visibility):**
     - per-staff emergency history shown to seniors at approval time (*"3rd emergency in 60 days"*);
     - pattern flags to owner: same weekday repeats, emergencies adjacent to day-offs (long-weekend
       engineering), end-of-month clustering;
     - monthly per-staff emergency usage in the digest;
     - same-day emergency only counts if requested BEFORE shift start (no retro-excusing a no-show) —
       mid-shift variant obviously exempt (they already checked in).

## 7. CHANGE DAY OFF (private, button flow) ⏳ — owner spec session 28
1. Staff taps **Change day off** → date buttons: next **30 days, excluding today** (`29/06` format).
2. **Swap-partner buttons:** full names of staff with similar/close (not necessarily exact) shift times
   whose swap would NOT further bottleneck expertise that day [Logic: schedule similarity + coverage check].
3. **Reason** — bilingual.
4. **Approvals:** same 2-senior escalation as AL **PLUS the swap partner must approve** — partner gets a DM
   with `[✅ I agree]` `[✋ No]`; required even after 2 senior approvals. **PARTNER FIRST** (owner agreed) —
   if they decline, seniors are never bothered.
   **PARTNER-DM TEMPLATE (owner-approved Khmer, session 28):**
   EN: *"{requester} wants to swap their day off with you: {requester} takes {weekday1} {dd/mm} off, you
   take {weekday2} {dd/mm} — same week. Reason: {reason}"*
   KH: *"{requester} ស្នើសុំប្តូរថ្ងៃឈប់ជាមួយអ្នក៖ {requester} ឈប់ {Wed 10/06}
   ហើយអ្នកឈប់ {Thu 11/06} — ក្នុងសប្តាហ៍ដដែល។"*
   (Dates stay ENGLISH inside Khmer text — owner rule, no Khmer weekdays/numerals.)
   **REASON IS NEVER TRANSLATED (owner, session 28 — GLOBAL rule for ALL flows):** the staff's typed
   reason is passed VERBATIM in whatever language they wrote it (English or Khmer) — to partners,
   seniors, owner, records. The bot's framing is bilingual; the quoted reason is raw.
5. **Constraint — RESOLVED (owner, session 28):** "same week" = **within 7 days of each other** (rolling,
   not calendar weeks) — Fri→next-Mon is a legal swap.
6. On full approval: both schedules updated for that week, Supervisors group plain notice, records kept.
7. **SWAP↔AL COLLISION RULES (owner question, session 28):**
   - **One pending case per day:** a date with an OPEN request (AL/Emergency/swap) is blocked in every
     other picker until decided — tapping it: *"You already have a pending request for that day."*
   - **Pickers resolve day-off PER DATE** (schedule + approved swaps + approved ALs), not per weekday —
     after a swap, "Friday off" is false for that one week.
   - **AL on a swap-affected day:** allowed (deducts normally), but the senior card adds:
     *"Note: this day is affected by her day-off swap approved on {date}."* No blind approvals.
   - Approved-change ripple (§8) re-validates everything else as usual.
8. **GLOBAL DATE FORMAT (all ladders — owner FINAL session 28): ENGLISH DATES EVERYWHERE, even inside
   Khmer sentences.** Buttons `Tu 23/06` (shared day_label helper) · message text `Tue 23/06` · Khmer
   lines embed the same English form (no Khmer weekday names, no Khmer numerals, NO Khmer-weekday
   helper). Identical in every flow.

## 8a. COVERAGE REQUIREMENTS — THE TABLE (owner interview, session 28) 🔒FINAL
> Powers: availability pictures, swap suggestions, payback need-slots, heatmap, Vannary-style
> auto-recommendations. ALL pure logic, zero API. PUSH-HIGH PRINCIPLE: ranges always target the
> high number (emergency headroom); below-min = critical flag, below-target = caution.
- **Windows:** morning 6–11 · lunch 11–14 · afternoon 14–17 · dinner/bar 17–21 · night 21–6.
  Busy-busy: Sat+Sun lunch, Fri+Sat dinner.
- **FRONT (pooled — bar/service can always cashier; some kitchen-mains can cashier but NOT
  service/bar; skills per registry):** lunch+dinner 3–4 (target 4) · morning/afternoon 2–3 (target 3) ·
  night 1–2 (1 normal — one person makes drinks; 2 = big-group speed).
- **KITCHEN:** lunch+dinner 3–4 (target 4; front/kitchen can split 3/4 or 4/3) · quiet windows 2–3 ·
  night: NO rule — intentional buffer crew (offs/emergencies; light deliveries + checks + preps);
  Heng = night-kitchen overflow helper.
- **BAKERY (night 9pm–6am + Samphass 6pm–6am): ESSENTIAL, immovable** — bakers never get moved to
  other times; ≥3 every night, Fri+Sat target 4 (fallback: borrow 1 kitchen hand when 3).
  Roster note: exactly 4 bakers whose day-offs never collide and all 4 align Fri+Sat — preserve this
  pattern when changing baker day-offs.
- **BAR: ≥1 bar-skilled present AT ALL TIMES** (drinkers = profit boost, serve fast).
- **PREP (daytime cake preparations — crusts etc., feeds the Cake makers): ≥2 prep-capable 10:00–19:00.**
  Prep-capable = explicit 'prep' skill + ALL daytime service people EXCEPT late-night service, Por and
  Rath (seniors anchor/supervise: Por watches-while-working; Rath = the main guy, does everything except
  Cake, directs preps, backed owner up since forever — moved to 6am–6pm because post-Lina the 6–7am
  crew are newbies).
- **CAKE: Thyda + Tyty only.** They CAN prep but shouldn't (cake output drops). Thyda also real bakery,
  helps nights 9pm–12am. Tyty mass-produces before her holidays (manual arrangement, no rule).
- **A PERSON FILLS ONE SLOT AT A TIME** — skills = where they CAN stand; minimums = bodies per station.
- **PREP TAIL ACCEPTED (owner):** Wed+Fri 17–19h showing 1 formal prepper is fine — the shop runs a
  **half-prepper culture**: many staff learned preps because whenever one person preps alone, another
  helps. Formal rule stays ≥2 in 10:00–19:00 for the engine; the tail dip is a non-flag.
- **STANDING EXCEPTION (week of Jun 8):** Chuch Pisey WORKS his day-off Mon Jun 8, special hours
  10:00–20:00 (covering Chomruen's AL), and takes **Thu Jun 11 off** instead (Vannary's swap, owner
  approved; her "Thursday 9th" resolved = Thursday the 11th). Any launch before Jun 11 must honor this.
- **HIRING-NEEDS ANALYZER (owner vision, session 28 — future organ of the brain):** the same coverage
  table tells the HIRE flow WHAT to hire: compute the week's thinnest structural windows → produce the
  hire profile ("we need MID-SHIFT now; experience optional — she can start FRONT"). New-hire skills
  start minimal (front/prep) and grow in the registry as they learn. Connects coverage engine ↔ hire bot
  when both are mature.

## 8. COVERAGE GUARDRAIL + RIPPLE CHECK (standing) ⏳ — LOCKED IN (owner session 28)
- Weekly skill map from expertise + schedules; warns BEFORE an AL/day-off/swap opens an expertise hole.
- Used inside AL approval (§5.7), swap-partner suggestion (§7.2), payback need-slots (§4.7); owner report.
- **RIPPLE CHECK (locked):** any APPROVED change (AL, swap, cancellation) automatically re-validates every
  future plan touching those days — payback slots on a vanished shift → cancelled + staff told to re-pick
  (buttons); availability pictures gone stale → coverage re-checked, seniors/owner warned. 100% automatic,
  pure logic, zero typing, zero API cost.
- **Phone-died / senior-vouch fallback: PARKED** (owner: not now, revisit if it becomes a real problem).
- **PHONE BINDING progress (session 28):** ✅ Khon Visalpisey confirmed = 768420022 (others dropped) ·
  ✅ Chuch Pisey bound via phone → uid 6818934685 · ✅ Sao Visal bound via phone → uid 5023909267 (which
  proved 'Sao Visal cv' was a DUPLICATE of him, not ex-staff — uid stripped from the dup record).
  ✅ Tyty bound via phone → uid 1067974900 · ✅ Thorn Kimheng bound via username @Kingmeow23 → uid
  6872279388. **EVERY active staff now has a uid.** Remaining: Rom Sopheaktra / Sen Vathanakthyda each
  have 2 candidate uids to settle (first DM or phone number decides which account is real).
  **USERNAMES vs IDs (owner asked):** we accept @usernames as INPUT (easy for the owner) but always store
  the numeric ID — usernames are optional, changeable, and re-assignable; the numeric ID never changes.
  Any future "bind X = @username" message → GM resolves to uid and stores that.

## 9. POINTS — CATALOGUED, **PENDING ACTIVATION** 🔒 (owner will review all causes/values, then activate)
> Design: store RAW events now (arrival times, late minutes, no-shows, check-ins) — points are a DERIVED
> view computed when owner finalizes values. No retroactive unfairness, full history available on activation.

| # | Cause | Points (owner-adjustable) |
|---|-------|--------------------------|
| P1 | Arrived >5 min early (live location in zone) — shifts AND booked payback/work slots (owner session 28: encourage, don't just break) | **+10** |
| P2/P3 | LATE — **INFORM-TIME SPLIT (owner FINAL, session 28):** minutes BEFORE they told us = **−2 each**; minutes AFTER they told us = **−1 each** (informed before shift start ⇒ all −1). **TIGHTER variant chosen:** the −1 rate holds only until their DECLARED arrival time — past it, −2 resumes (the team is guessing again). **Arriving EARLIER than declared = always fine** — actual location-measured minutes are charged, never the declared ones; over-padding ("2 hours" then 30 min) costs nothing in points but declared-vs-actual gaps are TRACKED and chronic padders surface in the digest (human conversation, not math). ≤5 min late = FREE; >5 = all minutes count from minute 1. | −2 silent / −1 informed |
| P4 | (existing) recognition/leaderboard points | unchanged |
| P5 | (future, owner) stock checks done, other duties | TBD |

- **5-MINUTE FREE WINDOW (owner updated session 28, replaces "no grace"):** late ≤5 min = free; >5 min →
  ALL minutes count from minute one (debt + points), measured by location.
- **CHECK-IN VERB (ChatGPT decision, owner session 28): ចុះវត្តមាន everywhere** (menu button updated;
  use in all future check-in strings, never ចូលវត្តមាន).

- config table `points_rules` (cause, value, active=false) — single place for the owner to adjust.
- **LEADERBOARD RESETS after every 2nd pay (owner, session 28):** when the owner confirms the 2nd pay
  went out, the points board restarts — every cycle is a fresh start ("courage for the next one").
  Repeat no-showers are an employment question, not a points question.
- **Informed-then-never-showed:** the informing earns NOTHING — no-show penalties apply in full.
- **NO-SHOW POINTS — RESOLVED (owner, session 28): −2 × every shift minute** (e.g. 9h shift ≈ −1080),
  on top of 1 day's pay + bonus not earned. Owner's consistency logic: someone 8h late on a 9h shift
  already eats ~−960, so a no-show MUST cost more or lying-by-absence beats showing up late. Monthly
  board reset keeps it recoverable.
- **BONUS LANGUAGE (extends earned/not-earned rule):** NEVER say the bonus is "gone" or "lost" — it was
  never theirs to lose. Always "no bonus this time" / "not earned".
- **RULES LIVE IN: About Work → 📜 Rules** (open to ALL staff now) — short, friendly, almost no math;
  the nudge messages stay one-liners and the precise rates live in the Rules screen + launch announcement.

## 10. RECORDS, DIGEST
- Tables ✅: al_requests, al_approvals, lateness_records, attendance_sessions; salary_usd/bonus_usd/phone
  on staff_registry ✅ (session 28). **NEW needed ⏳:** location_pings (secret feed) · payback_wallets
  (balance_min, source, deadline) + payback_events (auto-pay / scheduled chunk / AL / salary settlements) ·
  dayoff_swaps · points_rules/points_events (dormant) · emergency-AL usage stamp + bonus_eligible monthly
  flags · salary-deduction ledger (owner-gated, feeds month-end payroll).
- **Weekly digest** ✅ reads these tables. **Salary-touching actions** (pay cut, salary remainder) should be
  owner-gated + ledgered for month-end payroll.
- **PAYDAY SLIPS — OWNER-GATED BATCH (owner, session 28):** all money events silently write ledger rows
  all month; on BOTH pay days (1st + 15th) the GM asks the owner *"Do you want me to send all their payday
  slips now?"*. Owner may approve same day or days later — slips always show the pay-cycle data, not the
  approval-day data. Bonus line uses earned/not-earned wording + the approved disclaimer. **No-show ⇒
  bonus not earned — CONFIRMED.**
- **OWNER REVIEW = ONE TABLE MESSAGE, NOT 35 DMs (owner, session 28 — "don't rape the chat history"):**
  the preview is a SINGLE message (paged ~10 staff/page, ◀ ▶ buttons) listing each slip line; tap a name
  → that slip's detail + EDIT buttons (adjust amount, flip bonus earned/not-earned, add note) → ←Back.
  All edits update the SAME message in place (edit_message — Bot API, zero AI cost) and are logged for
  payroll audit. Bottom button: `✅ Approve & send all slips`. Staff each receive ONLY their own slip
  in private DM. **SLIP NAMING (owner CLARIFIED session 28): named by MONTH OF WORK, not month of
  payment** — the pay that lands June 1 + June 15 covers MAY's work, so the slips are *"May#1"* and
  *"May#2"*. **PRORATION:** joined mid-month (e.g. May 13) → that month's pay is calculated May 13–31.
- **AUTO-AL OFFERING — PARKED FOR LATER TEST (owner, session 28):** for staff with >10 AL, GM suggests
  full-day(s) AL placed on the FATTEST-coverage days for their expertise, **deliberately ADJACENT to their
  existing day off** (owner approved) so 2 AL days become a real 3-day break. Test ONE STAFF AT A TIME;
  owner reviews every pick before anything is sent. (NO auto OT offering — owner rejected.)
- **ABSOLUTE GATE (owner, session 28): until the explicit go-ahead, staff input is IGNORED entirely
  (no replies, no recording, not even silent location collection) and NOTHING is pushed to staff.**
  Only the roll-call greeting exists for staff. Testing = owner-only: /test shell + simulators +
  the whole-roster DAY DRY-RUN (compute_day_events walks every would-be message one tap at a time —
  same scheduling brain the launch jobs will use).
- **LAUNCH PROCEDURE (owner FINAL v2, session 28) — two phases:**
  1. **STEP-BY-STEP ROLE-PLAY (owner + me, no staff bugged):** GM pushes every flow to the OWNER ONLY,
     and he walks each LADDER step by step, response by response — first pretending to be the senior doing
     something, then pretending to be the person the GM pushes to next, and so on through every branch
     (attendance_test_mode). Owner tweaks wording + Khmer per message as we go.
  2. **STAGED GO-LIVE:** launch **WITHOUT the share-live-location requirement** until (a) the owner has
     fully explained it to staff AND (b) **every staff member has pressed START with the GM bot** on
     Telegram. (Hard Telegram constraint anyway: a bot CANNOT DM someone who never pressed Start — the
     Start campaign doubles as the uid-binding roll-call.)
- **KHMER/EN STRINGS AS DB TABLE (approved):** every staff-facing string lives as an editable EN+KH pair
  (not hardcoded) — role-play tweaks and later wording fixes need no deploy.
- **TIME-LEDGER DIGEST LINE (approved):** weekly digest carries *"staff owe shop Xh (N debts) · shop owes
  staff Yh (M banks)"*.
- **REMINDER HYGIENE (proposed as GLOBAL pattern):** any recurring GM reminder deletes its own previous
  message before sending the fresh one (born in the OT take-back reminder; owner hates chat clutter —
  candidate to extend to clarification nudges etc.).

---

## OUTPUTS BY DESTINATION (who sees what)
- **Private to staff:** all menus/back-and-forth, 👍 acks, check-in & arrival prompts, debt settlement,
  AL/Emergency/swap results, no-show deduction notice.
- **Private to each senior:** AL/Emergency/swap approval requests + availability + recaps.
- **Swap partner:** the swap request needing their personal ✅.
- **SUPERVISORS group (clean outcomes only):** instant lateness heads-up; approved AL/swap plain notices.
- **Private to owner:** quorum stand-offs, balance shortfalls, coverage warnings, salary-touching approvals,
  no-show/2-day-pay confirmations, uid-bind confirmations, anything unusual.
- **Never in any group:** availability details, who-approved, the questioning back-and-forth,
  family-death causes ("(family)" only). REASONS now DO reach the SUPERVISORS group (owner remodel,
  session 28): AL notices carry them; lateness reasons follow as a reply on arrival.
