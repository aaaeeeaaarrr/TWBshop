# Stateful Menu Patterns — design law for any multi-instance, shared-state UI

> **TRIPWIRE.** Building or editing **any** menu, picker, wizard, or multi-step flow that stashes
> selection state between taps — STOP and apply this doc before writing. Telegram inline menus are
> today's case, but the same trap lives in **any** UI where one state store backs **multiple live
> instances** of a menu: web SPA components, session-backed wizards, WhatsApp / Messenger flows,
> IVR trees, anything. If two copies of the screen can exist and share one state bag, this applies.

This is the generalized law distilled from the TWBshop GM attendance multi-menu fix (Jun 2026). The
worked example is at the bottom; read the laws first — they are framework-agnostic.

---

## The disease

One **mutable state store** (PTB `user_data`, a web session, React component state, …) backed by
**multiple live instances** of the same menu. The user opens two, or leaves an old one open, or
navigates the *old* one after a new one exists → the instances read/write the same stashes →
cross-contamination. **The screen is only a skin; the state underneath is shared.**

Two distinct failure shapes — and the second needs only ONE menu:

1. **Stash cross-contamination** (needs ≥2 instances): instance A's *Confirm* reads the selection
   instance B left in the shared stash → A submits B's data, or empty, or the wrong page.
2. **Single-slot overwrite** (needs only ONE instance): if there is one "pending input" slot per
   user, reaching a *second* input prompt silently overwrites the first — whatever the user then
   types lands in the wrong flow while the **old prompt still looks alive**. This is a live bug with a
   single menu; it does not need the multi-menu condition at all.

---

## The message / screen taxonomy — what you may and may not collapse

| Class | Examples | Collapse an old one when a new menu opens? |
|---|---|---|
| **Navigation** | main menu, sub-menus, pickers, date grids, lists | **Yes** — safe. Nothing committed rides on it; half-picked selections were never submitted. Relabel to a "continues below" pointer; remove its buttons. |
| **Armed input prompt** | "type the reason…", awaiting typed input | **No.** The user may step away (e.g. to check something) and come back to type. Only a *newer* prompt may supersede it — and then it must say so (Law 3). |
| **Decision / awaiting card** | approve ✅/❌, partner ✋ agree, "⏳ awaiting approval" | **Never.** These are separate messages with their own request-id in the callback. They are identifiable and excludable; collapsing one would hide a real commitment. |
| **Terminal / offer** | "Booked ✓", verdict, an open picker that commits money/time | **No need.** Their buttons must recompute from a trustworthy source at tap time (Law 1a), so two of them can't double-commit. |

---

## The laws (eight)

1. **A button must never trust the screen it sits on.** Recompute from a trustworthy source at *action
   time*. Three ways, most-preferred first:
   - **(a) Hard-gate at tap time** — best for money / booking / irreversible. Recompute the
     remaining/eligibility from the database the instant the button fires; ignore any stashed
     assumption. (TWBshop payback picker already does this.)
   - **(b) Stateless callback** — carry the needed context *in* the callback payload. Subject to size
     limits (Telegram `callback_data` ≤ 64 bytes → cannot hold an arbitrary multi-select set), so this
     fits single-value steps, not accumulating selections.
   - **(c) Fail-safe reset** — when neither fits (e.g. a multi-select that won't serialize into a
     payload), **reset the stash on entry** so a stale button reads *empty* and asks to start again,
     never acts on wrong data.
2. **Singleton the navigation, never the commitments.** Keep at most one live **nav** menu; collapse
   the old one to a "⤵ continues below" pointer with its buttons removed. **Never** collapse armed
   prompts, decision/awaiting cards, or terminal messages.
3. **Supersession honesty is the FLOOR, not the fix.** If a single per-user input slot is about to be
   overwritten, **edit the old prompt** to say it was replaced ("↩ Replaced — answer the newer prompt
   below"). But an *in-place edit above the keyboard does not push-notify* and loses to change-blindness
   exactly when the user is mid-typing — so it makes the wrong-flow landing *diagnosable*, not
   *prevented*. Name BOTH flows ("your AL question was set aside — what you type now answers the
   shift-change") and prefer a **new** message (new messages notify) over a silent relabel.
4. **Reset on entry — but a fresh menu must be a deliberate act.** Reset **all** per-flow stashes on
   open. Beware: if "opening a menu" can be triggered by the user merely *typing* (loose text), the
   reset becomes destructive of an in-progress selection — guard it (don't reset/open mid-selection; or
   tell them "you're mid-pick, tap Done or Back").
5. **Always a backstop, never a silent nothing.** Best-effort edits in `try/except`; a **dead-tap
   guard** that turns an orphaned button into "expired — here's a fresh menu"; a "not modified" no-op
   for double-tap races. Every `return` after `query.answer()` is a silent dead-tap — route it through
   the dead-tap collapse instead. Wording must match the cause: "try again" only where retry can
   actually succeed (use "already decided" / "not for you anymore" otherwise).
6. **Every armed state must be leavable and must announce its own death — WITH A PUSH.** (Added
   Jun 13; death-notice upgraded by owner Jun 13.) An armed input prompt needs: (a) a user-initiated
   exit — a ✕ Cancel that **disarms** the slot (so a later stray message can't become a ghost
   submission), while a harmless `← Back` may stay on pure-nav screens; (b) a death notice that
   **PUSH-notifies** — on expiry or dead-tap, send a **NEW message** (an in-place edit does NOT
   notify and is missed by change-blindness) headed **"❗ NOT CONFIRMED — TRY AGAIN"** (caps EN +
   **bold KH**) carrying *what* expired ("Death leave · 12–14 Jun") + 📋 Open menu, then remove the
   stale card (Telegram delete ≤48h, else edit it to a stub). Applies to **expired armed states only**
   — never to a finalized approved/declined card (those stay). **Non-text input is input:** if a flow
   waits for a typed reason, a voice note / photo / sticker must complete the same flow or be honestly
   refused — never thank-you'd and dropped.
7. **Resource exclusivity — first commit wins, at one atomic chokepoint.** (Added Jun 13.)
   Mutually-exclusive commitments on a shared resource (a staff-date/time) are enforced in ONE place:
   **hidden at request time** where clearly taken (a duplicate same-day isn't even offered) and
   **hard-claimed at approval time** with an atomic compare-and-swap (same idempotency trick as
   OT-banking — a plain read-check races and double-approves). First atomic claim wins; the rest are
   refused with a clear "❌ Unavailable — already approved for that day" (which **stays**, per the
   terminal rule), and the approving senior gets an **override** for the case where the new one should
   supersede (e.g. bereavement over a minor shift-change). This invariant is also an **`/audit` law**
   ("≤1 approved leave/redefine/swap per staff-date; each approved AL-day deducts AL once") — run it on
   real rows **before go-live** to catch collisions already in the data. Tell **both** humans **why,
   with details**: the loser-request's staffer ("❌ Unavailable — leave already approved for 12 Jun")
   AND the senior who was mid-approval — details turn "rejected" into "ah, that day was taken."
8. **Outcomes are pushed, not just displayed.** (Owner, Jun 13.) Every finalized outcome a human must
   know — confirmed / approved / declined / unavailable / expired — is delivered as a **FRESH message
   carrying full details** ("✅ APPROVED — AL 12–14 Jun"), so it push-notifies and they're never lost;
   the stale interactive card it supersedes is **removed** (≤48h delete, else edit to a stub). The party
   who **just tapped** may see it in place (already looking); the **passive/waiting** party always gets
   the fresh push. This fresh message IS the lasting record — it satisfies "staff remember what was
   agreed" better than a silent in-place morph, and reconciles with the terminal-persistence rule
   (the record still stays; it's just delivered, not whispered).

### The honesty rule (why staff never read it as "broken")
Every collapse / supersede should leave a **self-explanatory** message, and every failed edit should
**fall through** to the dead-tap guard. GOAL: no path ends in a button that does nothing with no
explanation — **this is the bar, not yet fully met.** The Jun-13 red-team (below) found several live
paths that still end in silent nothing; they are the backlog, not a description of today's reality.

---

## Worked example — TWBshop GM attendance menu

- **Disease present:** PTB `user_data` shared across menus that open via `/start` or *any* loose text
  with no armed pend (`gm_bot/bot.py` `_private_text_router`).
- **Six shared stashes:** `att_al_picked`, `att_al_cov`, `att_do_day`, `att_do_cov`,
  `att_al_from`/`att_al_page`, `att_ci_armed`.
- **One input slot:** `att_pending` (flow_state, DB, restart-safe) / `att_test_pending` (user_data, owner test).

### Fixes (status)
| Piece | Law | Status | Where |
|---|---|---|---|
| Tap-time DB hard-gate on payback booking | 1a | **LIVE** (Jun 11) | `_payback_slot_keyboard` recomputes remaining |
| **P2** — prompt-supersession honesty | 3 | **SHIPPED** `4faf196` | `_supersede_prev_pend()` wired into `_arm_pending` + `_arm_reason` |
| **P3** — reset all 6 stashes on open | 4 | **SHIPPED** `4faf196` | `open_live_menu` |
| **P1** — menu singleton + collapse-on-completion | 2 | **PENDING owner go-ahead** | claim at `open_live_menu`/`cmd_test`/`att:menu`, release in `_arm_pending`; collapse-on-completion only for *new-message* terminals (payback picker, check-in verdict) |

**Verified map (so P1 can't hide a commitment):** senior ✅/❌, partner ✋, shift Approve, and
"⏳ awaiting" are **separate messages** with request-id in the callback → Law 2 protects them. AL /
swap / shift morph the requester's prompt **in place** into their own awaiting card → no orphan menu
is ever left behind by those flows.

**Tests:** `tests/test_multimenu.py` (P2 supersession incl. same-message skip + no-prev no-op; P3
reset-all). Add one P1 test per collapse vector when P1 ships.

---

## Known gaps — fixes to be done (Fable red-team, 2026-06-13)

The human-mind red-team traced the laws into the live code and found paths that still break them.
Status: **none fixed yet** — captured here as the backlog. CRITICALs are pre-go-live. (Two CRITICALs
independently re-verified in code by the reviewing session: F1, F2.)

| ID | Human scenario (one line) | Law it breaks | Sev | Where | Status |
|---|---|---|---|---|---|
| **F1** | Staffer sends a **voice note** as their reason → "Got it 👍 thank you" + forwarded to Supervisors, but `_att_dispatch` never fires → the AL/swap/marriage/death request **silently never exists**. | 6 (non-text input) | **CRIT** | `bot.py:1091-1114` `_capture_voice_reason` | open |
| **F2** | Tap "✅ I confirm" on an **expired** death/marriage/sick/birth card → silent nothing (no toast, no record). | 5 | **CRIT** | `bot.py:4984` `_att_go_callback` | open |
| **F3** | Reason prompt expires (15-min TTL) while hands are busy; they type the reason late → a **fresh menu eats it**, old prompt still says "your next message submits…". | 6 (announce death) | **CRIT** | `bot.py:4845-4857`; TTL purge `database.py:3833-3848` | open |
| **F4** | Stale screen after reset/restart: `do:p` **defaults swap to TODAY**; empty-`picked` Done files a **0-day ghost AL**; `al:t` with popped `att_al_from` **crashes** → "⚠ Something broke" toast. | 1c | **HIGH** | `attendance_ui.py:2492, 2409-2453` | open |
| **F5** | No way to cancel an armed prompt; Back/`/start` don't disarm → later "thank you bong" becomes a **filed leave request**. | 6 (leavable) | **HIGH** | `attendance_ui.callback`, `cmd_start` | open |
| **F8** | Typing mid-selection ("and also the 24th") opens a menu → **P3 reset wipes the picked days** (conversation became destructive). | 4 (guard) | **HIGH** | `_private_text_router` + P3 reset | open |
| **F6** | "Expired — try again" on a re-tapped decided card → "try again" invites an **infinite retry loop**. | 5 (wording) | MOD | `bot.py:1240` | open |
| **F7** | Supersede edit lands above the keyboard mid-typing → AL excuse delivered as a shift-decline; honesty edit is diagnosable, not preventive. | 3 | MOD | `_arm_reason` path | open |
| **F9** | "↩ Replaced" has no subject — reads as "my request was rejected"; original content destroyed; ↩ points up but text says "below". | 3 (wording) | MOD | `attendance_ui.py:774-775` | open |
| **F10** | 👁 toggle on an armed prompt after reset **blanks the request summary** → nervous re-submit. | 1/4 | MOD | `attendance_ui.py:2397-2401` | open |
| **F11** | "⏳ Awaiting approval" sits silently for hours → re-submits (no duplicate guard). | 5 (waiting) | MOD | `_al_finalize` path | open |
| **F12** | If `attendance_live` flipped OFF (rollback), **every staff button goes silently dead** → 20 staff DM the owner "it's broken". | 5 | MOD→HIGH on first rollback | gate `attendance_ui.py:2166-2171` | open |
| **F13** | Multi-instance human reasons (chat-scroll loss, phone+desktop, **shared phone/spouse**), `_supersede` same-msg check ignores `chat_id`. | — | MINOR | `attendance_ui.py:765, 2172-2174` | note |
| **F14** | **Cross-request same-date collision** (owner find, Jun 13): nothing cross-checks requests on one date — AL+shift-change, swap+shift-change can contradict; **two AL on the same day deduct twice**. Only guard today is payback-skips-approved-redefine (`bot.py:1383,1424`). Owner lean: warn the approving senior. | data integrity | **HIGH** (pre-go-live) | `submit_shift_change`/`submit_swap`/`submit_al_request` — no overlap check | open |

### Agreed resolutions (owner walk, Jun 13 — build briefs)
- **F1 + F5 + Back buttons:** swap `← Back`→`✕ Cancel`(disarms the pend) on the **2 armed-prompt spots
  only** (`_arm_prompt:823`, `_confirm_prompt:896`); keep `← Back` on the ~38 nav spots. Keep the 👁
  toggle. Voice/photo on a reason prompt → refuse ("🎤 please type one line") + keep prompt armed.
  Carve-out: **selection screens** (AL grid / time grid / swap-day) — typing there must not silently
  wipe the pick (F8 guard).
- **F2 + F3 (expiry/dead-tap):** on expiry → **NEW push message** "❗ NOT CONFIRMED — TRY AGAIN"
  (caps EN + bold KH) + what expired + 📋 Open menu, then delete the stale card (≤48h, else stub).
  F3 = same nudge on type-after-expiry (no cheerful menu). Lift TTL to ~30–35 min. Optional upgrade:
  a proactive expiry sweep so they're nudged at the moment, not only on next touch. → Law 6.
- **F14 (cross-request collision):** first-commit-wins at one atomic chokepoint (hide at request,
  compare-and-swap claim at approval); loser told "❌ Unavailable — already approved", senior override
  for supersede. Add the `/audit` exclusivity law + backfill-run on real rows pre-go-live. → Law 7.
- **Fable:** not needed to build; do ONE red-team pass AFTER building, on the NEW behaviour (does the
  caps nudge scare, does auto-unavailable confuse the loser, does the override read clearly).
- **MODs fold into the laws (walk complete Jun 13):** F6 (wording) + F7 (supersede) + F9 ("Replaced"
  subject) → resolved by **Law 6/8** (push a fresh detailed message, wording matches cause — "already
  decided" not "try again"). F10 (toggle blanks summary) + F12 (live-off → silent dead buttons) →
  mechanical build-time fixes (rebuild from pend / maintenance toast). F11 (awaiting silence + dup) →
  duplicate side is **F14/Law 7**; the "decided" push is **Law 8**; add one reassurance line. No MOD
  needs a separate owner decision — all carried by the locked batch.

**Top 5 to do first (Fable's ranking):** F1 (voice submits or honestly refuses) · kill every silent
`return` after `query.answer()` (F2/F6/F12, reuse the existing dead-tap collapse) · expiry honesty
(F3) · stale-stash guards + no fabricated defaults (F4/F8, the missing half of Law 1c) · cancel
semantics (F5, + this whole law 6).

**Verified-good patterns to keep** (don't regress): the dead-tap catch-all with 📋 recovery button
(`bot.py:1245-1264`) — the fix for F2/F6 is "use it everywhere"; payback tap-time hard-gate; verdicts
as fresh push messages; the double-tap "not modified" no-op.

## Other surfaces to audit against this (not yet done)
Same PTB `user_data` pattern, so the same trap is latent — audit each when next touched:
- **Retail bot** menus (`run_bot.py`) · **B2B** order menus (`b2b_bot/`) · **Hire bot** intake.
- **B2B (owner, Jun 13):** owner has seen these same bugs in B2B "many times", paused B2B fixes, and
  will resume later applying **all 8 laws**. **When B2B work resumes, this is the trip — remind the
  owner and re-audit B2B menus against the 8 laws before/while changing them.** (The CLAUDE.md Rule 5
  tripwire + this line are the mechanism; don't rely on memory.)
- Any future **web / Messenger / WhatsApp** flow we build — apply the laws from day one.

## Pre-ship checklist (run before shipping any such menu)
- [ ] Can two instances exist? (multiple opens / loose-text reopen / multi-device same account)
- [ ] Is there ONE input slot per user a second prompt could overwrite? → **Law 3**
- [ ] Do any buttons read a stash another instance could have changed? → **Law 1 (a/b/c)**
- [ ] Are commitments (approvals / awaiting / terminals) separate, id-bearing messages? → **never collapse**
- [ ] Does every collapse / failure path leave a live pointer (no silent nothing)? → **Law 5** (grep every `return` after `query.answer()`)
- [ ] Can the flow receive **non-text input** (voice / photo / sticker) where it expects typing? → **Law 6** (complete or honestly refuse — never thank-and-drop)
- [ ] Is every armed prompt **leavable** (cancel / nav disarms) and does it **announce its own TTL death**? → **Law 6**
- [ ] Can "opening a menu" be triggered by the user merely *typing*? If so, does it destroy an in-progress selection? → **Law 4 guard**
