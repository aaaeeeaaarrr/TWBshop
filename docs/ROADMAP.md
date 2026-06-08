# TWBshop — GM Roadmap

> ⚠ Historical reference ONLY. Forward-looking roadmap; reference only, not a task list to auto-run.
> Contains internal IDs / staff names / server facts — do NOT paste externally.
> Moved out of the auto-loaded CLAUDE.md on 2026-06-08 to keep context lean.

---

## GM Backlog & Roadmap (session 26 — owner asked for the full list)
> The remaining GM "shop-brain" work, grouped. "Logic/Haiku/Sonnet/Opus" = which tier does each.
> KEY THEME (owner): build the GM's KNOWLEDGE via Claude-on-subscription (me, terminal) reading the
> groups and distilling structured rows — NOT per-message bot API. Live bot stays cheap; depth comes from me.

### A. Finance brain (TWB REPORT)
- **Sales-anomaly framework — DONE (session 26), silent until data.** gm_bot/sales.py learns a normal BAND
  per day-type (weekday + payday month-phase + Cambodia holiday/festival class) and flags a final report's
  sales only when below the band with enough same-type history (+ likely-reason context, trend-vs-blip).
  Embodies the owner's 7 ideas. _maybe_flag_sales_anomaly DMs owner. ACTIVATES once the years of Facebook
  Messenger daily reports are imported (owner exporting to email; ~5 days live data only so far).
- **Overexpense carryover model** (pending decision #1, owner thinking) — current: cash-out>cash-in deficit
  carried to next day off the $600 float. Owner wants cleaner model. I propose options when owner's ready.
- **Daily/weekly finance digest** (wanted, not built) — Opus-me or scheduled: sales, expenses, cumulative
  Over/Lost trend, anomalies. Pairs with the attendance digest already live.

### B. Attendance brain (Supervisors/Management) — lateness ladder DONE
- **Leave QUESTIONING — DONE & LIVE (session 26):** detect_leave_request (Haiku) on Supervisors/Mgmt;
  logs every leave to gm_leave_events (accumulates now); missing info ('off' w/o 'AL', or no date) opens a
  'leave_clarify' clarification on the EXISTING ladder (ask→nudge→escalate to owner). _leave_questions pure.
- **AL engine (math) — PENDING, gated on owner seeding balances + schedules.** LOGIC for the math + the
  Haiku detection above. Accrual +1.5/mo ARREARS (mid-month start confirmed). Deduct on confirmed leave.
  /al [name] balance cmd; monthly auto-accrual job; low-balance + frequent-short-notice flags.
- **AL AMENDMENTS/inconsistency (owner raised session 26):** staff often change their AL dates or are
  inconsistent. Design: each leave request is a logged event; the AL ledger uses the LATEST confirmed
  request per person for a pending period and SUPERSEDES the prior (same 'latest wins' pattern as finance
  reports) — release old dates, book new, never double-count, and only DEDUCT once actually taken. When a
  change is unclear/conflicting, GM confirms the final dates via the clarification ladder before adjusting.
  TODO when engine built: add amends_previous detection + supersede link on gm_leave_events.
- **Working-hours-per-staff** (attendance memory "pending") — so GM can judge if a late/absence notice came
  BEFORE shift start (else ask for screenshot). Needs the per-staff shift times once names are mapped.

### C. Stock/ops brain (Stock Checks) — semantic concern detection DONE
- **Stock minimums** — stock_minimums table + /minimums cmd; owner gives each item's minimum → low-stock
  alerts fire when reported below min / not restocked.
- **MINIMUMS ALREADY EXIST on the stock sheet (session 26):** Claude read a sample of Stock Checks photos
  on Max (free). The daily stock-count SHEET (e.g. msg stk_225) has a "Min.Stock (in each 1)" column +
  "Order this" column + daily count columns. So minimums are authoritative, not approximated. Transcribed
  ~48 items (Tomato Ketchup 2 tubs, Almond Ground 2 packs, Eggs 500pc, etc.). OWNER TO CONFIRM blurry ones:
  Black sesame, Vegetable oil, Pilot butter, Molasses; and set mins for handwritten add-ons (Soft Roll
  Plastic, Chocolatin Plastic, Red Velvet, Corn Powder). Insight: chronic 'almost out' items hover right
  at their min (Almond Ground min 2, sheet shows 3,3,3) → raise mins or tighten reordering.

**DAILY STOCK ORDER (7am) — owner spec session 26, foundation built, vision job PENDING:**
- Goal: 7am message to Stock Checks group: "Check if we need to order:\n- Qty Item\n- Qty Item...".
- BOT READS THE STOCK SHEET (owner chose this over the text report): daily ~$0.01 vision read (Sonnet) of
  the latest stock-sheet photo → current count per item → compare to min → below-min items + order qty.
  (A scheduled job can't use Claude-on-Max, so this one feature does use a small daily API call; owner OK.)
- ORDER QTY = bot's OWN determination from USAGE HISTORY (depletion rate), NOT the sheet's 'Order this'
  (many items don't state it). Bot maintains/raises its order-qty as usage grows over time; can suggest
  updating the sheet's 'Order this'. DECLINING usage (item used less than before) → inform owner (off-menu?).
- PERSISTENCE: re-list each 7am until the item clears. NO NEW SHEET: reuse last; 2 days in a row no sheet
  → escalate to the group ("why hasn't the stock check been done?"). Roll out owner-preview first, then live.
- Order-qty formula + clearing rules: owner deferred ("learn more, ask later") — first-pass default built,
  tune on real output.
- BUILT (session 26): gm_bot/stock.py PURE brain (is_low, suggest_order_qty [min+buffer, or usage*lead],
  build_order_list, format_order_message, no_sheet_decision, usage_trend) — 10 tests. stock_items +
  stock_counts tables (init_stock_db).
- SEEDED (session 26): stock_items has 50 items, 47 with owner-confirmed minimums (seed_stock_items_default,
  idempotent DO NOTHING — re-run safe, never clobbers edits). Owner confirmed the blurry ones: Black sesame
  4kg, Vegetable oil 1 tin, Pilot butter 25kg, Molasses 2 bottles, Soft Roll Plastic 10 packs, Chocolatin
  Plastic 10 packs, Red Velvet 8kg, Corn Powder 5kg. STILL need min from owner: White Sauce, Red Sauce,
  Homemade Jam. Each item has aliases for matching the messy daily reports.
- TODO next: ai_client.read_stock_sheet (Sonnet vision) + photo-classify to find the sheet + daily 7am job
  (owner-preview first) + count time-series → usage learning + decline alert. Order-qty formula tune later.

### D. Cross-group KNOWLEDGE (built by Claude-on-subscription, NOT bot API) — the "through you" theme
- **Knowledge Brief** — rolling living summary of ALL groups (3,619 chats, prioritized by importance):
  cheap classify → targeted extract → me folding distilled rows in incrementally. WOC tables would feed it
  (WOC shelved). Never re-read raw archive via API.
- **Staff roster/profiles** — one record per person: real name + call-name + aliases + role + attendance
  record + error/recognition history. Backbone for tagging, lateness, AL, scorecards. (Partial: alias +
  call-name maps exist.)
- **Decisions/policy ledger** (from Management) — distill decisions/announcements so the GM KNOWS settled
  policy (extends the approved-proposals playbook).
- **COMMS & Transfers reconciliation** — money/stock transfers between locations: track + reconcile.
- **Supplier knowledge** — prices over time, issues, who's reliable (ties to the price-list fetcher).
- **Recurring-issue tracker** — equipment faults, repeated complaints, themes across groups.

### E. My added ideas
- **"Ask the GM"** — owner asks free-text ("how often was X late last month?", "what did we decide about
  Y?", "best customers?") answered from the structured knowledge by me/Sonnet. Turns the brain into a tool.
- **Morning owner briefing** — daily digest: yesterday's sales, any Lost, attendance, open clarifications,
  new concerns. One message to start the day.
- **Cross-signal correlation** — combine signals (waste up + sales down + a late key staff) into one flag
  instead of separate pings.
- **Proactive supplier price-change alerts** — price fetcher → compare to last → flag increases to owner.
- **Recognition/morale trend** — extend the points leaderboard into a morale/retention signal.

---

