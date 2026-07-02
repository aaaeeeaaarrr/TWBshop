#!/usr/bin/env python3
"""
monitor.py - read-only lanes + service watcher (v1).

WHAT IT DOES (never writes git, never deploys, never restarts anything):
  - Lane board: every git worktree -> branch, dirty?, ahead/behind main.
  - Service health: `systemctl is-active` for the 5 twbshop-* units over SSH (best-effort).
  - Alerts the owner on Telegram (SEND-ONLY) when something needs attention.

USAGE:
  python scripts/monitor.py             # print the board + services once
  python scripts/monitor.py --test      # send a test DM (verify the bot/token)
  python scripts/monitor.py --watch     # loop (default 300s), DM owner on a NEW anomaly
  python scripts/monitor.py --watch 120 # loop every 120s

SAFETY: send-only (it NEVER reads bot updates, so random spam to the bot is ignored and
it can never be a second poller); read-only on git; SSH is best-effort and times out.
No external deps (urllib only). Owner chat id can be overridden with MONITOR_OWNER_CHAT_ID.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OWNER_CHAT_ID = os.environ.get("MONITOR_OWNER_CHAT_ID", "1313155971")
SERVICES = ["twbshop-retail", "twbshop-b2b", "twbshop-gm", "twbshop-listener", "twbshop-hire",
            "twbshop-automations", "twbshop-wizard"]   # +2 per the 2026-07-02 dead-end audit (were unwatched)
EXPECTED_INACTIVE = {"twbshop-b2b"}  # deliberately stopped - shown on the board, never alarmed
SSH_ALIAS = "twbshop"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(args, cwd=REPO):
    try:
        return subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                              text=True, timeout=15).stdout.strip()
    except Exception:
        return ""


def worktrees():
    out, wts, cur = _git(["worktree", "list", "--porcelain"]), [], {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur:
                wts.append(cur)
            cur = {"path": line[9:]}
        elif line.startswith("branch "):
            cur["branch"] = line[7:].replace("refs/heads/", "")
        elif line.strip() == "detached":
            cur["branch"] = "(detached)"
    if cur:
        wts.append(cur)
    return wts


def lane_board():
    rows = []
    for wt in worktrees():
        path, branch = wt["path"], wt.get("branch", "?")
        dirty = len([l for l in _git(["status", "--porcelain"], cwd=path).splitlines() if l.strip()])
        ahead = behind = 0
        if branch not in ("main", "(detached)", "?"):
            a = _git(["rev-list", "--count", "main..%s" % branch])
            b = _git(["rev-list", "--count", "%s..main" % branch])
            ahead = int(a) if a.isdigit() else 0
            behind = int(b) if b.isdigit() else 0
        rows.append({"name": os.path.basename(path), "branch": branch,
                     "dirty": dirty, "ahead": ahead, "behind": behind})
    return rows


def service_health():
    """SSH `systemctl is-active <units>` (read-only). Returns {unit: state} or None if SSH fails."""
    try:
        cmd = "systemctl " + "is-active " + " ".join(SERVICES)
        out = subprocess.run(["ssh", SSH_ALIAS, cmd], capture_output=True,
                             text=True, timeout=20).stdout.strip().splitlines()
        return dict(zip(SERVICES, [s.strip() for s in out])) if out else None
    except Exception:
        return None


def anomalies(rows, svc):
    """What actually warrants a DM: a service that should be up is down. Lane behind/ahead/dirty is
    normal workflow churn -> shown on the board, NEVER DM'd (no spam on every push). Silence = healthy."""
    a = []
    if svc:
        for name, state in svc.items():
            if state != "active" and name not in EXPECTED_INACTIVE:
                a.append("service %s is %s (was up, now down)" % (name, state))
    return a


def issues(rows, svc):
    """The richer 'what needs you' for the /issues command — each item carries a one-line FIX.
    Distinct from anomalies() (the spam-free DM trigger = service-down only). 'behind main' is normal
    churn so it's omitted here too. Order = severity: a down service, then unsaved work, then unpushed."""
    out = []  # (tag, text, fix)
    if svc:
        for name, state in svc.items():
            if state != "active" and name not in EXPECTED_INACTIVE:
                out.append(("DOWN", "%s is %s" % (name, state),
                            "restart it on the server + verify (it normally auto-restarts)"))
    for r in rows:
        if r["dirty"]:
            out.append(("WORK", "%s: %d uncommitted file(s)" % (r["name"], r["dirty"]),
                        "commit it in that terminal before closing the window, or the work is unsaved"))
    for r in rows:
        if r["ahead"]:
            out.append(("PUSH", "%s: %d commit(s) not yet on main" % (r["branch"], r["ahead"]),
                        "run `push` to merge it into main"))
    return out


def fmt(rows, svc):
    lines = ["LANE BOARD"]
    for r in rows:
        flags = []
        if r["dirty"]:
            flags.append("%d dirty" % r["dirty"])
        if r["ahead"]:
            flags.append("%d ahead" % r["ahead"])
        if r["behind"]:
            flags.append("%d behind" % r["behind"])
        lines.append("  %-22s %-18s %s" % (r["name"], r["branch"], ", ".join(flags) or "clean"))
    if svc:
        lines.append("SERVICES")
        for name, state in svc.items():
            if state == "active":
                mark = "OK"
            elif name in EXPECTED_INACTIVE:
                mark = "--"  # intentionally off
            else:
                mark = "!!"
            note = " (intentionally off)" if (name in EXPECTED_INACTIVE and state != "active") else ""
            lines.append("  [%s] %s: %s%s" % (mark, name, state, note))
    else:
        lines.append("SERVICES: (ssh unavailable - skipped)")
    return "\n".join(lines)


def _token():
    try:
        sys.path.insert(0, REPO)
        from secrets import MONITOR_BOT_TOKEN
        return MONITOR_BOT_TOKEN
    except Exception:
        return ""


def notify(text):
    token = _token()
    if not token:
        print("[notify] no MONITOR_BOT_TOKEN - skipped")
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": OWNER_CHAT_ID, "text": text}).encode()
        req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % token, data=data)
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        if not resp.get("ok"):
            print("[notify] telegram error: %s" % resp)
        return resp.get("ok", False)
    except urllib.error.HTTPError as e:
        try:
            desc = json.loads(e.read().decode()).get("description", "")
        except Exception:
            desc = ""
        print("[notify] failed: HTTP %s - %s" % (e.code, desc))
        return False
    except Exception as e:
        print("[notify] failed: %s" % e)
        return False


def main():
    args = sys.argv[1:]
    if "--test" in args:
        ok = notify("TWB monitor: test message - if you see this, the watcher can reach you.")
        print("test DM sent" if ok else
              "test DM FAILED (open the bot in Telegram and press Start, then retry)")
        return
    if "--watch" in args:
        i = args.index("--watch")
        secs = int(args[i + 1]) if len(args) > i + 1 and args[i + 1].isdigit() else 300
        print("watching every %ds (Ctrl-C to stop)..." % secs)
        notify("TWB monitor: started watching (every %ds). I'll DM only on a real problem - "
               "a service that was up going down. Silence = healthy." % secs)
        last = None
        while True:
            rows, svc = lane_board(), service_health()
            print("\n" + fmt(rows, svc), flush=True)
            anoms = anomalies(rows, svc)
            sig = "|".join(sorted(anoms))
            if sig != last:
                if anoms:
                    notify("TWB monitor - needs attention:\n- " + "\n- ".join(anoms) + "\n\n" + fmt(rows, svc))
                elif last:
                    notify("TWB monitor: all clear.")
                last = sig
            time.sleep(secs)
    else:
        rows, svc = lane_board(), service_health()
        print(fmt(rows, svc))


if __name__ == "__main__":
    main()
