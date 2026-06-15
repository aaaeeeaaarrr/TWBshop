# Khmer review - attendance / GM bot bilingual strings (TWBshop)

> Record of the bot's bilingual strings. The English is owner-approved; the Khmer is
> ChatGPT-polished and WIRED INTO CODE (gm_bot/). To review NEW strings: add them under the
> "## Pending" heading at the bottom, then paste this whole file into ChatGPT.

> **⚠ BUTTON LABELS — WIDTH RULE (owner, Jun 11):** Telegram truncates wide inline buttons.
> For any string that lives ON A BUTTON: keep the Khmer SHORT (a compact phrase, not a full
> sentence — e.g. `ស្អែកមកធ្វើការ`, never a polite long form). If English+Khmer together would
> overflow a phone-width button, say so and propose either a shorter Khmer or Khmer-only/
> English-only for that button. Message BODIES have no such limit — only buttons.

---

> **STATUS — WIRED INTO CODE (session 32, 2026-06-11).** All the polished live strings below are now
> applied in `gm_bot/`. Judgment-call deviations: (a) **English keeps "Working those hours/days"**
> (owner); the **Khmer is unified to `អ្នកធ្វើការពេលនោះ` ("who's working at that time")** for BOTH the
> hours and days labels (owner picked this over a literal `ម៉ោងនោះ`/`ថ្ងៃនោះ` split — natural Khmer). (b) `Day off = Free` → `Day off = No AL used · ថ្ងៃឈប់ = មិនដក AL` (applied). (c) The §2.6
> insufficient-balance senior card was RETIRED (replaced by the staff-side block — see the NEW section
> at the bottom), so its line is left only as a dead dry-run preview. A few owner-only dry-run preview
> lines still carry the source wording but no longer block go-live.

---

## 1. Check-in & check-out

### 1.1 Checked-out confirmation
- WHO: any staffer, private DM. WHEN: every successful checkout (manual AND silent auto-checkout
  at shift end). TONE: warm send-off — the last thing they read each day. [body]

Checked out ✓ Thank you, have a nice day! 🤍
ចុះវត្តមានចេញរួច ✓ អរគុណ សូមឱ្យថ្ងៃនេះល្អៗ 🤍

## A. Positive-points convention — ⭐ always

- WHO: staff, private DM. WHEN: footer of the shift-change card a senior sends them (and any
  card explaining pay-for-time). TONE: plain statement of the rules, the ⭐ marks the upside.
  Convention: every positive-points mention in the app carries the ⭐. [body]

You're paid for the time you work; come early → +10 points ⭐; normal late/no-show rules apply.
ប្អូនទទួលប្រាក់តាមម៉ោងដែលប្អូនធ្វើការ; មកដល់មុនម៉ោង → +10 points ⭐; ច្បាប់មកយឺត/No-show ធម្មតានៅតែអនុវត្ត។

## B. Over-balance AL → tell the STAFF

- WHO: the requesting staffer, private DM. WHEN: they picked AL days/hours costing more than
  their balance — the request is NOT submitted; this blocks it at the picker, before any senior
  sees it. {X} = days left, {Y} = days the request needs. TONE: helpful redirect, no blame. [body]

⚠ You only have {X} AL day(s) left, but this request needs {Y}. Please choose a smaller amount — you can request up to {X}.
⚠ ប្អូននៅសល់ AL តែ {X} ថ្ងៃប៉ុណ្ណោះ ប៉ុន្តែសំណើនេះត្រូវប្រើ {Y} ថ្ងៃ។ សូមជ្រើសចំនួនតិចជាងនេះ — ប្អូនអាចស្នើបានច្រើនបំផុត {X} ថ្ងៃ។

## C. Group-redirect — 5 rotating variants

- WHO: a staffer who posted an AL/sick/day-off request in a Telegram GROUP (visible to the whole
  group). WHEN: the bot detects it and replies in-group, redirecting them to DM — group messages
  are never recorded. The 5 variants rotate so the reply doesn't read like a bot stamp.
  TONE: friendly nudge, never scolding. [body, posted in-group]

1.

— AL, sick and days off only count when you tell me directly. Open @twb_gm_bot, or it won't be recorded 🙂
— AL, ឈឺ និងថ្ងៃឈប់ នឹងរាប់បានតែពេលប្អូនប្រាប់ខ្ញុំផ្ទាល់។ សូមបើក @twb_gm_bot បើមិនដូច្នេះ វានឹងមិនត្រូវបានកត់ត្រាទេ 🙂

2.

— quick reminder 🙏 time off has to come to me, not the group. Message @twb_gm_bot so it counts.
— រំលឹកបន្តិច 🙏 រឿងសុំឈប់ត្រូវផ្ញើមកខ្ញុំផ្ទាល់ មិនមែនផ្ញើក្នុង group ទេ។ សូមផ្ញើសារទៅ @twb_gm_bot ដើម្បីឱ្យវារាប់។

3.

— I can only record this if it comes to me 🙂 Please tap @twb_gm_bot; group messages don't count.
— ខ្ញុំអាចកត់ត្រារឿងនេះបានតែបើប្អូនផ្ញើមកខ្ញុំផ្ទាល់ 🙂 សូមចុច @twb_gm_bot; សារក្នុង group មិនរាប់ទេ។

4.

— leave, sick and day-off only register when you tell me at @twb_gm_bot. The group chat doesn't count 🙏
— AL, ឈឺ និងថ្ងៃឈប់ នឹងត្រូវកត់ត្រាតែពេលប្អូនប្រាប់ខ្ញុំតាម @twb_gm_bot ប៉ុណ្ណោះ។ សារក្នុង group មិនរាប់ទេ 🙏

5.

— this won't be counted from here 🙂 For AL, sick or time off, message me directly at @twb_gm_bot.
— រឿងនេះមិនរាប់ពី group នេះទេ 🙂 សម្រាប់ AL, ឈឺ ឬសុំឈប់ សូមផ្ញើសារមកខ្ញុំផ្ទាល់តាម @twb_gm_bot។

## Z. Hours-AL Supervisors notice

- WHO: the Supervisors group (seniors — but kept bilingual app-wide). WHEN: an HOURS-based AL
  (part of a shift off, not whole days) was approved — the group must know the coverage gap and
  when the person is back. {name} = call name; times/dates here are EXAMPLES, the code inserts
  real ones. TONE: informational. [body, group post]

{name} on leave 9pm–12am on Tue 23/06, Wed 24/06, Thu 25/06.
{name} ឈប់សម្រាក 9pm–12am នៅ Tue 23/06, Wed 24/06, Thu 25/06។

Back at work: 12am each of those nights (rest of shift as normal).
ត្រឡប់មកធ្វើការ 12am រាល់យប់នោះ (ម៉ោងនៅសល់នៃវេនធ្វើធម្មតា)។

---

## ChatGPT review notes (kept for reference)

Only real Khmer warning: do not use “ច្បាប់ AL”. It sounds doubled and awkward. Use AL alone, or AL, ឈឺ និងថ្ងៃឈប់ when listing categories.
One implementation warning: for variant 4, I used AL, ឈឺ និងថ្ងៃឈប់ instead of translating “leave” as ច្បាប់ឈប់. ច្បាប់ឈប់ is understandable, but it feels less natural and can sound like “permission/rule” rather than the bot category.

## D. Sick & decline accountability — WIRED Jun 11 (ChatGPT-polished, final)

> Shared context (all P1–P9 are staff private-DM unless noted): nightly sick nudges are
> expectation-first (coming = default), every "no" button costs a typed reason that the named
> recipient reads, 10/20-min silence nudges, auto-resolve at 30. Buttons follow the width rule.

P1 family nudge — sent ~8pm to a staffer off for a sick FAMILY member, asking about tomorrow
({relation} = child/spouse/parent, inserted as-is) [body]:
I hope your {relation} is better now 🤍 Are you coming tomorrow?
សង្ឃឹមថា {relation} របស់ប្អូនធូរស្បើយហើយ 🤍 ស្អែកប្អូនមកធ្វើការមែនទេ?

P2 "no" buttons — the "not coming" answer on three nudges; tapping arms the typed-reason prompt
(a = the P1 family nudge · b = the P3 own-sick nudge · c = day-1 sick opener "really can't come
in today?") [BUTTONS]:
[a] 📝 Can't come — explain · មកមិនបាន — ពន្យល់
[b] 📝 Still resting — explain · សម្រាកបន្ត — ពន្យល់
[c] 📝 Really can't — explain · មិនអាចមក — ពន្យល់

P3 own-sick nightly question — sent ~8pm to a staffer off sick THEMSELVES, asking about
tomorrow [body]:
I hope you're feeling better now 🤍 Are you coming in tomorrow?
សង្ឃឹមថាប្អូនធូរស្បើយហើយ 🤍 ស្អែកប្អូនមកធ្វើការមែនទេ?

P4 type-the-reason prompt — after a P2 "no" tap on a SICK flow; their next typed message goes
to the Supervisors group [body]:
Please type the reason — it goes to the Supervisors. 🤍
សូមវាយមូលហេតុ — វានឹងផ្ញើទៅបងៗ។ 🤍

P5 family re-book confirmation — after the typed reason lands: tomorrow's family-sick day is
booked (burns 1 of the 7-day family pool) and the staffer is told it's handled [body]:
Noted — tomorrow is covered. Take care 🤍
កត់ចំណាំហើយ — ស្អែកបានរៀបចំការឈប់ឱ្យរួចហើយ។ ថែទាំឱ្យបានល្អ 🤍

P6 decline buttons — every rejection costs a typed reason; tapping arms the P7 prompt
(a = senior rejecting an AL/swap approval card · b = swap partner refusing · c = staff
declining a senior's shift change) [BUTTONS]:
[a] ❌ Not approve — explain · មិនអនុម័ត — ពន្យល់
[b] ✋ No — explain · ទេ — ពន្យល់
[c] ❌ Can't — explain · មិនអាច — ពន្យល់

P7 one-line-why prompt — right after a P6 tap; the decision already landed (act-first),
this asks for the why ({name} = the person who will read the reason) [body]:
📝 One line why — it goes to {name}.
📝 មូលហេតុ 1 ឃ្លា — នឹងផ្ញើទៅ {name}។

P8 silence nudge — they tapped a "no/explain" button but typed nothing; re-asked at 10 and
20 minutes (max twice), auto-resolves at 30 [body]:
Still need one line from you 🤍 just type why.
នៅខ្វះមូលហេតុ 1 ឃ្លាពីប្អូន 🤍 សូមវាយប្រាប់មូលហេតុ។

P9 relay ack — the typed reason was delivered to its recipient; closes the loop [body]:
Sent 🤍
ផ្ញើរួចហើយ 🤍

### ChatGPT notes from this pass (kept)
- Don't hardcode the relation in P1 — one {relation} placeholder (the code inserts it dynamically).
- P5: "ស្អែកក៏បានឈប់ដែរ" was too blunt ("you can just stay off again"); the wired wording reads as
  "the bot has arranged/recorded it".
- Button Khmer shortened (សូមពន្យល់ → ពន្យល់) per the width rule.

## E. P10–P15 — WIRED Jun 13 (ChatGPT-polished, final)

> ChatGPT's polished batch applied to gm_bot/ on 2026-06-13 (commit follows this doc edit).
> Context per entry kept below. Wiring deviations:
> (a) **P11a** — ChatGPT's "…ពី menu។" DROPPED: the live English had already been shortened to
>     "please start again." (no "from the menu"), so the wired KH matches it.
> (b) **P15g** — ChatGPT correctly re-added {relation} inside the Khmer; wired through
>     `_who_kh()` (child→កូន, spouse→ប្តី/ប្រពន្ធ, parent→ឪពុក/ម្តាយ) so it can never show raw English.
> (c) **P14/P15 register** — ChatGPT's អ្នក→ប្អូន adopted EVERYWHERE the old draft said អ្នក,
>     including the shared "+10 points" line (7 spots) and all dry-run preview mirrors.
> (d) **P15e SENIOR card** — ChatGPT's two-line Khmer structure adopted (was one line with ។).

### P10 · Reason-relay + detailed rejections
- WHO: the requester (junior staff), private DM, right after a decliner types their reason.
- WHEN: a senior ❌'d their AL/swap (one ❌ decides), the partner said no, or a staffer declined
  a senior's shift change. {what_kh} = សំណើ AL (dates) · ការប្តូរថ្ងៃឈប់ (d1 ↔ d2) · ការប្តូរវេន
  (date time); {name} = decliner's call name; {reason} = typed text. TONE: neutral courier. [body]

📝 About your {what} — {name}: {reason}
📝 អំពី {what_kh} របស់ប្អូន — {name}៖ {reason}

Your AL for {dates} wasn't approved. · AL របស់ប្អូនសម្រាប់ {dates} មិនបានអនុម័តទេ។
The day-off swap ({d1} ↔ {d2}) wasn't approved. · ការប្តូរថ្ងៃឈប់ ({d1} ↔ {d2}) មិនបានអនុម័តទេ។

### P11 · Expired-button lines
- WHO: any staffer tapping a button that no longer works. WHEN: (a) the message itself collapses
  (orphaned buttons); (b) toast over an intact card; (c) recovery button under the collapsed line.
- TONE: blameless and directive.

(a) ⏳ Expired message — please start again. [body]
    ⏳ សារនេះផុតកំណត់ហើយ — សូមចាប់ផ្តើមម្តងទៀត។

(b) ⏳ Expired — try again · ផុតកំណត់ — សាកម្តងទៀត [TOAST]

(c) 📋 Open menu · បើក menu [BUTTON]

### P12 · Cancel AL flow (My Schedule)
- WHO: junior staff DM. WHEN: My Schedule → ✕ Cancel AL → list → confirmation → cancel.
- TONE: clear and calm. ChatGPT unified the verb to បោះបង់ (cancel), replacing the draft's លុប (delete).

✕ Cancel AL · បោះបង់ AL [BUTTON]

Which AL day do you want to cancel? [list header]
ប្អូនចង់បោះបង់ AL ថ្ងៃណា?

No upcoming AL to cancel. [empty case]
គ្មាន AL ខាងមុខដែលអាចបោះបង់បានទេ។

Are you sure you want to cancel your AL on {detail}? [confirm body]
This will return 1 day to your AL balance.
ប្អូនពិតជាចង់បោះបង់ AL នៅ {detail} មែនទេ?
វានឹងដាក់ AL 1 ថ្ងៃ ត្រឡប់ចូល balance របស់ប្អូនវិញ។

✅ Yes, cancel it · បោះបង់ [BUTTON] · ← Back · ត្រឡប់ក្រោយ [BUTTON]

Too late to cancel — that day has already started · យឺតពេលបោះបង់ហើយ — ថ្ងៃនោះបានចាប់ផ្តើមហើយ [TOAST]

### P13 · Book pay-back time — About Me picker
- WHO: junior staff DM. WHEN: About Me → 📅 Book pay-back time. TONE: matter-of-fact.
- ChatGPT relabeled the debt as ម៉ោងត្រូវសង ("hours to repay") — clearer than the money-loan-sounding បំណុល.

Debt · ម៉ោងត្រូវសង: {debt} [body]
Booked · បានកក់រួច: {booked_total}:
  {slot_lines}

Choose the times below to pay — these are the times we need you most:
សូមជ្រើសម៉ោងខាងក្រោមដើម្បីសង — ពេលទាំងនេះហាងត្រូវការប្អូនបំផុត៖

📅 Book pay-back time · កក់ម៉ោងសងវិញ [BUTTON]

### P14 · Pay-back flow messages
- WHO: staff DM. {X} = duration ("1h 30m"); {day}/{start}/{end} = "Sat 13/06" / "9am". [bodies]

a) fully booked (no picker):
Your pay-back time is already fully booked ✓ Just work the booked times.
ម៉ោងសងវិញរបស់ប្អូនបានកក់រួចទាំងអស់ហើយ ✓ សូមមកធ្វើតាមម៉ោងដែលបានកក់។

b) late check-in + picker:
Checked in ✓ — {X} late (counts as pay-back). Pick when to work it off — the times we need you most:
ចុះវត្តមានរួច ✓ — យឺត {X} (រាប់ជាម៉ោងសងវិញ)។ សូមជ្រើសពេលធ្វើសង — ពេលទាំងនេះហាងត្រូវការប្អូនបំផុត៖

b2) late check-in, fully booked: the b) first sentence + the a) line.

c) re-offer / ladder picker:
You owe {X}. Pick when to work it off — these are the times we need you most:
ប្អូននៅត្រូវសង {X}។ សូមជ្រើសពេលធ្វើសង — ពេលទាំងនេះហាងត្រូវការប្អូនបំផុត៖

c2) appended when partly booked:
({booked} booked already · បានកក់រួច {booked} — {remaining} left to book · នៅសល់ {remaining} ត្រូវកក់)

d) clash / stale slot:
That time isn't available any more — {remaining} left to book. Pick again:
ពេលនោះមិនអាចកក់បានទៀតទេ — នៅសល់ {remaining} ត្រូវកក់។ សូមជ្រើសម្តងទៀត៖

e) booking confirmation:
Booked ✓ — {day} {start}–{end}. · បានកក់រួច ✓ — {day} {start}–{end}។
Come 5 minutes early and you earn +10 points ⭐
មកដល់មុន 5 នាទី ប្អូននឹងទទួលបាន +10 points ⭐

f) stale-button short re-offer:
You owe {X} — pick when to work it off: · ប្អូននៅត្រូវសង {X} — សូមជ្រើសពេលធ្វើសង៖

### P15 · Shift-change + day-off-swap cards & notices
- Context: a senior re-times a working day (OT = worked beyond normal length); day-off swaps.
  {date}/{window}/{tag}/{reason}/{req}/{partner}/{d1}/{d2} as the flows insert them.

a) shift-change card (staff approves/declines) [body]:
🕒 Shift change — {date}: {window}{tag} · 🕒 ប្តូរវេន — {date}៖ {window}{tag}
Why · មូលហេតុ៖ {reason}
status suffixes: ✅ Approved · បានយល់ព្រម | ❌ Declined · មិនបានយល់ព្រម | ✅ Done · រួចរាល់
✅ Approve · យល់ព្រម [BUTTON] (decline = P6c)

b) senior's sent-confirmation [body]:
✅ Shift change sent — the staff is asked to approve.
✅ បានផ្ញើការស្នើប្តូរវេនហើយ — កំពុងរង់ចាំបុគ្គលិកយល់ព្រម។

c) senior reason prompt [body]:
📝 Type the reason — your next message sends it to them for approval.
📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើទៅពួកគាត់ ដើម្បីសុំការយល់ព្រម។

d) senior picker header [body]:
Give OT / change a shift — for whom? · ឱ្យ OT / ប្តូរវេន — សម្រាប់អ្នកណា?

e) swap cards (Reason · មូលហេតុ៖ {reason} closes each) [bodies]:
PARTNER: {req} wants to swap day off: {req} takes {d1} off, you take {d2} — same week.
         {req} ស្នើសុំប្តូរថ្ងៃឈប់ជាមួយប្អូន៖ {req} ឈប់ {d1}, ប្អូនឈប់ {d2} — ក្នុងសប្តាហ៍ដដែល។
REQUESTER: Day-off swap — your off {d1} ↔ {partner} off {d2}.
           ប្តូរថ្ងៃឈប់ — ប្អូនឈប់ {d1} ↔ {partner} ឈប់ {d2}។
SENIOR: Day-off swap: {req} ↔ {partner} / {req} off {d1}, {partner} off {d2}.
        ប្តូរថ្ងៃឈប់៖ {req} ↔ {partner} / {req} ឈប់ {d1}, {partner} ឈប់ {d2}។

f) partner declined → requester [body]:
Your day-off swap ({d1} ↔ {d2}) wasn't accepted by your partner.
អ្នកដែលត្រូវប្តូរជាមួយ មិនបានយល់ព្រមលើការប្តូរថ្ងៃឈប់ ({d1} ↔ {d2}) របស់ប្អូនទេ។

g) family-sick extension FYI → Supervisors group [body; {relation_kh} via _who_kh]:
FYI: {name}'s family-sick continues tomorrow ({relation}).
FYI: {name} បន្តសុំច្បាប់ឈឺសម្រាប់{relation_kh}ដល់ថ្ងៃស្អែក។
Reason · មូលហេតុ៖ {reason}

---

## Pending - new strings for the next ChatGPT pass

> CONTRACT: no string enters here without its context block — WHO reads it, WHEN it fires, what
> each {variable} is, the intended TONE, and BUTTON vs body. (See the record sections above for
> the format.)

### A1 — Schedule Changes redesign (Jun 15) — Change time +OT
- **WHO reads it:** seniors (the menu/picker) + the staffer (the verdict lines on their card).
- **WHEN:** the new "Staff Changes" flow under About Work; verdict lines fire when staff approves/declines.
- **TONE:** plain, clear. BUTTON = the menu/picker labels; the rest are short status lines. My KH is draft.
- Buttons / headers (EN · KH draft):
  - `🗓 Staff Changes (1 time)` · `ការផ្លាស់ប្តូរ (1 ដង)`
  - `🗓 Staff Changes (forever)` · `ការផ្លាស់ប្តូរ (រហូត)`
  - `⏱ Change time +OT` · `ប្តូរម៉ោង +OT`
  - `📅 Change day off` · `ប្តូរថ្ងៃឈប់`
  - menu header `Staff Changes (1 time) — pick one.` · `ការផ្លាស់ប្តូរ (1 ដង) — ជ្រើសមួយ។`
  - `Change time +OT — for whom?` · `ប្តូរម៉ោង +OT — សម្រាប់អ្នកណា?`
  - day picker `Change {nm}'s shift — which work day? (next 30 days)` · `ប្តូរវេនរបស់ {nm} — ថ្ងៃធ្វើការណា? (30 ថ្ងៃខាងមុខ)`
  - `⏱ Normal times {ws}–{we}` · `ម៉ោងធម្មតា {ws}–{we}`
  - start header `{day} — START time? (or ⏱ Normal times above)` · `{day} — ម៉ោងចាប់ផ្តើម?`
  - `🚧 {what} — coming next.` · `🚧 {what} — នឹងមកដល់ឆាប់ៗ។`
- Verdict lines (8a-1, on the senior's card when staff decides):
  - `✅ Approved` · `បានយល់ព្រម`
  - `❌ Declined` · `បានបដិសេធ`
  - `✋ Declined — leave kept` · `បានបដិសេធ — រក្សា AL`
  - `✅ Approved (AL refunded)` · `បានយល់ព្រម (AL ដាក់ត្រឡប់ចូលវិញ)`

### A2 — Change day off (a real move) — Jun 15
- **WHO:** seniors (the picker) + the staffer (the move card). **WHEN:** the new A2 flow under Staff
  Changes; the card is the staffer's approval card. **TONE:** plain, clear. My KH is draft.
- `Change day off — for whom?` · `ប្តូរថ្ងៃឈប់ — សម្រាប់អ្នកណា?`
- `{nm} — which day should they be OFF? (next 30 days)` · `{nm} — គួរឈប់សម្រាកថ្ងៃណា? (30 ថ្ងៃខាងមុខ)`
- `{nm} off {X} — which day-off will they WORK instead? (within 7 days)` · `{nm} ឈប់ {X} — នឹងធ្វើការជំនួសថ្ងៃឈប់ណា? (ក្នុង 7 ថ្ងៃ)`
- `{Y} · their day off` (button) · `{Y} · ថ្ងៃឈប់របស់គេ`
- `{Y} (their day off) — START time? (or ⏱ Normal times)` · `{Y} — ម៉ោងចាប់ផ្តើម?`
- prompt `Day-off move — {nm}: OFF {X}, works {Y} {win}{ot}.` · `ប្តូរថ្ងៃឈប់ — {nm}៖ ឈប់ {X}, ធ្វើការ {Y} {win}{ot}។`
- card `🗓 Day-off move — you're OFF {X}, and you WORK {Y}: {win}` · `🗓 ប្តូរថ្ងៃឈប់ — ប្អូនឈប់ {X}, ហើយធ្វើការ {Y}៖ {win}`
- A2 card 👁 both-date coverage (seniors+staff): `OFF {X} — who works (covers)` · `ឈប់ {X} — អ្នកធ្វើការ` ·
  `WORKS {Y} — who works` · `ធ្វើការ {Y} — អ្នកធ្វើការ`

### Walk findings (Jun 15) — co-approve collapse · mandatory reason · A2/co-approve coverage toggle
- **WHO/WHEN:** seniors during the A1/A2 co-approval + reason steps. **TONE:** plain. My KH is draft.
- co-approve card sibling-collapse, when ANOTHER senior already co-approved (button-less terminal line):
  `✅ Already co-approved by another senior — sent to {nm}` · `បានយល់ព្រមរួមដោយបងម្នាក់ទៀត — ផ្ញើទៅ {nm}`
- co-approve card sibling-collapse, when ANOTHER senior declined:
  `❌ Stopped — another senior declined this change` · `បានបញ្ឈប់ — បងម្នាក់ទៀតមិនបានយល់ព្រម`
- mandatory-reason nag (any schedule change submitted with a blank reason):
  `📝 A reason is required for a schedule change — please type the reason.` · `📝 ត្រូវការមូលហេតុសម្រាប់ការប្តូរវេន — សូមសរសេរមូលហេតុ។`
- The co-approve card + A2 reason prompt reuse the EXISTING 👁/🙈 toggle + both-date coverage strings
  (already vetted above) — no new toggle wording.

### WF2/WF3 — family-sick (Jun 14) — KH draft
- **WHO:** the staffer (confirm + booked) + Supervisors (FYI). **WHEN:** family-sick TIMES path now asks a confirm; FYI on booking.
- WF2 confirm `Family sick ({who}) — {window}.` · `គ្រួសារឈឺ ({who}) {window}។`  (window = `9:00am → 12:00pm`)
- WF3 FYI `FYI: {nm} takes sick leave for their {who} today ({window}).` · `FYI: {nm} សុំច្បាប់ឈឺសម្រាប់{who_kh}ថ្ងៃនេះ ({window})។`
  (no window = drop the parens: `…today.` · `…ថ្ងៃនេះ។`)

### WF5 — partner-swap redesign (Jun 14) — KH draft
- **WHO:** the requesting staffer. **WHEN:** the new 🔁 Change day off flow (pick partner → pick a pairing).
- partner picker `Swap day off — pick WHO to trade with (a different day off, similar shift times). You'll then choose a date-pairing.` ·
  `ប្តូរថ្ងៃឈប់ — ជ្រើសអ្នកដែលប្តូរជាមួយ (ថ្ងៃឈប់ខុសគ្នា, ម៉ោងវេនប្រហាក់ប្រហែល)។ បន្ទាប់មកជ្រើសគូកាលបរិច្ឆេទ។`
- `Your day off · ថ្ងៃឈប់របស់អ្នក៖ {day_off}`
- pairing button `🔁 you off {their_day} · {partner} off {your_day}` · (KH: `🔁 អ្នកឈប់ {their_day} · {partner} ឈប់ {your_day}`)
- pairings header `Swap with {pn} — pick a pairing. You take their day off, they take yours (≤ 6 days apart, coverage stays even).` ·
  `ប្តូរជាមួយ {pn} — ជ្រើសគូមួយ។ អ្នកយកថ្ងៃឈប់របស់គេ គេយកថ្ងៃឈប់របស់អ្នក (ក្នុង 6 ថ្ងៃ)។`
- no-pairing `No close day-off pairing with {pn} in the next 3 weeks (need ≤6 days apart, a different day off, and neither date already swapped).` ·
  `គ្មានគូថ្ងៃឈប់ជិតគ្នាជាមួយ {pn} ក្នុង 3 សប្តាហ៍ខាងមុខទេ។`

### MM1 — prompt superseded (multi-menu fix, piece 2)
- **WHO reads it:** a staffer who had a reason-prompt open ("type why…") and then started a *second*
  flow that opened its own prompt. The OLD prompt message is edited in place to this line.
- **WHEN it fires:** the moment the newer prompt is armed (the old one's typed-reason slot is about to
  be overwritten) — so they don't type into a dead prompt and have it silently land in the new flow.
- **TONE:** plain, reassuring, directive — "this one's stale, use the new one below." Not an error.
- **BUTTON vs body:** body text (buttons already removed/irrelevant). No variables.
- Live English: `↩ Replaced — answer the newer prompt below`
- Draft KH (mine, needs polish): `↩ បានជំនួស — សូមឆ្លើយសំណួរថ្មីខាងក្រោម`

### MM2 — Cancel button on armed prompts (Stage 1, F5)
- **WHO reads it:** any staffer on an armed reason/confirm prompt (AL, swap, shift, sick/marriage/
  death/birth). Replaces the old `← Back` on those prompts only.
- **WHEN:** always shown on the armed prompt; tapping it disarms the pend and returns to the menu.
- **TONE:** plain action label. **BUTTON.** No variables.
- Live English: `✕ Cancel` · Draft KH: `បោះបង់`

### MM3 — voice/photo refused on a reason prompt (Stage 1, F1)
- **WHO reads it:** a staffer who sends a voice note / photo instead of typing their reason.
- **WHEN:** the moment they send non-text while a reason prompt is armed; the prompt stays armed so
  their next typed line still submits.
- **TONE:** gentle, helpful, not an error — "I can't read that here, please type." **BODY.** No vars.
- Live English: `🎤 I can't read a voice note / photo here — please type your reason in one line.`
- Draft KH (mine, needs polish): `🎤 ខ្ញុំមិនអាចអានសារសំឡេង/រូបភាពនៅទីនេះបានទេ — សូមវាយមូលហេតុជាអក្សរ ១បន្ទាត់។`
- (owner walk Jun 13: dropped "or use the buttons below" — the refuse is a standalone reply, no buttons under it)

### MM4 — expiry / dead-tap nudge (Stage 2, F2/F3, Law 6/8)
- **WHO reads it:** a staffer whose tap-confirm card expired, or who typed a reason after the prompt
  expired. A FRESH message is pushed (so it notifies); the stale card is deleted.
- **WHEN:** on a dead/expired tap-confirm, or loose text after a just-expired reason pend.
- **TONE:** an honest alarm-but-recoverable nudge — caps EN, **bold KH**, then the details of what
  expired, then an Open-menu button. NOT a generic error.
- **BUTTON + BODY.** No variables (the detail line is the expired card's own text).
- Header EN: `❗ NOT CONFIRMED — TRY AGAIN` · KH (bold): `❗ មិនទាន់បានបញ្ជាក់ — សូមធ្វើម្ដងទៀត`
- Button: `📋 Open menu · បើក menu`

### MM5 — stale screen guard (Stage 3, F4/F10)
- **WHO:** a staffer tapping a button on an OLD screen whose selection was reset (new menu / restart).
- **WHEN:** instead of filing empty data or crashing. **BODY + Open-menu button.** No vars.
- EN: `⏳ This screen is old — please open the menu to start again.`
- KH: `⏳ ផ្ទាំងនេះចាស់ហើយ — សូមបើក menu ដើម្បីចាប់ផ្តើមម្តងទៀត។`

### MM6 — maintenance toast (Stage 3, F12)
- **WHO:** any staffer tapping any att button while attendance_live is OFF (maintenance/rollback).
- **WHEN:** instead of a silently dead button. **TOAST (show_alert popup).** No vars.
- EN: `🔧 Attendance is paused for maintenance — please talk to your senior.`
- KH: `ប្រព័ន្ធត្រូវបានផ្អាក — សូមនិយាយទៅបងៗ។`

### MM8 — collapsed old menu (Stage 6, P1 singleton)
- **WHO:** a staffer whose OLDER menu is collapsed when they open a newer one.
- **WHEN:** the old menu message is edited to this pointer (buttons removed) so two live menus can't
  share state. **BODY** (no buttons). No vars.
- EN: `⤵ Menu continues below` · KH: `ម៉ឺនុយនៅខាងក្រោម`

### MM7 — mid-pick typing guard (Stage 3, F8)
- **WHO:** a staffer who TYPES while mid-selection (days/time/swap) instead of tapping Done/Cancel.
- **WHEN:** to stop the typed message wiping their in-progress pick. **BODY.** No vars.
- EN: `You're in the middle of picking — tap ✅ Done or ✕ Cancel on the message above.`
- KH: `ប្អូនកំពុងជ្រើសរើស — សូមចុច ✅ រួចរាល់ ឬ ✕ បោះបង់ នៅសារខាងលើ។`

---
### F14 / schedule-model strings (session 33, Jun 13 — KH is MY draft, needs the native pass).
All behind attendance_live=OFF; rare conflict paths. Collected late (the re-sweep miss).

### SM1 — AL approval blocked by a same-day conflict (→ requester)
- **WHO/WHEN:** F14 — a senior tried to approve AL on a day already holding approved leave/shift-change.
- EN: `Couldn't approve — you already have approved leave on one of those days.`
- KH: `មិនអាចអនុម័តបានទេ — ប្អូនមានច្បាប់ឈប់សម្រាកដែលអនុម័តរួចនៅថ្ងៃនោះ។`

### SM2 — shift-change approval blocked by AL that day (→ staff)
- EN: `Couldn't approve — you have approved leave that day.`
- KH: `មិនអាចអនុម័តបានទេ — ប្អូនមានច្បាប់ឈប់សម្រាកនៅថ្ងៃនោះ។`

### SM3 — day-off swap approval blocked (→ both parties)
- EN: `Couldn't approve the swap — one of you has approved leave on a day it needs worked.`
- KH: `មិនអាចអនុម័តការប្តូរបានទេ — ម្នាក់ក្នុងចំណោមអ្នកមានច្បាប់ឈប់សម្រាកនៅថ្ងៃដែលត្រូវធ្វើការ។`

### SM4 — request-side block: don't submit an already-committed day (→ requester). VAR: `%s` = date(s).
- EN: `⚠ You already have approved leave or a scheduled shift change on: %s.` / `Pick other day(s).`
- KH: `⚠ ប្អូនមានច្បាប់ឈប់សម្រាក ឬការប្តូរវេនដែលអនុម័តរួចនៅ៖ %s។ សូមជ្រើសថ្ងៃផ្សេង។`

### SM5 — Cancel-AL confirm, exact refund label (S4). VAR: `%g` = fractional AL.
- EN: `1 day` · `no AL (this day costs none)` · `%g AL`
- KH: `AL 1 ថ្ងៃ` · `មិនដក AL (ថ្ងៃនេះមិនអស់ AL)` · `AL %g`

### SM6 (FUTURE, Phase 4 notify-all — draft only, not yet wired) — "new replaced old".
- EN: `🔁 {new — date · times · who} replaces {old — date · times · who}` (to supervisors + staff + senior + partner)
- KH: (to draft with ChatGPT when Phase 4 lands — the verb "ជំនួស/ផ្លាស់ប្តូរ" + the bilingual card form)

### SM7 (WIRED, Phase 3b-i/ii/iii) — an AWAY event stood down a senior redefine → notify senior + Supervisors.
Sent by `_announce_supersessions` (redefine kind) when AL / sick / special-leave supersedes a senior
redefine that day. VARS: `{name}`, `{date}`=`Mon 15/09`, `{times}`=` (6:00–14:00)` or empty,
`{away}` (EN ONLY — the KH half uses generic អវត្តមាន): `took approved AL` · `is out sick` ·
`is on bereavement leave` · `is on paternity leave`.
- EN: `🔁 {name} {away} on {date} — the shift change set for them{times} no longer applies. Please re-arrange cover if needed.`
- KH (my draft): `🔁 {name} អវត្តមាននៅ {date} — ការប្តូរវេនដែលបានកំណត់ឱ្យ{times} លែងប្រើទៀតហើយ។ សូមរៀបចំអ្នកជំនួសបើចាំបាច់។`

### SM8 (WIRED, Phase 3b-ii) — a sick day refunded a planned AL → notify the staffer + Supervisors.
`_announce_supersessions` "al" kind. VARS: `{name}`, `{date}`, `{n}`=AL days back (`%g`).
- EN: `🔁 {name} is now away on {date} — the AL approved for that day was returned (+{n} AL).`
- KH (my draft): `🔁 {name} ឥឡូវអវត្តមាននៅ {date} — AL ដែលអនុម័តសម្រាប់ថ្ងៃនោះត្រូវបានបង្វិលសងវិញ (+{n} AL)។`

### SM9 (WIRED, Phase 3b-iv) — confirmed-revoke: AL cancelled because a shift change was approved → staffer + Supervisors.
`_announce_supersessions` "al_revoked" kind. VARS: `{name}`, `{date}`, `{n}`.
- EN: `🔁 {name}'s approved AL on {date} was cancelled — a shift change for that day was approved instead. The AL is refunded (+{n} AL).`
- KH (my draft): `🔁 ច្បាប់ឈប់សម្រាក (AL) របស់ {name} នៅ {date} ត្រូវបានបោះបង់ — បានអនុម័តការប្តូរវេនជំនួសវិញ។ AL ត្រូវបានបង្វិលសង (+{n} AL)។`

### SM10 (WIRED, Phase 3b-iv) — the confirm-revoke CARD the staffer sees (approve a redefine on their own AL day).
Edited onto the shift-change card when they tap approve. VARS: `{date}`, `{win}`=`6:00-14:00`.
- EN: `⚠ You have approved AL on {date}. Approving this shift change ({win}) will CANCEL that leave (your AL is refunded) and schedule you to work. Confirm?`
- KH (my draft): `⚠ ប្អូនមានច្បាប់ឈប់សម្រាក (AL) ដែលអនុម័តនៅ {date}។ ការអនុម័តការប្តូរវេននេះ ({win}) នឹងបោះបង់ច្បាប់ឈប់នោះ (AL បង្វិលសងវិញ) ហើយកំណត់ឱ្យប្អូនធ្វើការ។ បញ្ជាក់ទេ?`
- BUTTONS — EN: `✅ Yes — cancel my leave & work` · `✋ Keep my leave`
- BUTTONS — KH (my draft): `✅ បាទ/ចាស — បោះបង់ច្បាប់ ធ្វើការ` · `✋ រក្សាច្បាប់ឈប់សម្រាក`

### SM11 (WIRED, Phase 3b-iv) — "kept my leave": staffer declined the leave-revoking shift change → the proposing senior.
VARS: `{name}`, `{date}`.
- EN: `{name} kept their approved leave on {date} — the shift change was not approved.`
- KH (my draft): `{name} រក្សាច្បាប់ឈប់សម្រាកនៅ {date} — ការប្តូរវេនមិនបានអនុម័តទេ។`

### SM12 (WIRED, Phase 6) — a day-off swap voided because one party is now away → BOTH parties + Supervisors.
`_announce_supersessions` "swap" kind. VARS: `{rn}`=requester, `{pn}`=partner, `{name}`=the away one.
- EN: `🔁 The day-off swap between {rn} and {pn} is off — {name} is now away. Both are back to their normal days; please arrange cover if needed.`
- KH (my draft): `🔁 ការប្តូរថ្ងៃឈប់រវាង {rn} និង {pn} ត្រូវបានលុបចោល — {name} អវត្តមាន។ ទាំងពីរនាក់ត្រឡប់ទៅថ្ងៃធម្មតាវិញ។ សូមរៀបចំអ្នកជំនួសបើចាំបាច់។`

You gave a new batch: MM1–MM8 plus SM1–SM12. I’m treating the older P10–P15 as already wired/final and only polishing the pending section from the latest upload.
## MM1 — prompt superseded

↩ Replaced — answer the newer prompt below
↩ បានជំនួសហើយ — សូមឆ្លើយសំណួរថ្មីខាងក្រោម

## MM2 — Cancel button on armed prompts

✕ Cancel · បោះបង់

## MM3 — voice/photo refused on a reason prompt

🎤 I can't read a voice note / photo here — please type your reason in one line.
🎤 ខ្ញុំមិនអាចអានសារសំឡេង/រូបថតនៅទីនេះបានទេ — សូមវាយមូលហេតុជា 1 បន្ទាត់។

## MM4 — expiry / dead-tap nudge

❗ NOT CONFIRMED — TRY AGAIN
❗ **មិនទាន់បានបញ្ជាក់ — សូមធ្វើម្ដងទៀត**

📋 Open menu · បើក menu

## MM5 — stale screen guard

⏳ This screen is old — please open the menu to start again.
⏳ ផ្ទាំងនេះចាស់ហើយ — សូមបើក menu ដើម្បីចាប់ផ្តើមម្តងទៀត។

📋 Open menu · បើក menu

## MM6 — maintenance toast

🔧 Attendance is paused for maintenance — please talk to your senior.
🔧 ប្រព័ន្ធវត្តមានកំពុងផ្អាកដើម្បីថែទាំ — សូមនិយាយជាមួយបងៗ។

## MM8 — collapsed old menu

⤵ Menu continues below
⤵ menu បន្តនៅខាងក្រោម

## MM7 — mid-pick typing guard

You're in the middle of picking — tap ✅ Done or ✕ Cancel on the message above.
ប្អូនកំពុងជ្រើសរើស — សូមចុច ✅ Done ឬ ✕ Cancel នៅសារខាងលើ។

## SM1 — AL approval blocked by same-day conflict

Couldn't approve — you already have approved leave on one of those days.
មិនអាចអនុម័តបានទេ — ប្អូនមានការឈប់សម្រាកដែលបានអនុម័តរួច នៅថ្ងៃមួយក្នុងចំណោមថ្ងៃទាំងនោះ។

## SM2 — shift-change approval blocked by AL that day

Couldn't approve — you have approved leave that day.
មិនអាចអនុម័តបានទេ — ប្អូនមានការឈប់សម្រាកដែលបានអនុម័តរួចនៅថ្ងៃនោះ។

## SM3 — day-off swap approval blocked

Couldn't approve the swap — one of you has approved leave on a day it needs worked.
មិនអាចអនុម័តការប្តូរថ្ងៃឈប់បានទេ — ម្នាក់ក្នុងចំណោមប្អូនទាំង 2 មានការឈប់សម្រាកដែលបានអនុម័តរួច នៅថ្ងៃដែលត្រូវមកធ្វើការ។

## SM4 — request-side block

⚠ You already have approved leave or a scheduled shift change on: %s.
⚠ ប្អូនមានការឈប់សម្រាកដែលបានអនុម័តរួច ឬការប្តូរវេនដែលបានកំណត់រួច នៅ៖ %s។

Pick other day(s).
សូមជ្រើសថ្ងៃផ្សេង។

## SM5 — Cancel-AL confirm, exact refund label

1 day
AL 1 ថ្ងៃ

no AL (this day costs none)
មិនដក AL (ថ្ងៃនេះមិនអស់ AL)

%g AL
AL %g

## SM6 — future “new replaced old”

🔁 {new — date · times · who} replaces {old — date · times · who}
🔁 {new — date · times · who} ជំនួស {old — date · times · who}

## SM7 — AWAY event stood down a senior redefine

🔁 {name} {away} on {date} — the shift change set for them{times} no longer applies. Please re-arrange cover if needed.
🔁 {name} អវត្តមាននៅ {date} — ការប្តូរវេនដែលបានកំណត់ឱ្យគាត់{times} លែងអនុវត្តទៀតហើយ។ សូមរៀបចំអ្នកជំនួស បើចាំបាច់។

## SM8 — sick day refunded planned AL

🔁 {name} is now away on {date} — the AL approved for that day was returned (+{n} AL).
🔁 {name} ឥឡូវអវត្តមាននៅ {date} — AL ដែលបានអនុម័តសម្រាប់ថ្ងៃនោះ ត្រូវបានដាក់ត្រឡប់ចូលវិញ (+{n} AL)។

## SM9 — AL cancelled because shift change approved

🔁 {name}'s approved AL on {date} was cancelled — a shift change for that day was approved instead. The AL is refunded (+{n} AL).
🔁 AL របស់ {name} ដែលបានអនុម័តនៅ {date} ត្រូវបានបោះបង់ — ព្រោះបានអនុម័តការប្តូរវេនសម្រាប់ថ្ងៃនោះជំនួសវិញ។ AL ត្រូវបានដាក់ត្រឡប់ចូលវិញ (+{n} AL)។

## SM10 — confirm-revoke card

⚠ You have approved AL on {date}. Approving this shift change ({win}) will CANCEL that leave (your AL is refunded) and schedule you to work. Confirm?
⚠ ប្អូនមាន AL ដែលបានអនុម័តនៅ {date}។ បើប្អូនអនុម័តការប្តូរវេននេះ ({win}) វានឹងបោះបង់ AL នោះ (AL នឹងដាក់ត្រឡប់ចូលវិញ) ហើយកំណត់ឱ្យប្អូនមកធ្វើការ។ បញ្ជាក់មែនទេ?

✅ Yes — cancel my leave & work · ✅ បាទ/ចាស — បោះបង់ AL ហើយមកធ្វើការ

✋ Keep my leave · ✋ រក្សា AL របស់ខ្ញុំ

## SM11 — staffer kept leave, shift change not approved

{name} kept their approved leave on {date} — the shift change was not approved.
{name} បានរក្សាការឈប់សម្រាកដែលបានអនុម័តនៅ {date} — ការប្តូរវេនមិនបានអនុម័តទេ។

## SM12 — day-off swap voided because one party is now away

🔁 The day-off swap between {rn} and {pn} is off — {name} is now away. Both are back to their normal days; please arrange cover if needed.
🔁 ការប្តូរថ្ងៃឈប់រវាង {rn} និង {pn} ត្រូវបានបោះបង់ — {name} ឥឡូវអវត្តមាន។ ទាំង 2 នាក់ត្រឡប់ទៅថ្ងៃឈប់ធម្មតារបស់ខ្លួនវិញ។ សូមរៀបចំអ្នកជំនួស បើចាំបាច់។
Key corrections I made: avoided ច្បាប់ឈប់សម្រាក where it becomes stiff or too legalistic, changed refund language from បង្វិលសង to ដាក់ត្រឡប់ចូលវិញ because this is AL balance not money, and kept Done, Cancel, menu, AL, points, and all numbers/times in Latin where the app convention needs consistency.

---

## VETTING OUTCOME — owner-reviewed, WIRED 2026-06-14 (suite 573 green)

Vetted ChatGPT's batch against the live code before wiring (real-path read, not blind trust):

- **WIRED as polished:** MM1, MM3, MM6 (both toasts — bot.py + attendance_ui.py), MM8, SM1, SM3,
  SM4, SM7 (+គាត់, លែងអនុវត្ត), SM8, SM9, SM10 (body + both buttons), SM11, SM12.
- **REJECTED — MM7:** ChatGPT's version referenced the buttons as English "Done/Cancel", but the
  actual buttons render Khmer (`✅ រួចរាល់` / `✕ បោះបង់`, attendance_ui.py:1606/1032). Kept the live
  wired KH (`✅ រួចរាល់ ឬ ✕ បោះបង់`) so staff are told to tap labels that actually exist.
- **SM5 — UNCHANGED (my earlier doubling concern was wrong):** real-path read of
  attendance_ui.py:2156-2168 shows `{detail}` is the DATE and `"AL 1 ថ្ងៃ"` lands in a separate clause
  (`វានឹងដាក់ AL 1 ថ្ងៃ ត្រឡប់ចូល balance`) — reads correctly, no "AL AL".
- **TERMINOLOGY decision (owner):** use bare **`AL`** where it means the counted balance (SM8/SM9/SM10
  + the SM10 buttons → `បោះបង់ AL` / `រក្សា AL`); keep generic **`ការឈប់សម្រាក`** only where the
  conflict could be any leave type (SM1/SM3/SM4). Replaced the old mixed `ច្បាប់ឈប់សម្រាក`.
- **REFUND wording:** adopted `ដាក់ត្រឡប់ចូលវិញ` (AL is a balance, not money) consistently — updated
  the already-wired SM8/SM9/SM10 (were `បង្វិលសង`) to match the existing P12 `…ត្រឡប់ចូល balance`.
- **SM6** stays future/unwired (its `{new — …}` is a description, not a template) — redraft at Phase 4.
- **SM2** has no live string (the flat block was replaced by the SM10 confirm-revoke flow) — nothing to wire.

All behind `attendance_live=OFF`; NOT deployed (batch gm-deploy at go-live prep).

I reviewed the latest uploaded file. The only fresh items needing a native pass are **A1, A2, WF2/WF3, and WF5**; I am not reopening the already-vetted MM/SM block. 

## A1 — Schedule Changes redesign — Change time +OT

🗓 Staff Changes (1 time) · ប្តូរការងារ (1 ដង)

🗓 Staff Changes (forever) · ប្តូរការងារ (រហូត)

⏱ Change time +OT · ប្តូរម៉ោង +OT

📅 Change day off · ប្តូរថ្ងៃឈប់

Staff Changes (1 time) — pick one.
ប្តូរការងារ (1 ដង) — ជ្រើសមួយ។

Change time +OT — for whom?
ប្តូរម៉ោង +OT — សម្រាប់អ្នកណា?

Change {nm}'s shift — which work day? (next 30 days)
ប្តូរវេនរបស់ {nm} — ថ្ងៃធ្វើការណា? (30 ថ្ងៃខាងមុខ)

⏱ Normal times {ws}–{we}
⏱ ម៉ោងធម្មតា {ws}–{we}

{day} — START time? (or ⏱ Normal times above)
{day} — ម៉ោងចាប់ផ្តើម? (ឬ ⏱ ម៉ោងធម្មតាខាងលើ)

🚧 {what} — coming next.
🚧 {what} — នឹងមានពេលក្រោយ។

### Verdict lines

✅ Approved · បានយល់ព្រម

❌ Declined · មិនបានយល់ព្រម

✋ Declined — leave kept · មិនបានយល់ព្រម — រក្សា AL

✅ Approved (AL refunded) · បានយល់ព្រម (AL ដាក់ត្រឡប់ចូលវិញ)

## A2 — Change day off — real move

Change day off — for whom?
ប្តូរថ្ងៃឈប់ — សម្រាប់អ្នកណា?

{nm} — which day should they be OFF? (next 30 days)
{nm} — ត្រូវឱ្យឈប់ថ្ងៃណា? (30 ថ្ងៃខាងមុខ)

{nm} off {X} — which day-off will they WORK instead? (within 7 days)
{nm} ឈប់ {X} — ត្រូវឱ្យមកធ្វើការជំនួសថ្ងៃឈប់ណា? (ក្នុង 7 ថ្ងៃ)

{Y} · their day off
{Y} · ថ្ងៃឈប់របស់គាត់

{Y} (their day off) — START time? (or ⏱ Normal times)
{Y} (ថ្ងៃឈប់របស់គាត់) — ម៉ោងចាប់ផ្តើម? (ឬ ⏱ ម៉ោងធម្មតា)

Day-off move — {nm}: OFF {X}, works {Y} {win}{ot}.
ប្តូរថ្ងៃឈប់ — {nm}៖ ឈប់ {X}, មកធ្វើការ {Y} {win}{ot}។

🗓 Day-off move — you're OFF {X}, and you WORK {Y}: {win}
🗓 ប្តូរថ្ងៃឈប់ — ប្អូនឈប់ {X}, ហើយមកធ្វើការ {Y}៖ {win}

OFF {X} — who works (covers)
ឈប់ {X} — អ្នកធ្វើការជំនួស

WORKS {Y} — who works
ធ្វើការ {Y} — អ្នកធ្វើការ

## WF2/WF3 — family-sick

Family sick ({who}) — {window}.
គ្រួសារឈឺ ({who}) — {window}។

FYI: {nm} takes sick leave for their {who} today ({window}).
FYI: {nm} សុំច្បាប់ឈឺសម្រាប់ {who_kh} ថ្ងៃនេះ ({window})។

FYI: {nm} takes sick leave for their {who} today.
FYI: {nm} សុំច្បាប់ឈឺសម្រាប់ {who_kh} ថ្ងៃនេះ។

## WF5 — partner-swap redesign

Swap day off — pick WHO to trade with (a different day off, similar shift times). You'll then choose a date-pairing.
ប្តូរថ្ងៃឈប់ — ជ្រើសអ្នកដែលប្អូនចង់ប្តូរជាមួយ (ថ្ងៃឈប់ខុសគ្នា, ម៉ោងវេនប្រហាក់ប្រហែល)។ បន្ទាប់មក ប្អូននឹងជ្រើសគូថ្ងៃ។

Your day off · ថ្ងៃឈប់របស់ប្អូន៖ {day_off}

🔁 you off {their_day} · {partner} off {your_day}
🔁 ប្អូនឈប់ {their_day} · {partner} ឈប់ {your_day}

Swap with {pn} — pick a pairing. You take their day off, they take yours (≤ 6 days apart, coverage stays even).
ប្តូរជាមួយ {pn} — ជ្រើសគូថ្ងៃមួយ។ ប្អូនយកថ្ងៃឈប់របស់គាត់ គាត់យកថ្ងៃឈប់របស់ប្អូន (ខុសគ្នាមិនលើស 6 ថ្ងៃ ហើយ coverage នៅស្មើគ្នា)។

No close day-off pairing with {pn} in the next 3 weeks (need ≤6 days apart, a different day off, and neither date already swapped).
គ្មានគូថ្ងៃឈប់ជិតគ្នាជាមួយ {pn} ក្នុង 3 សប្តាហ៍ខាងមុខទេ (ត្រូវខុសគ្នាមិនលើស 6 ថ្ងៃ, ថ្ងៃឈប់ខុសគ្នា, ហើយថ្ងៃទាំងពីរមិនទាន់បានប្តូររួច)។

Key fixes: I changed **ការផ្លាស់ប្តូរ** to **ប្តូរការងារ** for the menu because it is shorter and more practical for staff. For A2, **“គួរឈប់”** was too soft; **“ត្រូវឱ្យឈប់”** fits a senior-driven schedule change better.

## VETTING OUTCOME — A1/A2/WF2/WF5, WIRED 2026-06-16 (suite 586 green)
Vetted ChatGPT's batch against the live code + intent (not blind):
- **REJECTED `ប្តូរការងារ`** for "Staff Changes" — it reads as *change jobs / employment* ("ប្តូរការងារ
  (រហូត)" = quit/switch jobs forever). Used **`ប្តូរកាលវិភាគ`** ("change schedule") instead — accurate for
  both sub-options, unambiguous. (Owner-approved.)
- **WIRED as polished:** `ត្រូវឱ្យឈប់`/`ត្រូវឱ្យមកធ្វើការជំនួស` (senior-directive); the `គាត់` (3rd-person,
  senior picker) vs `ប្អូន` (staffer card) register split; `អ្នកធ្វើការជំនួស` (who-covers); unified
  declined → `មិនបានយល់ព្រម`; `មកធ្វើការ`, `នឹងមានពេលក្រោយ`, the START-time `(ឬ ⏱ ម៉ោងធម្មតា…)` suffix;
  WF5 register → `ប្អូន`/`គាត់`.
- **CODE FIX (vetting caught a half-English bug):** the family-sick confirms (`famf` + `famtt`) dropped the
  raw English `{who}` ("child") into the Khmer → now mapped via `_who_kh` (→ `កូន`).
- **WIDTH RULE:** the WF5 pairing button (date · name · date) + the A2 comp-day button kept **one language**
  (English) — a bilingual version would overflow phone width.
- ChatGPT left "coverage" English in a WF5 header; my live code never had it (KH says "ខុសគ្នាមិនលើស 6 ថ្ងៃ")
  so nothing to change.
