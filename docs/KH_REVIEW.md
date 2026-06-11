# Khmer review - attendance / GM bot bilingual strings (TWBshop)

> Record of the bot's bilingual strings. The English is owner-approved; the Khmer is
> ChatGPT-polished and WIRED INTO CODE (gm_bot/). To review NEW strings: add them under the
> "## D. Sick & decline accountability — WIRED Jun 11 (ChatGPT-polished, final)

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

(nothing pending)
