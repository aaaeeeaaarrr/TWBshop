# Khmer review — attendance strings (session 31, 2026-06-10)

Paste this whole file into ChatGPT and ask for a native Khmer pass. Everything below is **bot-facing
text added or changed today**. The English is owner-approved; the **Khmer is my draft** and needs a
native check for tone (ប្អូន/warm-firm register), naturalness, and the placement of the `·` separator.

Format per item: **English** — `Khmer draft` — *(where it shows)*.

---

## 1. AL — amount + reason prompt
- `Day off = Free` — *(no KH yet — should it be bilingual? e.g. `ថ្ងៃឈប់ = ឥតគិតថ្លៃ`)* — *(AL detail when a picked day is the staff's day-off)*
- `AL: {dates} · {from}–{to} = {N} AL.` — `AL៖ {dates} · {from}–{to} = {N} AL។` — *(hours-AL summary; replaced the old "Hours AL / fractional deduction" wording)*
- `③ HOURS-AL (part of a day)` / `Hours AL: 9pm → 12am (3h of a 9h shift = 0.3 AL).` — `AL តាមម៉ោង៖ 9pm → 12am (3h ក្នុង 9h = 0.3 AL)។` — *(walkthrough help card — still tagged "KH pending review")*

## 2. "Awaiting approval" card (the reason prompt becomes this once the reason is typed)
- `⏳ Awaiting approval` — `កំពុងរង់ចាំការអនុម័ត` — *(AL requester card, generic reason card)*

## 3. Coverage block + toggle (NEW today — the Show/Hide who's-working feature)
- `👥 Working those hours:` — `អ្នកធ្វើការម៉ោងនោះ` — *(hours-AL coverage header)*
- `👥 Working those days:` — `អ្នកធ្វើការថ្ងៃនោះ` — *(full-day-AL + day-off-swap coverage header)*
- `👁 Show who's working` — `បង្ហាញអ្នកធ្វើការ` — *(toggle button, collapsed)*
- `🙈 Hide who's working` — `លាក់អ្នកធ្វើការ` — *(toggle button, expanded)*
  - **Q for ChatGPT:** owner suggested maybe "working those *times*" reads better than "hours" in KH — advise.

## 4. Day-off swap cards (partner / senior / requester)
- `Day-off swap — your off {d1} ↔ partner off {d2}.` — `… · ប្តូរថ្ងៃឈប់។` — *(requester prompt; rest English)*
- `✅ You agreed — sent to seniors` — `បានផ្ញើទៅបងៗ` — *(partner card after agreeing)*
- `⏳ Awaiting senior approval` — `កំពុងរង់ចាំការអនុម័ត` — *(senior/requester swap card)*
- `⏳ Awaiting partner` — `កំពុងរង់ចាំដៃគូ` — *(requester swap card, before partner agrees)*
- `✅ Approved` — `បានអនុម័ត` — *(decided swap card)*
- `✋ Declined by partner` — `ដៃគូបានបដិសេធ` — *(swap card, partner said no)*
- `❌ Not approved` — `មិនបានអនុម័ត` — *(swap card, seniors declined)*
- **English-only right now (flag if KH wanted):** the senior swap card body (`Day-off swap: A ↔ B / A off …, B off …. Reason: …`) and the requester swap card body — these were never translated.

## 5. Shift-redefine / Give-OT prompt
- `Shift change — {day} {start}-{end}{ (+Nh OT)} for {name}.` — *(English only — flag if KH wanted)*
- `📝 Type the reason — your next message sends it to them for approval.` — `📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងផ្ញើទៅសុំការអនុម័ត។` — *(shift prompt)*

## 5b. Mid-shift extension (NEW session 32 — extend a RUNNING shift)
- `⚡ Extend the shift running NOW (started {time})` — `បន្ថែមវេនកំពុងដំណើរការ` — *(day-pick top button when the staffer is mid-shift; only way to reach yesterday's overnight shift)*
- `⏱ Extend the end (started {time})` — `បន្ថែមម៉ោងបញ្ចប់` — *(mode screen, mid-shift today — replaces Change time)*
- `{name} is MID-SHIFT (started {time}) — the start is locked. Extend the end, or move a day?` — `{name} កំពុងធ្វើការ (ចាប់ផ្តើម {time}) — ម៉ោងចាប់ផ្តើមផ្លាស់ប្តូរមិនបានទេ។ បន្ថែមម៉ោងបញ្ចប់ ឬប្តូរថ្ងៃ?` — *(mode screen header, mid-shift today)*

## 6. AL reason prompts (typed-reason flows)
- `📝 Type the reason — your next message submits the AL request for senior approval.` — `📝 សរសេរមូលហេតុ — សារបន្ទាប់នឹងបញ្ជូនសំណើ AL ទៅបងៗដើម្បីអនុម័ត។`
- `📝 Type the reason — your partner agrees first, then the seniors approve.` — `📝 សរសេរមូលហេតុ — ដៃគូយល់ព្រមមុន បន្ទាប់មកបងៗអនុម័ត។`

---

### Open questions for ChatGPT
1. Is `·` (middle dot) an OK English↔Khmer separator inside one button/line, or should each language be on its own line?
2. "Working those hours/days" — best natural Khmer (the owner floated "working those times").
3. Should the swap **senior/requester card bodies** and the **shift-change line** be bilingual, or stay English (they're senior-facing)?
4. Tone check on all `⏳/✅/✋/❌` status lines — short and warm, ប្អូន register where staff-facing.
