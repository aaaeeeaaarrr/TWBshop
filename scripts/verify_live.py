#!/usr/bin/env python3
"""Deploy/live verification (Hook 2) — TWBshop.

Proves "pushed AND live AND running" from GROUND TRUTH, not from the model's word:
  - local HEAD == origin/main HEAD
  - server HEAD == origin/main HEAD
  - the systemd service is active
  - (optional) the running file on the server actually contains an expected marker string

Exit 0 only if everything checks out; non-zero otherwise. Output is meant to be pasted as evidence.

Usage:
  python scripts/verify_live.py <service> [--marker "some unique string" --file gm_bot/bot.py]
  <service> in: gm | b2b | retail | listener | hire   (or a full twbshop-* unit name)
"""
import subprocess
import sys
import argparse

SVC = {"gm": "twbshop-gm", "b2b": "twbshop-b2b", "retail": "twbshop-retail",
       "listener": "twbshop-listener", "hire": "twbshop-hire"}


def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("service")
    ap.add_argument("--marker", default=None, help="string the running file must contain")
    ap.add_argument("--file", default=None, help="server file to check for --marker")
    a = ap.parse_args()
    unit = SVC.get(a.service, a.service if a.service.startswith("twbshop-") else "twbshop-" + a.service)

    ok = True
    print("=== verify_live: %s ===" % unit)

    _, local_head, _ = run("git rev-parse HEAD")
    run("git fetch -q origin")
    _, origin_head, _ = run("git rev-parse origin/main")
    rc, server_head, se = run('ssh twbshop "cd /root/TWBshop && git rev-parse HEAD"')
    if rc != 0:
        print("  [FAIL] could not reach server: %s" % se); return 3
    rc, active, _ = run('ssh twbshop "systemctl is-active %s"' % unit)

    print("  local  HEAD: %s" % local_head[:12])
    print("  origin HEAD: %s" % origin_head[:12])
    print("  server HEAD: %s" % server_head[:12])
    print("  service    : %s" % active)

    if not (local_head and local_head == origin_head):
        print("  [FAIL] local != origin (push first)"); ok = False
    if not (server_head and server_head == origin_head):
        print("  [FAIL] server != origin (server not pulled/deployed)"); ok = False
    if active != "active":
        print("  [FAIL] service is not active"); ok = False

    if a.marker and a.file:
        rc, found, _ = run('ssh twbshop "grep -c -- %s /root/TWBshop/%s"'
                           % (_q(a.marker), a.file))
        present = found.strip() not in ("", "0")
        print("  marker in %s: %s" % (a.file, "yes" if present else "NO"))
        if not present:
            print("  [FAIL] running file lacks the expected change"); ok = False

    print("RESULT:", "LIVE [OK]" if ok else "NOT LIVE [FAIL]")
    return 0 if ok else 1


def _q(s):
    return "'" + s.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    sys.exit(main())
