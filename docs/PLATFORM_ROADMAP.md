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
| 2 | **Points (check-in)** | early_arrival +10 · late split (−1/−2) | `points_events` | LOW | Derived from the verdict (done) + the late-declaration split (`late_declared_at`). Quick win, builds confidence. |
| 3 | **Checkout + worked** | worked-min · session close | `attendance_sessions` | MED | Bind checkout (done) + worked capped at end; the closer/auto-checkout edge. |
| 4 | **OT settle / bank** | ot_banked (cap, atomic claim) | `shift_changes.ot_banked` · `ot_bank` | **HIGH** | Money. The settle (worked−normal → OT, capped) + the atomic-claim law. Fresh focused session. |
| 5 | **Payback settle / debt** | payback credited · debt cleared | `payback_debts` · `payback_bookings` | **HIGH** | Money. Credit = ext worked vs the redefine window; the over-book guard. Fresh focused session. |
| 6 | **AL / sick / special leave** | days deducted (frozen map) · refund · short-notice points | `al_requests` · `sick_cases` · `special_leaves` | **HIGH** | Money/balance. The deduct-at-approval + refund-on-cancel laws (S1). Fresh focused session. |
| 7 | **Schedule changes** | swap · redefine · day-off move | `shift_changes` · `dayoff_*` | MED | Model as `shift_moved`/events on the shift entity (the clean platform way; replaces the shadow's resolve_day feed). |

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
