# Wizard & Config-Driven Platform — design + brainstorm (owner, 2026-06-23)

> The product is a **self-serve wizard** that sells a total business-management platform by the
> dimension (Attendance / Accountant / Stock / POS / …), each its own monthly price, with sub-settings,
> defaults, Simple/Advanced depth, cross-category unlocks, AI-power tiers, and channel choice
> (Telegram / web / app / mix). **TWBshop is tenant #1.** Governing vision: `docs/PLATFORM_VISION.md`.

## 0. The spine: the system IS its config
- A **tenant config** (JSON) = the entire ruleset: which categories are on, and every sub-setting.
- A **config-driven `core/` brain** executes ANY config (no per-tenant code).
- The **wizard** = the editor that produces the config (Simple = pick a template + a few toggles;
  Advanced = the full table).
- The **shadow** = proves `core(config=TWB)` == live TWB across the whole flow → validates the *product*.
- **RULE (owner): from now, every edit/write — even for TWB — is a config setting + core reading it.**
  TWB's rules get EXTRACTED into TWB's config; nothing is hard-coded or throwaway.

## 1. The category tree (main → sub → setting)
Every node has: **default** (stated, editable) · **Simple/Advanced** view · optional **lock** (needs another
category) · **channel** applicability · **AI-power** option where a decision can be a model call.

### Main categories (sellable dimensions — each a monthly line)
Brainstormed beyond the four you named:
1. **Attendance** (check-in/out, leave, OT, points, rosters) — TWB's live domain.
2. **Accountant** (expenses, receipts, payables, vendors, reports) — TWB inert build exists.
3. **Stock / Inventory** (counts, pars, reorder, waste, recipes/BOM).
4. **POS / Sales** (orders, payments, KHQR/Bakong, receipts, day-close).
5. **HR / Payroll** (salary, slips, bonuses, contracts, onboarding/offboarding, bans) — *deeply ties Attendance*.
6. **Scheduling / Rostering** (shift templates, swaps, coverage, forecast-to-roster).
7. **Supervisory / Tasks / Checklists** (opening/closing lists, photo proof, SOP compliance).
8. **CRM / Customers / Loyalty** (customer DB, points, marketing — ties POS; the WOC number archive).
9. **Suppliers / Purchasing** (POs, price lists, delivery photos — ties Stock + Accountant).
10. **Reporting / BI** (cross-category dashboards — the up-sell that needs ≥2 categories).
11. **Delivery / Logistics** (drivers, routes, proof-of-delivery — the WOC delivery domain).
12. **Marketing / Comms** (channel posts, campaigns — FB/IG/TikTok/Telegram).
13. **Maintenance / Assets** (equipment, service schedules).
14. **Compliance / Documents** (licenses, medical papers, expiry reminders).
*(Each is independently saleable; many SUBs only light up when 2+ mains are owned — the up-sell.)*

## 2. Attendance — full sub-tree (the first one we make config-driven)
- **Check-in METHOD** (radio): Telegram live-location · biometric/fingerprint (USB/▶ "plug device, Scan
  Devices") · mobile app (GPS/face) · web kiosk + PIN/QR · NFC card. *(per-tenant; multiple allowed)*
- **Geofence / zone** (on/off · radius · grace).
- **Verdict rules**: grace-late minutes · early-bonus threshold · rounding · minute-of-day vs seconds.
  *(TWB = 5 / 5 / minute-of-day — already in `core.attendance.verdict`, just needs to come from config.)*
- **Overnight / business-day** handling (interval model — already by construction).
- **Approvals (a TABLE — Simple or Advanced)** — one row per request type:
  | request type | needs approval? | # approvers | by whom (role/named) | reason required? | approver must be on-shift? | short-notice rule | re-ping cadence |
  AL · sick · OT/redefine · swap · day-off-move · special leave · early-leave… Each row is pure config.
  *(Heng's re-ping fix = the first row's `re-ping cadence` + escalation, config-driven — see §7.)*
- **Points system** (on/off → defaults shown, editable): early_arrival · late_informed/uninformed ·
  no_show · late_sick_inform · short_notice_al · return_after_doctor · owner_adjustment. *(TWB's catalogue
  already in `core.points` — comes from config.)*
- **Leave / AL** (entitlement days · accrual · short-notice window · fractional hours-AL · papers-cancel).
- **OT / payback** (bank cap · "make-up" model · who can grant · come-early/stay-late).
- **Sick policy** (paperless→payback · papers grace days · leave-early vs absent · the −15 rule — the
  fix we just shipped becomes config: "penalty for late-informing an ABSENCE; exempt if checked-in").
- **Notifications** (which groups get FYIs · supervisor ladder · quiet hours).
- **Reports** (daily digest · who · when).

## 3. AI Power (a per-DECISION toggle — your monetization)
Wherever a decision *can* be a model call, the tenant picks: **Computer Power** (rules only, free) ·
**AI Power** (model — billed 2× our API cost) · **Mixed** (AI assists, human confirms). Decisions that
qualify: receipt/medical-paper reading, photo/fridge/stock-sheet analysis, message monitoring/fraud,
anomaly detection, hiring CV/quiz scoring, demand forecasting, natural-language order intake.
*(One switch per decision; "smartness" = which model, but we say "AI Power level.")*

## 4. Channels (per tenant, mixable)
Telegram (bot — token paste + listener creds) · Web (browser app/kiosk) · Mobile app · Mixed. The brain
holds NO channel code (enforced by the test guard); each is an adapter. Some sub-features are
channel-specific (fingerprint device = on-prem; KHQR = needs the payment rail) and the wizard greys out
what a chosen channel can't do.

## 5. Integrations (penetration = speak the tools they already use)
Offer "be the system" OR "tap your existing one" per category. Most-used to target (verify market share
when we pick each):
- **Attendance**: ZKTeco/biometric, Deputy, When I Work, Homebase, Jibble, Connecteam.
- **Accounting**: QuickBooks, Xero, Wave, FreshBooks, Zoho Books.
- **Stock**: Sortly, inFlow, Zoho Inventory, AppSheet (TWB today), Square for Retail.
- **POS**: Square, Loyverse (big in SE-Asia/cafés), Toast, Lightspeed, SambaPOS; local: ABA/Bakong (KH).
- **Comms/Marketing**: Meta Graph (FB/IG), TikTok, Telegram.
Each integration = an adapter behind a stable interface; a cross-category lock shows "Get Accountant to
unlock auto-posting receipts → books."

## 6. Cross-category ties (the up-sell map)
- Attendance ⇄ **HR/Payroll**: hours/OT/leave → slips & salary (the biggest, most natural bundle).
- Attendance ⇄ **Accountant**: labour cost → P&L; food-allowance → expenses.
- Stock ⇄ **Accountant**: receipts/payables → COGS, vendor price trends.
- Stock ⇄ **POS**: sales deplete stock; recipes/BOM tie a sold item to ingredients.
- POS ⇄ **Accountant**: daily sales → revenue, KHQR reconciliation.
- POS ⇄ **CRM**: customer purchases → loyalty/points; the WOC number archive.
- Suppliers ⇄ Stock ⇄ Accountant (3-way): PO → receive → pay, with price-trend analytics.
*(Each tie is a SUB that only unlocks with both mains — natural revenue expansion.)*

## 7. How this changes the SHADOW + the build
- **Shadow becomes config-driven + full-flow:** `core(config=TWB)` mirrors EVERY GM/staff menu action
  (check-in/out, AL, sick, OT, swap, approvals, points), comparing new-vs-live — not just check-in.
- **Sequence (each safe, shadow-proven, fits the wizard):**
  1. **Extract a `tenant_config` for attendance** (TWB's current rules → config) + make `core` read it
     (verdict/points already pure → just source the numbers from config). *Foundational; small.*
  2. **The AL re-ping fix as the FIRST config-driven feature** (proves the pattern on a real live bug):
     the Approvals table row → config (who/#approvers/reason/on-shift/short-notice/**re-ping 6h×4 +
     delete-prior + skip-responders + escalate-to-owner after #4 + past-window expiry**); `core` holds
     the pure schedule/skip rule (shadow parity-tested), the live `gm_bot` job drives the Telegram
     ping/delete, auto-logged to `gm_events`+`[AL-LADDER]`. → fixes Heng's class, fits the wizard, extends the shadow.
  3. **Wire the remaining menu actions into the shadow** (checkout/settle, AL, sick, points) config-driven.
  4. **Wizard UI** (channel-agnostic, on `core.channel`) producing the config; Simple/Advanced.
  5. **Other categories** (Accountant first — inert build exists) onto the same config+shadow pattern.

## 8. Universal vs tenant-specific (decide together)
Universal (everyone): the category tree, the config schema, Simple/Advanced, AI-power tiers, channels,
the shadow-run-before-cutover tool. Tenant-specific: the *values* (their numbers, their approvers, their
integrations). **Goal: 100% of behaviour = config; 0% per-tenant code.**

## 9. Bonuses / findings (things to capitalize on)
- **Shadow-run is itself a SELLABLE feature**: "run our brain in parallel to your current system, see it
  match for days, then cut over with instant revert" — exactly what we're doing for TWB. Huge trust-seller.
- **Industry template packs** (bakery/café/retail/restaurant) pre-fill all defaults → 5-minute onboarding.
- **Roles/permissions** = a cross-cutting config (who sees/does what) — needed by every category.
- **Wizard "preview/dry-run"**: show what a rule would do on sample data before saving.
- **Data import** from their existing tool (lowers switching cost → penetration).
- **Audit log of config changes** (who changed which rule when) — compliance + trust.
- **Multi-location/chain** (one owner, many shops, shared or per-site config).
- **The AI-power 2× markup is cleanest as per-decision** (transparent, scales with their usage).
- **Pricing levers**: per-category monthly · Simple vs Advanced tier · AI usage · bundle discounts ·
  integration add-ons · shadow-run trial period.

## 10. Parked (do not forget) + how each now fits the wizard
- **AL re-ping fix** (owner spec: 6h×4 · delete-prior · skip-responders · live+shadow · auto-logged) →
  becomes §7 step 2 (the Approvals config POC). Open decisions: escalate-to-owner after #4? past-window
  expiry? (both recommended). Heng's #434 to cancel (moot — he worked the shift).
- **2 Jun-17 shadow boundary edges** (root-cause) · **come-at-X informed/uninformed** Q · the **−15 +
  payback** going-forward test-walk — all parked, all become config rows in the Approvals/Sick sub-tree.
- **Company name** brainstorm — parked (owner to do with me).
