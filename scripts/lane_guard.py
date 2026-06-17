#!/usr/bin/env python3
"""PreToolUse LANE GUARD (WARN-only v1) — cross-lane edit awareness for parallel worktrees.

Reads parallel_lanes.json. Derives THIS worktree's lane from its git branch (lane/<name>).
When an Edit/Write/MultiEdit targets a file OUTSIDE the current lane's owned paths, it prints
a loud warning naming the lane(s) that file concerns — so the owner can pause those lanes.

DESIGN (v1, deliberately conservative):
  - WARN ONLY. It ALWAYS exits 0 — it can never block an edit, so it can never lock up your
    workflow. It fires deterministically on every edit, so you always SEE the warning.
  - On `main` / any non-`lane/...` branch: silent (you're the integrator, allowed to cross).
  - On its OWN error: exits 0 silently — a guard bug must never break the workflow.
  - Fail toward warning: anything not provably inside your own lane warns.
  - ASCII-only output (a Windows console can't encode emoji; ASCII renders everywhere).

NOT ACTIVE until wired into .claude/settings.json as a PreToolUse hook. Until then this file
just sits here and does nothing. (Wiring it is an owner step — the highrisk guard blocks Claude
from editing .claude/.)

UPGRADE PATH (later, when running real concurrent lanes): hard-block-with-ack, a live
sibling-worktree dirty check, and git sparse-checkout so other-lane files are simply ABSENT.
"""
import json
import os
import re
import subprocess
import sys


def _norm(p: str) -> str:
    return (p or "").replace("\\", "/").lstrip("./").rstrip("/")


def _current_lane():
    try:
        b = subprocess.run(["git", "branch", "--show-current"],
                           capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return None
    m = re.match(r"lane/(.+)$", b)
    return m.group(1) if m else None


def _load_map():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # scripts/ -> repo root
    try:
        with open(os.path.join(root, "parallel_lanes.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _under(path: str, prefixes) -> bool:
    p = _norm(path)
    for x in prefixes or []:
        x = _norm(x)
        if p == x or p.startswith(x + "/"):
            return True
    return False


def main(raw: str) -> None:
    data = json.loads(raw)
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return  # only file-edit tools are lane-scoped
    ti = data.get("tool_input") or {}
    path = _norm(ti.get("file_path") or ti.get("notebook_path") or "")
    if not path:
        return

    lane = _current_lane()
    if not lane:
        return  # main / non-lane branch = integrator; nothing to cross

    m = _load_map()
    lanes = m.get("lanes", {})
    if _under(path, lanes.get(lane, [])):
        return  # editing your own lane — silent

    if _under(path, m.get("shared", [])):
        concerns = "ALL lanes (shared file)"
    else:
        owners = [ln.upper() for ln, paths in lanes.items() if _under(path, paths)]
        concerns = ", ".join(owners) if owners else "the SHARED / unowned area"

    sys.stderr.write(
        "\n============================================================\n"
        "  CROSS-LANE EDIT  ->  you are in lane: %s\n"
        "============================================================\n"
        "  File:     %s\n"
        "  Concerns: %s\n"
        "  If you're actively working any of those lanes, PAUSE them until this edit is done.\n"
        "============================================================\n\n"
        % (lane, path, concerns)
    )


if __name__ == "__main__":
    try:
        main(sys.stdin.read())
    except Exception:
        pass  # never break the workflow
    sys.exit(0)
