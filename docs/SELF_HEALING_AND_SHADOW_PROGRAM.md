# Self-Healing + Parallel-Shadow Program — the reliability moat (owner-directed, 2026-06-27)

> Owner's vision: cut TWB onto the platform safely (flip asap, fix one-at-a-time, monitored), then run **hundreds
> of parallel shadows** with different setting combinations against real activity (TWB + clients) WITHOUT touching
> live — so the whole config space our dashboard allows is continuously validated. Plus: **an alarm for everything
> that didn't reach its next ladder/step**, and **seamless self-healing** so errors recover by design even when the
> owner isn't at the terminal. This doc is the durable master plan so the multi-step build is never lost.

## Four self-healing laws (everything obeys these — so an error LANDS SAFE by construction)
1. **Land safe** — atomic + idempotent + fail-safe-on-read; a failure never makes things worse.
2. **Heal if unambiguous** — mechanical safe fixes happen automatically + log.
3. **Freeze + alarm if risky** — money/decision-sensitive → hold in the safe state, alarm, queue for owner / nightly agent.
4. **Never silently swallow** — anything that didn't reach its next step emits an alarm.

## Phases (each de-risks the next; never flip a live aspect before its net covers it)
- **Phase 0 — Safety foundation (FIRST):**
  - ① **Sentinel** (`core/sentinel.py`) — universal liveness monitor: registered FLOWS, each with a detector that
    finds instances stuck past their SLA. `sweep(org_id)` → alarms. Org-scoped → TWB · shadows · clients alike.
    READ-ONLY (detect only; heal/alarm are separate). Detectors plug in as the platform grows.
  - ② **Reverse-shadow + instant-revert flag** — flip core authoritative but keep the OLD engine running as the
    shadow OF core; any divergence → alarm + a single flag flips authority back instantly. The net that survives the flip.
  - ③ **Invariant monitor** — alarm on impossible states (negative balance, double-count, verdict ∉ set, …). The
    net that scales to clients (who have no "old engine" to compare against).
- **Phase 1 — Safe first flip:** the **verdict brain** (core == live → behaviorally identical → zero-risk first step, netted).
- **Phase 2 — Net + flip each aspect one at a time:** recording → points → payback → settle (net each, flip, watch, keep/revert).
- **Phase 3 — Parallel-shadow harness:** a config MATRIX (presets × key axes + client-picked + edge cases — NOT
  brute-force) fed the real event stream; per-config outputs recorded; **guardrail mining** (combos that produce
  impossible/extreme results → dashboard auto-warns/blocks), **auto-tuned defaults**, the **config-diff preview**
  (a client nudges a setting → instant shadow delta = the dashboard's killer feature), **risk-free-try** (a prospect
  runs combos against their own last month). Reuses `scripts/replay_checkins.py` + `core/whatif.py` + `shadow_hook`.
- **Phase 4 — Self-healing actions:** per issue-kind, auto-heal the safe (restart hook · catch-up missed job ·
  re-derive a record · auto-settle an unambiguous case · auto-expire a moot request) or safe-hold + alarm + queue.
- **Phase 5 — Nightly rounds:** (a) deterministic SERVER jobs (Sentinel sweep + auto-heal-safe + digest DM, prod
  access) generalizing the 21:45 digest/watchdog; (b) an intelligent nightly AGENT (own budget/time) that reasons
  over the day's data, PREPARES + queues the risky fixes (vetted script + staging proof) for a one-tap approve,
  runs the suite, updates guardrails. **Neither moves money/payroll or deploys to prod autonomously.**

## Issue → kryptonite (self-healing catalogue; grow it as new kinds appear)
| Issue | Lands safe because | Auto-heal | Else |
|---|---|---|---|
| Service crash | systemd Restart=always | restart + alarm on loop | — |
| Server reboot | units auto-start | idempotent catch-up of missed jobs | — |
| DB/DNS blip | pooled+retried, jobs idempotent | backoff + circuit-breaker; next tick heals | alarm if persistent |
| Crash mid money-write | atomic txn | (no partial state) | — |
| Double-tap / redelivery | claim-first / ON CONFLICT | de-duped | — |
| Debt created, never settled | Sentinel SLA | auto-settle unambiguous | hold + alarm |
| Request stuck pending | escalation ladder | re-ping → auto-expire when moot | escalate |
| Shadow stops comparing | Sentinel (events but no comparisons) | restart hook + alarm | — |
| Scheduled job missed | per-job heartbeat | catch-up | alarm |
| Config typo / bad value | fail-safe-on-read | logs fallback | alarm |
| Balance wrong | audit chain + /audit | auto-reconcile clear case | freeze + alarm |
| Unknown new error | graceful-degrade | — | log + alarm + manual-review queue |

## The crux — read this before ANY flip
The single most important truth: **a naive flip turns the monitoring net OFF** — once core becomes live there is
nothing left to compare it against, and the alarms go dark. So:
1. **Reverse-shadow:** flip core authoritative, keep the OLD engine running as the shadow OF core, alarm on any
   divergence, and a single flag flips authority back INSTANTLY.
2. **The net only catches what it compares.** Today it compares the VERDICT (+ settle) — NOT the recording, points,
   or payback writes. So extend the net to each aspect BEFORE flipping that aspect. "Flip one at a time" literally =
   net it → flip it → watch → next.

## Current state / readiness (2026-06-27)
- There is **NO built "flip switch"** — the shadow only COMPARES; making core authoritative is a migration (re-wire
  the live recording + every reader: points · payback · settle · payroll · watchdog), done in the phases above.
- **Check-in verdict: core == live, 100% agreement since 2026-06-23** (227 compared; the only 5 mismatches were one
  morning, 06-22, early-shadow teething where core under-applied grace and live was correct — none since). So Phase 1
  (the verdict-brain flip) is **behaviorally a no-op = the safe first step.**
- Settle shadow: 100% (9 compared). Shadow_run is ON; the Sentinel's first detector guards against it silently dying.

## Flip ↔ parallel-shadows — separable but synergistic
- The parallel-shadows vision does **NOT require** flipping TWB — they are read-only simulations fed by the real
  event stream; they run regardless of who is authoritative.
- BUT running TWB itself on core (the flip / dogfood) makes core **production-proven**, which is the credibility
  behind "validated across hundreds of configs." flip = battle-tested engine; parallel shadows = exhaustively
  validated config space — build both. And the parallel-shadow infra IS the dashboard's live-preview infra (one
  build, two payoffs).

## Bonuses (ALL taken — owner 2026-06-27)
- **Auto-mine guardrails** — any config combo producing an impossible/extreme result → the dashboard auto-warns or
  blocks it (clients can't foot-gun).
- **Auto-tune defaults** — watch which combos produce the healthiest real outcomes → "shops like yours run best with grace = 7."
- **Config-diff preview** (the killer dashboard feature) — a client nudges a setting → instant shadow delta ("this
  would have flagged 3 more people late last month").
- **Risk-free try** — a prospect runs combos against their OWN last month before committing.
- **Invariant monitoring** — the net that scales to clients (who have no "old engine"): impossible-state alarms +
  cross-config divergence + anomaly-vs-own-baseline.
- **The moat / sales line:** *"every setting our dashboard allows is validated continuously against a real operating
  business."* Synthetic-only competitors can't say that.

## Caveats — from every angle (ours + different clients')
- **"Flip then fix in prod" is a TWB-ONLY tolerance.** You own TWB; the stakes + the revert are yours. NEVER
  fix-in-prod on a client's payroll → clients receive only the HARDENED result (proven on TWB + the parallel shadows
  first). TWB's flip-and-fix is the canary that PROTECTS clients.
- **Cost:** check-in is low-frequency + deterministic → hundreds of shadows are cheap. Keep each shadow computer-tier
  (no model calls per shadow); for high-frequency / AI domains (POS, message analysis) cap the matrix + guard cost.
- **Don't brute-force the combo space** (astronomically large) — run MEANINGFUL sets (presets × key axes +
  client-picked + edge cases). Grow from a handful.
- **Privacy:** a tenant's shadows run only on THAT tenant's own data — never one client's config against another's data.
- **Lean discipline:** start with a few parallel configs on the existing replay; grow when real clients/configs justify it.

## Status
Plan captured (2026-06-27). Phase 0 brick ① (Sentinel) — ✅ BUILT + tested (`core/sentinel.py`, 5 tests). Everything
else sequenced above. HIGH-RISK live aspects (the flips) get staging proof + the net + a quiet-window deploy +
instant-revert; never a blind switch. Companion record: `docs/BONUSES_AND_FINDINGS.md` §s57.
