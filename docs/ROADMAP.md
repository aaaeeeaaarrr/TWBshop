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

### F. Marketing & customer acquisition (PARKED, session 49 — owner ideas, NOT started, no build)
> Parked for later. No code yet. The design reasoning lives in chat / CLAUDE.md session-49.
- **AI order-taker for customer DMs (retail side — NOT the listener).** Customers already order by private
  DM. Goal: AI helps take/parse orders. SAFE pattern = **AI-assist BEHIND A HUMAN** on a real staff number:
  AI reads + parses + drafts, a human presses send → no automated-userbot ban risk, and non-customers are
  filtered by the human. Keep the confirmation gate (Arch Rule 3) + free-first. Do NOT auto-reply from a
  user account (Telegram bans automated userbots that message strangers — same risk flagged for the listener).
- **Telegram marketing Channel.** A public Channel for marketing posts; the bot can auto-post there on a
  schedule, and a `t.me/<bot>` link lets readers start a chat with the order bot → Channel = reach, bot =
  conversion. Fully in our stack, no platform approval needed. Likely the easiest first marketing win.
- **FB / Instagram / TikTok automation (owner asked what's possible).** Buildable, but each needs the OWNER's
  platform accounts + API access first (Claude builds the automation; it cannot conjure access):
  - FB + IG = Meta Graph API (a Page + an IG Business account + a Meta app with review) → schedule/publish
    posts, pull insights, route Page DMs into the order system. Native Meta Business Suite scheduling = a
    no-code starting point.
  - TikTok = most gated (Content Posting API needs approval) → likely lean on TikTok's own scheduler first.
  - Highest-value CUSTOM work = connect marketing -> the order system (post -> DM the bot -> order), where
    in-house beats generic schedulers. Mass-DM / cold outreach is OFF the table (ToS + ban + spam).
- **WOC customer-number extraction — METHOD DECIDED (session 49), PARKED for later.** Goal: pull customer
  phone numbers (+ names) from the years of Grab/Foodpanda receipt photos in the listener's archive, for
  outreach once the Telegram Channel is live. **Decided path:** extract via Claude-on-subscription
  interactively, batch-by-batch ("next...next"), in a **dedicated isolated session/worktree that writes
  ONLY to its own output file** (e.g. `woc_numbers.csv`) — reads photos read-only, never touches live
  bots / other lanes; **marginal cost ~$0**. **Cost facts (this session):** billed PER PHOTO, not per
  number; a repeat number OR a food-only/no-number photo costs the SAME on the paid path (the bill is the
  image; dedupe is free in our own code). Through-me path = ~$0 but low throughput (~dozens/turn,
  context-bound -> many rounds for a big archive); automated alternative = Haiku script ~$0.002/photo
  (~$100 per 50k). Grab photos: instruct "customer number ONLY, ignore driver" (negligible cost; validate
  on a sample). **First step when unparked:** fetch a SAMPLE out of Telegram to local files -> pilot to
  measure hit-rate (% photos with a usable customer number) + driver-vs-customer accuracy -> THEN size
  through-me vs script by the real photo count. **WARNING - privacy/legal flag on the OUTREACH stage**
  (data-protection + anti-spam + Grab/Foodpanda terms): extraction is cheap; messaging the numbers is the
  part to clear first.
  **DISCOVERED (session 49, read-only DB):** group = `WOC DELIVERY PICTURES` (chat_id `-715759659`); our
  `ops_messages` ALREADY holds the full history backfill — **123,776 photos, 2022-01-07 -> now, continuous**
  (2022: 5.2k · 2023: 8.7k · 2024: 27k · 2025: 49k · 2026: 34k-so-far). So "how far back / how many" is answered
  from our own DB — no Telegram re-fetch needed for the count, no listener stop needed. CAVEAT: `ops_messages`
  stores METADATA only (message_id + date + media_type), NOT the image files — actual extraction must first
  DOWNLOAD the ~124k photos from Telegram (the session step: brief listener stop or separate login;
  bandwidth/time/rate-limits). Real cost at 124k: Haiku script ~$250 the lot · Sonnet ~$870 · through-me ~$0 but
  thousands of turns (pilot/sample only). Numbers yielded = hit-rate x 124k (hit-rate TBD by a sample; many photos
  are food-only or duplicates).
  **DATA MODEL (owner, session 49):** the PHONE NUMBER is the stable key — customers change their
  Telegram/display names over time, so a number must keep ALL names ever seen under it (one number -> many
  names; accumulate distinct, NEVER overwrite). Same shape as staff `config.STAFF_ALIAS_MAP` (one person, many
  display names) but for customers. Extraction output = UPSERT by number: add a new name to that number's
  name-set if unseen, keep first_seen/last_seen + source photo ids. Record = number -> {names[], dates, sources}.

---

## G. Food money (staff meal allowance) — calc BUILT (inert); button INTEGRATION pending owner decisions (2026-06-21).
**Today: MANUAL** — a line staff write on the daily expense sheet (no calc existed in code before this).
**✅ CONFIRMED MODEL (owner) + BUILT:** `gm_bot/food_money.py::food_money_cents(minutes)` — **500៛ per
STANDARD work hour ÷ 4000, HALF-UP** (9h → $1.13); standard hours = the day's **scheduled shift length**
(`shift_len_min(work_start, work_end)`); **OT/PB NOT counted**; **no-show → $0**. Pure, tested (6 cases),
INERT (nothing imports it; no deploy).
**▶ BUTTON APPROACH (owner-locked):** a GM-bot **"Food allowance"** menu → shows staff **on shift** → tap a
staff → records their standard-hours amount, the name **disappears** → bot confirms which report it lands on.
Shown SEPARATELY as a "Day/Night staff food" list — **never added to the drawer/report money count** (owner:
pre/post-report gives must not miscount the money). Needs no staff conversation (unlike checkout-only).

**✅ OWNER ANSWERS LOCKED (2026-06-21):**
1. **Standard hours = scheduled shift length** (`shift_len_min`); late arrival doesn't reduce it; a 12h
   person = $1.50. (Validated against the real handwritten sheet: $1.38/$1.50/$1.13 = 11h/12h/9h, total $11.92.)
2. **Report assignment = EVENT-DRIVEN, not a clock** ("better when the report is done"): a give is recorded
   OPEN and attaches to the **next daily report STORED** (`gm_daily_reports` via `save_daily_report`). The
   bot predicts the coming report (day↔night alternate) for the confirm message.
3. **Cash-expense tie-in = SHOW only** — the bot reproduces the "Day/Night staff food" list; it does NOT
   touch the typed report's cash count.
4. **Menu = the LISTENER↔bot PRIVATE DM only** (not the owner); listener already pressed Start.

**✅ BUILT (staging, INERT — nothing imports it, no deploy):** `gm_bot/food_money.py` (`food_money_cents`
half-up · `next_report_kind` · `render_food_list`) + `gm_bot/food_money_db.py` (open gives · partial-UNIQUE
idempotency so a re-tap can't double-count · `close_food_period` attaches open gives to a stored report ·
self-migrating init). 10 tests incl. the $11.92 sheet + close-then-reopen.

**⛔ REMAINING before go-live (the HIGH-RISK live wiring):**
- **Menu** in the listener DM (scope: private chat + listener id `1271537077`): list on-shift staff (minus
  already-open) → tap → `record_food_money_give` → confirm "Recorded for the coming Day/Night report."
- **Close hook:** after `save_daily_report` in `gm_bot/bot.py::_maybe_store_daily_report` (~line 1055), call
  `close_food_period(report_id, business_day, report_kind)` → post the rendered list.
- On-shift staff source (reuse `attendance_ui._present_now` / roster) — verify read-only on prod first.
- **Deploy = a LIVE GM-bot restart** (payroll-adjacent) → quiet window + verify (HEAD==origin, active, code carries it).
**PARKED:** checkout-only timing (owner will discuss with staff) — the button approach doesn't need it.

