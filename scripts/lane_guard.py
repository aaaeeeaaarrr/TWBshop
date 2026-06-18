#!/usr/bin/env python3
"""PreToolUse LANE GUARD (v2) — read any lane, write only your own + shared.

Reads parallel_lanes.json. Derives THIS worktree's lane from its git branch (lane/<name>).
Fires only on file-EDIT tools (Edit/Write/MultiEdit/NotebookEdit), so READS are NEVER
affected — you can grep/open any lane freely. On a WRITE:

  - your own lane            -> silent (allowed).
  - a SHARED file            -> WARN, allowed (legitimate cross-cutting; coordinate the lanes).
  - ANOTHER lane's file      -> BLOCK (exit 2) unless an ack is present.
  - an unowned/new file      -> WARN (it wants a home in the map), allowed.
  - on main / non-lane branch-> silent (you're the integrator, allowed to cross).

ACK (to make a deliberate cross-lane WRITE): create an empty file `.lane_ack` in this
worktree (or set env LANE_ACK=1 before launching). Redo the edit, then delete `.lane_ack`.
The friction is intentional — this should be rare; it stops the *accidental* edit, not you.

SAFETY: on its OWN error it exits 0 (a guard bug must never lock the workflow). ASCII-only
output (a Windows console can't encode emoji). NOT active until wired into
.claude/settings.json as a PreToolUse hook.
"""
import json
import os
import re
import subprocess
import sys

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SOFT_LANES = {"docs"}  # can't break a build -> cross-lane edits WARN, never block


def _norm(p):
    return (p or "").replace("\\", "/").lstrip("./").rstrip("/")


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # scripts/ -> root


def _current_lane():
    try:
        b = subprocess.run(["git", "branch", "--show-current"],
                           capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return None
    m = re.match(r"lane/(.+)$", b)
    return m.group(1) if m else None


def _load_map():
    try:
        with open(os.path.join(_repo_root(), "parallel_lanes.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _under(path, prefixes):
    p = _norm(path)
    for x in prefixes or []:
        x = _norm(x)
        if p == x or p.startswith(x + "/"):
            return True
    return False


def _ack_present():
    if os.environ.get("LANE_ACK"):
        return True
    return os.path.exists(os.path.join(_repo_root(), ".lane_ack"))


def _decide(lane, path, m, ack):
    """Pure decision. Returns (verdict, concerns) with verdict in silent|warn|block."""
    lanes = m.get("lanes", {})
    if _under(path, lanes.get(lane, [])):
        return ("silent", "")
    if _under(path, m.get("shared", [])):
        return ("warn", "ALL lanes (shared file)")
    owners = [ln for ln, paths in lanes.items() if _under(path, paths)]
    if owners:
        concerns = ", ".join(o.upper() for o in owners)
        soft = all(o in SOFT_LANES for o in owners)  # docs etc. -> warn, not block
        return ("warn" if (ack or soft) else "block", concerns)
    return ("warn", "the SHARED / unowned area")


def main(raw):
    data = json.loads(raw)
    if data.get("tool_name") not in EDIT_TOOLS:
        return 0  # only file-edit tools are lane-scoped; reads are never touched
    ti = data.get("tool_input") or {}
    path = _norm(ti.get("file_path") or ti.get("notebook_path") or "")
    if not path:
        return 0

    lane = _current_lane()
    if not lane:
        return 0  # main / non-lane branch = integrator; allowed to cross

    verdict, concerns = _decide(lane, path, _load_map(), _ack_present())
    if verdict == "silent":
        return 0

    if verdict == "block":
        sys.stderr.write(
            "\n============================================================\n"
            "  CROSS-LANE WRITE BLOCKED  ->  you are in lane: %s\n"
            "============================================================\n"
            "  File:     %s\n"
            "  Concerns: %s\n"
            "  You may WRITE only your own lane (%s) + shared/. Reads are never blocked.\n"
            "  Deliberate? create an empty '.lane_ack' in this worktree, redo the edit,\n"
            "  then delete '.lane_ack'.\n"
            "============================================================\n\n"
            % (lane, path, concerns, lane)
        )
        return 2

    # warn (shared, unowned, or an acked cross-lane edit)
    sys.stderr.write(
        "\n============================================================\n"
        "  CROSS-LANE EDIT (allowed)  ->  you are in lane: %s\n"
        "============================================================\n"
        "  File:     %s\n"
        "  Concerns: %s\n"
        "  If you're actively working any of those lanes, PAUSE them until this edit is done.\n"
        "============================================================\n\n"
        % (lane, path, concerns)
    )
    return 0


if __name__ == "__main__":
    try:
        code = main(sys.stdin.read())
    except Exception:
        code = 0  # never break the workflow on a guard bug
    sys.exit(code)
