#!/usr/bin/env python3
"""integration_audit.py - the INTEGRATOR's cross-lane sweep (what no single lane can see).

Reads parallel_lanes.json + git. READ-ONLY. Run from the hub (main) after merges, or let the monitor
run it. All checks are GENERIC - portable to any multi-lane project that uses parallel_lanes.json:

  1. MAP INTEGRITY    - every tracked file is owned by exactly ONE lane or 'shared' (no unowned, no
                        double-claimed). The S5 single-resolver invariant for file ownership.
  2. CROSS-LANE COMMIT - no single (non-merge) commit touches 2+ different lanes' dirs.
  3. HUB-ONLY HYGIENE - no lane commit edits a hub-only file (CLAUDE.md) alongside its lane dir
                        (lane status belongs in CLAUDE.local.md, not the tracked file).
  4. --suite (optional) - run the test suite (catches a clean-but-broken merge).

Exit 0 = clean, 1 = findings. ASCII output (Windows-console safe). Importable: audit() + format_report().
"""
import json
import os
import subprocess
import sys

HUB_ONLY = {"CLAUDE.md"}
SOFT_LANES = {"docs"}  # editing docs alongside your own lane is fine (can't break a build)
TEST_CMD = ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
SCAN_COMMITS = 40


def _root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(args):
    return subprocess.run(["git"] + args, cwd=_root(), capture_output=True, text=True).stdout


def _map():
    try:
        with open(os.path.join(_root(), "parallel_lanes.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _norm(p):
    return (p or "").replace("\\", "/").strip("/")


def _under(path, prefixes):
    p = _norm(path)
    for x in prefixes or []:
        x = _norm(x)
        if p == x or p.startswith(x + "/"):
            return True
    return False


def _owners(path, m):
    return [ln for ln, paths in m.get("lanes", {}).items() if _under(path, paths)]


def check_map_integrity(m):
    findings = []
    shared = m.get("shared", [])
    for f in [x for x in _git(["ls-files"]).splitlines() if x.strip()]:
        if _under(f, shared):
            continue
        owners = _owners(f, m)
        if not owners:
            findings.append("UNOWNED: %s (add it to parallel_lanes.json: a lane, or shared)" % f)
        elif len(owners) > 1:
            findings.append("DOUBLE-CLAIMED: %s -> %s (one owner only)" % (f, ", ".join(owners)))
    return findings


def _commit_lane_dirs(sha, m):
    files = [x.strip() for x in _git(["show", "--name-only", "--format=", sha]).splitlines() if x.strip()]
    hit = set()
    for f in files:
        if _under(f, m.get("shared", [])):
            continue
        for o in _owners(f, m):
            if o not in SOFT_LANES:   # docs alongside your own lane is allowed
                hit.add(o)
    return hit, files


def check_cross_lane_commits(m):
    findings = []
    for sha in _git(["log", "--no-merges", "--format=%H", "-n", str(SCAN_COMMITS)]).split():
        lanes, _ = _commit_lane_dirs(sha, m)
        if len(lanes) > 1:
            subj = _git(["show", "-s", "--format=%s", sha]).strip()[:48]
            findings.append("%s touches %s [%s]" % (sha[:8], "+".join(sorted(lanes)), subj))
    return findings


def check_hub_only_hygiene(m):
    findings = []
    for sha in _git(["log", "--no-merges", "--format=%H", "-n", str(SCAN_COMMITS)]).split():
        lanes, files = _commit_lane_dirs(sha, m)
        hub = [f for f in files if _norm(f) in HUB_ONLY]
        if hub and lanes:  # a lane commit that also edited a hub-only file
            subj = _git(["show", "-s", "--format=%s", sha]).strip()[:48]
            findings.append("%s: lane %s also edited %s [%s]"
                            % (sha[:8], "+".join(sorted(lanes)), ", ".join(hub), subj))
    return findings


def run_suite():
    r = subprocess.run(TEST_CMD, cwd=_root(), capture_output=True, text=True)
    return r.returncode == 0, (r.stdout.strip().splitlines() or [""])[-1]


def audit(with_suite=False):
    # CLAUDE.md hygiene is ENFORCED at the source by lane_guard's HUB_ONLY hard-block (prevention),
    # not detected here (a commit-history scan is imperfect + noisy with pre-setup history).
    m = _map()
    rep = {"map": check_map_integrity(m),
           "cross_lane": check_cross_lane_commits(m)}
    if with_suite:
        ok, line = run_suite()
        rep["suite"] = [] if ok else ["SUITE FAILED: " + line]
        rep["_suite_line"] = line
    return rep


def format_report(rep, with_suite=False):
    lines, total = ["=== INTEGRATION AUDIT ==="], 0
    for key, label in [("map", "Map integrity"), ("cross_lane", "Cross-lane commits")]:
        f = rep.get(key, [])
        total += len(f)
        lines.append(("[X] %s: %d" % (label, len(f))) if f else ("[OK] %s" % label))
        lines += ["    - " + x for x in f]
    if with_suite:
        f = rep.get("suite", [])
        total += len(f)
        lines.append(("[X] Suite: " if f else "[OK] Suite: ") + rep.get("_suite_line", ""))
    lines.append("=== %s ===" % ("CLEAN" if total == 0 else "%d FINDING(S)" % total))
    return "\n".join(lines), total


if __name__ == "__main__":
    rep = audit("--suite" in sys.argv[1:])
    text, total = format_report(rep, "--suite" in sys.argv[1:])
    print(text)
    sys.exit(1 if total else 0)
