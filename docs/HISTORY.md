# TWBshop — Historical Archive

> **PRIVATE OPERATIONAL HISTORY — DO NOT SHARE, PASTE, EXPORT, OR UPLOAD OUTSIDE OWNER-CONTROLLED
> PRIVATE REPOS.** Contains historical chat IDs, staff references, server/deploy context, and
> operational notes.
> **Historical reference only. Not current truth unless reopened and verified.**
> Moved out of the auto-loaded CLAUDE.md on 2026-06-08 to keep context lean.

---

## Old session logs (sessions 19–28) — moved from Current Status

**Session 28 (Jun 7) additions on top of the block below:**
- **GM clarification fixes LIVE (the deaf-GM bugs from REPORT):** replies to nudges resolve (nudge_msg_ids);
  understand-without-reply (single open case accepts loose messages); EDITED reports re-parsed + auto-resolve
  + "✓ Corrected — thank you!"; edited ANSWERS resolve too; judged-good answers acked in-group; receipt
  vendor knowledge (gm_receipt_vendors + /vendor cmd, Atlas seeded, prompt injection + skip mode).
- **DATA RELIABILITY LIVE (May 28/29 lesson):** listener self-heals on startup (_catch_up backfills missed
  history, proved on first run); GM bot no longer writes ops_messages (listener = single canonical writer);
  dedupe ran (REPORT 28, Stock 117, COMMS 764 rows); May 28+29 fully backfilled (52 msgs, 4 reports);
  run_collection_watchdog.py on cron */30 (alerts owner if listener dead or no rows 3h).
- **LEVEL-1 RECONCILIATION LIVE (validated by hand on 5 real days, 12/12 exact):** same Haiku receipt call
  now classifies expense_sheet/pos_screen + extracts totals → gm_report_docs; on every FINAL report owner
  gets the reconciliation DM (cash sheet vs mid, day+night vs final, ABA sheet, POS GRAND TOTAL vs sales);
  existence watchdog jobs (no mid by 17:30 PP / no final by 06:30 PP → owner). gm_bot/reconcile.py pure+7 tests.
- **Shell wording COMPLETE:** batch-30 Khmer finals wired (all check-in/out msgs, verdicts, AL/day-off/OT
  screens, My-schedule labels); Special Leave branch fully bilingual; one shared 📍 how-to line on every
  location-asking message; T−10+T0+T+5 carry [I'm late] while undeclared (suppressed once declared);
  no Sick button by design (type → menu → Special Leave). Dry-run v2 = possibility catalogue (10 distinct
  messages once each + one schedule-summary message) — owner rule: walk possibilities, summarize repetition.
- **LATENESS = TIME ONLY (owner final):** no AL option ever; reason on arrival (no tag needed, 30-min
  text-wait, burst messages append, "buttons never block" principle); ignore-the-planner ladder: daily
  check-in line → day-3 "Pick before tomorrow, or I'll pick for you" → day-4 auto-book #1 need slot →
  skip×2 = next bonus not earned + owner digest. Payback slot = MINI-SHIFT: T−10/T0/check-in + early
  +10 points (owner: encourage, not just break); booked-confirm carries the ⭐ line; 12h-before reminder
  for all booked events (+10 = work slots only, reminder = both work + buyback rest).
- **Registry live updates:** Sun Kimying added (Jun 4 start, $160/$15, 145/30 split, 6am-3pm, Wed off,
  uid 7376569669 pre-bound + pressed Start); Failin shift→11am-9pm; Anan→7am-5pm; roll-call 31/33
  (missing: Seth, Vann Failin); /rollcall owner command live. Khmer naming rule: LEFT=surname,
  RIGHT=given (call names from right name).
- **Pending ChatGPT batch (build-time strings):** day-3 warning, booked-confirm frame, 12h reminder,
  check-in debt line, auto-book notice, arrival watch — drafts in docs/ATTENDANCE_SYSTEM_DETAILED.md.
- **Stocks/COMMS outage healed + senior-room recording armed (Jun 7 late):** May 28-29 backfilled for
  Stock Checks (105 msgs/90 photos) + COMMS (26). DISCOVERY: listener account is NOT in Supervisors/
  Management (owner: must NEVER join — junior staff use the shop account) → GM bot = permanent sole
  writer there (exception re-added in _live_group_handler); Supervisors/Management May 28-29 =
  unrecoverable (low cadence, accepted). Watchdog now also monitors twbshop-gm + twbshop-hire services
  + per-chat cadence (REPORT/Stock 26h, COMMS 48h, Supervisors 96h). HIRE BOT = backup recorder for the
  2 senior groups (_backup_recorder, group=-2; same message_id space = dup-free dual writing) — OWNER
  ACTION: BotFather /setjoingroups ON + Group Privacy OFF for hire bot (it was group-blocked by design),
  THEN add it to Supervisors + Management (privacy must be off BEFORE adding).
- Suite green: 297.

**▶ RESUME HERE (session 28 end): ATTENDANCE BUILD IN PROGRESS.**
- **DESIGN 100% CLOSED — docs/ATTENDANCE_SYSTEM_DETAILED.md is the build spec.** Owner answered every 🔒
  over an 8-round brainstorm: button-driven private DM (any text → main menu, one button/row, ←Back first,
  long labels NEVER side-by-side); check-in at shift start via live location (200m, no continuous tracking,
  voluntary always-on secretly stored in location_pings); Late ladder (time buttons → reason ON ARRIVAL w/
  quick-reason buttons → Supervisors notice name+time only) + payback = need-targeted slots (7-day window,
  need-ranked, tie→closest date, before/after own shift + 1 day-off option in their usual hours, partials,
  14-day deadline → AL → salary, no payback-of-payback, no +10 during slots); AL days 7–90 (today+6 =
  Emergency only), balance shown in menu header, cancel until AL TIME starts; Emergency AL 1×/30d from last
  APPROVED (2nd = bonus-not-earned warning, 3rd = hard block incl. "counts as absence (1 day's pay)" line),
  mid-shift variant From-now/I'll-be-back with 1-senior-to-leave; Give OT = SENIOR grants 30min–6h →
  OWNER approves → time bank (cap 14h, no money, no expiry — daily self-deleting reminder) → staff books
  buyback at business-best slots, no approval; day-off swap (same week, 2 seniors + partner, partner
  FIRST); no-show = 1 day's pay (never mention the law) + next bonus not earned, cut carries to next
  month's #1 pay if current already paid; slips named by MONTH OF WORK (May#1=paid Jun 1, May#2=Jun 15,
  prorated from join date), owner reviews ONE paged editable table message → Approve & send all; bonus
  language = earned/not-earned ONLY, surprise reveal on #2 payday, approved legal disclaimer auto-appended;
  points CATALOGUED PENDING owner review (raw events stored now, +10 early/−1/−2 per min etc.); ripple
  check + coverage heatmap + /whois + /payroll + time-ledger digest line + EN/KH strings as DB table;
  👍 ALWAYS for owner messages + explicit action confirmations, staff 👍 never on problems; ALL seniors
  get approval requests even on AL/off-hours. ZERO-API: all flows buttons+logic, Haiku only for group
  redirect + understand-without-reply.
- **REGISTRY FULLY BOUND (session 28):** every active staff has a uid. CSV v3 imported (34 upd, day-offs,
  AL balances, expertise) + 4 planned ALs as approved al_requests (Chun Jun5-7, Kiry Jun4, Soleng Jun4,
  Visal Jun9/10/12). Salaries+bonuses+first/second pays imported (33). New registry cols: salary_usd,
  bonus_usd, phone, first_pay_usd, second_pay_usd (migration APPLIED to prod via init_attendance_db).
  Phones: 9 auto via listener + Khon Visalpisey CONFIRMED=768420022 (+phone), Chuch Pisey=6818934685,
  Sao Visal=5023909267 (proved 'Sao Visal cv' was a DUP of him — uid stripped from dup), Tyty=1067974900,
  Thorn Kimheng=6872279388 (@Kingmeow23). Dual-uid left: Rom Sopheaktra, Sen Vathanakthyda (first DM
  settles). Ex-staffed this week: Met Solina (resigned Jun 5), Lim Soleng (Jun 5), Yorng Lyhouy (owner:
  gone). 'Cheata Sok' renamed → Sok Cheata (KHMER NAMING: left=surname, right=given; call name = right
  name or its tail). Rule: store numeric uid always; accept @username/phone as input only.
- **ROLL-CALL HANDLER BUILT (gm_bot/rollcall.py) — deployed this session:** staff DM /start or hello →
  known active uid = bilingual greet by call name ONCE (gm_state rollcall_greeted), multi-uid settles to
  the writing account; unknown uid + name match (difflib/substring, Khmer name order, zero-AI) → owner
  confirm card [✅ Bind] (callback bind:) , silence to sender; stranger → silence + one-time owner note.
  staff_bind_uid() in database.py. _private_text_router replaces _owner_private_departure registration
  (owner → departure detect, others → roll-call). 12 tests test_rollcall.py. OWNER IS TELLING ALL STAFF
  TO MESSAGE THE GM NOW (roll-call = binding + Start-press collection).
- **MENU SHELL BUILT & DEPLOYED (gm_bot/attendance_ui.py):** owner-only /test → persona picker (any active
  staff) → full main menu + first screens of every flow (Late ladder times, AL date-grid multi-select +
  full-day/15-min from→to, Emergency warning+dates, Day-off dates+partner candidates, OT staff/senior views
  + Give-OT durations+staff pick, Check-in instructions, My schedule card). Cross-audience messages appear
  as [TEST PREVIEW] text; DB-writing endpoints are 🚧 stubs. SAFETY CONTRACT: module has NO send to any
  chat but the owner's own /test message — staff still only get the roll-call greeting. 6 tests
  test_attendance_ui.py (fmt12/day_label/shift_len/late_offsets/grid).
- **NEXT BUILD (in order):** wire real ladders behind the shell — check-in job (+check-out,
  shift-continuity) → Late ladder + payback slots → AL/Emergency flows → day-off swap → Give OT/time bank
  → slips/payroll →
  role-play test with owner (attendance_test_mode: everything to owner only, he plays every role, tweaks
  wording+Khmer) → go-live WITHOUT live-location until owner explains + ALL staff pressed Start.
- **Button stacking fixes shipped:** gm _exstaff_kb + b2b Confirm-Recurring ×2 + Bank-account-number.
- **Still pending from session 27:** 143-item stock order CSV import (owner's staff filling); AppSheet
  decision (own-Google-accounts vs shared-link). Suite green: 280.

**Previous status (session 26):**

**Session 26 also shipped (finance + digest):**
- Lost>$2 group-ask: gm_bot/bot._maybe_ask_lost + finance.lost_exceeds + config.GM_LOST_FLAG_THRESHOLD (2.0). Opens 'cash_lost' clarification; judge prompt updated for cash_lost.
- Finance AI-fallback + alias learning: finance.looks_like_report_attempt + parse_report_text(extra_aliases=) threading; ai_client.extract_daily_report_ai (Sonnet, GM_FINANCE_FALLBACK_MODEL) runs ONLY when the regex parser under-reads a report-shaped message; recompute() math stays deterministic (AI only reads). New labels learned into gm_finance_aliases (init_gm_finance_aliases_db, gm_add/get_finance_alias) and fed back into the free parser. _store_daily_report_if_any is now async.
- Weekly attendance/AL digest: ai_client.generate_attendance_digest (Opus, GM_ATTENDANCE_DIGEST_MODEL) + _weekly_attendance_digest_job (run_daily 01:30 UTC, fires Mondays PP only) + gm_get_lateness_cases_since / gm_get_concerns_since. DMs owner; skips when no data. (AL section will populate once the AL engine + balances exist.)
- Tests: test_finance.py now 26 (added lost threshold + report-attempt heuristic + alias learning).
- TEST SUITE FIXED (session 26): added repo-root conftest.py that imports the real config.py before collection, so test_intake.py's `sys.modules.setdefault("config", stub)` no longer poisons later GM test modules. `python -m pytest tests/` now runs the WHOLE suite green (232 passed). Run the full suite normally again.
**Phase:** Retail bot complete. B2B bot Phases 1+2 complete. GM Manager bot live. Ops listener live. Hiring system: intake + quiz + Haiku intake intelligence + Opus assessment plumbing built. Chaos tests: B2B 42/42, Hire 57/57. Assessment decision tests: 17/17.

**(session 27 note, still pending):** owner's staff are filling the
full 143-item stock order CSV (C:\Users\Papa\Documents\stock_order_template.csv — 3 sheets: Sheet1 dry/baking
50, Sheet2 Meats 26 + Cheese 18, Sheet3 frozen/condiments/spices/pasta-delis/packaging 49). When owner sends
it: IMPORT into stock_items — create the ~93 NEW items + set each item's order_qty_override (fixed "how many
to order", replaces the bot computing it → no more 748-eggs) + supplier + confirm units/mins (esp. Meats/
Cheese which had blank units/mins). Watch for [X]=discontinued and [Delis] flags. Then the 7am order list
reads "Order N {unit} {item} — from {supplier}".
STRATEGIC (see "STRATEGIC — POS convergence"): stock staff-entry will start on AppSheet (throwaway bridge),
OUR Postgres stays source of truth; cross-ref the POS repo later. To START AppSheet build, owner must pick:
own-Google-accounts vs shared-link + by-area counter assignments.
PAUSED: Private-DM Attendance overhaul (owner planning more — full design in docs/ATTENDANCE_SYSTEM_*.md;
CSV importer DONE, registry rebuilt 35 active). SHELVED: Delivery System (WOC). Parked: AL engine, Lost-ask
sales-drop %, Knowledge Brief, stock /stock Telegram flow (owner-test mode).
GM shop-brain broadly LIVE: semantic concerns, policy replies+72h repeat, Lost>$2 ask, finance AI-fallback,
weekly digest, REPORT dedup, staff registry + ex-staff offboarding (auto-remove OFF — bot not group admin;
owner to promote TheWineBakery24PP if wanted), stock minimums seeded + vision-read job + 7am order (owner-
preview), global staff tagging. Whole pytest suite green (268).

**Semantic concern detection + policy replies — built & live (session 25):**
- shared/ai_client.py: detect_concern_semantic (Haiku, GM_CONCERN_MODEL) — meaning-based waste/mistake/low_stock judge. Replaces the 2-keyword scan. Catches zero-keyword reports ("tray slipped, 6 cakes fell"); ignores negations ("no waste today"). Fails flagged (_error) so caller can fall back.
- gm_bot/analyzer.py: _detect_text_concerns renamed _keyword_text_concerns (kept as FREE fallback). New _worth_checking pre-gate + _semantic_text_concerns (per-msg AI error -> keyword fallback) + detect_text_concerns dispatcher. analyze_live_message now async. run_analysis awaits it. config.GM_SEMANTIC_CONCERNS (default True) + ANTHROPIC_API_KEY gate semantic vs keyword.
- gm_compose_reply WIRED to approved policies: live concern -> gm_get_approved_policy_for_type(type) [SQL, no AI] -> gm_compose_reply (Haiku) drafts a fresh reply -> _policy_reply_plan routes it. Owner-gated by gm_state 'policy_replies_to_staff' (mirrors report_corrections_to_staff): not 'true' = private preview to owner; 'true' = posts in-group as reply. SET TO 'true' (live) session 25.
- Matching v1: correction + recipients='group' + concern_type match (or 'mixed'), newest approved wins. Skips individual/recognition proposals. NOTE: 0 approved group-correction policies exist today, so nothing fires until owner approves a proposal via /proposals — going live is dormant-safe.
- 72h REPEAT-NOTIFY (session 25, replaces the cooldown idea): no suppression. If the same policy/type fires again in the same group within config.GM_POLICY_REPEAT_HOURS (72), GM still replies in-group as usual AND pings the owner privately ("correction not landing") + forwards the triggering message. Tracked via gm_state key 'policy_last_reply:<chat>:<type>' (ISO ts), stamped only on a real in-group post. Pure helpers _repeat_within / _humanize_gap / _repeat_alert_text in bot.py.
- Tests: tests/test_semantic_concerns.py (12, injected fake detector) + tests/test_policy_reply.py (11: 4 routing + 7 repeat-notify). Full GM suite 49/49.

**Staff alias map — checked (session 25):** Scanned Stock Checks 2026-05-27 roll-call ("my name is X, call me Y"). config.STAFF_ALIAS_MAP already complete for the prior unknowns: Cat=Mon Chenda, Nakk=Doeun Rothanak, NY=Yi Sony, O=Korn Chantrea, Seth 🫵=Phan Piseth, Boss TT=Tyty, por=Por. STILL UNRESOLVED (did not self-ID in roll-call — ASK OWNER): **Pew, Me Me, Chan Oun, Roth** ("Roth" is ambiguous — ~70 B2B senders contain it).

**Owner "remind me later" queue (resurface each session until done):**
- Finance #1 overexpense carryover model (owner to think of an approach)
- Finance #3 BUILD: wire the Lost>$2 group-ask into the finance flow
- Stock minimums intake (#6 — table + /minimums, then owner gives each item's minimum)
- Provide real names for: Pew, Me Me, Chan Oun, Roth
- Facebook Messenger export (Sara Bologna account)
- Bakong/KHQR registration (needs passport on other PC)
- Hire bot: tap the pending owner Approve/Reject button, then run /create Test Candidate end-to-end
- Review the 383 concern cards in GM chat (/review for missed)
- Hiring: owner will send more questionnaire papers to analyze (targeted replies, salaries) → judge+educate via ChatGPT

**Telethon listener restored (session 24):**
- twbshop-listener was DOWN (crash-looping) since the session-22 secrets.py reformatting wiped TELETHON_API_ID/API_HASH/PHONE. Those creds were only ever on the server, never pushed to the repo → not git-recoverable. (Same corruption that killed GM_BOT_TOKEN.)
- Recovered api_id/api_hash from my.telegram.org (app "TWB Listener", id=30110706). Restored to secrets.py LOCAL + SERVER + REPO. Phone +85510655010 also stored everywhere.
- ops_intelligence/listener.py fixed: connect() + is_user_authorized() first, phone login only as fallback — so a valid session reconnects with NO re-login (start(phone="") used to raise before checking the session).
- Listener account = TheWineBakery24PP (id=1271537077) — the shop account that posts in groups. Session file ops_listener.session intact (created May 28, valid).
- ops_messages now holds 567,707 messages / 3,619 chats / 2020-2026 (330,933 text + 210,310 photos). This is the full 6-year business archive — STORED but not yet DIGESTED into a knowledge brief (that is the GM "shop-brain" build, still pending).

**SECRETS DURABILITY RULE (learned the hard way, session 22→24):**
- EVERY secret must live in the twbshop-secrets REPO, never only on the server. Server-only secrets get silently wiped by any secrets.py reformat/bootstrap and are unrecoverable.
- After adding/restoring any secret: push secrets.py to the repo via `gh api --method PUT /repos/aaaeeeaaarrr/twbshop-secrets/contents/secrets.py`.
- secrets.py is multi-line Python ALWAYS (one-line corruption = SyntaxError). Verify with `python -c "import secrets"` after any edit.
- The dangerous secret for the listener is the SESSION FILE (ops_listener.session = auth_key), NOT api_id/api_hash. Guard the session file. Consider 2FA on the account.

**GM finance parser — wired + storing (session 24):**
- gm_bot/finance.py: deterministic parser. parse_report_text + is_daily_report + recompute (drawer = float + cash in - cash out; Over/Lost = count - expected; catches staff math slips) + business_day_for (06:00 boundary) + classify_report (final=dawn <06:00, mid=daytime) + parse_full. No AI, no DB.
- shared/database.py: gm_daily_reports table + init_gm_finance_db + save_daily_report (idempotent on chat+message_id) + get_daily_reports_for_day. init called from run_gm_bot.py.
- gm_bot/bot.py: REPORT text that is_daily_report -> _store_daily_report_if_any (parse+recompute+store, NO messaging — owner-gated). MISROUTED ROUTING REMOVED per owner (no more wrong-group DMs; pure ingest). Receipt clarity check on REPORT photos unchanged.
- tests/test_finance.py: 14 tests pass (real reports 27/28/30, math-error catch, day-boundary, 4:55 final, caps/comma/spacing variations).
- STILL TO DO per owner's design: AI fallback when free-parse fails + learn new aliases; knowledge-brief (built by Opus-me on subscription, not bot API); semantic concern detection (replace 2-keyword); stock minimums intake; new /commands. Dedup (#5) before aggregation. See REPORT Finance Tracking section.

**Clarification escalation ladder — built + staff-facing ON (session 24):**
- gm_bot/clarify.py: pure logic — is_checking_phrase + decide_ladder_action (nudge 10min open / 30min checking / escalate at 2h) + nudge_text (hardens after 3) + escalation_text. 9 tests.
- gm_clarifications table + init_gm_clarifications_db + create/find/nudge/checking/answer/escalate helpers.
- bot.py: when GM posts a staff-facing math correction it opens a clarification (question_msg_id = the correction msg). _clarification_ladder_job (every 120s) nudges in-group on schedule, escalates to owner at 2h. _resolve_clarification_response records staff reply as the answer (their reason), or backs off to 30min on a "we're checking" phrase.
- report_corrections_to_staff flipped to 'true' — corrections now go in-group, tagging the report.
- 26 tests pass (17 finance + 9 clarify).
- RECEIPTS now folded into the ladder (topic='receipt_clarity'): unclear receipt opens a clarification; a later clear receipt or a text reply resolves it; same nudge/escalate cadence.
- "ANSWER DOESN'T ADD UP" judge wired: ai_client.judge_clarification_answer (Sonnet, claude-sonnet-4-6, configurable). On every staff answer the GM asks Sonnet if it genuinely resolves the question; if not -> escalate to owner with the answer + reason. Fails open (no escalation) on AI error. Sonnet chosen over Opus: bounded short Q+A judgment, runs live/API-metered, cheap+fast; Opus reserved for the brief + cross-week reasoning.

**GM misrouted message detection (session 23):**
- `_notify_misrouted()`: DMs owner + forwards the message whenever something lands in the wrong group
- `_check_misrouted_photo()`: for photos in non-REPORT groups — runs `assess_receipt_photo()` (Haiku, non-blocking via `asyncio.create_task`) — notifies owner if `is_receipt=True`
- `_check_report_receipt()`: now notifies owner when a non-receipt photo arrives in REPORT (previously silent)
- REPORT group text/doc/video: notifies owner with content type + preview, then stops (was previously falling through to Stock Checks concern scanner — bug fixed)
- GM_BOT_TOKEN was missing from secrets.py (lost during session 22 reformatting) — restored to local secrets.py, pushed to twbshop-secrets repo, added to server. GM bot active.

**Correction + offer flow wired (session 22):**
- correction:* callbacks registered in hire_bot/bot.py → delegates to correction_flow.handle_correction_callback
- DB fallbacks added to correction_flow: targeted_message_id and critical_hold loaded from DB on restart
- _store_correction_response idempotent: SELECT before INSERT, one response per attempt
- offer_flow refactored: send_offer_message (no DB) + record_offer_accepted (INSERT only on applicant accept)
- owner_approval_kb(attempt_id) replaces static OWNER_APPROVE_KB — attempt_id encoded in callback_data
- offer:owner_approve:{id} / offer:owner_reject:{id} registered in bot.py (owner private chat)
- offer:accept / offer:question registered (applicant side)
- E-T2 partial check before offer send — pauses and asks owner for last working day
- Path A open-check → correction_understood → auto-sends owner approval button (request_owner_approval)
- handle_open_check_answer returns classification dict for Path A detection
- 6 new tests in tests/test_correction_offer_flow.py — 87/87 pass
- secrets.py reformatted (was one-liner, local corruption)
**Assessment plumbing built (session 21):**
- hiring_ai_assessments, hiring_targeted_messages, hiring_correction_responses, hiring_offers tables
- assessment_package.py: evidence builder + Sonnet rule detectors (critical signals, partial answers, consistency checks)
- assessment_runner.py: run_final_hiring_assessment() — configurable model, JSON validator requiring evidence_refs
- assessment_notify.py: English-only owner notification, idempotent
- correction_flow.py: agreement buttons, open understanding check, Opus classification, resistance handling
- offer_flow.py: all gates checked, hiring_offers row only after owner approval
- assessment_pipeline.py: wired into _end_screen, fails silently (quiz never blocked)
- Khmer validator: 19/19 tests — catches COENG splits, anusvara/vowel splits, multi-space, box/dash artifacts, Latin adjacency

**Khmer status — BLOCKED permanently until manual solution:**
- khmer_auto_send = false
- khmer_status = pending_manual_approval
- All Khmer stored as NULL until manually reviewed and approved
- Khmer validation pipeline itself is unreliable (test strings being corrupted in transit)
- Do not attempt Opus Khmer generation via this pipeline — handle Khmer translation manually

**Live test results (session 22):**
- Service: twbshop-hire.service active (running) on server
- Service file: /etc/systemd/system/twbshop-hire.service (systemctl enable if needed)
- Assessment pipeline: FIRED — hiring_ai_assessments id=1, recommendation=hire, valid=True
- Owner notification: SENT to Telegram (check phone)
- Targeted message: id=1, English stored, Khmer validation FAILED (expected — blocked by design)
- Path A (correction_understood + proceed_to_verbal_retest): PASS
- Path B (conditional_reporting + reject_unless_owner_override): PASS
- hiring_offers: None (correct — row only created when applicant taps accept)
- Bugs found and fixed: JSONB double-decode in assessment_package + bot.py; Opus max_tokens 4096→8192; jsonschema missing from requirements.txt

**Pending (before Opus assessment is truly live):**
- Opus system prompt calibration with approved examples (waiting on clean samples)
- systemctl enable twbshop-hire (service not auto-start on reboot yet)
**Last completed (session 20):**
- B2B chaos test: 38/38 pass. 5 bugs found and fixed:
  1. FIXED: bm_edit_order (SEE YOUR ORDERS) was deleting the live [Confirm][Edit][Cancel] message — _menu_msg not cleared in _do_confirm
  2. FIXED: bm_back didn't clear _recurring_pending/_days — state leaked into next session
  3. FIXED: b2b_cancel keep/cancel-all dialog was dead code (existing_bread/cake never set) — replaced with live DB query
  4. FIXED: handle_menu_callback didn't call _restore_cart — cart lost after bot restart
  5. Hire chaos test: 33/33 pass
- Multi-file CV storage built: hiring_intake_media table, "Done sending files" button flow, 10-file limit
  - Applicants can send 5+ CV photos/certificates before tapping Done
  - All files stored in hiring_intake_media (one row per file)
  - No AI analysis before TEST_UNLOCKED — store first, analyse later
  - Photos at any state (fulltime_gate, appt_set) also stored silently
  - Migration: migrations/2026_05_29_hiring_intake_media.sql (run on server)
- Added new chaos tests: restart/resume (R01-R03), cross-group isolation (X01-X03), Telegram failure (T01), S12 fix verification (T02), multi-file CV (M01-M08)
- Run tests: python3 run_test_b2b_chaos.py (38/38) && python3 run_test_hire_chaos.py (33/33)
**Last completed (session 19d):**
- GM Manager bot fully live: privacy mode disabled, re-added to Stock Checks group, correct chat_id=-1003952029131
- Stock Checks Nov1–May27 2026 imported: 5,276 messages under correct chat_id
- 411 concerns analyzed; historical ones re-sent via local script run_send_historical_photos.py
- 383 concerns sent with photos (364/383 had matched local photos, 95% rate)
- /review command added: resends sent-but-unreviewed concerns by staff with fresh buttons
- Fixed: double /check button session bug, cmd_staff double-send bug
- Button flow: /check → staff buttons → concerns flow; /review → same for already-sent ones
- Buttons: [✓ All good] closes concern; [🚨 Real issue] flags for tracking; [📚 Teach bot] suppresses future similar via gm_rules
- /proposals + /approved + /points commands added (Claude API clustering, approval flow, monthly leaderboard)
- Teach flow improved: shows original concern text, no 60-char limit
- Supervisors TWB history imported: 323 messages (Jun 2025 – May 2026)
- All group chat_ids confirmed: Stock Checks, Supervisors, Management, COMMS & Transfers
- DAILY_REPORT_CHAT_ID=-5136886404 (TWB REPORT group, replaces Facebook Messenger daily reports)
- Management group imported: 538 messages (May 2023–May 2026)
- Staff alias map: 25+ Telegram display name → real name mappings from May 2026 salary sheet
- Proposals redesigned: Opus model, soft skip (pool return), AI-powered refine, 24h auto-skip, model ranking
- [✏️ Refine] on /approved: stacked notes, conflict detection, [New/Old/Keep both] resolution buttons, refinement_history column
- Buonissimo supplier added to price fetcher (chat_id=-5218925376)
- PDF price list handling rewritten with PyMuPDF: text-layer PDFs sent as PDF; image-only PDFs rendered page-by-page as JPEG
- TWB REPORT receipt checking: GM bot now monitors every new photo in REPORT group and replies in-thread if unclear
- Reply uses Telethon (not Bot API) to avoid MTProto/Bot API message ID mismatch for regular groups
- AI clarity rules tightened: only flags unreadable total amount or items — ignores missing vendor, date, phone, blank columns
- Receipt clarification learning: past answered Q&As stored in receipt_clarifications DB, injected into AI prompt as few-shot examples
- Backfilled 5 expense format examples into DB (mixed delivery+gas sheet, Atlas Ice, daily staff food money, food ingredient expense list, B2B delivery charges)
- run_check_report_photos.py: one-time historical scan — all 9 existing REPORT photos now pass clean (zero unclear after learning)
- run_backfill_clarifications.py: one-time script to import staff replies to historical clarification questions into DB
- Proposal conflict resolution: added [✏️ Explain...] button — owner can type free-text instruction to Opus instead of choosing preset buttons
- Global CLAUDE.md push protocol updated: any push/commit wording triggers full protocol (CLAUDE.md update + commit all + push)
- Hiring scoring engine built, tested, and refined: hire_bot/scorer.py + followups.py + readtime.py
  - Phase 1: auto_grade() → score_summary + is_correct per row; 0 contradiction rows written in Phase 1
  - Phase 2: detect_semantic_contradictions() → polished liar detection (tick=CORRECT + responsibility ≤ 1)
    Wrong tick + bad written = consistent failure → NOT flagged. hiring_contradictions stays clean.
  - 6 CONTRADICTION_PAIRS finalized: A2-Q13/C-Q8, A4-Q34/C-Q12, A4-Q38/C-Q12, A5-Q42/C-Q11 (updated),
    A6-Q58/C-Q16, A6-Q51/D3; + 1 written-vs-written pair: C-Q3/C-Q8
  - Risk profile: category-gated overrides; A2-Q13 → honesty 'weak'; A4-Q38 → quiet 'weak';
    A2-Q20 → experience 'red_flag'; both schedule questions wrong → schedule 'red_flag'
  - 13 curated bilingual follow-ups, capped at 5, eligibility blockers first
  - Per-language read-time: EN button vs EN words only; KH button vs KH words only
  - 7 repeatable tests in tests/test_hire_scorer.py (6 Phase 1 + 1 Phase 2 pre-scored)
- Session state schema added: attempt_status (9 states), abandoned_at_question_id, resume_count on attempts;
  resume_count + reopened_by on hiring_sessions; migration in migrations/2026_05_28_session_state_schema.sql
- run_session_state_migration.py deleted (one-time script, already run on production)
- hire_bot/bot.py built: token verify → identity confirm → intro block → 111 questions
  (yes/no, single-choice, D1 ranking, free-text) → follow-ups → end screen → owner notify
  Only accepts answer for currently expected question; deletion best-effort; 10-min timeout job
  Staff /create [Name] → one-time deep link; /reopen [attempt_id] → second resume
- hire_bot/sessions.py: DB layer; SELECT FOR UPDATE on open; check-before-insert on record_answer
- hire_bot/questions.py: QUESTION_SEQUENCE (111 items); D1 uses sorted(correct_order) for scrambled buttons
- run_hire_bot.py: entry point; requires HIRE_BOT_TOKEN in secrets repo (not added yet)
- Schema additions: hiring_contradictions table, risk_profile+score_summary on quiz_attempts, quiet_time_behavior+schedule_story_match on trial_outcomes
- Quiz bank live + reproducible: 111 questions in DB + migrations/2026_05_28_load_final_v3_quiz_questions.sql seed
- migrations/2026_05_28_scoring_schema.sql preserved — idempotent, safe to re-run
- Server stash list cleared (3 stale stashes dropped — all work already in main)
- Quiz bank audit passed: 0 duplicates, 0 missing answers, 23 critical tags correct, 8 verbal retest flags correct, D1 order correct
- Legacy paper import system live: hiring_assessments table + schema migration (2026_05_28_hiring_assessments_schema.sql)
  - assessment_id on hiring_feedback_points + hiring_contradictions; attempt_id made nullable on contradictions
  - staff_level_expectation, confidence, interpretation columns added to hiring_feedback_points
  - severity + source_type CHECKs expanded
- Vannary imported: candidate_id=24, assessment_id=2, 14 findings (leadership_audit, senior_staff)
  - Most critical: A2-Q13 risk_critical PENDING VERBAL RETEST (not confirmed dishonesty; tick position ambiguous)
    Retest Q stored in interpretation: "if you make a mistake and nobody sees it, what do you do first, and why?"
    If correct in person → downgrade to gap_medium. If defends hiding → escalate.
  - Training method gap (D3): corrected to senior_expected_gap (worker-level answer, senior-level gap)
  - Strengths: quiet-time instinct, problem chain detection (D2), customer/product awareness
  - map_confidence() added: medium_high → medium for per-finding field (assessment level retains 4-value scale)
- hiring_assessment_evidence table added: audit trail of photos/scans per assessment
  - file_hash (SHA-256, auto-computed when file available) + storage_status (8 precise values, not vague 'local_only')
  - storage_status: local_to_owner_phone | local_to_pc | server | cloud | telegram_file | chatgpt_only | missing | deleted
  - hash_file() helper in import scripts: fills file_hash automatically when path is known, NULL otherwise
  - Placeholder rule: update row #1 to photo #1 when filing — never mix NULL file_name with real file_name rows
  - Vannary evidence_id=1: storage_status='chatgpt_only' (photos uploaded to ChatGPT, not saved elsewhere)
- Part E hiring-facts added + structural fixes (sessions 18 + 18b + 18c):
  - hire_bot/questions.py: PART_E_ALWAYS (7 questions: E-A1a, E-A1, E-A2, E-A3a, E-A3b, E-A4, E-A5)
    E-A1a: structured "Can you start within 3 days?" (Yes/No/Not sure) — E-T3 fires on B or C
    E-A3 split into E-A3a (studying? Yes/No) + E-A3b (working? Yes/No) — no more keyword guessing
    evaluate_e_triggers(_rows=None): _rows injection for unit tests; DB load when None
    Triggers evaluated after PART_E_ALWAYS[-1] (E-A5) — not hardcoded "E-A5" in bot.py
  - hire_bot/sessions.py: get_answered_part_e_ids(), store_part_e_triggers(), load_part_e_triggers()
  - hire_bot/bot.py: cb_answer validates Part E questions correctly (was silently rejecting E-A3a/E-T1)
    _advance_part_e: triggers computed after PART_E_ALWAYS[-1], stored in DB immediately
    _after_main_quiz: reads DB for Part E answers — handles bot restarts without relying on user_data
  - Part E answers stored in hiring_quiz_answers (same table, E-* question IDs as FK)
  - tests/test_part_e.py: 30 unit tests, all pass (no DB required via _rows injection)
    Covers E-T1/E-T2/E-T3 structured + keyword paths, all-triggers, no-triggers, sequence ordering,
    get_next_part_e_question, get_part_e_progress
  - migrations/2026_05_28_part_e_and_ops_assessment.sql: original (8 questions, CHECK expansions)
  - migrations/2026_05_28_part_e_v2.sql: v2 structural fixes
    - E-A3 deactivated; E-A3a, E-A3b, E-T3 inserted with ON CONFLICT DO UPDATE
    - answer_sensitivity column: normal/owner_only (E-T2 = owner_only for salary data)
    - part_e_triggered text[] on hiring_quiz_attempts for DB-persisted trigger state
    - hiring_assessment_message_refs table: links findings to specific ops_messages rows
  - migrations/2026_05_28_part_e_v3.sql: v3 fixes (NOT YET RUN ON SERVER)
    - E-A1a question inserted (display_order=0, before E-A1)
    - All original Part E seeds converted to ON CONFLICT DO UPDATE
    - hiring_assessment_message_refs.message_id → ops_message_row_id (rename)
    - telegram_message_id column added; backfilled from ops_messages.message_id
    - UNIQUE constraint → hamr_unique_per_finding (assessment_id, finding_id, chat_id, ops_message_row_id)
    - 4 previously skipped Seth message refs re-inserted (multi-finding support now works)
    - staff_identity_aliases table created with Seth's 5 aliases seeded
- Seth (Phan Piseth) attendance assessment imported (session 18):
  - run_import_seth_assessment.py: creates candidate + ops_messages/attendance_review assessment + 6 findings
  - candidate: existing_staff, alias=Seth, day-shift service
  - findings: repeated lateness, payback pattern x4, multi-supervisor reporting (5 supervisors), no-show May 27, rotating excuses, accountability gap
  - ENTITY NOTE: Phan Piseth (Seth) ≠ Piseth Vinal (Hikaru, night bakery) ≠ Mr Pisey (SAM kitchen) — 3 separate people, never merge
  - SALARY PRIVACY: regular new staff salary OK in management group; supervisor/senior/chef/above is owner-only, never in any group
**EVIDENCE STATUS:**
  - assessment_id=2 (Vannary): COMPLETE — 12 photos linked, renamed 01_page.jpg–12_page.jpg, SHA-256 hashed
    Path: C:\Users\Papa\Documents\Bluetooth\Staff Assessments\Vannary\2026-05-13 leadership audit\
    storage_status=local_to_pc. Move to cloud/server when convenient.
  - Every future import: provide zip/photos at import time and evidence rows are inserted automatically
**MANUAL TEST CHECKLIST (before heavy B2B rollout / public hiring ads):**
  B2B:
  - [ ] True restart test: build cart → `systemctl stop twbshop-b2b` → start → tap old Confirm/Edit/Cancel/See Orders from Telegram
  - [ ] Live two-group test: two real B2B groups, verify carts/orders/locations never cross
  - [ ] Check actor logging is appearing in logs: `journalctl -u twbshop-b2b | grep 'b2b_confirm\|b2b_edit\|b2b_cancel\|Location set'`
  Hiring:
  - [ ] Live Telegram test with 5+ photos/files (send each separately, tap Done, verify count in message)
  - [ ] Verify `SELECT * FROM hiring_intake_media WHERE intake_id=X` shows all rows after live test
  - [ ] Confirm no AI call before TEST_UNLOCKED: `grep -i 'anthropic\|claude' logs/hire_bot.log` should be empty during intake
  - [ ] Start hire bot: `systemctl start twbshop-hire`
  - [ ] /create Test Candidate → full quiz flow
**Next task (immediate):**
  1. Run manual test checklist above
  2. User reviews 383 concern cards in GM chat (tap buttons as they go; /review for anything missed)
  3. Staff real names mapping: provide real names for aliases (Cat, Nakk, NY, O, Pew, Me Me, Seth, Boss TT, Chan Oun, Roth, por Khmer Bruce PP)
  4. Supplier price extraction [IN PROGRESS] — run `python run_extract_prices.py` on server
  5. Customer reactivation: extract names+phones from WOC DELIVERY PICTURES photos
  6. B2B bot rollout: add bot to all 24+ B2B customer groups
**Next task (hiring system):**
  1. Add HIRE_BOT_TOKEN to secrets repo, then test /create → deep link → candidate flow end-to-end
     Use this test path: /create Test Candidate → intro → 111 Qs → E-A1a=B (triggers E-T3) + E-A3a=A (triggers E-T1) + E-A3b=A (triggers E-T2) → all 3 triggers fire → E-Final → end screen → owner notify
  2. Wire up Phase 2 async scoring: after complete_session(), kick off draft_rubric_scores + detect_semantic_contradictions + build_risk_profile (background job or webhook)
  3. Intake funnel (hire_bot/intake.py) BUILT — all migrations run on server, 39 unit tests pass
     "cook have?" fix: hire_bot/bot.py handle_text now starts intake on ANY first message (no session),
       not just keyword matches. Bot is ad-linked — all first contacts are applicants.
     Edge case fixes (session 19d):
       - Photo/doc as first message: _handle_language_check detects has_media → skips to cv_pending
         _handle_document_or_photo: no-session → start_intake then handle_message (photo processed in 1 flow)
       - Blocked session + new text: start_intake handles cooldown; expired → reset to language_check
       - test_unlocked + new text: replies "quiz ready, use invite link" — does NOT reset session
     9/9 integration test scenarios pass: run_test_intake.py on server
     Next: add HIRE_BOT_TOKEN → start bot → run live Telegram test with real phone
     DESIGN NOTE: hiring_intake_sessions has flat UNIQUE (telegram_chat_id) — upsert overwrites old row
       on re-apply, no audit history. Future fix: partial unique index (active attempts only) or
       separate applicant_person → intake_attempts hierarchy. Not urgent before first real applicant.
  4. Insert Norin's 24-point bilingual feedback into hiring_feedback_points
  5. Link the 47 draft feedback_points to quiz question IDs (update source_ref, evidence_status from draft_unlinked to linked)
  6. Feed more questionnaire photos to ChatGPT → paste structured block here → import via same pipeline
  7. After 2–3 more person-specific import scripts: build generic structured-block importer
     (reads one standard block → inserts candidate + assessment + evidence rows + findings in one pass)
  8. Seth: formal accountability conversation, then update assessment findings with outcome
**Next task (new systems):** ChatGPT export ZIP pending (hiring bot questionnaire). Facebook Messenger export pending (Sara Bologna account).

---

## REPORT Finance — full design notes (condensed in CLAUDE.md)

## REPORT Finance Tracking — Design Notes & Pending Decisions (GM bot)
> Gathering/design phase (Opus). NO rules built yet. Read this every session and remind the owner of the pending list.

**Group:** TWB REPORT (chat_id -5136886404). Replaced Facebook Messenger daily reports. Live data since 2026-05-27.

**Confirmed business model:**
- **Business day = 06:00 → 06:00** (24h). Café/bakery trades late.
- **~05:00:** staff post the final 24h total — deliberately 1h before the 06:00 close so there's a buffer to hunt down any discrepancy.
- **05:00–06:00:** mistake-hunting hour. If clean, books close.
- Receipts posted **after the ~05:00 close but before 06:00 roll into the NEXT day.**
- A final total posted ~05:00 and labelled e.g. "28/05" closes the window that ran 06:00 27th → 06:00 28th. **File it under the day that just closed (the 27th), not the morning-of-writing label.**
- Two reports per day: **afternoon mid-report (~16:00, ≈ day-shift handover)** + **05:00 final (full 24h).** Keep BOTH, label mid vs final, so a discrepancy can be localised to a shift (night ≈ final − mid).

**Daily total report format (decoded + verified on 3 days):**
```
DD/MM/YYYY
Cash on hand : $ 600        ← starting float (constant)
cash income  : $ X          ← cash sales
Aba income   : $ Y          ← bank-app (ABA) sales
total sales  : $ X+Y        ← revenue
Cash expense : $ Z          ← cash paid out
ABA Expense  : $ W          ← bank paid out
Total        : $ ___        ← expected drawer = 600 + cash income − cash expense
Cash count   : $ ___        ← physically counted
Over / Lost  : $ ___        ← cash count − expected  (Over = surplus, Lost = short)
```
- ABA money never touches the cash drawer reconciliation (bank-app, tracked separately).
- **FX margin is BY DESIGN:** peg is 4000 riel = $1, but $1 usually buys a bit more than 4000 riel. Staff are encouraged to pay local riel expenses, so the float more often than not ends with a small surplus. **A small "Over" is EXPECTED and benign — never flag it.** Real signals = "Lost"/shortfall and sales dropping.

**GM behaviour (owner-gated — same pattern as concern cards):**
- GM parses each report, recomputes the drawer math (600 + cash in − cash out), catches staff arithmetic slips (e.g. May 27 was off by 10¢) and format breaks.
- For NOW: GM reports computed errors + anomalies **to the OWNER privately only.** Owner reviews daily, we tune over the terminal. GM does **NOT** tell staff about calc errors until owner explicitly says "GM can now inform them."
- Also wanted: daily/weekly digest (sales, expenses, cumulative Over/Lost trend) + anomaly flags (Lost over threshold, sales drop).

**PENDING DECISIONS (discuss with owner over terminal — remind every session until resolved):**
1. **Overexpense carryover** — OPEN (session 25: owner wants to "think of something" — REMIND next session). Current practice: when a day's cash out > cash in, the deficit is carried into the next day as an expense taken from the $600 float. Owner wants a cleaner model. Opus to propose options when owner is ready.
2. **Float restoration** — ANSWERED (session 25): owner normally NEVER tops up the float except in extreme cases. The drawer "tops itself" back toward $600 from cash income most days (because of the 4000=$1 FX margin → daily small surplus). So: do NOT model a top-up source; the float self-restores from the FX-margin surplus. Only an extreme/unusual shortfall would involve a manual top-up. Tied to #1.
3. **Thresholds** — ANSWERED (session 25) + BUILT & LIVE (session 26): flag "Lost" > $2 (config.GM_LOST_FLAG_THRESHOLD). _maybe_ask_lost posts "Cash short by $X... does anyone know why?" with the FX framing (4000 riel=$1 so drawer should run a little OVER), gated by report_corrections_to_staff, opens a 'cash_lost' clarification on the ladder. finance.lost_exceeds() pure helper. Sales-drop % still TBD after more baselining.
4. **Shift cutoff** — ANSWERED (session 25): confirmed. Mid-report ~16:00 = day-shift handover cutoff. night ≈ final − mid uses the 16:00 boundary.
5. **Dedup prerequisite** — DONE (session 26). It was a ONE-TIME overlap on 2026-05-27 only (Telethon listener initial capture coincided with GM bot go-live on REPORT); zero dup groups after 2026-05-28, so only one collector writes REPORT now — NOT an ongoing leak. Cleaned REPORT ops_messages 88→81 rows (7 dup pairs removed), 0 dup groups left, 0 orphaned gm_daily_reports pointers. Reusable helper shared.database.dedupe_ops_messages(chat_id, prefer_message_ids, dry_run) + dedup_keeper (pure, prefers gm_daily_reports-referenced id else min id) + gm_daily_report_message_ids. 5 tests test_dedup.py. Re-run for other chats if a future listener/bot overlap recurs.
6. **Go-live switch** — DONE 2026-05-31: gm_state report_corrections_to_staff='true'. GM now posts worked-out math corrections IN-GROUP (tagging the report) and opens a clarification so the ladder records staff reasons.

---


---

## Supervisors/Management Lateness·AL·Tagging — full spec

## Supervisors / Management — Lateness, AL & Tagging (owner spec, session 25)
> Build spec from owner. Tagging foundation DONE; lateness ladder + AL engine PENDING build.

**Staff tagging convention (GLOBAL — applies to every GM tag everywhere):**
- When the GM tags a staff member, show the name WE CALL them by next to the account tag.
- EXCEPTION: if the call-name already matches the account display name (ignoring case/punctuation/emoji), show only the tag.
- DONE & GLOBAL: config.STAFF_CALL_NAME (display→nickname, 2026-05-27 roll-call) + config.call_name_for() + config.display_for_call_name() (reverse) + gm_bot/mentions.py (format_mention / mention) producing HTML `tg://user?id=<uid>` inline mentions (pings without a @username; send parse_mode=HTML). bot._staff_mention(name,uid) is the canonical resolver — resolves uid via gm_get_staff_uid (latest sender_id in ops_messages) or the reverse call-name map. USE _staff_mention FOR EVERY GM TAG OF A STAFF MEMBER, not just lateness (owner instruction, session 26). Audited: lateness is currently the only pinging path; no other inline-mention code exists. 9 tests test_mentions.py.

**Lateness / pay-back ladder (Supervisors + Management) — BUILT & LIVE (session 26):**
- shared/ai_client.py: detect_lateness_report (Haiku) → {is_lateness_report, late_person, payback_day, confidence}; extract_payback_day (Haiku) for replies. Both fail safe.
- gm_bot/lateness.py: PURE ladder logic decide_lateness_action (awaiting_payback 30min→ask_group; group_asked 24h→escalate) + text builders. 10 tests test_lateness.py.
- shared/database.py: gm_lateness_cases table + init_gm_lateness_db (wired in run_gm_bot.py) + create/get_open/get_open_in_chat/mark_group_asked/resolve/escalate + gm_get_staff_uid.
- gm_bot/bot.py: _handle_lateness (live, Supervisors+Management) = free pre-gate (len + ATTENDANCE_KW) → Haiku detect (conf≥0.55) → if payback day given, log resolved; else open case + ask senior (tagged). Resolution: a reply to the case msg or GM question with a payback day (extract_payback_day) → resolved. _lateness_ladder_job every 120s drives ask_group/escalate. Staged-model design exactly per owner: logic owns timers, Haiku reads, Sonnet reserved (not needed here), Opus for future weekly digest.
- Tagging: all tags via _staff_mention (call-name + ping, drops call-name when == account name).

**Annual Leave (AL) tracking — PENDING build (engine now, seed later):**
- Staff announce off/AL → GM deducts from their AL leftover balance.
- Accrual: every new month each staff +1.5 days.
- New-staff rule (CONFIRMED session 25 — arrears): accrual is credited in arrears. A full calendar month worked earns 1.5, credited on the 1st of the NEXT month. Mid-month start → start month is partial (earns 0); the month immediately following the start also shows 0 (they are earning it); the first 1.5 lands the month after the first FULL month. Example: start Mar 15 → Mar 0, Apr full → +1.5 credited May 1. (Existing/active staff: +1.5 on the 1st of every month.)
- Build schema + accrual/deduction logic + a balance command NOW, but DO NOT start counting until owner fills current AL balances and says "begin counting from today."
- REMIND OWNER: fill current AL balances.
- Align with existing attendance memory [[gm-attendance-policies]]: short-notice AL ok if rare, vague "off tomorrow" → GM asks "Is this AL?", sudden sick full-day → suggest 0.5 AL + half-day, all notices must be BEFORE shift start (else ask for screenshot of when staff told their senior).

**Hiring papers + Khmer refinement workflow (owner, session 25 — re #7/#12):**
- Owner will send more hiring questionnaire papers. GM/Opus generates ALL outputs (replies, analysis, targeted messages, salaries). Owner + ChatGPT review/judge → corrections saved into GM "knowledge" (examples store). Over time, accumulated approved examples refine the Khmer output AND every GM output. This is the path that eventually unblocks Khmer (#12) — manual-approved examples become the training set, not auto-generated Khmer.

---


---

## Staff Registry / Ex-staff / Paperless stock — full spec

## Staff Registry + Ex-Staff Offboarding + Paperless /stock (owner spec, session 26 — PENDING)
> Shared foundation: a STAFF REGISTRY with status. Both features below sit on it. Build registry once.

**STAFF REGISTRY (foundation):** one record per person — canonical name, call-name, aliases, telegram
user_id(s), status (active | ex_staff), groups seen, joined/left dates. Ties together the existing alias +
call-name maps, lateness, AL/leave, points, tagging.

**EX-STAFF OFFBOARDING (owner priority, session 26):** owner tells GM "X no longer works here" → mark
ex_staff in registry. Effects: (1) loses ALL staff privileges; (2) historical data KEPT (becomes
history-only); (3) no bot ENGAGES them — GM (and internal bots) ignore an ex-staff/non-staff sender;
(4) removed from ALL groups, OR GM reports which groups they're still in so owner removes them.
GM only replies to STAFF (not non-staff, not ex-staff). DECISIONS (owner, session 26): (1) IDENTIFY: owner
just messages GM that they left. PLUS PROACTIVE — when a known staff member LEAVES an internal group, GM
DMs owner: "did X leave the company? they left [group(s)]". (2) GROUP REMOVAL: BOTH — auto-remove where
the bot has rights + report the rest. (3) ENGAGE-SCOPE: GM + all INTERNAL groups only (retail/B2B keep
serving customers, who aren't staff). (4) NO Telegram-level blocking (not needed). Detect group-leaves via
GM bot left_chat_member events (covers internal groups) + Telethon. Verify bot admin rights for auto-remove
at build. REGISTRY SEED: from existing STAFF_CALL_NAME/STAFF_ALIAS_MAP (~30 known) as 'active'; owner
prunes leavers via the ex-staff flow.
BUILT & LIVE (session 26): staff_registry seeded (36 people, 33 with telegram ids) + helpers. /exstaff
<name> OR owner plain-language DM ('X no longer works here') -> confirm card (shows which internal groups
they're in) -> mark ex_staff (history kept) + ban from internal groups WHERE BOT CAN + report rest. Multi-
match -> pick buttons. Proactive: known active staff leaving an internal group (left_chat_member) -> GM
DMs owner with the same confirm. ⚠️ AUTO-REMOVAL OFF: GM bot (@twb_gm_bot 8827684951) is only a MEMBER
(not admin) in all 5 internal groups, so it CANNOT kick — currently marks ex + REPORTS groups for manual
removal. TO ENABLE (owner chose listener route): CHECKED session 26 — listener account TheWineBakery24PP is also
NOT admin (admin=False, ban_users=False in Stock Checks/COMMS/REPORT; Supervisors/Management are basic-
group ids needing different lookup). So NEITHER account can kick yet. OWNER ACTION NEEDED: promote
TheWineBakery24PP to admin with 'Ban users' in the 5 internal groups. THEN build the removal QUEUE (GM bot
enqueues -> listener processes via Telethon kick -> reports). Until promoted, ex-staff stays in mark+report
mode (works). NOTE for build: Telethon entity for basic groups (Supervisors -4980513319, Management
-865916135) needs PeerChat/dialog resolution, not raw get_entity. 'No bot engages ex-staff' gate
(staff_get_by_uid/active_uids) ready; apply to future /stock + interactive flows.

**PAPERLESS /stock OVERHAUL (owner spec, session 26):** staff-only /stock command (GM ignores non/ex-staff)
→ category buttons → item buttons → enter counts. Can add new stock → owner gets a PRIVATE message of the
addition (to confirm unit+min). Later: award staff POINTS for doing checks (+ other checks). Counts flow
straight into stock_counts (no more paper / 'almost out' report). My ideas to make it easier: pre-fill last
counts (only change what moved); show UNIT IN BRACKETS per item (kills unit confusion); 'same as
yesterday' shortcut; only prompt items that move (weekly full audit); photo fallback (vision job reads the
sheet when rushed); add-new-item -> pending -> owner confirms; implausible-entry validation; remind the
usual checker. Replaces the photo-sheet vision flow over time (keep vision as fallback).

**STOCK UNIT MISMATCH lesson (session 26):** the sheet's MIN column mixes units vs how staff COUNT
(min 'per egg/per kg/per piece' but they count racks/blocks/packs). So the spec min CANNOT be the order
trigger. Readjusted 7 items to count-unit (President butter 50pc->2 packs, plastics 10->1). Right long-term
fix: bot LEARNS each item's reorder level from the numbers staff write (calibrated by 'almost out'),
in their own count-unit; unit brackets on names lock it down. UNITS NOW CONFIRMED (session 26): Pilot
butter=kg (10 is genuinely LOW vs 25), Red Velvet=kg (low), Corn Powder=kg (low), Eggs=per egg, White/Red
Sauce=pots (1.5), Homemade Jam=jars. All 50 items now have unit + min in the staff counting unit.

---


---

## Delivery System (WOC DELIVERY PICTURES) — design (SHELVED session 26, pilot validated)
> STATUS: SHELVED by owner (parked, not abandoned). Design + pilot findings below; resume when owner asks.
> PILOT FINDINGS (80 photos downloaded, 22 read by Claude-on-Max at $0 API, then ALL pilot photos+scripts
> DELETED from server+local for PII hygiene):
> - Extraction WORKS well. 3 platforms, each distinguishable: Foodpanda (USD, #52xx/#8xxx, pink panda),
>   GrabFood (RIEL, GF-xxx, green, shows Customer+Driver), E-GetS (#N).
> - DRIVER EXCLUSION confirmed: Grab app explicitly labels "Customer:" vs "Driver:" with both numbers →
>   exclude driver by label (e.g. excluded Leang Panharith, Ros Chanthea).
> - DEVICE-vs-TICKET cross-check corrects misreads (Mali→Matt, Buonn→Bunna, $4.50→$3.50). RULE: device
>   screen is PRIMARY, dedup by order #, tickets/food confirm. Same order appears 2-3× (device+ticket+food).
> - Item modifiers captured ("No Tomato/No Raw Onion") for the wrong-food check. Kitchen tickets show ✓ ticks.
> - 6 brands seen (Café Wine O'clock, Burger 50/50, Paris Croissants, The Wine Bakery, Pasta House, +E-GetS).
>   Foreign customers exist (+63 PH, +44 UK) — phone-as-ID still holds.
> - ⚠️ UNRESOLVED PRIVACY/LEGAL FLAG (decide before building any customer-contact DB): Grab app states
>   verbatim its numbers "can only be used for confirming changes to an order. Saving them or using them for
>   any other reasons will violate privacy laws and your contract with Grab." Foodpanda likely similar.
> - COST: ~$0.004/photo Haiku, ~$0.011/photo Sonnet; 22-photo table ≈ $0.28 if API. Full year (64,919) naive
>   ~$750-850, but dedup-by-order (extract once per order, -40-60% Sonnet) + food-only→Haiku-only →
>   realistic ~$400-600. Measure real cost-per-order with a true ~50-photo API batch before any full run.
> - WOC scale: chat_id -715759659, 64,919 photos last 365d. Telethon download works (stop listener ~30s,
>   run via /root/venv/bin/python with PYTHONPATH=/root/TWBshop, restart — resumes clean).

> The "Delivery System": mine the WOC delivery-photo archive into structured business data.
> Built the wise way: cheap EXTRACTION (metered API, automated) → structured tables → expensive
> SYNTHESIS (Opus-on-subscription = Claude-in-terminal, over rows not raw photos). Never loop the
> archive through bot API. Same pattern feeds the Knowledge Brief.

**Scale (measured session 26):** WOC DELIVERY PICTURES chat_id = **-715759659**. 120,226 photos total
(range 2022→now); **64,919 in the last 365 days** (180d=35,015; 90d=18,718). Server: 40G free / 48G.
**Window to process = last 365 days** (owner: closest to current two-ticket double-check standard;
older data = weaker past habits, skip).

**Owner decisions (session 26):** (1) process last 1 year, newest. (2) Take ALL customer numbers
(exclude drivers by logic). (3) Storage = rolling download→extract→DELETE, batch-by-batch, ~1-month
auto-purge (full year ≈16GB would fit but tight; rolling keeps peak ~1-2GB). (4) Start Phase 0+1.

**COST REALITY (the real budget — NOT Claude Max hours):** the 65k-photo vision extraction runs on the
ANTHROPIC API KEY as a checkpointed background batch (NOT through Claude Max terminal sessions). Rough
full-year estimate: Haiku classify 65k (~$80) + Sonnet extract ~60% tickets/devices (~$400) + Opus on a
SAMPLED few-thousand hard cases (~$250) ≈ **$500-800 API spend**, hours-to-a-day runtime. Claude Max
(terminal) is only for building code + synthesis over distilled rows — light, fits normal windows.
**MANDATORY PILOT FIRST:** process a random ~400-photo sample end-to-end (~$5-8) to measure
classify/extract accuracy + real cost-per-photo, extrapolate the full-year bill, and get owner approval
on the number BEFORE the full run. Pilot also tunes prompts on real photos.

**Pipeline (staged models/logic per stage):**
- Stage 0 Inventory/download/dedup — LOGIC: Telethon resumable bulk-download; SHA-256 + pHash dedup.
- Stage 1 Normalize — CV/LOGIC: EXIF auto-orient, OpenCV deskew/auto-rotate (handles non-90° angles), denoise.
- Stage 2 Classify photo — HAIKU vision: kitchen_ticket|order_ticket|device_screen|food_plate|receipt|other (skip 'other').
- Stage 3 Extract — SONNET vision: phones+name+addr+app+items+price (devices/papers), items+addons+TICKS (tickets); food components on a sample.
- Stage 4 Cross-check/judgment — LOGIC compares kitchen vs order ticks; OPUS (sampled) for blind-tick, wrong-food (e.g. "no bacon" but bacon present), food-looks-right + builds the food-appearance reference library.
- Stage 5 Aggregate — LOGIC into tables: woc_customers, woc_phone_observations, woc_orders, woc_ticket_items, woc_errors, woc_food_catalog, woc_price_history.
- Stage 6 Synthesis — OPUS-ON-SUBSCRIPTION (me, terminal): rolling food catalog+latest prices, off-menu candidates (not ordered in N months → owner confirms), customer intelligence, error/demand trends. Refreshed incrementally.
- Stage 7 Owner-in-the-loop — off-menu confirm, ambiguous customers, wrong-food disputes (gated like concern cards).

**COST MODEL — who looks, not where (owner clarified session 26):** API $ is incurred whenever the
SERVER's code looks at a photo (it calls the API key = metered $). When CLAUDE-IN-TERMINAL (me, on the
owner's Claude Max subscription) looks at a photo, there is NO extra API charge (Max already paid), but
it's bounded by the Max window + my context (~dozens of photos per session, not hundreds) and is manual/
unrepeatable. So: Max-me = piloting/tuning/learning + synthesis (free-ish, small batches); server+API =
production scale (the only practical engine for the full 64,919). PILOT PLAN (owner: use Max not API):
Stage 0 download is free (Telethon); I read ~30-40 local photos here per window at ZERO API to validate
accuracy + tune prompts; then owner decides continue-via-Max (slow, free) vs flip-to-server-API (scale).
Photos must be downloaded to local disk for me to Read them.

**Customer DB:** phone = permanent ID (names change on app, number doesn't). Customer name/number often
ALSO appears on the order ticket itself (not just the device) → cross-check (same number on ticket+device
= high confidence). DRIVER number on the device is labelled with the word "driver" nearby → LOGIC rule:
exclude any number with "driver" adjacent; we do NOT collect driver numbers for now. Driver vs customer
also = LOGIC (number recurring across many distinct orders = driver/platform → exclude; one-order context
= customer).
Normalize E.164 KH. woc_phone_observations logs every sighting+confidence+source photo for audit before
promotion. Link per customer: order history, RFM (recency/frequency/monetary → best + LAPSED customers),
favorite items, preferences/allergies ("no bacon"), delivery brand/app + area, avg spend, peak time, LTV,
complaint history, name variants. Export later as phone contacts "Customer — {name}".

**8 development ideas (the "Delivery System" roadmap, owner approved to track):**
1. Per-staff error scorecards (wrong input / blind-tick / error types + trend) → feeds GM recognition/correction.
2. Demand forecasting (item velocity by day/time) → prep planning + waste reduction.
3. Plating/portion drift QC vs reference library.
4. Price-integrity check (same item sold at inconsistent prices).
5. Menu lifecycle (new items appear, off-menu detection, seasonality).
6. Leakage/fraud signal (food photographed but no matching POS/report entry).
7. Channel timeline (which delivery apps/companies over time → which channels are profitable).
8. Reactivation campaigns (lapsed-customer lists + their favorite item).

**Build order:** Phase 0 download+dedup → Phase 1 classify+phones+Customer DB (fastest payoff: reactivation)
→ Phase 2 ticket extract → food catalog + price history + off-menu list → Phase 3 cross-check/wrong-food/
scorecards (Opus sampled) → Phase 4 fold into Knowledge Brief. **START: Phase 0+1 after the pilot.**

**Knowledge Brief (the big one) — same method, all groups:** apply distill→synthesize to ALL operational
groups (3,619 chats, prioritized by importance), not just WOC/REPORT: cheap classify → targeted extract →
Opus-on-subscription folds distilled rows into a rolling living brief incrementally. Never re-read raw
archive through bot API. WOC structured tables are the first big input to the brief.

---


---

## Private-DM Attendance Overhaul (AL + Lateness + Live-Location) — owner spec session 26
> ⏸️ PAUSED (session 27): owner is planning MORE for this — DO NOT build flows until owner returns.
> SAVED STATE: full design in docs/ATTENDANCE_SYSTEM_MAP.md + docs/ATTENDANCE_SYSTEM_DETAILED.md (every step/
> branch/edge/message). CSV importer DONE (import_staff_schedule_csv) — registry rebuilt from owner CSV: 35
> active (29 TWB/6 Delis), 5 seniors, 6 ex-staff, schedules+expertise+5 planned ALs loaded. NEXT when resumed:
> live-location check-in (which also BINDS each person's real uid on first DM — current telegram_ids are
> seed-guessed from display names, imperfect for repeated names like 'Pisey') -> lateness -> AL approval ->
> group redirect -> understand-without-reply + 👍. Coverage analysis built (gm_bot/attendance.py available_staff).
> REPLACES the group-based lateness ladder + leave-questioning (both SILENCED:
> config.GM_ATTENDANCE_GROUP_ACTIVE=False). All attendance now happens in PRIVATE DM with the GM.
> If anyone posts AL/lateness in a GROUP -> GM replies "Please tell {name} to message me directly."

**WHY (2 photos session 26):** group lateness/leave ladder didn't understand non-threaded replies ->
re-asked + nudged + threatened escalation repeatedly -> spammed Supervisors, looked broken. Root cause:
resolution required a Telegram threaded reply. Fix = understand plain messages everywhere + 👍 ack + go private.

**GLOBAL FIXES (apply to ALL cases, not just attendance):**
- UNDERSTAND-WITHOUT-REPLY: resolve open lateness/AL/clarifications from a plain message (no threaded
  reply needed) — Haiku extract + Sonnet judge while a case is open in that chat.
- 👍 ACK: when GM registers any business reply that is NOT a concern, react 👍 so staff know they were heard.
  If the reply IS a problem/concern -> NO 👍 (so staff don't think it's fine). 👍 never replaces the GM's
  actual reply/escalation — it's only an acknowledgement.

**AL flow (private):** staff DM GM the AL days/hours + reason (no reason -> GM asks). >=2 of the chosen
seniors must approve. GM DMs each senior privately: ✅approve/❌not-approve buttons + the request + an
AVAILABILITY PICTURE — per AL day/window, the staff working those hours that day (EXCLUDING anyone on
day-off OR on AL themselves that day — don't list people who aren't there). On 2 approvals: the senior
messages collapse and a fresh message to all seniors restates details tagging who approved/not. Approved ->
Supervisors group gets a plain notice of the AL days/times (NO availability, NO who-approved). Rejected ->
nothing to the group, seniors only.

**Lateness flow (private):** staff DM "late X min/hrs". GM assumes their NEXT shift unless the shift already
started (then: "ok, but please tell us well before your start time next time"). GM posts the lateness to
the SUPERVISORS group for that shift (so others know he won't be there a while; real time confirmed when he
checks in via location). If he said e.g. 10 min late -> at 10 min past his start: "Have you arrived yet?
Share location if you did." No approval. Frequency reminders; negative points LATER.

**Live-location attendance (WHOLE shift):** staff share LIVE location with GM privately as their time-
attendance. Geofence 200m from TWB (GPS buffer). NOT for Delis staff yet. If live location goes off ->
"Did you leave work early? If not, share location again." Allowance: 30 min total outside per shift (shop
errands/food) — once exceeded -> "What are you doing outside the shop?" (10min + 20min = ask). ALSO: any
staff who hasn't checked in by their start time -> GM reminds them to check in (in case they forgot).

**REGISTRY SOURCE LESSON (session 26):** staff_registry was wrongly seeded from CONVERSATION history
(ops_messages) -> dragged in ex-staff + a duplicate account (Sao Visal/Sao Visal cv). FIX: the owner's
filled CSV is the source of truth. Marked 6 ex-staff (Buy Vong Sakada, Morn Putheavy, Ret Det, Sot Somnang,
Von Vichhka, Sao Visal cv) -> 30 active. When the final CSV is imported, REBUILD registry from it (anyone
not in CSV -> ex_staff; new people -> add). Refreshed CSV: C:\Users\Papa\Downloads\staff_schedule_REFRESHED.csv
**Facts from CSV (session 26):** Seniors (Y): Chim Samphass, Met Solina, Tengmarim Chaktopor, Phal Rath,
Hong Vannary — BUT Met Solina resigns 5 Jun 2026 (pick a replacement senior). Tyty (Boss TT) = CO-OWNER,
exempt from all rules. DELIS staff (separate location/TEAM, excluded from GM for now, AL TBD): Chea Seavluy,
Cheata Sok (Delis supervisor), Khil Chantra, Sopheak Nalmonyboth, Chheng Minea, Ouk Sokchea. New TWB staff
not in any group yet: Yorng Lyhouy, Chuch Pisey. Many TWB shifts are OVERNIGHT (9pm-6am etc.) — attendance
overlaps() handles overnight. Day-offs still to fill. DELIS = different team; if ever allowed to DM the GM,
treat as a separate team (its own seniors/availability pool), don't mix with TWB.

**Foundation BUILT (session 26):** gm_bot/attendance.py (pure: haversine, in_work_zone 200m, to_min,
overlaps incl overnight, available_staff [excludes day-off + AL], lateness_kind, outside_exceeded) — 9
tests. Schema: staff_registry +work_start/work_end/day_off/al_left/org/is_senior; al_requests, al_approvals,
lateness_records, attendance_sessions (init_attendance_db, applied to prod).
**NEEDS owner before flows can run:** fill C:\Users\Papa\Documents\staff_schedule_template.csv (work times,
day off, current AL left, TWB/Delis, SENIOR Y/N; suspected dual account flagged: Sao Visal / Sao Visal cv).
**TODO next:** CSV importer -> staff_registry schedules; then the private DM flows (AL intake+approval,
lateness intake, live-location handler + reminders, group redirect), understand-without-reply + 👍 ack.
AL accrual +1.5/mo arrears starts from the seeded al_left. Negative points later.

---


---

## Operations Intelligence System — Planned (Phase 3)

A new system to be built alongside the existing bots. Three layers:

### Layer 1 — Data Collection (build first)
- **Telethon user-account listener** runs on the server as the owner's personal Telegram account (or a dedicated staff account added to all groups). Reads full message history + streams all new messages silently into a new `messages` DB table: sender, timestamp, group_id, text, media metadata.
- **One-time historical import script** reads Telegram JSON exports (exported manually from each group via the app) into the same table. Covers all history before the listener joined.
- **Photo analysis included from day 1** — every image sent in any group gets passed to AI vision.
- Both the listener and the existing bots share the same PostgreSQL database.

### Layer 2 — AI Analysis (all 4 tiers active from day 1, owner monitors costs and tones down)
| Tier | Model | Approx cost | Job |
|------|-------|-------------|-----|
| Free | None | $0 | Keyword summaries, counts, rule-based daily reports |
| Budget | Claude Haiku | ~$0.25/M tokens in | Daily digest — who said what, complaints flagged, order mentions, photo descriptions |
| Mid | Claude Sonnet | ~$3/M tokens in | Weekly deep analysis — staff behavior patterns, tone, operational issues |
| Premium | Claude Opus | ~$15/M tokens in | Special reports — long-context reasoning across weeks of data, hiring evaluation |

Scheduled jobs send analysis results to owner's private Telegram.

### Layer 3 — Hiring / Interview Bot (build after Layer 1+2)
**Access control — token-based, invite-only:**
- Candidates first contact a separate Telegram account (human contact, not the bot) to apply
- When candidate arrives in person, owner/staff runs `/approve @username` → bot generates a one-time deep link (e.g. `t.me/yourhirebot?start=abc123`)
- Only that token works — random people get silence from the bot
- Token is single-use and expires after a timeout (e.g. 30 min if not started)

**Interview session flow:**
- Candidate taps link → interview starts immediately in private chat with the bot
- Each question sent → candidate replies → bot deletes BOTH the question and the answer from the chat immediately after recording the answer → next question appears. Chat window stays visually empty throughout.
- If candidate goes inactive (no reply for 10 min) → session expires → token burned → owner notified: "Candidate @x abandoned at question N"
- Completed or abandoned: session locked, that token never works again, no way to restart

**Evaluation:**
- AI (Sonnet or Opus) scores answers against the rubric from the questionnaire system already designed with ChatGPT
- Owner receives a scored report in private Telegram

**To provide before building:**
1. ChatGPT export ZIP: ChatGPT → avatar → Settings → Data controls → Export data → download ZIP → upload here. Claude will read `conversations.json` and extract the hiring/interview system design.
2. The questionnaire document.

### Planned Repo Structure Addition
```
ops_intelligence/
├── listener.py         ← Telethon user-account message collector
├── importer.py         ← one-time Telegram JSON export loader
├── analysis.py         ← scheduled AI analysis jobs (all 4 tiers)
└── hire_bot/
    ├── bot.py          ← interview bot handler registration
    ├── sessions.py     ← token generation, session state, expiry
    └── evaluator.py    ← AI scoring against questionnaire rubric
run_listener.py         ← entry point: python run_listener.py (systemd: twbshop-listener)
run_hire_bot.py         ← entry point: python run_hire_bot.py (systemd: twbshop-hire)
```

---


---

## Sessions 29-31 (Jun 8-10, 2026) — moved from CLAUDE.md to keep live status lean

**Session 31 (Jun 9) — HIGH-RISK guard: proven live, then hardened (owner: "I always say yes"):**
- **Proved the live hook wiring** (the session-30 resume task). The PreToolUse guard DOES fire
  (instrumented probe: invoked every call, CLAUDE_PROJECT_DIR correct — Claude runs it via Git Bash).
  BUT this session runs in a permission-BYPASS mode (a non-allowlisted `rm -rf` ran with NO prompt), so
  the guard's `permissionDecision:"ask"` was a NO-OP — `systemctl restart` etc. ran unguarded. Same
  cause as session-30's "systemctl didn't prompt." Only `exit 2` actually blocks in bypass mode (proven
  with a sentinel). My very first manual probe "failed" only because MY shell lacked CLAUDE_PROJECT_DIR
  — not a wiring bug.
- **Owner insight → design change:** owner ALWAYS approves prompts reflexively, so "ask" never protected
  them. Protection moved OFF the human rubber-stamp ONTO a hard stop. Guard now HARD-BLOCKS (exit 2)
  every HIGH-RISK match in ALL modes unless the per-action, auditable marker `#HIGHRISK-OK` is appended
  to the command (accidents/reflexes/runaways never carry it; Claude adds it only after articulating the
  risk). Dropped the mode-aware "ask" path entirely (simpler + strictly more protective for this owner).
- **Red-team caught a real gap:** the matcher missed the **PowerShell tool** — how deploys run on
  Windows (`PowerShell(ssh twbshop "...systemctl restart...")`) — so destructive PS ops sailed past.
  Added PowerShell to BOTH the settings.json matcher AND classify(). ⚠ The matcher change activates only
  NEXT session (loaded at startup); Bash is guarded live NOW (proven).
- **Verified:** live block of `systemctl restart` (did NOT run) + live allow with marker; script harness
  green across all modes (block / marker-allow / safe-allow / PowerShell block / fail-closed block /
  edit-secrets.py block); py_compile OK; settings.json valid JSON. Files: `.claude/hooks/highrisk_guard.py`,
  `.claude/settings.json`. All probe/diagnostic code removed; git clean except the two intended files.
- **STILL the real lock (NOT this guard):** the staging/local Postgres so prod creds aren't in dev
  (dated backlog, due 2026-06-30). This guard is the accident/reflex backstop, not the wall.

**Session 31 (Jun 10) — guards made UNIVERSAL (owner: "as guarded in every project as you are here"):**
- **Why:** only TWBshop was guarded; POSbusiness/Personal/future projects + the global `~/.claude` had
  NO hook. Owner wants every project, every machine, as protected.
- **Global install + sync:** `bootstrap.py::_ensure_global_guards()` (list-driven via `GLOBAL_GUARDS`)
  copies each repo guard → `~/.claude/hooks/` and merges a PreToolUse entry into `~/.claude/settings.json`
  — idempotent (refreshes, never duplicates), non-destructive (preserves theme/model + other hooks,
  `.bak` first), and BEST-EFFORT (any failure swallowed so it can never break a pull). Runs on every
  pull via `--sync`, so every machine self-installs on its next TWBshop pull; every project on that
  machine inherits it. Repo is the single source of truth.
- **Guard 2 — secret-leak block** (`.claude/hooks/secret_guard.py`): scans the text being WRITTEN
  (content/new_string/command, never removed text) for live key/token/private-key/DB-URL patterns and
  hard-blocks them landing anywhere but secrets.py/.env. 12/12 acceptance (incl. secrets.py allowed,
  secret-REMOVAL allowed, marker override, fail-closed). Same `#HIGHRISK-OK` override.
- **Marker protocol documented in the global laws** (`~/.claude/CLAUDE.md` → "How to Behave"), pushed
  via `bootstrap.py --push-global` so every session/machine knows: HIGH-RISK hard-blocks; STOP, say why,
  append `#HIGHRISK-OK`. Framed as a mechanical backstop, NOT a replacement for the precision standard.
- **Verified:** both guards registered globally (2 PreToolUse entries, theme/model preserved); both
  enforce standalone; bootstrap py_compile OK; idempotent over 2 runs. ⚠ Global hooks ACTIVATE on next
  session start (loaded at startup) — open sessions (incl. POSbusiness) need a restart to pick them up.
  Residual: hook command uses bare `python` (fine on Windows-on-PATH; revisit if a Mac/Linux dev machine
  is added). NEXT (owner, one at a time): guardrail 2 = "tests must pass before done" gate.

**Session 30 (Jun 9) — OT-end checkout: midnight worry closed (kept GPS, rejected the button):**
- Owner floated replacing the GPS OT-end checkout with a "senior (+ staff) confirm OT done" button to
  dodge the midnight edge. Thought it human-side: a staff SELF-confirm is EXPLOITABLE (OT banks at
  ACCEPT → tap-done-and-leave-early keeps full pay); busy senior / hasty staff just don't tap → never
  verified. GPS (must be physically in-zone at OT-end) is the STRONGER anti-fake → kept GPS.
- Fixed the real wart instead: `ot_now_ends_today` → **`ot_now_end_times(today, tz)`** returns the
  LATEST OT-end as a tz-aware DATETIME (queries today+yesterday grants → an overnight OT granted
  yesterday that ends after midnight IS included). `_checkin_scheduler_job` fires at real
  elapsed-minute offsets 0/10/20/40 from that datetime → correct ACROSS MIDNIGHT, no minute-of-day
  wrap, no `end_min>=1440` skip. 'already out' is now a datetime compare. Suite 402 green.
- FLAGGED, NOT solved by this (owner to decide): "leave early, keep OT pay" is a bank-on-ACCEPT
  question, fixable only by banking OT on COMPLETION — checkout UI can't fix it. On the discuss list.
- Advisor rule "SIMPLER-PATH / COST-HONESTY" written as a self-contained ~7-line block (a How-to-Behave
  habit, NOT a 7th law); handed to owner to forward — NOT yet added to standing rules (preview-first).

**Session 30 (Jun 9) — LIVE STAFF ENTRY for attendance (gated OFF):**
- **What:** a real ACTIVE TWB staffer can now open their OWN attendance menu (Check-in / Late / About
  Work / About Me → AL, Special Leave, day-off swap, OT, My schedule) and fire the REAL submit_* as
  themselves. Same menus/callbacks/submit_* as the owner /test shell — NO behavior fork (Rule 1).
- **Entry:** non-owner /start or private text → if `attendance_live` AND active TWB staff →
  `attendance_ui.open_live_menu` (persona LOCKED to self; "🎭 Switch persona" hidden; pick/persona
  callbacks refused). Else → roll-call (unchanged). Check-in & late→payback-on-arrival stay on the
  already-live location path (`_handle_staff_location`).
- **Reason capture:** flow_state (DB, restart-safe) per the doc — `flow_save(uid,"att_pending",…)`;
  the staffer's next text completes the flow. Owner test path still uses user_data (unchanged).
- **Unified dispatcher:** `_att_test_dispatch` → `_att_dispatch(update, ctx, pend, *, live)`. live=True
  acts as self, requester_uid=self, routes to real recipients; live=False = owner test (routed to
  owner, is_test). **LIVE late = declare-only** (heads-up); the payback debt+picker appear on arrival
  via live location. TEST collapses declare+arrival (so the owner can test booking) — per the doc note.
- **Gating/safety:** everything behind `_attendance_live()` (still OFF) — module messages no one but
  the owner until go-live. Module docstring safety-contract updated to the live+test contract.
- **Verified:** suite 379 green (+10 new in tests/test_attendance_live_entry.py — persona self-lock,
  menu hides switch, armed gating, flow_state routing, LIVE late declare-only vs TEST collapse,
  unknown-uid rejected). py_compile OK. Real-staff DELIVERY provable only at go-live (single account +
  gate OFF) — the documented plan (owner role-play test in test mode covers the message shapes).
- Khmer WIRED into all 11 live reason/'go' prompts (bilingual EN·KH), mirroring the file's already-
  approved terms (បងៗ / ច្បាប់រៀបការ / មរណភាពគ្រួសារ / ប្រពន្ធសម្រាលកូន / ប្តូរថ្ងៃឈប់ / ទីតាំងផ្ទាល់);
  Latin kept for go/AL/OT/numbers. Real callback path proves the %-formatted ones (late/marriage/famf/
  ot) format without error. Owner should still eyeball via ChatGPT before go-live (my drafts, not yet
  owner-reviewed). The dispatcher confirmations were already bilingual.

**Session 30 (Jun 9) — Part 3: end-of-OT re-checkout (simpler path, owner-approved):**
- A Now-OT extends the shift → the checkout fires at the **LATEST OT-end** (a 2nd OT just moves the
  end), reusing the same message+nudges, and **overwrites the single `checked_out_at`** (no new
  state — `att_check_out` already overwrites; "final departure = OT end"). Now-OT is now stamped
  `when_date=today` so it's findable; `database.ot_now_ends_today()` returns the latest end per staff;
  the scheduler suppresses the plain shift-end checkout while OT runs, then fires the OT-end one
  (derives "already out" from `checked_out_at >= end`). Suite 402.
- **UPDATE (later same session): the overnight edge is now FIXED** — `ot_now_end_times` is datetime-based
  (see the midnight-safe note above), so cross-midnight OT-ends fire correctly. Remaining: overlapping-OT
  double-bank is a separate OT-pay concern. Live firing is scheduler-driven (gated by attendance_live) →
  provable only at go-live; logic unit-tested (`ot_now_end_times`).

**Session 30 (Jun 9) — checkout window 60-min + nudges +10/+20/+40 (owner):**
- Check-out capture window 90→**60 min**; nudge ("Did you leave early? share location") now fires at
  **+10/+20/+40** (was just +10) — `staff_day_events` raw list. Suppressed once checked out. test_day_events
  updated. Suite 401. (Part 3 — OT-end re-checkout — next.)

**Session 30 (Jun 9) — late arrival = ONE combined message + 3-outcome test sim:**
- Live late arrival is now ONE message: `_offer_payback(late_min=…)` combines the check-in verdict
  ("X min late, counts as pay-back") WITH the picker, so reason+action can't be read separately.
- TEST simulate-arrival now offers 3 buttons (they declared late but may arrive otherwise): **early >5**
  (+points verdict), **on-time ±5** (free, verdict only), **late >5** (combined verdict+picker) — each
  running the real verdict (5-min grace). `_late_simarr_callback` reworked.
- ⚠ FIXED 2 LATENT NameErrors: `cmd_start` + `_private_text_router` used `attendance_ui` without a
  local import (module imports it locally everywhere) — would've crashed at GO-LIVE when a live
  staffer texts/Starts. Now import locally. Suite 401 green.

**Session 30 (Jun 9) — late TEST: simulate-arrival button (mirrors live):**
- TEST late no longer auto-collapses to the payback picker. It now sends the heads-up + a
  "📍 Simulate arrival — shared correct live location" button (`att:simarr:{persona}:{mins}`,
  `_late_simarr_callback`, test-only/owner-only) → tapping fires the real arrival payback (debt +
  picker), exactly mirroring the live declare→arrival split. LIVE late unchanged. Suite 400 green.

**Session 30 (Jun 9) — audit fixes A+B+D:**
- D: deleted dead **Emergency AL** code (emergency_screen/dates + att:em branch) — unreachable since
  the owner removed it from the menu; confirmed SEPARATE from short-notice AL (kept).
- A: fixed STALE dry-run/walkthrough previews — sick "3-day→payback" → pay-back-from-declaration +
  2-day papers cancel + nightly return-check (catalogue4 ⑨/⑦/②, walkthrough end-line); OT owner-
  approve-gate → reject-only/silence-approval/staff-consent-first (catalogue6 ④/⑧/⑪, ot_owner_card).
- B: owner test-coaching "approve as two seniors" → "(2; or 1 if the requester is a senior)".
- C RESOLVED (owner): OT ⚡ Now shows "starts at shift end" AND a start pick ON PURPOSE — so staff
  read "now" as the clean shift-end (4pm), not the current clock time (4:36pm). Do NOT "fix" it.
  Suite 399 green.

**Session 30 (Jun 9) — death/birth confirm prompts: warm + direct (owner):**
- Dropped "no reason needed" and the flat "Sends condolences/congratulations and notifies the
  Supervisors" descriptions (those were MY wording, not ChatGPT). Death now leads "🤍 So sorry for
  your loss" + leave (N days) + date; birth leads "👶 Congratulations!" + leave (2 days) + date.
- (Sick prompts famf/mecant still carry mild "notifies the Supervisors / opens a sick case" meta —
  not yet reworded; flagged.)

**Session 30 (Jun 9) — marriage = no reason (confirm button):**
- Marriage no longer asks for a typed reason (it's their own wedding). Now a `_confirm_prompt`:
  "Marriage leave (N days) · Date: from → to · If you need more days you can request AL" + ✅ I confirm
  (→ att:go → submits to seniors). Dispatch submits reason "Marriage leave" (no appended text).
- Suite 399 green.

**Session 30 (Jun 9) — coverage-gap Supervisors FYIs (round 2):**
- Added 4 more group FYIs: **sick papers accepted** ("X on covered sick leave for N days"), **OT
  cancelled by owner** (only if it was confirmed/banked/booked), **no-show** (informational — decided
  the NEXT-MORNING 08:00 sweep over yesterday, so it's after-the-fact, not "please cover"), **AL day
  cancelled** ("X cancelled AL on D — back to work"). Now the group hears every coverage-relevant event.
  Still silent (intentionally): AL/swap REJECTED (no schedule change), sick no-papers-final (internal).
- Suite 399 green.

**Session 30 (Jun 9) — Supervisors-group FYIs + sick return-check buttons:**
- Added Supervisors FYIs: **own sick declared** ("X out sick today") and **OT confirmed** ("X on extra
  OT — window"). The light-duty "come" note now goes to the **Supervisors group** (was per-senior DMs;
  they're already in the group).
- **Sick nightly return-check now has buttons** (`att:sret:`): ✅ coming tomorrow / 🛌 still resting /
  ⏰ coming in today at… (hour picker) → each posts a Supervisors FYI (returns tomorrow / not back /
  coming today at HH). `_sick_return_callback` + `_sick_return_kb` + `_sret_time_kb`. Wired into the
  nightly job + the test 'skip' preview.
- Suite 399 green.

**Session 30 (Jun 9) — senior self-AL/swap needs only 1 approval:**
- `al.approvals_needed(is_senior)` → 1 for a senior's own AL/swap, 2 for regular staff. `quorum_reached`
  /`quorum_rejected` take a `needed` arg. Wired into `_al_approval_callback` + `_swap_senior_callback`
  (needed derived from the REQUESTER's is_senior). Suite 399 green.

**Session 30 (Jun 9) — paperless-sick model corrected (owner): pay-back from declaration:**
- RULE (owner): paperless sick is **pay-back from the moment they declare** (any length); accepted
  doctor's papers within **2 days** (PAPERS_GRACE_DAYS 3→2) CANCEL it; after 2 days it's final.
- `_att_dispatch` sick_me now creates the pay-back debt at declaration (`payback_add_debt`, missed
  shift). Papers are mentioned ONCE at declaration; nudges NEVER mention papers or pay-back (they
  know). Owner Accept (cov:Xd) within the window → `_wipe_sick_payback` cancels the debt; Skip → it
  stands ("✓ Noted"). The deadline job no longer CREATES debt — it sends the nightly **return check**
  ("coming in tomorrow?", `_SICK_RETURN_CHECK`) while open, finalizes (`no_papers`) after the 2-day
  window. Test 'skip' previews the return-check so the flow continues.
- Suite 398 green.

**Session 30 (Jun 9) — tap-to-confirm + bilingual Back:**
- No-reason flows (own-sick, family-sick, family-death ×2, wife-birth) now show a **"✅ I confirm ·
  ខ្ញុំបញ្ជាក់"** button (`att:go`) instead of asking to type 'go'. New `_confirm_prompt` + bot
  `_att_go_callback` (owner→user_data pending, live→flow_state) fires the real submit_* via
  `_att_dispatch(reason="(confirmed)")`. `_att_dispatch` made callback-safe (no `message.text`).
- **Back button bilingual:** `_back_row` → "← Back · ត្រឡប់ក្រោយ" (applies everywhere).
- Suite 396 green (+ att:go-confirms, back-row-bilingual).

**Session 30 (Jun 9) — AL date-picker polish + day-off-aware count/span:**
- Selected dates now show **✅** (green-tick emoji) not the `✓` unicode; al_screen header trimmed to
  "You have X AL days left" (Eng+Kh) — dropped the "Choose dates (tap to ✓…)" line.
- **Day-off is never charged AL + from→to span:** `al.al_charged_days` / `al.al_span_label` /
  `al_day_count(day_off=…, non_working=…)`. Picking 3 days where one is the day off = **2 AL**; leave
  shows "Tue 23/06 → Thu 25/06", bridging the day off whether or not tapped. A genuine WORKING-day gap
  does NOT bridge.
- **Span bridges ANY absence, not just the weekly day-off** (owner): `non_working` set from new
  `database.staff_absent_dates(staff_id)` = approved AL + special-leave spans + swap day-off overrides.
  So a gap that's another AL/leave bridges into one from→to span (and isn't re-charged).
- **PUBLIC-HOLIDAY placeholder wired (empty):** `database.public_holidays()` reads gm_state
  ['public_holidays'] (JSON list, empty default) and is folded into `staff_absent_dates`. Add dates
  via **/holiday add YYYY-MM-DD** (owner/Tyty) — they then auto-bridge AL spans and cost NO AL / NO
  points, no code change. `set_public_holidays()` + `/holiday` (list/add/del) shipped. (Per-person
  paid-free grants could extend the same seam later.)
- Suite 394 green (+ al-day-off-excluded-and-span, updated summary test).

**Session 30 (Jun 9) — AL card redesign + edit-in-place on decision:**
- AL senior cards are now **English-only, BOLD space-separated dates** (`_al_summary`, HTML parse_mode);
  buttons English ("✅ Approve" / "❌ Not approve").
- **Decision edits the card in place** — `submit_al_request` stores each card's (chat_id, msg_id) in
  `bot_data["al_cards"][req_id]`; `_al_finalize` edits every card to "{request}…✅/❌ <verdict> by X and Y"
  and DROPS the old per-senior "Approved by X" new messages. Fallback recap if card refs lost (restart).
  Requester + Supervisors notices kept (bilingual; owner sees English via strip).
- `_att_send` now takes `parse_mode` and RETURNS the sent Message (so cards can be edited later).
- AUDIT (decision → new msg vs edit card): AL fixed. Already edit-in-place: OT yes/can't, OT reject,
  OT buyback, swap-partner, sick-papers, death-upgrade. STILL TO CONVERT (owner to decide): **swap
  SENIOR cards** (only the voter's card updates; others go stale) — best next candidate for the same
  edit-all-cards style; minor: OT owner-reject leaves the staff's pending card stale.
- Suite 391 green (+ _al_summary, _al_finalize-edits-in-place).

**Session 30 (Jun 9) — location-mix fix + swap/OT edit-in-place:**
- **LOCATION BUG (owner): DELIS staff leaked into TWB AL coverage.** `_al_availability_lines` built its
  roster from ALL active staff. Fixed → TWB only (excl Tyty). Audited every `staff_all` aggregation:
  also filtered `_seniors` (TWB only — defensive; no Delis senior today), the `/test` persona picker,
  and the dry-run sample. (The greeting/started report intentionally labels "(Delis)" — left as-is.)
  Org values are `TWB` / `DELIS`; the 4 seniors are all TWB; Tyty is TWB & not senior.
- **Swap senior cards now edit-in-place** (like AL): `_swap_partner_callback` stores card refs in
  `bot_data["swap_cards"]`; `_swap_apply` edits them all to "Day-off swap … ✅/❌ verdict" (no more
  stale non-voter cards).
- **OT owner-reject** now edits the staff's pending Yes/Can't card to "cancelled" (stored in
  `bot_data["ot_staff_card"]`) instead of leaving it stale + a new message; senior still memo'd.
- Suite 393 green (+ al-availability-excludes-Delis, swap-apply-edits-cards).

**Session 30 (Jun 9) — OT approval model = silence-is-approval (owner):**
- **OT no longer waits for owner approval.** Senior gives OT (Now or Later) → the STAFF is engaged
  IMMEDIATELY (Now = bank on the spot + buyback picker; Later = Yes/Can't ask) and the owner gets a
  **REJECT-ONLY** notice. Owner silence = approval; owner can veto until the OT START time
  (`_ot_started`); a Now grant that already banked is REVERSED on veto. Statuses: banked / staff_asked
  → booked / declined / rejected. Old pending_owner→approve gate removed.
- Files: `submit_ot_grant`, `_ot_owner_callback` (now veto-only + window check + bank reversal),
  `_ot_future_callback` (staff_asked→booked/declined), `_ot_started`, dispatcher OT confirm text.
- **OT confirmations show the real time window** (e.g. `4pm-5pm`), never "now" — `_ot_window()` (Now =
  shift-end→end; Later = date + window); used in the owner notice + the staff ask.
- **Staff consent FIRST for BOTH Now and Later:** submit_ot_grant now ASKS the staff Yes/Can't first
  (no auto-bank). NOW banks + offers buyback only in `_ot_future_callback` AFTER the staff accepts;
  LATER books. (Was: NOW auto-banked at grant without asking.)
- **Take-back ≠ payback:** earned-OT buyback slots are now at the shift EDGES (come in late / leave
  early) via new `payback.takeback_windows`, not the before/after-shift payback windows. Labeled
  🌅 in late / 🌙 leave early.
- **OWNER never gets Khmer — but ONLY in message BODIES, not the shell.** `attendance.strip_khmer()` is
  applied in `_att_send` when the recipient is the owner (test-routed previews + owner notices →
  English). The `/test` shell menus/screens STAY BILINGUAL so the owner previews exactly what staff see
  (owner corrected the scope, session 30 — do NOT strip the shell/menu). Live staff always bilingual.
- Suite 389 green (+ _ot_started, Later/Now ask-first, now-accept-banks, _ot_window, takeback_windows,
  strip_khmer).

**Session 30 (Jun 9) — /testseed + restart test-mode sync + /testmode diagnostic:**
- **/testseed [name]** (owner/Tyty): mirrors real approved ALs + open payback debts into is_test copies
  so TEST mode shows realistic data after a /testreset wipe (idempotent — clears prior test copies
  first; real rows never touched). `database.attendance_testseed()` + generic `_copy_test_rows` (schema-
  proof via information_schema). Ends the "re-seed Visal by hand each reset" loop.
- **Restart bug fixed:** `build_app` now restores `set_att_test(gm_get_state('attendance_test_mode'))`
  on boot — a restart no longer silently flips att_test_on() to False while the DB says test_mode=true
  (which made TEST mode show REAL rows instead of the is_test sandbox — likely source of earlier
  "ALs still gone in test" confusion).
- **/testmode no-confirmation: RESOLVED.** Temp debug log proved command reaches the handler (uid=owner,
  chat=private, args=['on']) and replies (sendMessage 200) after a clean restart. Earlier silence was a
  transient (process not processing updates during the overload/restart churn) — not reproduced, not a
  code bug. Debug line removed.
- **Give OT ⚡ Now picker fixed:** was listing the WHOLE roster; now only staff present right now —
  on shift OR finished < 1h ago (new `attendance_ui._present_now`, schedule-based, excludes day-off/AL-
  today). Empty → points to 📅 Later. Back from "to whom" now goes to the now/later screen.
- Suite 382 green (+ test_copy_test_rows, + test_present_now_for_ot, both DB-free).

**Session 30 (Jun 9) — precision standard + data fixes:**
- **Precision standard trimmed + sharpened (v2026-06-09-A):** 15 HARD RULES → 6 RULES (deduped, no
  teeth lost) in BOTH global ~/.claude/CLAUDE.md and project CLAUDE.md. New first-class **Rule 2 PROOF,
  NOT ECHO** — operation echo ≠ persisted state: PUSHED ≠ LIVE and WRITTEN ≠ SAVED (commit/close then
  re-read on a SEPARATE connection; RETURNING / return value / 2xx / enqueue-ack are not proof).
- **Visal AL corrected real+test:** req 17 was 9/10/12 but the 10th is his day off (Wed) → now 9/11/12
  approved (is_test=False); seeded matching test copy (req 20) + Por 240 test payback (debt 11).
- **Root cause of the "/testreset won't restore Visal's ALs" saga:** NOT a bot bug and NOT test
  isolation. My earlier inline `ssh … psycopg2.connect()` restore scripts never called commit
  (autocommit defaults off) → implicit ROLLBACK on process exit; RETURNING showed the in-txn value so
  it looked restored. The REPO write path (`shared/database.py::_db()` context manager) commits
  correctly — every bot/helper write is sound. Fix: ad-hoc DB scripts use _db() or autocommit + a
  fresh-connection readback (now Rule 2).

**Session 29 (Jun 8):**
- **DEPLOYMENT-DRIFT AUDIT (owner feared lost work):** verified ALL last-night work safe — 20 commits
  pushed, server HEAD==origin, 19 attendance tables live in prod, attendance_live=OFF, all 5 services
  running current code. Root cause of "Give OT shows no time": fixes were pushed to GitHub but the
  twbshop-gm service was never restarted. LESSON: after any gm_bot/ push, `ssh twbshop pull + systemctl
  restart twbshop-gm` — code on GitHub ≠ code running. coverage_requirements is NOT a table (hardcoded
  in coverage.window_target).
- **OT /test flow fixed:** added the missing WHEN step — 📅 Later now picks day + start-time before the
  owner card; ⚡ Now skips it (it's now). Owner card + stub show the real chosen window.
- **EVERY LADDER WALKS TO THE END (no more "Next build" dead-ends):** new generic walkthrough engine in
  attendance_ui (att:walk:{name}:{idx}) + step sequences for late→payback, AL, day-off swap, sick(me/
  family), marriage, family-death, wife-birth. Each stub has "▶️ See the rest of this flow" stepping
  through every following message (senior cards, group notices, final staff confirm) — preview only,
  gated. Personal OT view points to My schedule; dead Emergency "Later" stub removed.
- **FULL KHMER REVIEW EXPORT for ChatGPT:** C:\Users\Papa\Documents\khmer_full_review.txt — Section A =
  195 EXISTING bilingual messages (the "21" was only last-night's new strings; ~174 were already done in
  prior sessions), Section B = 61 genuine staff-facing English-only gaps (mostly the just-extended
  walkthrough lines, marked "(KH pending)"). Owner translating via ChatGPT. NEXT: regenerate the export
  after this batch to capture the new walkthrough lines; then wire Khmer into the walkthroughs.
- Suite green: 369.

### Superseded RESUME pointer (session 29 — go-live sequence)

**▶ RESUME HERE (session 29): TEST HARNESS COMPLETE — ready for the owner's single role-play test.**
All 8 flows are wired test-aware AND drivable from /test in test mode: AL · late/payback · check-in ·
Give-OT · day-off swap · sick (declare + papers) · marriage · death/birth. In /testmode on, every
flow runs the REAL submit_* code; every message (staff/senior/group) routes to the OWNER labeled
[→ role]; the owner taps the other roles' buttons (actor-override); every write is is_test-tagged;
real balances/data are NEVER touched. Commands: /testmode on|off · /teststatus · /testreset.
Mechanism: shell terminals set att_test_pending {flow, persona, picks} + prompt the reason → bot
_att_test_dispatch fires the real submit_* (no-reason flows use 'type go'). Safety: PreToolUse
HIGH-RISK guard (.claude/hooks/highrisk_guard.py, per-action ask, fail-closed) + scripts/verify_live.py
(ground-truth deploy check) installed; live hook-wiring needs a fresh-session check by the owner.
Dry-runs/walkthroughs DEMOTED to read-only previews (persona picker says trust /testmode).
NEXT: (1) owner runs the single role-play test (walk every topic, tweak wording/Khmer). (2) Then
go-live: /testreset → /testmode off → send the greeting (Documents/gm_greeting_FINAL.txt) + attach the
persistent 📋 Menu button → flip attendance_live='true' (live-location requirement waits until owner
explains it + all staff pressed Start). Design: docs/ATTENDANCE_TEST_MODE.md.
attendance_live=OFF, attendance_test_mode=OFF.

