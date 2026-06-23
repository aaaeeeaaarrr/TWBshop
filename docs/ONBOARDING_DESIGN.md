# Customer onboarding — design (go live in an afternoon, not months)

The governing principle: **DISCOVER, don't dictate. CONFIRM, don't type.** TWB's data was gathered by hand
over months (staff registry, group ids, rules, all manual). A paying customer will not do that — so the
wizard must make the system DETECT as much as possible and have the human just CONFIRM, one tap at a time.
That contrast (months → an afternoon) is itself the sales pitch.

> Validated by the owner (2026-06-23): the entity+event / **shift-id (not date) model is the right way** for
> shifts that cross midnight — a shift is a stable id with a real start→end interval; the date is only a
> label. Overnight is correct by construction, no date confusion. (Already how `core/` works.)

## A. Telegram onboarding — the hard part, made easy

### A1. The bot — guided creation + auto-configuration
Telegram won't let us create a bot programmatically (BotFather is manual), so the wizard makes it a
**3-tap guided flow**, then does the rest itself:
1. Deep-link to **@BotFather** with copy-paste-ready steps ("send `/newbot`, name it, copy the token").
2. Customer pastes the token (a SECRET → encrypted store, never shown — already built).
3. The wizard then **auto-configures the bot via the Bot API**: `setMyCommands`, `setMyName`,
   `setMyDescription`, the menu button, and starts the listener loop. It also tells them the ONE BotFather
   toggle we can't set by API — **`/setprivacy → Disable`** (so the bot can read group messages).
4. A **connectivity self-check** runs immediately: can the bot post? read the group? see a location? — so
   problems surface during setup, never in production.
*(Optional later: a "use our managed bot" path for customers who don't want their own — they trade away
branding. Most want their own bot, so guided-creation is the default.)*

### A2. The listener — use the BOT IN THE GROUPS, not a user-account session (the big simplification)
TWB uses a Telethon **user-account session** to read chats. For a customer that's the worst friction +
risk (full-account access, a session string to generate). **Don't.** Instead: the customer **adds their
bot to their staff/supplier groups** and (privacy off) the bot reads them directly. The bot *is* the
listener. No user-session, no session string — the "approval" is simply adding the bot (or approving an
"add me to your group" deep-link). Safer (scoped to groups it's in), simpler, instant.
*(Keep the user-session path as an ADVANCED option for someone who must read history or chats the bot
can't join — but it's never the default.)*

### A3. Group discovery + mapping — auto-detect, tap to assign
Once the bot is in their groups it knows each group's id + title. The wizard shows:
"I found **Staff Chat**, **Suppliers**, **Management** — which is which?" → the customer taps to assign each
group a ROLE (staff / suppliers / management / expenses / reports). No ids typed. The bot connects the dots.

### A4. Staff discovery + identity linking — the bot connects the dots, the customer confirms one-by-one
This is the owner's idea, made concrete:
- The bot, in the staff group, sees who posts → the wizard lists them ("I see **Sok**, **Dara**, **Lin**…")
  with their Telegram name + @username + id.
- The customer **confirms each as staff, one at a time**: real name, role, hours (below), senior? — or
  "not staff, skip." A discovered Telegram id → linked to the new staff record on confirm.
- For staff who haven't posted yet (the bot can't see silent members): the wizard generates a **/start
  deep-link with a one-time token** per staffer ("send this to each staffer; when they tap it, they're
  linked") → tap-to-link, no typing.
- **Google linking** (for web/app or calendar): a **"Sign in with Google" link** the staffer taps once
  (OAuth) → their Google id links. Again: approve a link, don't type.

## B. Staff data model (names · hours · split shift · midnight)
A staff record: name · call-name · role · senior? · salary (secret) · weekly day-off · **shift windows** ·
telegram id · google id · consent. **Shift windows** are a LIST of `{start, end}` intervals so we support:
- **Split shifts** — e.g. 06:00–10:00 **and** 16:00–20:00 in one day (two windows).
- **Overnight** — 21:00–06:00 is ONE window where end<start; the core binds it to the shift-id interval, so
  a 2am check-in attaches to the prior day's shift by construction (no date confusion — the owner's point).
Entry methods: **discover-confirm** (default, from the group) · **manual** (type one) · **bulk import**
(paste a list / upload a sheet / import from Deputy/Loyverse/POS).

### B1. Expertise / skills + minimum coverage (owner, 2026-06-23)
A staffer can hold **one or more expertises** (baker, cashier, barista, supervisor…). The tenant defines, per
skill, a **minimum needed at all times** (e.g. always ≥1 baker working), and **day/hour overrides** to raise
or lower it (≥2 bakers on weekends, 0 overnight). The system can then refuse/flag a schedule or a leave
request that would drop a skill below its minimum. **Config:** `categories.attendance.expertise`
(`enabled` · `roles{skill:{min_required}}` · `coverage_overrides[{role,days,hours,min}]`); each staff carries
`expertises:[…]`. **Build now:** the config + the `enabled` toggle + full explanations. **Build next (with the
staff CRUD):** the per-skill minimum + override editor (a small repeatable-row UI) and the staff skill picker.

### B2. The bot as an APPROVER (owner, 2026-06-23)
In the Approvals table, **"Approved by"** now offers **the bot** (alongside senior / management). When the bot
approves, a **decision rule** says HOW (each spelled out for the customer): **Keep coverage** (auto-approve only
IF minimum skill coverage still holds without this person, else a senior) · **Within their quota** · **Always
approve** · **Easy ones only** (bot does the clear cases, escalates the borderline). This is the "Computer/AI
Power" applied to approvals — the bot handles routine decisions, humans handle the judgement calls.

## C. Beyond Telegram
- **Web / app onboarding:** the same config + staff data; access via a browser login or app instead of a
  bot. The brain is identical (channel-agnostic) — only the adapter differs.
- **Migration:** import staff/rosters/vendors from their existing tool (spreadsheet, Loyverse, Deputy, a
  POS) so they don't re-enter anything.

## D. Accelerators
- **Industry templates** — "Bakery / Cafe / Retail" pre-fills typical rules, roles, shift patterns,
  approvals; the customer only tweaks. Minutes, not hours.
- **Progressive onboarding** — start with ONE module (attendance), get value the same day, add
  accountant/stock/POS later. Don't demand everything upfront.
- **The onboarding checklist (a state machine)** — bot created ✓ · groups mapped ✓ · staff confirmed 8/10
  · rules set ✓ · test passed ✓ → "go live". The customer always sees what's done + what's left.

## E. De-risking go-live (this is a SELLABLE feature)
- **Test mode** — role-play the whole thing alone first (TWB has this).
- **Per-customer SHADOW** — run the new system BESIDE their current way for a trial, compare, and only cut
  over when THEY'RE convinced. "Try it risk-free for 2 weeks beside how you work today" — our shadow tech
  becomes a customer-facing selling point.

## F. Consent & privacy
A staffer's first `/start` explains what's tracked (attendance, location at check-in) and asks consent —
configurable, logged. Builds trust + covers us legally. Tokens/sessions encrypted (the W3 hard gate).

## G. More dimensions / open ideas (think deeper — carried)
- Self-healing roster: a new person posts in the staff group → "new staffer detected, add them?".
- QR / NFC onboarding for non-Telegram check-in methods (fingerprint device pairing, a kiosk code).
- Auto-detect the timezone + business hours from the first days of activity, propose them.
- A "clone another branch" flow for multi-location owners.
- Reseller/agency onboarding (an installer sets up many tenants from one console).
- Approve-by-link everywhere (admin rights, staff linking, integration OAuth) — maximise tap, minimise type.

## H. What we build first (the slice)
1. The **onboarding config** (listener_mode = bot-in-groups · staff_entry = discover-confirm ·
   auto_provision_bot = guided · consent · industry_template) — DONE in `core/tenant_config.py`.
2. **Split-shift + overnight** in the schedule model — DONE (config flag; the core already does overnight).
3. The wizard **Onboarding & staff** screen (approach options + the discover-confirm explanation) — the UI.
4. THEN (bigger, sequenced): the staff-CRUD + the live discover-confirm flow (bot reads group → list →
   confirm) + guided BotFather + the Bot-API auto-config + the /start deep-link linker.
