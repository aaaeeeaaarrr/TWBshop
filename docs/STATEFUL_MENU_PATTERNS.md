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

## The five laws

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
3. **Supersession honesty.** If a single per-user input slot is about to be overwritten, **edit the
   old prompt** to say it was replaced ("↩ Replaced — answer the newer prompt below"). Convert
   *silently wrong* into *visibly replaced*. This is the fix for failure shape #2 and needs no
   multi-menu condition.
4. **Reset on entry.** A fresh menu is a clean slate. Reset **all** per-flow stashes on open, not just
   the obvious one — a half-done flow from an older instance must not leak into the new menu.
5. **Always a backstop, never a silent nothing.** Best-effort edits in `try/except`; a **dead-tap
   guard** that turns an orphaned button into "expired — here's a fresh menu"; a "not modified" no-op
   for double-tap races. The user is always pointed at something live — this is what stops "boss, your
   system isn't working."

### The honesty rule (why staff never read it as "broken")
Every collapse / supersede leaves a **self-explanatory** message, and every failed edit **falls
through** to the dead-tap guard. There is no path that ends in a button that does nothing with no
explanation.

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

## Other surfaces to audit against this (not yet done)
Same PTB `user_data` pattern, so the same trap is latent — audit each when next touched:
- **Retail bot** menus (`run_bot.py`) · **B2B** order menus (`b2b_bot/`) · **Hire bot** intake.
- Any future **web / Messenger / WhatsApp** flow we build — apply the laws from day one.

## Pre-ship checklist (run before shipping any such menu)
- [ ] Can two instances exist? (multiple opens / loose-text reopen / multi-device same account)
- [ ] Is there ONE input slot per user a second prompt could overwrite? → **Law 3**
- [ ] Do any buttons read a stash another instance could have changed? → **Law 1 (a/b/c)**
- [ ] Are commitments (approvals / awaiting / terminals) separate, id-bearing messages? → **never collapse**
- [ ] Does every collapse / failure path leave a live pointer (no silent nothing)? → **Law 5**
