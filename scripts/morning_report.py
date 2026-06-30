"""Morning report (B3 generator) — a READ-ONLY digest of the platform's overnight state, so Claude / the
B3 nightly cloud-agent (or the owner) can see "what happened + what needs attention" at a glance without
reading a terminal full of logs. It NEVER writes anything.

Pulls four reliable sources:
  1. /audit  — live money/data-integrity problems (run_audit over the REAL ledger)
  2. Sentinel — stuck flows / impossible states / the shadow-net-itself (core.sentinel.sweep)
  3. Alarm sink — open (unacked) alarms incl. UNDELIVERED ones (the ones the owner may have missed)
  4. Shadow  — the check-in cut-over agreement signal (best-effort)

Usage:  TWBSHOP_ENV=prod python scripts/morning_report.py [org_id]

The nightly SCHEDULING (run this without a terminal) is the owner-gated half — a scheduled cloud agent /
cron that runs this + DMs the result. This generator is what it would run."""
import datetime
import os
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repo root on path
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # bilingual/emoji bodies vs cp1252
    except Exception:
        pass


def build_report(org_id: str = "twb") -> str:
    now = datetime.datetime.now(ZoneInfo("Asia/Phnom_Penh"))
    out = ["=== Morning report — %s — %s ===" % (org_id, now.strftime("%Y-%m-%d %H:%M %Z"))]

    # 1) /audit — live money/data integrity
    try:
        from gm_bot.audit import run_audit
        probs, _ = run_audit(now.date(), test_rows=False)
        out.append("\n[/audit] " + ("✅ 0 problems" if not probs else "❌ %d problem(s):" % len(probs)))
        out += ["   • " + p for p in probs[:15]]
    except Exception as e:
        out.append("\n[/audit] ERROR: %s" % e)

    # 2) Sentinel — stuck flows / impossible states / shadow-net-dark
    try:
        from core import sentinel
        al = sentinel.sweep(org_id)
        out.append("\n[Sentinel] " + sentinel.summary_line(al))
        out += ["   • [%s] %s — %s" % (a["severity"], a["flow"], a["detail"]) for a in al[:15]]
    except Exception as e:
        out.append("\n[Sentinel] ERROR: %s" % e)

    # 3) Alarm sink — open (unacked) alarms, incl. UNDELIVERED (owner may have missed these)
    try:
        from gm_bot import alarms
        op = alarms.open_alarms()
        out.append("\n[Alarm sink] %d open / unacked:" % len(op))
        for a in op[:15]:
            flag = "" if a["delivered"] else " [UNDELIVERED]"
            out.append("   • #%d [%s] %s%s — %s"
                       % (a["id"], a["severity"], a["kind"], flag, (a["body"] or "").replace("\n", " ")[:120]))
    except Exception as e:
        out.append("\n[Alarm sink] ERROR: %s" % e)

    # 4) Shadow agreement — the check-in cut-over readiness signal (best-effort; API may vary)
    try:
        from core import shadow
        if hasattr(shadow, "comparison_stats"):
            out.append("\n[Shadow] %s" % (shadow.comparison_stats(),))
    except Exception as e:
        out.append("\n[Shadow] (n/a): %s" % e)

    return "\n".join(out)


def _send_to_owner(text: str) -> bool:
    """DM the digest to the owner via the MONITOR bot — this is a BUILDER/system report (audit + Sentinel +
    alarm-sink + shadow), so it must NOT go via the client GM bot (client/builder separation law). Routes
    through shared.monitor_notify (the ONE Monitor channel; prod-gated; a direct POST, no async). Never raises."""
    try:
        from shared.monitor_notify import notify_monitor
        ok = notify_monitor(text)
        print("(--send: delivered via Monitor)" if ok else "(--send: Monitor not-ok / not prod / no token)")
        return bool(ok)
    except Exception as e:
        print("(--send failed: %s)" % e)
        return False


def main() -> int:
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    org = args[0] if args else "twb"
    report = build_report(org)
    print(report)
    if "--send" in flags:
        _send_to_owner(report)        # the nightly cron uses this; without --send it's just read-only print
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
