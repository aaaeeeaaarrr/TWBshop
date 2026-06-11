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

Checked out ✓ Thank you, have a nice day! 🤍
ចុះវត្តមានចេញរួច ✓ អរគុណ សូមឱ្យថ្ងៃនេះល្អៗ 🤍

## A. Positive-points convention — ⭐ always

You're paid for the time you work; come early → +10 points ⭐; normal late/no-show rules apply.
ប្អូនទទួលប្រាក់តាមម៉ោងដែលប្អូនធ្វើការ; មកដល់មុនម៉ោង → +10 points ⭐; ច្បាប់មកយឺត/No-show ធម្មតានៅតែអនុវត្ត។

## B. Over-balance AL → tell the STAFF

⚠ You only have {X} AL day(s) left, but this request needs {Y}. Please choose a smaller amount — you can request up to {X}.
⚠ ប្អូននៅសល់ AL តែ {X} ថ្ងៃប៉ុណ្ណោះ ប៉ុន្តែសំណើនេះត្រូវប្រើ {Y} ថ្ងៃ។ សូមជ្រើសចំនួនតិចជាងនេះ — ប្អូនអាចស្នើបានច្រើនបំផុត {X} ថ្ងៃ។

## C. Group-redirect — 5 rotating variants

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

{name} on leave 9pm–12am on Tue 23/06, Wed 24/06, Thu 25/06.
{name} ឈប់សម្រាក 9pm–12am នៅ Tue 23/06, Wed 24/06, Thu 25/06។

Back at work: 12am each of those nights (rest of shift as normal).
ត្រឡប់មកធ្វើការ 12am រាល់យប់នោះ (ម៉ោងនៅសល់នៃវេនធ្វើធម្មតា)។

---

## ChatGPT review notes (kept for reference)

Only real Khmer warning: do not use “ច្បាប់ AL”. It sounds doubled and awkward. Use AL alone, or AL, ឈឺ និងថ្ងៃឈប់ when listing categories.
One implementation warning: for variant 4, I used AL, ឈឺ និងថ្ងៃឈប់ instead of translating “leave” as ច្បាប់ឈប់. ច្បាប់ឈប់ is understandable, but it feels less natural and can sound like “permission/rule” rather than the bot category.

## Pending - new strings for the next ChatGPT pass

> Every entry below carries its FULL context: WHO reads it, WHEN it fires, what each {variable}
> is, the intended TONE, and whether it lives on a BUTTON (width rule applies) or in a body.
> The English is owner-approved and fixed; the Khmer is Claude's DRAFT — improve it freely.

### P1 · Family-sick night nudge — the question
- WHO: the staff member whose child/spouse/parent was sick TODAY (private DM from the GM bot).
- WHEN: every night while a family-sick case from today is open (the nightly sick job).
- {child/spouse/parent}: the relation word, inserted as-is (កូន / ប្តីប្រពន្ធ / ឪពុក​ម្តាយ).
- TONE: warm but expectation-first — coming to work is the DEFAULT; this must NOT make "not
  coming" feel pre-approved. ប្អូន register.

I hope your {child} is better now 🤍 Are you coming tomorrow?
សង្ឃឹមថា{កូន}របស់អ្នកធូរស្បើយហើយ 🤍 តើស្អែកប្អូនមកធ្វើការទេ?

### P2 · The "no" BUTTONS (width rule — keep KH a compact phrase)
- WHO taps: (a) the family-sick staffer on P1; (b) an own-sick staffer on the nightly return
  check; (c) a sick staffer on the day-1 opener ("what time can you come?").
- WHAT a tap does: asks them to TYPE a reason; the reason goes to the Supervisors group.
- TONE: neutral-firm. Positive buttons elsewhere stay one-tap; only "no" costs a sentence.

[BUTTON a] 📝 Can't come — explain · មកមិនបាន — សូមពន្យល់
[BUTTON b] 📝 Still resting — explain · សម្រាកបន្ត — សូមពន្យល់
[BUTTON c] 📝 Really can't — explain · មកមិនបាន — សូមពន្យល់

### P3 · Own-sick nightly return check — the question
- WHO: a staff member out on own-sick, private DM, each night while the case is open.
- WHEN: the nightly sick job. TONE: same expectation-first warmth as P1.

I hope you're feeling better now 🤍 Are you coming in tomorrow?
សង្ឃឹមថាប្អូនធូរស្បើយហើយ 🤍 តើស្អែកមកធ្វើការទេ?

### P4 · Type-the-reason prompt (sick flows)
- WHO: the staffer who just tapped a P2 button; the message EDITS IN PLACE over the nudge.
- Says explicitly WHERE the reason goes (that visibility is half the accountability).
- TONE: gentle instruction, one line.

Please type the reason — it goes to the Supervisors. 🤍
សូមវាយមូលហេតុ — វានឹងទៅដល់បងៗ។ 🤍

### P5 · Family-sick re-book confirmation
- WHO: the family-sick staffer, right after their typed reason books tomorrow as another
  family-sick day. TONE: warm closure — the request worked, no scolding.

Noted — tomorrow is covered. Take care 🤍
បានកត់ត្រា — ស្អែកក៏បានឈប់ដែរ។ ថែទាំខ្លួនផង 🤍

### P6 · Decline BUTTONS on approval cards (width rule)
- WHO taps: (a) a SENIOR on an AL or day-off-swap approval card; (b) the swap PARTNER on the
  partner-first card; (c) a STAFFER declining a senior's Give-OT/shift-change proposal.
- WHAT a tap does: the decision fires IMMEDIATELY (act-first), then they're asked to type one
  line which is relayed to the person the decision reached. TONE: neutral.

[BUTTON a] ❌ Not approve — explain · មិនអនុម័ត — សូមពន្យល់
[BUTTON b] ✋ No — explain · ទេ — សូមពន្យល់
[BUTTON c] ❌ Can't — explain · មិនអាច — សូមពន្យល់

### P7 · One-line-why prompt (after a decline tap)
- WHO: the decliner (senior/partner/staffer), sent right under the card they just decided.
- {name}: the call-name of whoever will RECEIVE the reason (e.g. the requester "Meng", or the
  proposing senior). TONE: light — the decision already counted; this is just the why.

📝 One line why — it goes to {name}.
📝 មូលហេតុមួយឃ្លា — នឹងទៅដល់ {name}។

### P8 · The 10/20-minute silence nudge
- WHO: anyone who tapped an explain/decline button and hasn't typed for 10 (then 20) minutes.
  Maximum twice ever; at 30 min the system resolves without them. Private DM.
- TONE: patient, tiny — never scolding (they may be busy with a sick child at night).

Still need one line from you 🤍 just type why.
នៅខ្វះមូលហេតុមួយឃ្លា 🤍 សូមវាយប្រាប់ផង។

### P9 · Reason-relayed confirmation
- WHO: the decliner, after their typed reason was forwarded. TONE: minimal ack, one word-ish.

Sent 🤍
បានផ្ញើ 🤍

