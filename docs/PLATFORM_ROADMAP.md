# Platform Roadmap — the lineup (shadow-loop, vertical by vertical)

> Owner (2026-06-22): line up the remaining work + carry the bonuses/findings. The METHOD is proven (the
> check-in vertical went 24%→98% in one session via the shadow loop). Each row below is one run of that
> loop. Risk tag drives sequencing: do the LOW/MED ones to build confidence, give the HIGH-RISK money
> ones their own focused sessions. Governing design: `docs/PLATFORM_VISION.md` + `ATTENDANCE_DOMAIN_MODEL.md`.

## The proven loop (repeat per vertical)
1. Build the core logic (channel-agnostic, interval-only, atomic-claim-at-write) in `core/`.
2. Shadow-compare it to live (real-time hook + the `replay_checkins.py`-style backtest over real history).
3. Read the grouped mismatches → port the gap → re-replay → agree-rate climbs.
4. READY when every scenario-type agrees (coverage), excluding known one-offs (the go-live launch grace).
Every measurement is local replay = **no deploy to measure**; the shadow is isolated = **zero live risk**.

## The lineup
| # | Vertical | Compare new-vs-live on | Live source | Risk | Notes / approach |
|---|---|---|---|---|---|
| 1 | **Check-in** | state · late · early | `attendance_sessions` | MED | ✅ DONE — 98–100% (redefine-aware). Residual: 2 launch-week early-5 edges. |
| 2 | **Points (check-in)** | early_arrival +10 · late split (−1/−2) | `points_events` | LOW | ✅ DONE — `core/points.py`, PARITY-proven vs `gm_bot.points` (split cross-checked full space + catalogue). |
| 3 | **Checkout + worked** | worked-min capped at edges | `attendance_sessions` | MED | ✅ MATH DONE — `core.settle.worked_minutes` (edge-clamped). Remaining: the closer/auto-checkout orchestration. |
| 4 | **OT settle / bank** | ot_earned · banked · cap | `shift_changes.ot_banked` · `ot_bank` | **HIGH** | ✅ MATH DONE — `core/settle.py`, drift-guarded vs `gm_bot.ot` + honest bank-cap. Remaining (live build): the **atomic claim-or-reject** on the bank. |
| 5 | **Payback settle / debt** | pb_cleared (OT clears debt first) | `payback_debts` · `payback_bookings` | **HIGH** | ✅ MATH DONE — `core.settle.settle_shift` (one currency). Remaining (live build): WHICH debt + redefine window + the **over-book guard** (book_room). |
| 6 | **AL / sick / special leave** | days deducted (frozen map) · short-notice points · fractional | `al_requests` · `sick_cases` · `special_leaves` | **HIGH** | ✅ MATH DONE — `core/leave.py`, drift-guarded vs `gm_bot.al` (incl. the S1 frozen-map invariants). Remaining (live build): the **atomic deduct-at-approval + symmetric refund-on-cancel** (S1) + the ≥2-senior quorum. |
| 7 | **Schedule resolver + changes** | precedence (leave>redefine>day-off) | `resolve_day` | MED | ✅ BRAIN DONE — `core/schedule.py`, parity vs live's precedence (full space). Remaining: derive the day's modifiers from core EVENTS (`shift_moved`/`leave_granted`…) so the core self-derives instead of being fed (the event-sync wiring). |

> **▶ session 53 — SETTLE shadow WIRED LIVE (verticals 3–5 now proving on REAL checkouts).**
> `core/shadow_hook.shadow_settle` runs at every real redefine checkout (`gm_bot/bot.py::_settle_redefined_shift`,
> isolated + gated by `shadow_run`=ON) and records core-vs-live **worked · ot_banked · pb_cleared** to
> `shadow_comparisons (kind='settle')`. Normal redefines are fully compared (core.settle uncapped = live
> `gm_bot.ot.settle_shift`, drift-guarded by `tests/test_core_shadow_settle.py`); a **payback-slot**'s
> ext-worked window isn't modeled in core yet → recorded *informational* (never a false alarm) = the next
> port (#5). The nightly digest is now **per-action-type** (check-in · settle · …) with check-in still the
> readiness gate. So 3/4/5's math is now validated on live data, not only parity tests. The remaining
> "live build" notes below (atomic claim / over-book guard / ≥2-senior quorum) are the CUT-OVER
> orchestration — still ahead, after the shadow agrees.

## After the verticals (the platform shell)
- **Channel adapters** — Telegram is proven as the shadow hook; add a **web adapter** (same commands, a page) → "Telegram? web? both?" becomes config.
- **Onboarding wizard** — explained + conditional + skippable steps (the UX law); writes the tenant config.
- **Multi-tenancy + entitlements** — `org_id` everywhere (foundation laid), per-tenant config, package/bundle gating.
- **Integration layer** — POS / stock connectors behind stable interfaces (AppSheet today → own cloud later).

## Bonuses / findings to fold in (carried)
- **Readiness = COVERAGE, not calendar time** — track which scenario-types have been seen AND agreed; READY when all covered. (Days, not weeks.)
- **Digest should score the LIVE-source (ongoing real-time) stream for readiness**, and report the `replay` backfill separately as gap-analysis (so launch-week backfill noise doesn't drag the live readiness).
- **Reconstruct historical schedules from `gm_events` + logs** for exact backtests (today's replay uses current schedules — a small caveat); the entity+event model freezes history going forward.
- **Replay-as-CI / regression-by-replay** — re-run the full backtest after every port to confirm it closed its gap without breaking others.
- **Auto-draft the code fix per mismatch pattern** — the digest proposes; next step is it drafts the diff for owner approval.
- **The HIGH-RISK money verticals (4–6) are exactly where the bedrock audit found the over-book / non-atomic bug-class** — the shadow + the atomic-claim-first law will prove them safe before any cut-over. (B2B money path also still owes F2/F3/F4 before re-enable.)
- **Known residual:** the 2 launch-week early-5 check-in edges (s31/s19, Jun 17) — needs a live-log trace; 1.7%, boundary.
