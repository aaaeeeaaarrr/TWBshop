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

## D. Sick & decline accountability — WIRED Jun 11 (ChatGPT-polished, final)

> Context per entry lives in git history; in short: nightly sick nudges are expectation-first
> (coming = default), every "no" button costs a typed reason that the named recipient reads,
> 10/20-min silence nudges, auto-resolve at 30. Buttons follow the width rule.

P1 family nudge ({relation} = child/spouse/parent, inserted as-is):
I hope your {relation} is better now 🤍 Are you coming tomorrow?
សង្ឃឹមថា {relation} របស់ប្អូនធូរស្បើយហើយ 🤍 ស្អែកប្អូនមកធ្វើការមែនទេ?

P2 "no" buttons (a family · b own-sick night · c day-1 opener):
[a] 📝 Can't come — explain · មកមិនបាន — ពន្យល់
[b] 📝 Still resting — explain · សម្រាកបន្ត — ពន្យល់
[c] 📝 Really can't — explain · មិនអាចមក — ពន្យល់

P3 own-sick nightly question:
I hope you're feeling better now 🤍 Are you coming in tomorrow?
សង្ឃឹមថាប្អូនធូរស្បើយហើយ 🤍 ស្អែកប្អូនមកធ្វើការមែនទេ?

P4 type-the-reason prompt (sick):
Please type the reason — it goes to the Supervisors. 🤍
សូមវាយមូលហេតុ — វានឹងផ្ញើទៅបងៗ។ 🤍

P5 family re-book confirmation:
Noted — tomorrow is covered. Take care 🤍
កត់ចំណាំហើយ — ស្អែកបានរៀបចំការឈប់ឱ្យរួចហើយ។ ថែទាំឱ្យបានល្អ 🤍

P6 decline buttons (a senior cards · b swap partner · c staff vs shift change):
[a] ❌ Not approve — explain · មិនអនុម័ត — ពន្យល់
[b] ✋ No — explain · ទេ — ពន្យល់
[c] ❌ Can't — explain · មិនអាច — ពន្យល់

P7 one-line-why prompt ({name} = who receives the reason):
📝 One line why — it goes to {name}.
📝 មូលហេតុ 1 ឃ្លា — នឹងផ្ញើទៅ {name}។

P8 silence nudge (10/20 min, max twice):
Still need one line from you 🤍 just type why.
នៅខ្វះមូលហេតុ 1 ឃ្លាពីប្អូន 🤍 សូមវាយប្រាប់មូលហេតុ។

P9 relay ack:
Sent 🤍
ផ្ញើរួចហើយ 🤍

### ChatGPT notes from this pass (kept)
- Don't hardcode the relation in P1 — one {relation} placeholder (the code inserts it dynamically).
- P5: "ស្អែកក៏បានឈប់ដែរ" was too blunt ("you can just stay off again"); the wired wording reads as
  "the bot has arranged/recorded it".
- Button Khmer shortened (សូមពន្យល់ → ពន្យល់) per the width rule.

## Pending - new strings for the next ChatGPT pass

> CONTRACT: no string enters here without its context block — WHO reads it, WHEN it fires, what
> each {variable} is, the intended TONE, and BUTTON vs body. (See git history for the P1–P9
> example format.)

### P10 · Reason-relay line + detailed rejections (Jun 11; KH = Claude DRAFT)
- WHO: the REQUESTER (junior staff — hence bilingual, owner: "some staff won't understand"),
  private DM, right after a decliner types their reason.
- WHEN: a senior ❌'d their AL/swap (ONE ❌ now decides), the partner said no, or a staffer
  declined a senior's shift change — the decision message already arrived; this is the why.
- {what_kh}: សំណើ AL (dates) · ការប្តូរថ្ងៃឈប់ (d1 ↔ d2) · ការប្តូរវេន (date time) — dates ride
  inside the parentheses as English (Tue 23/06), per the app-wide convention.
- {name} = the decliner's call-name · {reason} = their typed text (any language).
- TONE: neutral courier — the bot relays, it doesn't judge.

📝 About your {what} — {name}: {reason}
📝 អំពី{what_kh}របស់ប្អូន — {name}៖ {reason}

Also new (compositions of already-approved fragments, sanity-check only):
Your AL for {dates} wasn't approved. · AL របស់ប្អូនសម្រាប់ {dates} មិនបានអនុម័តទេ។
The day-off swap ({d1} ↔ {d2}) wasn't approved. · ការប្តូរថ្ងៃឈប់ ({d1} ↔ {d2}) មិនបានអនុម័តទេ។

