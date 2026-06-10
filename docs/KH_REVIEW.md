# Khmer review - attendance / GM bot bilingual strings (TWBshop)

> Record of the bot's bilingual strings. The English is owner-approved; the Khmer is
> ChatGPT-polished and WIRED INTO CODE (gm_bot/). To review NEW strings: add them under the
> "## Pending" heading at the bottom, then paste this whole file into ChatGPT.

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

(add new English + Khmer drafts here, then paste the whole file into ChatGPT)
