"""builder_monitor — a STANDALONE, org-scoped, read-only BUILDER MONITORING sweep (W3 #5 foundation).

WHY (client/builder separation law): the builder/system monitoring JOBS (live-watchdog · sentinel-sweep ·
daily-audit) currently run INSIDE the client GM bot process. At multi-client they must move OUT into a
builder monitor that sweeps ALL orgs (CLAUDE.md separation backlog #1). The daily read-only DIGEST half
already runs standalone (scripts/morning_report.py); THIS is the ALERTING half (deduped, real-time-capable)
still embedded in gm today. It runs the checks outside the client bot, iterates every org, and routes NEW
alarms to the durable sink + the Monitor — NEVER the client GM bot.

SCOPE-HONEST (owner): the full continuous all-org service is a MULTI-CLIENT / post-core-cut-over concern —
tolerable in gm today because TWB is the lone tenant, and `run_audit` audits TWB's *legacy single-tenant*
ledger (so its audit half is twb-only; the Sentinel half is already org-scoped). This file is the turnkey
FOUNDATION + an on-demand independent sweep, deliberately NOT a speculative always-on service.

INERT until the owner cuts over: it is NOT scheduled / not deployed. The gm bot keeps running its own
watchdog + sentinel jobs. Do NOT schedule this ALONGSIDE them — both would alarm the same problem. At
cut-over (docs/BUILDER_MONITOR_CUTOVER.md) the owner schedules this + removes the gm jobs; then it is the
single builder monitor. Its dedupe state uses distinct `bmon_*` keys so a manual run can't corrupt the gm
jobs' state.

Usage:
  TWBSHOP_ENV=prod python scripts/builder_monitor.py            # DRY-RUN: print what it would alarm (read-only)
  TWBSHOP_ENV=prod python scripts/builder_monitor.py --send     # persist to the sink + DM the Monitor (prod-gated)
  TWBSHOP_ENV=prod python scripts/builder_monitor.py --send twb # limit to one org (default: all orgs)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repo root on path
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # bilingual/emoji bodies vs cp1252
    except Exception:
        pass

LEGACY_LIVE_ORG = "twb"    # the org whose LIVE legacy ledger run_audit covers (single-tenant audit)


# ── pure dedupe helpers — re-implemented lean here (parity-guarded in tests/test_builder_monitor.py vs the
#    gm_bot.bot originals `_watchdog_delta` / `_sentinel_new_alarms`, so the two copies can't drift) ─────────
def watchdog_delta(prev_json, problems):
    """(prev JSON, this cycle's problems) -> (new_sorted, cleared_sorted, cur_json). A corrupt/empty prev = none seen."""
    cur = set(problems)
    try:
        prev = set(json.loads(prev_json or "[]"))
    except Exception:
        prev = set()
    return sorted(cur - prev), sorted(prev - cur), json.dumps(sorted(cur))


def sentinel_new(found, prev_json):
    """(sentinel.sweep() alarms, prev JSON) -> (new_alarms, cur_json). Dedup key = flow:key (alarm once, not per sweep)."""
    try:
        prev = set(json.loads(prev_json or "[]"))
    except Exception:
        prev = set()
    cur = {"%s:%s" % (a.get("flow"), a.get("key")): a for a in found}
    return [cur[k] for k in cur if k not in prev], json.dumps(sorted(cur.keys()))


def all_orgs():
    """Every org the platform knows (today: just 'twb'). Falls back to ['twb'] if the table isn't reachable."""
    try:
        from shared.database import _db
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT org_id FROM orgs ORDER BY org_id")
                orgs = [r["org_id"] for r in cur.fetchall()]
        return orgs or [LEGACY_LIVE_ORG]
    except Exception:
        return [LEGACY_LIVE_ORG]


def sweep_org(org):
    """READ-ONLY: run the builder checks for one org. Returns {'audit': [problems], 'sentinel': [alarms]}.
    The audit runs only for the legacy live org (single-tenant ledger); the Sentinel is org-scoped."""
    import datetime
    from zoneinfo import ZoneInfo
    out = {"audit": [], "sentinel": []}
    if org == LEGACY_LIVE_ORG:
        try:
            from gm_bot.audit import run_audit
            probs, _ = run_audit(datetime.datetime.now(ZoneInfo("Asia/Phnom_Penh")).date(), test_rows=False)
            out["audit"] = list(probs)
        except Exception as e:
            out["audit_error"] = str(e)
    try:
        from core import sentinel
        out["sentinel"] = sentinel.sweep(org)
    except Exception as e:
        out["sentinel_error"] = str(e)
    return out


def _emit(kind, body, severity, send):
    """Route ONE alarm: always print; on --send persist to the sink + DM the Monitor + flag delivered."""
    print("  ALARM [%s/%s] %s" % (severity, kind, body.replace("\n", " ")[:160]))
    if not send:
        return
    from gm_bot import alarms
    from shared.monitor_notify import notify_monitor
    aid = alarms.log_alarm(kind, body, severity=severity)     # durable first (never lost)
    if notify_monitor("🛰 [builder-monitor] " + body):        # then DM the Monitor (prod-gated inside)
        alarms.mark_delivered(aid)


def run(send=False, only_org=None):
    """Sweep every org (or one), emit NEW alarms (deduped vs the stored bmon_* state). Dedupe state is
    written ONLY on --send, so a DRY-RUN is fully read-only. Returns the count of NEW alarms."""
    from shared.database import gm_get_state, gm_set_state
    orgs = [only_org] if only_org else all_orgs()
    total_new = 0
    for org in orgs:
        print("\n=== builder-monitor sweep — org '%s' ===" % org)
        res = sweep_org(org)
        # audit (legacy single-tenant ledger)
        if "audit_error" in res:
            print("  [audit] ERROR: %s" % res["audit_error"])
        elif org == LEGACY_LIVE_ORG:
            new, cleared, cur = watchdog_delta(gm_get_state("bmon_audit_%s" % org), res["audit"])
            print("  [audit] %d problem(s); %d new, %d cleared" % (len(res["audit"]), len(new), len(cleared)))
            for p in new:
                _emit("watchdog", "🚨 Builder audit — new data inconsistency (%s): %s" % (org, p), "money", send)
            total_new += len(new)
            if send:
                gm_set_state("bmon_audit_%s" % org, cur)
        # sentinel (org-scoped)
        if "sentinel_error" in res:
            print("  [sentinel] ERROR: %s" % res["sentinel_error"])
        else:
            new, cur = sentinel_new(res["sentinel"], gm_get_state("bmon_sentinel_%s" % org))
            print("  [sentinel] %d alarm(s); %d new" % (len(res["sentinel"]), len(new)))
            for a in new:
                sev = {"critical": "money", "warn": "warn"}.get(a.get("severity"), "info")
                _emit("sentinel:%s" % a.get("flow"), "🛰 Sentinel (%s) — %s" % (org, a.get("detail")), sev, send)
            total_new += len(new)
            if send:
                gm_set_state("bmon_sentinel_%s" % org, cur)
    print("\n=== builder-monitor: %d NEW alarm(s) across %d org(s)%s ===" %
          (total_new, len(orgs), "" if send else "  [DRY-RUN — nothing persisted or sent]"))
    return total_new


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(send="--send" in flags, only_org=(args[0] if args else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
