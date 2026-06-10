# Khmer review — attendance bot strings (sessions 31–32, 2026-06-10)

> **Paste this WHOLE file into ChatGPT.** Ask it to return, for each entry, a polished native-Khmer
> line (and to flag any English that reads awkwardly once paired with Khmer). The English is
> owner-approved and fixed; the **Khmer is my rough draft** — improve it freely. Read the context
> block below FIRST; every entry then gives you who reads it, where it fires, what each `{variable}`
> is, and the intended tone, so you never have to guess.

---

> **STATUS — WIRED INTO CODE (session 32, 2026-06-11).** All the polished live strings below are now
> applied in `gm_bot/`. Judgment-call deviations: (a) kept English "Working those hours/days" rather
> than "Working during that time" — keeps the hours/days pair consistent; only the KH changed to
> `ពេលនោះ`. (b) `Day off = Free` → `Day off = No AL used · ថ្ងៃឈប់ = មិនដក AL` (applied). (c) The §2.6
> insufficient-balance senior card was RETIRED (replaced by the staff-side block — see the NEW section
> at the bottom), so its line is left only as a dead dry-run preview. A few owner-only dry-run preview
> lines still carry the source wording but no longer block go-live.

# KH_REVIEW — polished Khmer output

## 1. Check-in & check-out

### 1.1 Checked-out confirmation

Checked out ✓ Thank you, have a nice day! 🤍
ចុះវត្តមានចេញរួច ✓ អរគុណ សូមឱ្យថ្ងៃនេះល្អៗ 🤍

Note: this works for 6am finishes better than the literal `សូមមានថ្ងៃល្អ`, which sounds translated.

## 2. Annual Leave (AL)

### 2.1 Day off = Free

Day off = Free
ថ្ងៃឈប់ = មិនដក AL

Do **not** use `ឥតគិតថ្លៃ` here. That sounds like money/free of charge. `មិនដក AL` is the cleanest and abuse-proof.

### 2.2 Hours-AL summary line

AL: {dates} · {from}–{to} = {N} AL.
AL៖ {dates} · {from}–{to} = {N} AL។

This is already good.

### 2.3 Hours-AL help line

Hours AL: 9pm → 12am (3h of a 9h shift = 0.3 AL).
AL តាមម៉ោង៖ 9pm → 12am (3h ក្នុងវេន 9h = 0.3 AL)។

### 2.4 Short-notice warning

⚠ Short notice (within 7 days) — about −54 points for a full day (−0.1/min).
⚠ ស្នើជិតពេល (ក្នុង 7 ថ្ងៃ) — ប្រហែល −54 points សម្រាប់ពេញមួយថ្ងៃ (−0.1/min)។

Good. Clear, not harsh.

### 2.5 From-now mid-shift leave — senior card

Asking to leave from now. One senior ✅ lets them go; a 2nd confirms after.
សុំចេញពីពេលនេះ។ បង 1 នាក់ ✅ អាចអនុញ្ញាតឱ្យចេញបាន; បងទី 2 បញ្ជាក់តាមក្រោយ។

### 2.6 Insufficient-balance flag — senior card

Note: {name} only has 1.5 AL days left but is requesting 3 — your call.
ចំណាំ៖ {name} នៅសល់ AL តែ 1.5 ថ្ងៃ តែស្នើ 3 ថ្ងៃ — សម្រេចតាមបង។

Use `បង`, not `អ្នក`, because this is senior-facing.

### 2.7 AL approved — requester

Your AL is approved ✓ {from} → {to}. You have {N} AL days left. 🤍
AL របស់ប្អូនបានអនុម័តហើយ ✓ {from} → {to}។ ប្អូននៅសល់ AL {N} ថ្ងៃទៀត 🤍

### 2.8 Hours-AL — Supervisors group notice

{name} on leave 9pm–12am on {days}. Back at work: 12am each of those nights (rest of shift as normal).
{name} ឈប់សម្រាក 9pm–12am នៅ {days}។ ត្រឡប់មកធ្វើការ 12am រៀងរាល់យប់នោះ (ម៉ោងនៅសល់ធ្វើធម្មតា)។

## 3. Awaiting approval / status lines

### 3.1

⏳ Awaiting approval
⏳ កំពុងរង់ចាំការអនុម័ត

### 3.2

⏳ Awaiting senior approval
⏳ កំពុងរង់ចាំបងៗអនុម័ត

This should differ from 3.1 because the English says senior approval.

### 3.3

⏳ Awaiting partner
⏳ កំពុងរង់ចាំដៃគូយល់ព្រម

### 3.4

✅ Approved
✅ បានអនុម័ត

Button form:
✅ Approved · ✅ បានអនុម័ត

Do **not** use `យល់ព្រម` for approved. `យល់ព្រម` = agreed; `បានអនុម័ត` = approved.

### 3.5

✋ Declined by partner
✋ ដៃគូមិនបានយល់ព្រម

❌ Not approved
❌ មិនបានអនុម័ត

This is softer than `ដៃគូបានបដិសេធ`, which sounds more rejecting/blunt.

## 4. Show who’s working

👥 Working those hours:
👥 អ្នកធ្វើការពេលនោះ៖

👥 Working those days:
👥 អ្នកធ្វើការថ្ងៃនោះ៖

👁 Show who's working
👁 បង្ហាញអ្នកធ្វើការ

🙈 Hide who's working
🙈 លាក់អ្នកធ្វើការ

Decision: use `ពេលនោះ` for hours/partial-time coverage. It means “during that time” and is more natural than `ម៉ោងនោះ` here.

## 5. Day-off swap

### 5.1 Requester reason prompt

Day-off swap — your off {d1} ↔ partner off {d2}.
ប្តូរថ្ងៃឈប់ — ប្អូនឈប់ {d1} ↔ ដៃគូឈប់ {d2}។

### 5.2 Partner agreed

✅ You agreed — sent to seniors
✅ ប្អូនបានយល់ព្រមហើយ — បានផ្ញើទៅបងៗ

### 5.3 Senior/requester card bodies

Recommendation: make them bilingual. These are “semi-internal,” but they affect approvals and staff trust. Keep them short:

Day-off swap: {nameA} ↔ {nameB}. Reason: {reason}
ប្តូរថ្ងៃឈប់៖ {nameA} ↔ {nameB}។ មូលហេតុ៖ {reason}

{nameA} off {d1}, {nameB} off {d2}.
{nameA} ឈប់ {d1}, {nameB} ឈប់ {d2}។

## 6. OT / shift-redefine

### 6.1 Shift-change approval card — staff

Shift change — {day} {start}-{end}{ (+Nh OT)} for {name}.
ប្តូរវេន — {day} {start}-{end}{ (+Nh OT)} សម្រាប់ {name}។

You're paid for the time you work; come early → +10 points; normal late/no-show rules apply.
ប្អូនទទួលប្រាក់តាមម៉ោងដែលប្អូនធ្វើការ; មកមុន → +10 points; ច្បាប់មកយឺត/No-show ធម្មតានឹងអនុវត្ត។

Recommendation: make the title bilingual because staff must clearly understand shift changes.

### 6.2 Reason prompt — senior

📝 Type the reason — your next message sends it to them for approval.
📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើទៅពួកគាត់ ដើម្បីសុំការអនុម័ត។

### 6.3 Mid-shift extension

⚡ Extend the shift running NOW (started {time})
⚡ បន្ថែមវេនដែលកំពុងដំណើរការ (ចាប់ផ្តើម {time})

⏱ Extend the end (started {time})
⏱ បន្ថែមម៉ោងចប់ (ចាប់ផ្តើម {time})

{name} is MID-SHIFT (started {time}) — the start is locked. Extend the end, or move a day?
{name} កំពុងធ្វើវេន (ចាប់ផ្តើម {time}) — ម៉ោងចាប់ផ្តើមផ្លាស់ប្តូរមិនបានទេ។ បន្ថែមម៉ោងចប់ ឬប្តូរថ្ងៃ?

## 7. Special leave — marriage & bereavement

### 7.1 Marriage approved

Your marriage leave is approved ✓ {from} → {to}. Congratulations! 🤍
ច្បាប់រៀបការរបស់ប្អូនបានអនុម័តហើយ ✓ {from} → {to}។ អបអរសាទរ! 🤍

### 7.2 Bereavement — compassion tier

We're very sorry for your loss 🤍 1 day of leave today. No approval needed.
យើងសូមចូលរួមរំលែកទុក្ខចំពោះការបាត់បង់នេះ 🤍 ថ្ងៃនេះប្អូនអាចសម្រាក 1 ថ្ងៃបានភ្លាមៗ។ មិនចាំបាច់រង់ចាំការអនុម័តទេ។

This is better than `សម្រាក 1 ថ្ងៃថ្ងៃនេះ`, which sounds mechanical.

## 8. Group redirect

Please message me directly about your time off 🤍
សូមផ្ញើសារមកខ្ញុំផ្ទាល់អំពីការឈប់សម្រាករបស់ប្អូន 🤍

## 9. AL & swap reason prompts

📝 Type the reason — your next message submits the AL request for senior approval.
📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើសំណើ AL ទៅបងៗ ដើម្បីសុំការអនុម័ត។

📝 Type the reason — your partner agrees first, then the seniors approve.
📝 សរសេរមូលហេតុ — ដៃគូត្រូវយល់ព្រមមុន បន្ទាប់មកបងៗអនុម័ត។

# Open question answers

1. `·` is fine for button labels. Keep it. Stacking English/Khmer on buttons will make Telegram buttons too tall and messy.

2. For “Working those hours,” use `អ្នកធ្វើការពេលនោះ៖`. For “Working those days,” use `អ្នកធ្វើការថ្ងៃនោះ៖`.

3. Senior/requester swap-card bodies and shift-change title lines should be bilingual. They directly affect staff/senior decisions; English-only creates avoidable misunderstanding.

4. Status-line tone:
   ⏳ កំពុងរង់ចាំការអនុម័ត
   ⏳ កំពុងរង់ចាំបងៗអនុម័ត
   ⏳ កំពុងរង់ចាំដៃគូយល់ព្រម
   ✅ បានអនុម័ត
   ✋ ដៃគូមិនបានយល់ព្រម
   ❌ មិនបានអនុម័ត

5. English that reads slightly awkward:

* “Day off = Free” is dangerous because “free” can sound like money. Better English: `Day off = No AL used`.
* “Working those hours” is understandable, but “Working that time” maps better into Khmer. Better English: `Working during that time:`
* “1 day of leave today” is okay, but softer English would be: `You can take 1 day today. No approval needed.`

---

# NEW (session 32) — two owner fixes, please polish the Khmer

### A. Positive-points convention — ⭐ always
Owner rule: **whenever a message mentions positive points, it carries the ⭐ star** the staff are used
to (e.g. `+10 points ⭐`, `+15 points ⭐`). Already applied across the code; the only outlier was the
shift-change card, now fixed. Use the English word **points** (not `ពិន្ទុ`) inside Khmer, to match
every other string. The shift-change line is now:
> You're paid for the time you work; come early → +10 points ⭐; normal late/no-show rules apply.
> ប្អូនទទួលប្រាក់តាមម៉ោងដែលប្អូនធ្វើការ; មកមុន → +10 points ⭐; ច្បាប់មកយឺត/No-show ធម្មតានឹងអនុវត្ត។

### B. Over-balance AL → tell the STAFF (don't flag seniors)
NEW behaviour: if a staffer picks more AL than they have, they're told to choose a smaller amount and
the request is NOT sent to seniors. `{X}` = AL days left, `{Y}` = days requested (both Latin numbers).
> ⚠ You only have {X} AL day(s) left, but this request needs {Y}. Please choose a smaller amount — you can request up to {X}.
> ⚠ ប្អូននៅសល់ AL តែ {X} ថ្ងៃប៉ុណ្ណោះ តែសំណើនេះត្រូវការ {Y} ថ្ងៃ។ សូមជ្រើសរើសចំនួនតិចជាងនេះ — ប្អូនអាចស្នើបានរហូតដល់ {X} ថ្ងៃ។

(The old §2.6 "Note: {name} only has … — your call" senior card is now obsolete for normal AL — it was
only ever a dry-run preview and is being retired by this change.)
