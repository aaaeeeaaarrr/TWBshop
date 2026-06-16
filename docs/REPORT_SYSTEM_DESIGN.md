# Report / Expense / Payment System — Design Record (brainstorm, NOT built yet)

> **Status:** DESIGN / brainstorm only — nothing here is built. This is the next work item after the
> attendance go-live. Captured 2026-06-16 so the design survives across machines (chat is disposable).
> Owner is continuing this thread on another computer — **read this file first.**
>
> Two halves: (A) the owner's vision, (B) Claude's grounded analysis (what already exists vs the real
> gaps) + recommendations + the open decisions to make before building.

---

## A. The owner's vision (from the brainstorm message)

**Question 1 — where does it live?** Report done partly/nearly-all by the GM bot, or by a **new
"Accountant TWB" bot**? Pros & cons of a separate bot, considering updates/restarts and operational load.

**The flow the owner wants:**

**Expense Group** — receives photos of receipts (either already paid by **Cash**, or to-be-paid by **ABA**).
System auto-updates the DB on what's paid vs not paid before doing the report. Any unpaid ABAs are
reminded for the next report. Steps:
1. Photos of receipts.
2. Bot reads & **tags** the photo in a reply with all info. **Staff may correct** it.
3. Owner pays and shares the payment to the group.
4. Bot **recognises it's paid** — *how?* (the crux question).
5. Bot updates, tagging the payment in the group — and **confirms which receipt numbers** this payment
   is for. If there's a mistake in the payment, the bot messages the ABA Expense group to confirm.

**Report time** — the system just asks staff to **count the money** and tell us **how much Cash sales /
ABA sales**, then the bot does the rest and **types the normal report** we usually do (and we check it).
Maybe also continue the **photo of the POS terminal** (SambaPOS) so the bot can cross-check.
Owner asks: what am I missing, and what's the sequence?

**Other questions:**
- How will the bot **list receipt details in the Expense Group**? What if some info is missing
  (e.g. local handwritten receipts)?
- How to do this **as efficiently as possible — least API, mostly "Brain"** (rule-based)?

---

## B. Claude's analysis

### B0. THE KEY REFRAME — you're ~70% built already
This is not a from-scratch design. Verified in code (2026-06-16):

| Capability | Where it lives | What it does |
|---|---|---|
| **Receipt reading** | `ai_client.assess_receipt_photo` | ONE Haiku call: classifies *expense_sheet / pos_screen / receipt / other*, reads total (USD **or** Riel ៛), detects handwriting, reads vendor, extracts fields (expense-sheet day/night/ABA totals; POS `pos_kind`+`grand_total`). **Learns** per-vendor formats (`vendor_rules`) + uses past clarifications as few-shot. |
| **"Tag it, staff correct it" + escalation** | `gm_bot/clarify.py` | Pure ladder: unclear → ask in group → nudge every 10 min → back off 30 min if staff say "checking" (EN+KH phrases) → escalate to owner after 2 h. |
| **The typed report engine** | `gm_bot/finance.py` | PURE Brain: regex `parse_report_text` → `recompute()` (drawer = float + cash − cash expense; total sales = cash + ABA; Over/Lost = count − expected) → `format_correction()` (worked arithmetic). AI (`extract_daily_report_ai`, Sonnet) is **fallback only** when the free parser under-reads (≤2/day). Business day = 06:00→06:00 PP; mid vs final (dawn) classification. |
| **Photo ↔ report cross-check** | `gm_bot/reconcile.py` | expense-sheet totals == report cash/ABA expense; **POS grand total == report total sales**. |
| **Payment reading** | `ai_client.read_payment_amount` / `_pdf` | amount, currency, destination account, seller. |
| Groups | TWB REPORT (`-5136886404`); the GM bot already does REPORT receipt checks. | |

### B1. The GENUINE gaps (= the real new build)
1. **Per-receipt ledger** with **numbered rows + paid/unpaid state.** Today receipts feed *totals*
   (expense-sheet level), not individually tracked, numbered, payable items. **This is the spine.**
2. **Payment → receipt matching.** Reading an ABA transfer exists; *tying it to specific unpaid
   receipts and flipping them paid* does not.
3. **Unpaid-ABA carry-forward + reminder loop.**
4. **Report *generation* from minimal input** — today staff TYPE the whole report; the bot only
   parses/checks it. The owner wants: staff count cash + state sales → bot composes. Math engine exists;
   it's a re-org of inputs + a composer.
5. **A dedicated Expense Group workflow** (today the receipt role is in TWB REPORT).

### B2. Architecture — separate "Accountant TWB" bot vs keep in GM
**Recommendation: a separate Accountant bot — *because attendance went live 2026-06-16*.** The GM bot is
now a live, real-time, staff-facing service (check-ins, schedulers, location). Finance will be the
highest-churn build area. A separate bot means **finance deploys never blip live attendance.**

Pros (separate): deploy isolation from live attendance · clean code boundary (bot.py is ~7k lines) ·
independent failure · a clear "money" persona in only Expense+REPORT. 
Cons (separate): +1 token, systemd unit (`twbshop-accountant`), watchdog, log, error-handler wiring, a
one-time owner `/start`. 
**Integration cost is LOW** because the finance logic is already **pure + modular** (`finance.py`,
`reconcile.py`, `clarify.py` have no Telegram/DB coupling) — a new bot imports them, shares the Postgres
DB + shared modules (`ai_client`, `database`, `error_handler`). **The one gotcha: GM must HAND OFF its
REPORT receipt role** so two bots aren't talking in one group.

Timing is the only real question: **split now** (isolation is most valuable right when the other bot just
went live — Claude's lean) **vs build-in-GM-then-split** (the split is cheap *because* the logic is pure).
Either way: **keep all finance logic in a self-contained package so the move stays mechanical.**

### B3. "How does the bot know it's PAID?" — the crux
**Rule: never *infer* "paid" — always *confirm* it** (matches the project's no-silent-AI-guessing +
mandatory-confirmation-gate rules). Two mechanisms, cheapest first:
- **(a) Reply-to-receipt — ZERO API, zero ambiguity.** Every tagged receipt gets a **number** (`🧾 #14`).
  Owner pays by **replying** to that message with the ABA slip → Telegram gives `reply_to_message_id` →
  the bot knows the exact receipt. **Primary path.**
- **(b) Amount+vendor auto-match + ✅ tap.** Owner drops the ABA slip → `read_payment_amount` reads
  `$X → seller` (1 Haiku) → **Brain** finds unpaid receipt(s) for that vendor summing to $X → bot posts
  *"Looks like payment for #14 Atlas $138.60 — ✅ correct / ✏️ different."* The **match is arithmetic
  (free); the confirm is the gate.**
- **Mistake path** = the ✏️ branch → bot asks which receipt #s, or posts to the Expense group to confirm.
  A payment matching nothing stays **"pending match,"** never silently paid.
- The **receipt number is the spine** — humans + bot share one ID space (payments, corrections,
  disputes, reminders all reference `#14`).

### B4. Expense-Group flow (concrete)
```
1. Staff photo a receipt.
2. Bot (1 Haiku) → creates ledger row #14, replies:
     🧾 #14 · Atlas · $138.60 · ABA (unpaid)
     Items: beer keg ×2, soft drinks
     ✏️ reply to fix   ✅ looks right
3. Cash receipt → auto-PAID on the spot (cash = already paid).
   ABA receipt → stays UNPAID, joins the open list.
4. Owner pays → reply to #14 with the ABA slip → bot flips #14 PAID, tags it.
5. Report time → bot lists any still-UNPAID ABA → carries forward + reminds.
```
**Listing details / missing info / handwritten / Riel:** show what's read, `?` for what isn't, and
**only block on a missing AMOUNT** (the books need the number; vendor/items are best-effort).
`assess_receipt_photo` already returns `readable_partial` + `issues` + `is_handwritten` and handles Riel
(store currency per receipt; convert at the fixed **4000៛ = $1** the books already use). No clear total →
the **existing `clarify.py` ladder** asks staff to type it.

### B5. Report time
Math already exists — change the INPUTS. Minimal staff action: **count the cash** (only a human can) +
**snap the POS** (SambaPOS grand total = the *truth anchor* for sales; can even supply the cash/ABA
split so staff may not type sales at all). Then the bot: pulls **expenses from the ledger** (cash+ABA) +
the **float carried over** from yesterday's close → `recompute()` → **cross-checks total sales vs the POS
photo** → **types the standard report** → flags mismatches → asks to confirm. More trustworthy than today
because every number traces to a source (ledger / POS / carry-over), not hand-typing.

### B6. Efficiency — least API, mostly Brain
The right inversion (already your pattern): **the model converts pixels→numbers; the Brain decides
everything.** Keep it strict: ~1 Haiku per photo (receipt/payment/POS — `assess_receipt_photo` already
does classify+read+fields in one call); **matching, paid-state, report assembly, cross-checks, reminders,
dedup are pure Python (zero marginal API)**; reply-to-receipt = 0 API for the most common action; the
vendor-rule + few-shot **learning shrinks clarifications over time.** Net: the new system adds essentially
**no new API load.**

### B7. What the owner is missing / beyond
- **Float carry-over** — yesterday's close *is* today's float; never re-type it.
- **Idempotency / dedup** — same receipt photographed twice (mid+final, or two staff) = ONE row; same
  payment twice = one paid flip (OT-banking lesson: flip status FIRST, atomically).
- **Multi-currency** — store currency per receipt (Riel common on handwritten ones).
- **One transfer covering many receipts** — matching handles subset-sum, or the reply path sidesteps it.
- **Who can correct + audit trail** — log who edited what (the confirmation gate applies to corrections).
- **Cutoff** — a receipt at 11pm vs 2am = different business days (06:00→06:00 already defined — reuse).
- **Close-of-day invariant** — every receipt ends *cash-paid* or *ABA-matched*; anything "pending" is
  flagged. A `/audit`-style law (the pattern already exists).
- **POS digital export** — a file/export beats a photo read. There's already a "POS convergence, Postgres
  source-of-truth" strategy noted — check if SambaPOS can hand the numbers directly instead of a photo.

### B8. Suggested sequence
1. **Receipt ledger** (table + numbered intake + correct loop) — reuses `assess_receipt_photo` +
   `clarify.py`. Cash auto-paid.
2. **Payment matching** (reply-to-receipt first; amount+vendor + ✅ second; mistake → Expense group).
3. **Unpaid-ABA carry-forward + reminder.**
4. **Report assembly** (count cash + POS → ledger + float → `recompute` → cross-check → type → confirm).
5. **Close-of-day audit invariant.**
6. **(If not at step 0) split into the Accountant bot.**

---

## ▶ OPEN DECISIONS (owner — decide before building)
1. **Accountant bot now, or build-in-GM-then-split?** (Claude leans: separate now, because attendance
   is live; but pure-modules make a later split cheap.)
2. **Is SambaPOS reachable as DATA (file/export/API), or do we stay with the POS photo** for the
   cross-check?

## ▶ NEXT STEP (when work resumes)
Draft the **receipt-ledger schema** + the **Phase-1 Expense-Group intake** as a concrete build plan.
Owner found this "very interesting" and wants to work on it next.
