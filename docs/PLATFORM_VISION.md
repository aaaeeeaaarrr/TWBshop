# Platform Vision — total management system (product) — DESIGN DRAFT, keep refining

> **Owner vision (2026-06-22).** The end goal is NOT "fix TWB's bot." It's a **total business-management
> platform** sold/leased as a service: **attendance + POS + stock control + back-office + supervisory/HR +
> more.** Delivered as a program and/or a **browser page**. Onboarding is a **stupid-proof wizard** ("Want
> Telegram? Or app/browser/multiple?", "paste your token", "listener details", …) — skippable, usable at
> bare-minimum. **Multi-tenant**, **multi-channel**, **integration-friendly** (tap into a customer's
> existing POS, or be the POS; stock via AppSheet today, maybe our own cloud tomorrow if cost allows).
> Sold as **many packages/bundles/layers** to penetrate different market segments (e.g. the suite *minus*
> POS for businesses that already have one). **This doc governs EVERY architectural decision from here.**
> Status: **VISION DRAFT — refining requirements, nothing built.**

## What this vision demands architecturally (the pillars)
The TWB shift-model question was the tip of the iceberg. The real decision is the **platform shape.**

1. **Multi-tenant by construction.** `org_id` on every row; strict per-tenant isolation (a leak across
   customers is the #1 SaaS catastrophe). Decision to refine: shared-DB row-level vs schema-per-tenant vs
   DB-per-tenant (cost ↔ isolation ↔ scale).
2. **Modular suite, independently enableable.** Attendance · POS · Stock · Finance/back-office ·
   Supervisory/HR · … each a module a tenant can turn on/off. **Recommendation: a modular MONOLITH first**
   (one codebase, clean module boundaries, feature-flagged) — NOT microservices (premature ops cost for a
   small team). Clean boundaries so we *can* split later if scale demands.
3. **Channel-agnostic core + adapters (the biggest change from today).** The business logic (the "brain")
   must contain **zero** Telegram/web/app code. Channels become **adapters** that translate an input
   (Telegram message / web form / app tap) into a domain command, and render the domain's response. This is
   what makes "Telegram OR web OR app OR several" a *config choice*. Today the logic is fused with
   python-telegram-bot — un-fusing it (ports & adapters / hexagonal) is the core enabler of the whole product.
4. **Config-driven, self-serve onboarding.** A per-tenant config object drives everything (channels,
   tokens, enabled modules, rules, integrations, locale, timezone, currency). A wizard populates it;
   sensible defaults + skippable + bare-minimum-usable. **No hard-coded TWB anything** (today many rules are
   TWB-specific constants — those become per-tenant config).
5. **Pluggable integrations.** POS connectors + stock connectors behind **stable interfaces** so "tap into
   their POS", "be the POS", or "AppSheet today → our cloud tomorrow" are connector swaps, not rewrites.
6. **Entitlements / packaging.** Which modules + features a tenant has paid for = a licensing layer that
   gates functionality → enables the bundles/layers go-to-market.
7. **Event backbone.** An internal event log (the event-sourcing insight) ties modules together, feeds
   integrations (a POS/payroll/BI subscribes), and gives audit-by-construction. Modules emit + consume events.
8. **Every domain thing = a first-class entity + event** (the shift-model insight, generalized): shift,
   sale, stock movement, leave, payment — each a proper entity with a **stable ID** + an event trail,
   tenant-scoped, never an overloaded label. *The shift model is just module #1 of this same pattern.*

## The pivotal strategic decision: evolve TWB, or build the platform fresh with TWB as tenant #1?
- **Evolve the current TWB codebase into the product:** reuse working logic; but it carries legacy
  (Telegram-fused, single-tenant, TWB-hard-coded) and we'd be rebuilding the foundation under a live system.
- **Build the platform foundation clean (multi-tenant, modular, channel-agnostic) and onboard TWB as the
  FIRST tenant — via shadow-run.** The live TWB keeps running untouched until the platform proves itself on
  TWB's real events; then cut over with instant revert. **This is the owner's "run parallel / keep old
  aside" instinct applied at the platform level** — and it's almost certainly the right call: it removes the
  "changing a live system" risk entirely, and forces a clean multi-tenant foundation instead of contorting
  single-tenant code. Reuse TWB's *domain logic* (the rules are valuable + battle-tested); rebuild the
  *plumbing* (tenancy, channels, config) clean.

## Honest critique (bedrock — red-teaming the vision)
- **Scope is enormous.** POS + stock + HR + back-office + multi-channel + multi-tenant + integrations +
  packaging — funded companies do *one* of these. Success = **ruthless MVP focus + sequencing**, not
  building it all. The vision is the north star; the plan must be one thin slice at a time.
- **Validate the market before building the whole suite.** Likely cheapest entry: sell the **attendance
  module** (our most mature, most painful-for-others problem) as the MVP — prove people pay — then expand.
- **Small team.** A multi-module SaaS is a large, sustained build. Be realistic about pace; favor boring,
  proven tech; avoid premature microservices/over-engineering (contradicts the owner's own "simple,
  faultless" value).
- **"Be the POS" is the deepest, most regulated, most competitive piece** (payments, tax, hardware). The
  smartest wedge may be the owner's own idea: **suite-minus-POS that integrates with their existing POS** —
  far easier market entry, lower risk, still valuable.

## Likely MVP (to refine, not locked)
A single thin vertical that proves the whole shape:
**Attendance module · multi-tenant · channel-agnostic core + Telegram adapter (web adapter next) ·
self-serve onboarding for that one module · TWB onboarded as tenant #1 via shadow-run.**
Everything else (POS, stock, more channels, packaging) extends the same proven foundation, module by module.

## Open questions to refine together (the "keep refining" list)
1. **MVP scope:** attendance-only first to validate sales? Or attendance + stock (since AppSheet exists)?
2. **Tenancy model:** row-level vs schema vs DB-per-tenant (cost vs isolation)?
3. **Channels for v1:** Telegram only first, web close behind? Native app later?
4. **Build approach:** fresh platform + TWB-as-tenant-1-via-shadow-run (recommended) vs evolve TWB in place?
5. **Tech stack for web/app:** keep Python backend + add a web UI (which framework)? hosting/scale?
6. **Stock:** keep AppSheet as a connector for now (abstract it) — agreed?
7. **POS strategy:** integrate-with-existing first (wedge) vs build-our-own (later)?
8. **Packaging:** what are the first 2–3 sellable bundles + rough pricing/positioning?
9. **Go-to-market:** who's the first paying customer after TWB? (validates the whole thing.)

## Onboarding wizard — UX law (owner, 2026-06-22)
The self-serve wizard: **every step carries a plain-language explanation + conditional (if-this-then)
branching** so the least technical human can do it. "Do you want Telegram? → if yes, here's exactly how
to get a token, paste it here → we'll verify it live." Skippable; bare-minimum-usable; later steps appear
only if earlier answers make them relevant. Stupid-proof is a measured requirement, not a slogan.

## Live-TWB safety during the build (verified 2026-06-22)
A read-only sweep confirmed the LIVE attendance ACTION/BALANCE/DECISION paths are overnight-correct
(they use `_shift_date_now` / `resolve_day` / datetime windows / `_shift_end_dt`, not raw calendar
dates). The only overnight-naivety left is a couple of AUDIT FLAGS (false-alarm noise, not wrong
numbers/actions). **Conclusion: the old model is safe to keep running during the multi-week shadow-run
build — building the new entity+event model (the real fix) does NOT drop the essential live fix.** The
remaining audit-flag noise can be cheaply hardened so the watchdog stays trustworthy meanwhile.

## Principles to carry into EVERY decision from here (owner's standing instruction)
- Multi-tenant, config-driven, channel-agnostic, entity+event-based, integration-pluggable — **by default**,
  even in small choices.
- **Stupid-proof + skippable + bare-minimum-usable** is a *product* value, not just UX polish.
- **Simple & faultless beats clever** (the owner's repeated value) — and prove big changes via shadow-run,
  never a risky in-place cutover.
- Reuse TWB's hard-won *domain rules*; don't reuse its single-tenant, Telegram-fused *plumbing*.
