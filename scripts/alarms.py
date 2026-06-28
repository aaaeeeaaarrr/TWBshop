"""Read the GM alarm sink (B1, session 58) — so Claude / the B3 nightly agent can see EVERY alarm the
GM bot raised, including ones the owner missed or that never delivered over Telegram.

Usage (read-only unless --ack):
    TWBSHOP_ENV=prod python scripts/alarms.py              # recent 30 (non-test)
    TWBSHOP_ENV=prod python scripts/alarms.py --open       # unacked only ("still needs attention")
    TWBSHOP_ENV=prod python scripts/alarms.py --recent 100
    TWBSHOP_ENV=prod python scripts/alarms.py --sev money  # high-severity only
    TWBSHOP_ENV=prod python scripts/alarms.py --ack 42     # mark one handled
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repo root on path

# Alarm bodies are bilingual (Khmer/emoji); the Windows console defaults to cp1252 and would crash on
# them. Force UTF-8 output so the reader works everywhere.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from gm_bot import alarms


def main() -> int:
    ap = argparse.ArgumentParser(description="Read/ack the GM alarm sink.")
    ap.add_argument("--open", action="store_true", help="only unacked alarms")
    ap.add_argument("--recent", type=int, default=30, help="how many recent alarms (default 30)")
    ap.add_argument("--sev", choices=alarms.SEVERITIES, help="filter by severity")
    ap.add_argument("--ack", type=int, metavar="ID", help="mark alarm ID handled")
    ap.add_argument("--all", action="store_true", help="include test-mode rows")
    args = ap.parse_args()

    if args.ack:
        alarms.ack_alarm(args.ack)
        print("acked #%d" % args.ack)
        return 0

    rows = (alarms.open_alarms() if args.open
            else alarms.recent_alarms(args.recent, include_test=args.all, severity=args.sev))
    if not rows:
        print("(no alarms)")
        return 0
    undelivered = sum(1 for r in rows if not r["delivered"])
    for r in rows:
        flags = ("" if r["delivered"] else " [UNDELIVERED]") + (" ✓acked" if r["acked"] else "")
        body = (r["body"] or "").replace("\n", " ⏎ ")[:300]
        print("#%-5d %s  [%s] %-14s%s\n      %s" % (r["id"], r["at"], r["severity"], r["kind"], flags, body))
    print("\n%d shown · %d undelivered (the owner may have missed these)" % (len(rows), undelivered))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
