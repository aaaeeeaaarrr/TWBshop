#!/usr/bin/env python3
"""PreToolUse HIGH-RISK guard (Hook 1) -- TWBshop.

Stops dangerous actions. Reads the Claude Code hook JSON on stdin and decides:
  - HARD BLOCK (exit 2)  -> classified HIGH-RISK. The action does NOT run; the reason is fed back to
        Claude, which must STOP, explain what it is about to do and why, and only then re-issue the
        SAME command WITH the deliberate per-action override marker (see OVERRIDE below).
  - ALLOW (exit 0, silent) -> the override marker is deliberately present, OR the action is not
        HIGH-RISK. The override is per-action and auditable (it appears in the command), never a
        session-wide bypass.
  - FAIL CLOSED (exit 2) -> input we could not parse/classify that still looks protected. Block.

WHY HARD BLOCK IN EVERY MODE (not "ask"): the owner runs Claude in a permission-bypass mode AND (by
their own account) approves every prompt reflexively -- so an "ask" prompt protects nothing, in any
mode. Only exit 2 actually stops an action (proven, session 31). Protection therefore lives OFF the
human rubber-stamp and ON a hard stop that accidents/reflexes/runaways cannot pass: they don't carry
the deliberate OVERRIDE marker. Claude must consciously add it after articulating the risk. Covers the
Bash AND PowerShell tools (deploys run via PowerShell on Windows) plus Edit/Write/MultiEdit paths.

NOTE (honest): a denylist is never complete, and this still trusts Claude's *deliberate* judgement
(it adds the marker). The REAL lock for prod data is a staging/local Postgres so prod creds aren't in
dev -- see the dated backlog note in CLAUDE.md. This guard is the backstop against accidents + reflex.
"""
import sys
import json
import re

# Deliberate per-action consent marker. Built by concatenation so the literal token does NOT appear
# verbatim in this file -- editing this guard does not accidentally carry its own override.
OVERRIDE = "#HIGHRISK" + "-OK"

# ---- HIGH-RISK patterns (case-insensitive). ----
RX = re.IGNORECASE
PROTECTED = [
    ("destructive SQL",        re.compile(r"\b(drop\s+table|truncate\b|delete\s+from|drop\s+database|alter\s+table\b.*\bdrop\b)", RX)),
    ("DB migration",           re.compile(r"\b(migrate|alembic|init_attendance_db|\.sql\b|psql\b)", RX)),
    ("rm -rf / recursive del", re.compile(r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r|\brm\s+-rf\b|remove-item\b.*-recurse", RX)),
    ("force/destructive git",  re.compile(r"git\s+push\b[^|;&]*--force|git\s+reset\s+--hard|git\s+clean\s+-[a-z]*f|filter-branch", RX)),
    ("prod deploy / restart",  re.compile(r"systemctl\s+(restart|stop|disable)\b|service\s+\S+\s+(restart|stop)\b", RX)),
    ("secrets/session/config", re.compile(r"(secrets\.py|\.session\b|config\.py|\.bootstrap_token|\.env\b|\.claude[\\/](settings\.json|hooks[\\/]))", RX)),
    ("bash write-redirect",    re.compile(r"\bsed\s+-i\b|\btee\b|>\s*\S*(secrets|config|payroll|payment|salary|\.session)|\bcat\s*>|<<\s*['\"]?\w+['\"]?\s*>", RX)),
    ("powershell write",       re.compile(r"\b(set-content|out-file|add-content)\b", RX)),
    ("payments KHQR/Bakong",   re.compile(r"\b(khqr|bakong|payment)\b", RX)),
    ("payroll/salary/staff",   re.compile(r"(payroll|salary|first_pay|second_pay|bonus_usd|staff_registry)", RX)),
    ("permissions/ban/offboard", re.compile(r"\b(ban_chat_member|kickchatmember|unban|exstaff|offboard|ban_users?)\b", RX)),
]
# Broad keyword net used ONLY for the fail-closed raw fallback (parse failed / fields missing).
KEYWORDS = re.compile(r"(drop\s+table|truncate|delete\s+from|\brm\s+-[a-z]*[rf]|--force|reset\s+--hard|"
                      r"systemctl\s+(restart|stop)|secrets\.py|\.session|config\.py|payroll|salary|"
                      r"khqr|bakong|migrate|staff_registry|\.claude[\\/]settings)", RX)


def hard_block(reason):
    """Exit 2 = blocking error. The only decision proven to stop an action in bypass mode."""
    sys.stderr.write("HIGH-RISK BLOCKED -- %s\n"
                     "This action did NOT run. It is irreversible/sensitive, so it is hard-blocked in "
                     "every mode. To proceed: STOP, state plainly what you are about to do and why, then "
                     "re-issue the SAME command with the marker `%s` appended (deliberate, per-action "
                     "consent). Accidents/reflexes never carry the marker.\n"
                     % (reason, OVERRIDE))
    sys.exit(2)


def classify(tool, tool_input):
    """Return the text to inspect for a recognized tool, or None if we can't (fail-closed upstream)."""
    if tool in ("Bash", "PowerShell"):
        return tool_input.get("command", "") or ""
    if tool in ("Edit", "Write", "MultiEdit"):
        return tool_input.get("file_path", "") or ""
    if tool == "NotebookEdit":
        return tool_input.get("notebook_path", "") or ""
    return None  # unrecognized tool -> fail-closed fallback


def main(raw):
    data = json.loads(raw)                      # JSONDecodeError -> caught -> fail-closed
    tool = data.get("tool_name")
    tool_input = data.get("tool_input")
    if not tool or tool_input is None:
        raise ValueError("missing tool_name/tool_input")   # -> fail-closed fallback
    text = classify(tool, tool_input)
    if text is None:
        # unrecognized tool: only block if it smells protected, else let normal flow handle it
        if KEYWORDS.search(raw) and OVERRIDE not in raw:
            hard_block("unrecognized tool touching a protected surface (fail-closed)")
        sys.exit(0)
    if OVERRIDE in raw:
        sys.exit(0)  # deliberate, per-action consent present -> allow
    for label, rx in PROTECTED:
        if rx.search(text):
            hard_block("HIGH-RISK (%s)" % label)
    sys.exit(0)  # clean, recognized, not protected -> allow via normal flow


if __name__ == "__main__":
    raw = sys.stdin.read()
    try:
        main(raw)
    except Exception as e:
        # FAIL CLOSED: couldn't parse/classify. Block only if it looks protected; else don't brick work.
        if KEYWORDS.search(raw or "") and OVERRIDE not in (raw or ""):
            hard_block("guard could not classify a protected-looking request (fail-closed): %s"
                       % type(e).__name__)
        sys.exit(0)
