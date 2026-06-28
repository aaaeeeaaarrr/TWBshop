"""Config-diff preview (E, lean) — run the org's recent REAL check-ins through a few grace values at once
and show what each would reclassify. READ-ONLY. The seed of the parallel-shadow harness / the dashboard's
config-diff killer feature. Usage:  TWBSHOP_ENV=prod python scripts/config_diff.py [org] [early]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core import parallel_shadow as ps


def main() -> int:
    org = sys.argv[1] if len(sys.argv) > 1 else "twb"
    early = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print("=== Config-diff preview (grace sweep) — %s ===" % org)
    for line in ps.summary_lines(ps.verdict_matrix(org, early=early)):
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
