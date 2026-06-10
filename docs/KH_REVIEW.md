# Khmer review — attendance bot strings (sessions 31–32, 2026-06-10)

> **Paste this WHOLE file into ChatGPT.** Ask it to return, for each entry, a polished native-Khmer
> line (and to flag any English that reads awkwardly once paired with Khmer). The English is
> owner-approved and fixed; the **Khmer is my rough draft** — improve it freely. Read the context
> block below FIRST; every entry then gives you who reads it, where it fires, what each `{variable}`
> is, and the intended tone, so you never have to guess.

---

## 0. CONTEXT — read this before translating anything

**What the product is.** A Telegram bot that acts as the **GM (General Manager)** of a Cambodian
bakery–café (TWB). It speaks to staff privately about attendance: checking in/out by sharing live
location, lateness, annual leave (AL), sick/special leave, overtime (OT), and day-off swaps. It is
warm and human — a caring manager, never a cold system.

**The four audiences (this drives the register):**
- **Staff** — address them in the **ប្អូន** register: warm, gentle, respectful, like a kind older
  sibling/manager speaking to a younger team member. Most strings below are staff-facing.
- **Seniors** (the approvers / shift leaders) — **បង** register, a touch more matter-of-fact; these
  are decision cards, not pep talk.
- **Owner / Tyty** — owner-only cards; usually English, rarely translated (noted per line).
- **Supervisors GROUP** — short, clean outcome notices posted to a staff group; neutral and brief.

**Voice rules.**
- Warm-but-firm. Rewards (e.g. earned rest) are encouraging, never threatening. Debts are
  firm-but-fair, never harsh. Condolences are gentle and sincere.
- Sound like a real Cambodian manager talking kindly to younger staff — **NOT** stiff,
  machine-translated officialese. Natural spoken-but-polite Khmer.

**HARD formatting rules (do not break these):**
1. **Dates, clock times, and numbers stay in LATIN/English form even inside Khmer sentences** —
   e.g. `Tue 23/06`, `9pm`, `9pm–6am`, `0.3 AL`, `+10 points`, `1.5 days`. **Never** Khmer numerals,
   **never** Khmer weekday names.
2. Every staff-facing message is **bilingual**: the English line(s), then the Khmer line(s)
   underneath. On short **buttons**, the two languages are joined on one line with a `·` middle dot
   (e.g. `Show who's working · បង្ហាញអ្នកធ្វើការ`). **Open question Q1:** is `·` natural, or should
   buttons stack? Please advise.
3. These tokens stay **English** inside Khmer: `AL`, `OT`, `points`, `bonus`, `Pin`, and all proper
   names (staff names, day names, month).
4. Keep the **emoji** exactly where they are.
5. End Khmer sentences with `។` where natural.
6. A staff member's own **typed reason** is shown verbatim and is **never** translated — it is not in
   this file.

**Recurring `{variables}` (all render in Latin, never translate them):**
- `{name}` / `{staff}` — a person's call-name (their given name), e.g. `Meng`, `Davy`.
- `{time}` — a clock time, e.g. `9pm`, `6am`.
- `{start}-{end}` — a shift window, e.g. `9pm-10am`.
- `{day}` / `{from}` / `{to}` / `{d1}` / `{d2}` / `{days}` / `{dates}` — date(s), e.g. `Tue 23/06`.
- `{N}` — a number (AL days left, OT hours, etc.).

---

## 1. Check-in & check-out (the daily rhythm — staff, ប្អូន)

### 1.1 Checked-out confirmation (sent on EVERY successful checkout)
- **EN:** `Checked out ✓ Thank you, have a nice day! 🤍`
- **KH draft:** `ចុះវត្តមានចេញរួច ✓ អរគុណ សូមមានថ្ងៃល្អ! 🤍`
- **Seen by:** staff. **Where/when:** the moment a checkout is recorded — BOTH when they manually
  share location to check out AND when the bot auto-checks-them-out (live share stayed on in-zone).
  **Tone:** warm, friendly sign-off. **Note:** many staff finish at 6am (night shift) — confirm
  "have a nice day" reads fine in Khmer for a morning finish, or suggest a time-neutral warm closer.

---

## 2. Annual Leave (AL) — staff requests + the senior approval cards

### 2.1 "Day off = Free" label
- **EN:** `Day off = Free`
- **KH draft:** *(none yet — propose one, e.g. `ថ្ងៃឈប់ = ឥតគិតថ្លៃ`)*
- **Seen by:** staff. **Where/when:** in the AL breakdown, marking a picked day that is already the
  person's weekly day-off, so it costs no AL. **Tone:** light, reassuring. **Note:** confirm the
  phrasing means "that day is free / not counted", not "free of charge (money)".

### 2.2 Hours-AL summary line
- **EN:** `AL: {dates} · {from}–{to} = {N} AL.`  (example: `AL: Mon 23/06 · 9pm–12am = 0.3 AL`)
- **KH draft:** `AL៖ {dates} · {from}–{to} = {N} AL។`
- **Seen by:** staff. **Where/when:** confirming a partial-day (hours) AL request before they submit.
  Replaced an older confusing "Hours AL / fractional deduction" wording. **Tone:** plain, clear.

### 2.3 Hours-AL help line (explains the fraction)
- **EN:** `Hours AL: 9pm → 12am (3h of a 9h shift = 0.3 AL).`
- **KH draft:** `AL តាមម៉ោង៖ 9pm → 12am (3h ក្នុង 9h = 0.3 AL)។`
- **Seen by:** staff. **Where/when:** a walkthrough/help card explaining how partial-day AL is
  counted. **Tone:** instructional, friendly.

### 2.4 Short-notice warning (within 7 days)
- **EN:** `⚠ Short notice (within 7 days) — about −54 points for a full day (−0.1/min).`
- **KH draft:** `⚠ ស្នើជិតពេល (ក្នុង 7 ថ្ងៃ) — ប្រហែល −54 points សម្រាប់ពេញមួយថ្ងៃ (−0.1/min)។`
- **Seen by:** staff. **Where/when:** when they pick an AL date inside the next 7 days — it costs
  points; the computed total is shown before they confirm. **Tone:** a clear heads-up, not a scold.

### 2.5 "From-now" mid-shift leave — senior card
- **EN:** `Asking to leave from now. One senior ✅ lets them go; a 2nd confirms after.`
- **KH draft:** `សុំចេញពីពេលនេះ។ បង 1 នាក់ ✅ អនុញ្ញាតឱ្យចេញ; បងទី 2 បញ្ជាក់តាមក្រោយ។`
- **Seen by:** **senior (បង)**. **Where/when:** a staffer mid-shift asks to leave now; the rule is one
  senior can release them immediately, a second ratifies afterward. **Tone:** clear instruction to the
  approver.

### 2.6 Insufficient-balance flag — senior card
- **EN:** `Note: {name} only has 1.5 AL days left but is requesting 3 — your call.`
- **KH draft:** `ចំណាំ៖ {name} នៅសល់ AL តែ 1.5 ថ្ងៃ តែស្នើ 3 ថ្ងៃ — សម្រេចតាមអ្នក។`
- **Seen by:** **senior**. **Where/when:** on the approval card when the request exceeds the balance;
  seniors still decide. **Vars:** `{name}` person; the `1.5`/`3` are example numbers. **Tone:**
  neutral, informative.

### 2.7 AL approved — to the requester
- **EN:** `Your AL is approved ✓ {from} → {to}. You have {N} AL days left. 🤍`
- **KH draft:** `AL របស់អ្នកអនុម័តហើយ ✓ {from} → {to}។ ប្អូននៅសល់ AL {N} ថ្ងៃទៀត។ 🤍`
- **Seen by:** staff. **Where/when:** after two seniors approve. **Tone:** warm confirmation; note the
  draft already uses ប្អូន — keep that warmth.

### 2.8 Hours-AL — Supervisors group notice
- **EN:** `{name} on leave 9pm–12am on {days}. Back at work: 12am each of those nights (rest of shift as normal).`
- **KH draft:** *(none yet — needs a full Khmer line)*
- **Seen by:** **Supervisors group**. **Where/when:** posted so the team sees who is partially off and
  when they return. **Tone:** short, factual. **Note:** keep all times/dates Latin.

---

## 3. "Awaiting approval" status lines (staff + senior cards)

These short status lines replace a prompt once an action is pending or decided. Keep them **short**.

### 3.1
- **EN:** `⏳ Awaiting approval` — **KH draft:** `កំពុងរង់ចាំការអនុម័ត`
- **Seen by:** staff/requester. **Where:** their own AL/leave card while seniors decide.

### 3.2
- **EN:** `⏳ Awaiting senior approval` — **KH draft:** `កំពុងរង់ចាំការអនុម័ត`
- **Seen by:** staff + senior swap card. **Note:** if it should differ from 3.1 (mention "senior"),
  advise.

### 3.3
- **EN:** `⏳ Awaiting partner` — **KH draft:** `កំពុងរង់ចាំដៃគូ`
- **Seen by:** requester of a day-off swap, before the swap partner agrees.

### 3.4
- **EN:** `✅ Approved` — **KH draft:** `បានអនុម័ត`  ·  **EN:** `✅ Approved · យល់ព្រម` (button form)
- **Where:** a decided card (AL, swap, shift-change).

### 3.5
- **EN:** `✋ Declined by partner` — **KH draft:** `ដៃគូបានបដិសេធ`
- **EN:** `❌ Not approved` — **KH draft:** `មិនបានអនុម័ត`
- **Where:** swap card outcomes. **Tone:** neutral, not blaming.

---

## 4. "Show who's working" coverage toggle (staff + senior cards)

A button on AL/swap cards reveals who else is working those hours/days, so the requester/approver can
see the coverage impact.

- **EN header:** `👥 Working those hours:` — **KH draft:** `អ្នកធ្វើការម៉ោងនោះ`  *(hours-AL header)*
- **EN header:** `👥 Working those days:` — **KH draft:** `អ្នកធ្វើការថ្ងៃនោះ`  *(full-day-AL + swap header)*
- **EN button:** `👁 Show who's working` — **KH draft:** `បង្ហាញអ្នកធ្វើការ`  *(collapsed state)*
- **EN button:** `🙈 Hide who's working` — **KH draft:** `លាក់អ្នកធ្វើការ`  *(expanded state)*
- **Seen by:** staff + senior. **Tone:** plain UI labels.
- **Open question Q2:** owner felt "working those **times**" may read better than "hours" in Khmer —
  please pick the most natural word.

---

## 5. Day-off swap (staff requester + swap partner + senior cards)

A staffer asks to swap their day off with a teammate; the partner agrees first, then seniors approve.

### 5.1 Requester reason prompt (header)
- **EN:** `Day-off swap — your off {d1} ↔ partner off {d2}.`
- **KH draft:** `… · ប្តូរថ្ងៃឈប់។` *(only the tail is drafted; full line welcome)*
- **Seen by:** staff requester. **Vars:** `{d1}` the date the requester takes off, `{d2}` the date the
  partner takes off. **Tone:** clear.

### 5.2 Partner agreed
- **EN:** `✅ You agreed — sent to seniors` — **KH draft:** `បានផ្ញើទៅបងៗ`
- **Seen by:** the swap partner, after they tap "I agree". **Note:** the draft drops "You agreed" —
  consider including it.

### 5.3 English-only bodies (flag if Khmer wanted)
The **senior swap card body** (`Day-off swap: A ↔ B / A off …, B off …. Reason: …`) and the
**requester swap card body** are currently English-only. **Open question Q3:** should these
senior/requester card bodies be bilingual, or stay English? (They are semi-internal.)

---

## 6. OT / shift-redefine (senior gives OT by retiming/extending a shift)

A senior redefines a staffer's shift (retime, extend, or move it); the staffer approves; OT is any
time worked beyond their normal shift length.

### 6.1 Shift-change approval card — to the staff
- **EN:** `Shift change — {day} {start}-{end}{ (+Nh OT)} for {name}.` then a body:
  `You're paid for the time you work; come early → +10 points; normal late/no-show rules apply.`
- **KH draft (body):** `អ្នកទទួលបានប្រាក់តាមពេលដែលអ្នកធ្វើ; មកមុន → +10 points; ច្បាប់យឺត/អវត្តមានធម្មតាអនុវត្ត។`
- **Seen by:** staff (they tap Approve / Can't). **Vars:** `{day}` date, `{start}-{end}` the new window,
  `(+Nh OT)` appears only if it adds OT, `{name}` the staffer. **Tone:** clear and fair. **Open
  question Q3 (cont.):** the title line is English-only — bilingual or keep English?

### 6.2 Reason prompt (shift)
- **EN:** `📝 Type the reason — your next message sends it to them for approval.`
- **KH draft:** `📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើទៅសុំការអនុម័ត។`
- **Seen by:** the senior, after they pick the new times. **Tone:** brief instruction.

### 6.3 Mid-shift extension (NEW — extend a shift that is running right now)
- **EN button:** `⚡ Extend the shift running NOW (started {time})`
- **KH draft:** `បន្ថែមវេនកំពុងដំណើរការ` *(consider including "(started {time})")*
- **Where:** top of the day-pick list when the staffer is currently mid-shift; it is the only way to
  reach an overnight shift that began yesterday. **Vars:** `{time}` their real start, e.g. `9pm`.

- **EN button:** `⏱ Extend the end (started {time})` — **KH draft:** `បន្ថែមម៉ោងបញ្ចប់`
- **Where:** the mode screen for a mid-shift staffer; it replaces "Change time" (the start is locked).

- **EN header:** `{name} is MID-SHIFT (started {time}) — the start is locked. Extend the end, or move a day?`
- **KH draft:** `{name} កំពុងធ្វើការ (ចាប់ផ្តើម {time}) — ម៉ោងចាប់ផ្តើមផ្លាស់ប្តូរមិនបានទេ។ បន្ថែមម៉ោងបញ្ចប់ ឬប្តូរថ្ងៃ?`
- **Seen by:** the senior. **Tone:** clear; "start is locked" means it cannot be changed because the
  shift already began.

---

## 7. Special leave — marriage & bereavement (staff, gentle)

### 7.1 Marriage approved
- **EN:** `Your marriage leave is approved ✓ {from} → {to}. Congratulations! 🤍`
- **KH draft:** `ច្បាប់រៀបការរបស់ប្អូនអនុម័តហើយ ✓ {from} → {to}។ អបអរសាទរ! 🤍`
- **Seen by:** staff. **Tone:** genuinely happy/celebratory.

### 7.2 Bereavement — compassion tier (sibling/grandparent), instant 1 day
- **EN:** `We're very sorry for your loss 🤍 1 day of leave today. No approval needed.`
- **KH draft:** `យើងសូមចូលរួមរំលែកទុក្ខ 🤍 សម្រាក 1 ថ្ងៃថ្ងៃនេះ។ មិនចាំបាច់រង់ចាំការអនុម័តទេ។`
- **Seen by:** staff, immediately, with zero questions asked. **Tone:** **this one matters most** —
  sincere, soft condolence; never bureaucratic. Please make the Khmer feel truly heartfelt.

---

## 8. Group redirect (someone posts attendance in a group)

### 8.1
- **EN:** `Please message me directly about your time off 🤍`
- **KH draft:** `សូមផ្ញើសារមកខ្ញុំផ្ទាល់អំពីការឈប់សម្រាករបស់អ្នក 🤍`
- **Seen by:** a staffer who posted a leave/late message in a group; the GM gently pushes them to a
  private chat. **Tone:** warm nudge, not a reprimand.

---

## 9. AL & swap reason prompts (typed-reason flows — staff)

- **EN:** `📝 Type the reason — your next message submits the AL request for senior approval.`
  **KH draft:** `📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងបញ្ជូនសំណើ AL ទៅបងៗដើម្បីអនុម័ត។`
- **EN:** `📝 Type the reason — your partner agrees first, then the seniors approve.`
  **KH draft:** `📝 សរសេរមូលហេតុ — ដៃគូយល់ព្រមមុន បន្ទាប់មកបងៗអនុម័ត។`
- **Seen by:** staff. **Tone:** brief, friendly instruction.

---

## Open questions for ChatGPT (please answer these too)
1. Is `·` (middle dot) a natural English↔Khmer separator inside one button/line, or should each
   language stack on its own line?
2. "Working those hours/days" — the most natural Khmer (owner floated "working those *times*").
3. Should the **senior/requester swap-card bodies** (§5.3) and the **shift-change title line** (§6.1)
   be bilingual, or stay English since they are semi-internal?
4. Tone pass on every `⏳ / ✅ / ✋ / ❌` status line — short and warm, ប្អូន register where
   staff-facing, បង where senior-facing.
5. Anywhere the **English** itself reads awkwardly once it sits above Khmer — say so; the owner can
   adjust the English too.
