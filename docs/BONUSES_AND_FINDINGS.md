# Bonuses & Findings — running ledger

> **Standing practice (owner, 2026-06-23):** as we build, ALWAYS append the **bonuses** (unexpected wins,
> sellable angles, leverage) and **findings** (discoveries, gotchas, decisions) here — capture everything,
> shave/improve later. This is the home; one line per item + a tag. Newest section on top.

Tags: `[ship]` shipped/true · `[idea]` worth doing, not built · `[sell]` a sellable angle · `[gotcha]`
a trap to remember · `[needs-validate]` built but unproven · `[decision]` a choice made.

---

## Session 53 — config-driven wizard · onboarding · channels · platform

### 🎁 Bonuses
- **Shadow-run as a SELLABLE feature** `[sell]` — "run the new system beside your current way risk-free, cut
  over when YOU'RE convinced." Our internal cut-over tooling → a sales line ("try it in parallel, 2 weeks").
- **Bot-IN-groups as the listener** `[ship]` — drop the Telethon user-account session; the tenant just adds
  their bot to the group and it reads. Safer (scoped), simpler, "approve a link = add the bot."
- **Bot-as-approver** `[ship]` — "Computer/AI Power" applied to approvals: the bot auto-decides on coverage
  ("approve leave only if min skill coverage still holds"), humans handle judgement calls. A differentiator.
- **The cut-over dashboard** `[ship]` — the wizard shows shadow agreement per vertical = a go-live control panel.
- **"DISCOVER don't dictate, CONFIRM don't type"** `[ship]` — the onboarding principle; turns TWB's months of
  manual setup into an afternoon. The contrast IS the pitch.
- **LIVE-FIXED-editable** `[ship]` — editing a not-yet-cut-over knob is a harmless SAVED PREFERENCE (zero live
  effect till cut-over), so a customer configures everything freely + safely.
- **Templates = a 60-second start** `[sell]` — bakery/cafe/retail presets; and sellable **industry packs**.
- **"Approve a link" everywhere** `[ship]` — `/start` deep-link (silent staff), Google OAuth (planned), the
  web check-in token. Minimise typing, maximise tap.
- **The web channel proves channel-agnostic OPERATION** `[ship]` — staff check in/out via a browser link, same
  brain as Telegram + the replay. Not just onboarding — daily use, any channel.
- **Two domains in one wizard** `[ship]` — attendance (live-mirrored) + accountant (modelled); proves the
  "total business platform," not "an attendance app."
- **Per-customer shadow + test-mode as a de-risked go-live** `[idea/sell]` — each tenant validates before cutover.

### 🔍 Findings
- ⭐ **`secrets.py` shadows the stdlib `secrets` module** `[gotcha]` — it crashed werkzeug password-hashing
  (`import secrets` → no `choice`). Worked around with hashlib pbkdf2. WILL bite any library that imports the
  stdlib `secrets`. Renaming `secrets.py` is a big change (the global rule mandates it) → work around, don't fight.
- ⭐⭐ **The whole Telegram onboarding + the web channel are BUILT but UNVALIDATED end-to-end** `[needs-validate]`
  — mock-tested, wired to no live bot, reachable only via the tunnel. Validate on a real test bot before more.
- **Check-in vertical is shadow-READY** `[ship]` — the open mismatches were stale pre-grace-port artifacts
  (reconciled). A real cut-over candidate — owner's call, NOT flipped.
- **The "PLANNED" badge conflated "not built" with "live-but-not-config-driven"** `[ship]` — fixed with a 4th
  state **LIVE-FIXED**.
- **BotFather can't be automated** (anti-abuse) `[gotcha]` → guided creation + Bot-API auto-config is the path.
- **The shift-id / interval model gives overnight + split shifts FOR FREE** `[ship]` — a 2am check-in binds to
  the prior-day shift by construction; no date confusion (owner validated).
- **deep-merge replaces lists, merges dicts** `[gotcha]` → modelled `expertise.roles` as a list for clean
  add/remove; templates/accountant config merge cleanly.
- **Wizard deploys never touch the bots** `[ship]` — empty gm/core diff verified on every deploy; a clean
  isolation guarantee (only `twbshop-wizard` restarts).
- **Secrets must live OUTSIDE the readable config** `[ship]` — `core_org_secrets`, encrypted at rest (Fernet);
  activates when `ORG_SECRET_KEY` is set. Before public: also CSRF + HTTPS + login rate-limit (W3).
- **Accountant landmines F5/F6 FIXED** (atomic claim-by-construction); **B2B F2/F3/F4 = a ready plan**
  (HIGH-RISK money, with owner at re-enable) `[ship/decision]`.

### 📌 Owner decisions still open (for review)
- Company **name** (shortlist in `docs/COMPANY_NAME_IDEAS.md`) · **cut over** check-in · **B2B re-enable** ·
  set **`ORG_SECRET_KEY`** · public hosting + W3.
