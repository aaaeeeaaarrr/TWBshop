#!/usr/bin/env python3
"""PreToolUse LANE GUARD (v3) — read any lane, write only your own + shared.

Reads parallel_lanes.json. Derives THIS worktree's lane from its git branch (lane/<name>).
Fires only on file-EDIT tools (Edit/Write/MultiEdit/NotebookEdit) — READS are NEVER touched.
  - your own lane            -> silent.
  - a SHARED file            -> WARN (loud banner), allowed; coordinate the lanes.
  - ANOTHER lane's file      -> BLOCK (exit 2) unless `.lane_ack` is present.
  - an unowned/new file      -> WARN, allowed.
  - on main / non-lane branch-> silent (you're the integrator).
  - `docs` is a SOFT lane    -> WARN, never block (docs can't break a build).

v3 adds two things so a crossing actually REACHES YOU instead of relying on the lane's Claude to
relay it: (1) a LOUD banner; (2) every cross-lane edit is appended to ~/.twbshop_lane_events.jsonl
(a shared sink OUTSIDE all worktrees) which the monitor bot reads and DMs you (with red lights).

ACK (deliberate cross-lane WRITE): create an empty `.lane_ack` in this worktree, redo the edit,
then delete it. SAFETY: on its OWN error it exits 0 (a guard bug must never lock the workflow).
ASCII-only banner (a Windows console can't encode emoji — the red lights live in the Telegram DM).
"""
import json
import os
import re
import subprocess
import sys
import time

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SOFT_LANES = {"docs"}        # can't break a build -> cross-lane edits WARN, never block
HUB_ONLY = {"CLAUDE.md"}     # hub-owned: lanes put notes in CLAUDE.local.md, never the tracked file
EVENTS_FILE = os.path.expanduser("~/.twbshop_lane_events.jsonl")  # shared sink, outside all worktrees


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
    if _norm(path) in HUB_ONLY:                       # CLAUDE.md etc. — lanes are blocked outright
        return ("warn" if ack else "block", "HUB-ONLY (put lane notes in CLAUDE.local.md)")
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


def _log_event(lane, verdict, path, concerns):
    """Append a cross-lane event to the shared sink so the monitor can DM the owner. Fail-safe."""
    try:
        rec = {"ts": time.time(), "lane": lane, "verdict": verdict,
               "file": path, "concerns": concerns}
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass  # never break the workflow


def _banner(verdict, lane, path, concerns):
    hint = ""
    if _norm(path) == "CLAUDE.md":
        hint = ("\n     NOTE: lane notes go in CLAUDE.local.md (gitignored) - never the tracked "
                "CLAUDE.md.\n           Only the HUB (main) edits CLAUDE.md.")
    if verdict == "block":
        return (
            "\n\n"
            "  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "  !!!                                                        !!!\n"
            "  !!!     >>>>   CROSS-LANE WRITE   * B L O C K E D *   <<<<  !!!\n"
            "  !!!                                                        !!!\n"
            "  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "     you are in lane:  %s\n"
            "     tried to WRITE:   %s\n"
            "     which belongs to: %s\n"
            "     >> you may WRITE only your own lane (%s) + shared/.  reads are always fine.\n"
            "     >> deliberate? create '.lane_ack' in this worktree, redo the edit, then delete it.%s\n"
            "  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n"
            % (lane, path, concerns, lane, hint)
        )
    return (
        "\n\n"
        "  ==============================================================\n"
        "  >>>>   CROSS-LANE EDIT  (allowed)   --   HEADS UP   <<<<\n"
        "  ==============================================================\n"
        "     you are in lane:  %s\n"
        "     editing SHARED:   %s\n"
        "     concerns:         %s\n"
        "     >> if you're actively working those lanes, PAUSE them + coordinate the merge.%s\n"
        "  ==============================================================\n\n"
        % (lane, path, concerns, hint)
    )


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

    _log_event(lane, verdict, path, concerns)        # -> monitor DMs you (red lights in Telegram)
    sys.stderr.write(_banner(verdict, lane, path, concerns))
    return 2 if verdict == "block" else 0


if __name__ == "__main__":
    try:
        code = main(sys.stdin.read())
    except Exception:
        code = 0  # never break the workflow on a guard bug
    sys.exit(code)
