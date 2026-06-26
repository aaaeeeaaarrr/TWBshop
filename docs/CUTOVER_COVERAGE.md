# Cut-over Coverage — making the LIVE gm config-driven (instant-live, no restart)

> The owner's reliability goal: a customer tweaks a dashboard setting and it's **instantly live, no restart, no
> faults**. The config MECHANISM already delivers this (`tenant_config.get_config` reads fresh every call — no
> cache; writes are atomic; `set_config` is now `SELECT … FOR UPDATE` so concurrent tweaks can't clobber). The
> GAP is COVERAGE: only **2** live-gm paths read config today (the day-off **swap rule** `attendance_ui.py:1842`
> and the **AL re-ping ladder** `bot.py:6105`). Every other live setting is a hardcoded constant → changing it
> needs a gm **deploy**. This doc is the prioritized map to close that gap, path by path.
>
> (Full "are-we-there-yet" verdict + the mechanism evidence → `docs/BONUSES_AND_FINDINGS.md` §s55 due-diligence.)

## The migration pattern (behavior-preserving — no cut-over of LOGIC, just the value's SOURCE)
For a hardcoded constant whose value already equals TWB's current rule, migrating is **behavior-preserving** (the
config DEFAULT == the constant, so with no override the behavior is identical) and does NOT need the shadow→live
logic cut-over. The swap rule is the template:
1. Read the value from `core.tenant_config` **at execution time** (not at import) → instant-live.
2. **Fail-safe on read:** fall back to the current constant if the setting is missing/malformed (a typo can never
   fault a live path).
3. **Validate on write** (the wizard already type/range/enum-validates the customer editor; keep it).
4. **HIGH-RISK proof:** these are payroll/attendance-adjacent — prove `default == current` on staging + a real-row
   before/after, deploy in a quiet window, verify the running value is unchanged with no override.
5. **Consolidate duplicates** while you're there (see GRACE_MIN below).

## ▶ Migrate FIRST — highest value, lowest risk (default already == TWB's value)
1. **`attendance.verdict.grace_min`** (=5) → `gm_bot/checkin.py:14` (+ **dup** `gm_bot/late.py:8`) — the lateness
   grace window; highest-frequency check, pure lateness math. **Consolidate the two copies into the config read.**
2. **`attendance.verdict.early_bonus_min`** (=5) → `gm_bot/checkin.py:15` — the early-arrival bonus threshold.
3. **`attendance.leave.papers_grace_days`** (=2) → `gm_bot/sick.py:11` — doctor's-paper deadline; low blast radius.
4. **`attendance.leave.short_notice_days`** (=7) → `gm_bot/al.py:12` — the <7-days AL penalty boundary.
5. **`attendance.ot.bank_cap_min`** (=14*60) → `gm_bot/ot.py:13` — the OT-bank ceiling.

These five are the cleanest "tweakable instantly" wins a customer would actually want, each behavior-preserving.

## HIGH-RISK map (payroll / attendance / money-adjacent — staging-prove each)
| Setting (tenant_config) | Hardcoded at | Controls |
|---|---|---|
| `verdict.grace_min` | `checkin.py:14` + `late.py:8` (DUP) | ≤N min late = free |
| `verdict.early_bonus_min` | `checkin.py:15` | ≥N min early = +10 |
| `staff_rules.auto_clockout_grace_min` | `checkin.py:16` (=3) | in-zone within N of end = present |
| `ot.bank_cap_min` | `ot.py:13` (=14*60) | OT-bank ceiling |
| `leave.short_notice_days` | `al.py:12` (=7) | short-notice AL penalty boundary |
| `leave.papers_grace_days` | `sick.py:11` (=2) | doctor's-paper deadline |
| `leave.sick.late_inform_threshold_min` | `attendance_ui.py:~1160` (=30) | window for the −15 |
| `leave.sick.late_inform_penalty_points` | `points.py:22` (=−15) + applied `bot.py:4137` | the late-sick penalty |
| `approvals[kind].approvers` | `al.py:14` (=2) + senior=1 `al.py:119` | seniors needed per request type |
| `points.catalogue.*` | `points.py:13-27` (early +10 · late −1/−2 · return +15 · ot_no_show −30 · short_notice_al −0.1) | every point value |

## MED-RISK map (workflow / timing — no payroll drift)
| Setting | Hardcoded at | Controls |
|---|---|---|
| (new) family-sick soft-note window | `attendance_ui.py:~1161` (=10) | family-sick note (not a penalty) |
| (new) AL-today gate lead | `attendance_ui.py:~1671` (=30) | gate arms N min before start |
| (new) approval nudge/escalate caps | `al.py:140-141` (12h/24h) | approval-ladder timing |
| (new) lateness ladder timing | `lateness.py:16-17` (30m/24h) | group-ask / escalate timing |
| (new) flow TTLs | `flow.py:22-23` (120m/30m) | button/text flow timeouts |
| (new) family-sick pool | `sick.py:13` (=7) | annual family-sick budget |
| OT UI granularity / max | `ot.py:41-42` (30 / 4h) | OT picker step / max extension |

*(Several MED rows need a NEW config key added to `tenant_config.DEFAULTS` first — they aren't modelled yet.)*

## Discipline (so "instant-live" never means "a typo breaks live")
- **Validate-on-write + fail-safe-on-read** on every migrated path (the swap rule + AL ladder already do this).
- Each HIGH-RISK migration ships only with a staging proof that **default == current** + a quiet-window deploy.
- Consolidate every duplicated constant into the single config read as you migrate it (kills the drift class).
- The AL re-ping ladder reads config; **swap/OT/special-leave approvals do NOT yet** — point them at `approval_rule`.
