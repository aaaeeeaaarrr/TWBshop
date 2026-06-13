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
