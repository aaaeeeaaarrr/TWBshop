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

### P11 · Expired-button lines (Jun 11 — owner's dead-tap design; KH = Claude DRAFT)
- WHO: any staffer who taps a button that no longer works (an orphaned message after an update,
  or a stale card someone already answered).
- WHEN: (a) full collapse — the message itself is REPLACED by this line (orphaned buttons);
  (b) popup toast — a small alert over an intact card (stale taps; the card stays for others).
- TONE: blameless and directive — it's the SYSTEM that expired, they should simply retry.

(a) ⏳ Expired message — please start again from the menu.
    ⏳ សារផុតកំណត់ — សូមចាប់ផ្តើមម្តងទៀតពីម៉ឺនុយ។

(b) [TOAST — keep VERY short] ⏳ Expired — try again · ផុតកំណត់ — សូមម្តងទៀត


### P12 · Cancel AL flow — My Schedule button + list + confirmation (Jun 11; KH = Claude DRAFT)

Context: staff opens My Schedule → sees a "Cancel AL" button when they have future AL → taps →
gets a list of cancelable days → picks one → sees a confirmation card → confirms or backs out.
Audience: junior staff DM (bilingual throughout). Tone: clear and calm, not alarming.

---

**My Schedule button** [BUTTON]:
✕ Cancel AL · បោះបង់ AL

---

**Cancel AL list screen** — header asking which day to pick:
Which AL day do you want to cancel?
ថ្ងៃ AL ណាដែលប្អូនចង់លុប?

Per-day buttons (one per cancelable day; {lbl} = "Mon 23/06" or "Mon 23/06 9pm–12am" for hours-AL):
✕ {lbl}

No-upcoming case (shown if all AL days already passed or shift started):
No upcoming AL to cancel.
គ្មាន AL ខាងមុខដែលអាចលុបបានទេ។

---

**Confirmation card body** — {detail} = day label (+ hours if hours-AL):
Are you sure you want to cancel your AL on {detail}?
This will return 1 day to your AL balance.

ប្អូនពិតជាចង់លុប AL ថ្ងៃ {detail} មែនទេ?
ថ្ងៃ AL 1 ថ្ងៃនឹងត្រូវបានដាក់ចូលវិញក្នុងតុល្យភាព AL របស់ប្អូន។

**Confirmation buttons** [BUTTON pair]:
✅ Yes, cancel it · លុបចោលបាន
← Back · ត្រឡប់ក្រោយ

---

**Too-late toast** (shown if tapped after the day has already started) [TOAST]:
Too late to cancel — that day has already started · យឺតពេលលុបចោលហើយ — ថ្ងៃនោះបានចាប់ផ្តើមហើយ


### P13 · Book pay-back time — About Me picker message (Jun 11; KH = Claude DRAFT)

Context: staff taps "Book pay-back time" from About Me → gets this message + slot buttons.
Audience: junior staff DM (bilingual). Tone: matter-of-fact, not punitive.

**Message body** — {debt} / {booked_total} / {slot_lines} are EN-formatted durations + date+time strings.

Debt · បំណុល: {debt}
Booked · កក់រួច: {booked_total}:
  {slot_lines}   ← each line: "{dur}: {Day DD/MM} {start}–{end}"

Choose the times below to pay — these are the times we need you most:
សូមជ្រើសម៉ោងខាងក្រោមដើម្បីសង — ពេលទាំងនេះហាងត្រូវការប្អូនបំផុត:

**About Me button** [BUTTON]:
📅 Book pay-back time · កក់ម៉ោងសងវិញ


### P14 · Pay-back flow messages — late-arrival + booking states (Jun 11; KH = Claude DRAFT)

Context: all these appear in staff DM only. Audience: junior staff (bilingual). Tone: matter-of-fact.
{X} = formatted duration e.g. "1h 30m". {day} = "Sat 13/06". {start}/{end} = "9am" / "10am".

---

**a) Fully booked — all debt already covered by booked slots**
(shown instead of the picker when remaining = 0)

Your pay-back time is already fully booked ✓ Just work the booked times.
ម៉ោងសងរបស់ប្អូនត្រូវបានកក់រួចរាល់ហើយ ✓ គ្រាន់តែធ្វើតាមម៉ោងដែលបានកក់។

---

**b) Late-arrival combined — picker WITH slots still remaining**
(sent at check-in when late; {X} = minutes late)

Checked in ✓ — {X} late (counts as pay-back). Pick when to work it off — the times we need you most:
ចុះវត្តមានរួច ✓ — យឺត {X} (រាប់ជាម៉ោងសងវិញ)។ សូមជ្រើសពេលធ្វើម៉ោងសងវិញ — ពេលទាំងនេះហាងត្រូវការអ្នកបំផុត៖

**b2) Late-arrival combined — fully booked already**
(same check-in, but all debt already covered)

Checked in ✓ — {X} late (counts as pay-back).
ចុះវត្តមានរួច ✓ — យឺត {X} (រាប់ជាម៉ោងសងវិញ)។

[followed by the "fully booked" line from (a)]

---

**c) Re-offer / ladder — picker, not at check-in** (context: re-offer from ladder or About Me)

You owe {X}. Pick when to work it off — these are the times we need you most:
អ្នកនៅត្រូវសង {X}។ សូមជ្រើសពេលធ្វើម៉ោងសងវិញ — ពេលទាំងនេះហាងត្រូវការអ្នកបំផុត៖

**c2) Info line appended when some debt already booked** (appended to b or c above):

({booked} booked already · កក់រួច {booked} — {remaining} left to book · នៅសល់ {remaining})

---

**d) Clash / stale button — picked slot no longer available, show fresh picker**

That time isn't available any more — {remaining} left to book. Pick again:
ពេលនោះមិនអាចកក់បានទៀតទេ — នៅសល់ {remaining} ត្រូវកក់។ សូមជ្រើសម្តងទៀត៖

---

**e) Booking confirmation** (replaces the picker after a successful book)

Booked ✓ — {day} {start}–{end}.
បានកក់រួច ✓ — {day} {start}–{end}។
Come 5 minutes early and you earn +10 points ⭐
មកដល់មុន 5 នាទី អ្នកនឹងទទួលបាន +10 points ⭐

**f) Stale-button recovery — short re-offer variant** (an old-format button was tapped;
the bot shows a fresh picker with this shorter header)

You owe {X} — pick when to work it off:
អ្នកនៅត្រូវសង {X} — សូមជ្រើសពេល៖

---

**P11 ADDENDUM — recovery button** [BUTTON] (sits under the collapsed "expired message" line,
one tap re-opens the main menu):
📋 Open menu · បើកម៉ឺនុយ


### P15 · Shift-change + day-off-swap cards & notices (Jun 11; KH = Claude DRAFT)

Context: the shift-redefine flow (a senior re-times someone's working day; OT is what's worked
beyond normal length) and the day-off swap flow. All staff-facing pieces are bilingual.
{date} = "2026-06-14" or "Sat 14/06" · {window} = "7am-7pm" · {tag} = "(+2h OT)" or "(+1h PB)" ·
{reason} = typed text · {name}/{req}/{partner} = call names · {d1}/{d2} = "Wed 10/06" style.

---

**a) Shift-change card — STAFF receives it from a senior, must approve/decline** [body]:

🕒 Shift change — {date}: {window}{tag}
🕒 ប្តូរវេន — {date}៖ {window}{tag}
Why · មូលហេតុ៖ {reason}

[then the already-approved "You're paid for the time you work…" line from section A]

**Status suffixes** (appended to the same card as the decision lands) [body]:
✅ Approved · បានយល់ព្រម
❌ Declined · បានបដិសេធ
✅ Done · រួចរាល់

**Approve button** [BUTTON] (the decline button is P6c "❌ Can't — explain · មិនអាច — ពន្យល់"):
✅ Approve · យល់ព្រម

---

**b) Senior's confirmation after sending a shift change** [body]:

✅ Shift change sent — the staff is asked to approve.
✅ បានផ្ញើការប្តូរវេន — បានសុំបុគ្គលិកអនុម័ត។

---

**c) Senior reason prompt — type why before the proposal goes out** [body, last line of the
preview card; reader is a SENIOR but kept bilingual for junior seniors]:

📝 Type the reason — your next message sends it to them for approval.
📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើទៅពួកគាត់ ដើម្បីសុំការអនុម័ត។

---

**d) Senior picker header — whom to give OT / change a shift for** [body]:

Give OT / change a shift — for whom?
ឱ្យ OT / ប្តូរវេន — ឱ្យអ្នកណា?

---

**e) Day-off swap cards — THREE audiences, same swap** [bodies; "Reason · មូលហេតុ៖ {reason}"
closes each one]:

PARTNER (asked to accept; {req} wants the swap):
{req} wants to swap day off: {req} takes {d1} off, you take {d2} — same week.
{req} ស្នើសុំប្តូរថ្ងៃឈប់ជាមួយអ្នក៖ {req} ឈប់ {d1}, អ្នកឈប់ {d2} — ក្នុងសប្តាហ៍ដដែល។

REQUESTER (their own card, tracks status):
Day-off swap — your off {d1} ↔ {partner} off {d2}.
ប្តូរថ្ងៃឈប់ — ប្អូនឈប់ {d1} ↔ {partner} ឈប់ {d2}។

SENIOR (approval card after the partner says yes):
Day-off swap: {req} ↔ {partner}
{req} off {d1}, {partner} off {d2}.
ប្តូរថ្ងៃឈប់៖ {req} ↔ {partner}។ {req} ឈប់ {d1}, {partner} ឈប់ {d2}។

---

**f) Partner declined — notice to the requester** [body; the partner's typed reason follows
separately via the P10 relay line]:

Your day-off swap ({d1} ↔ {d2}) wasn't accepted by your partner.
អ្នកដែលត្រូវប្តូរជាមួយ មិនបានយល់ព្រមលើការប្តូរថ្ងៃឈប់ ({d1} ↔ {d2}) របស់អ្នកទេ។

---

**g) Family-sick extension FYI — Supervisors group** [body; {name} = staffer, {reason} = their
typed reason for not coming tomorrow]:

FYI: {name}'s family-sick continues tomorrow ({relation}).
FYI: ច្បាប់ឈឺគ្រួសាររបស់ {name} បន្តដល់ថ្ងៃស្អែក។
Reason · មូលហេតុ៖ {reason}

