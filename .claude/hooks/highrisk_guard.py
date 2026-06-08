#!/usr/bin/env python3
"""PreToolUse HIGH-RISK guard (Hook 1) — TWBshop.

Per-action approval for dangerous actions. Reads the Claude Code hook JSON on stdin and emits a
PreToolUse permission decision:
  - "ask"  -> classified HIGH-RISK: the user must approve THIS exact action (no session-wide bypass,
              no persisted 'always allow'). Claude cannot answer the prompt itself.
  - "deny" -> FAIL-CLOSED: input we could not parse / classify that still looks like it touches a
              protected surface. Safer to block than to let it through.
  - (silent exit 0) -> everything else flows through the normal permission system unchanged.

Design rules honored:
  * FAIL CLOSED: a parse error / missing fields on a protected-looking request -> deny, never
    silently allow. (A clean, recognized, clearly-safe command is still allowed so normal work
    isn't bricked.)
  * Inspects BOTH Bash commands AND Edit/Write/MultiEdit file paths (a denylist leaks via Bash:
    sed -i / cat > / tee / redirections are matched in the command string too).
  * No "always allow" is ever emitted for HIGH-RISK; it asks every time.
NOTE (honest): a denylist is never complete. The real lock for the prod DB is a staging/local
Postgres so prod creds aren't in dev — see the dated backlog note in CLAUDE.md. This is the backstop.
"""
import sys
import json
import re

# ---- HIGH-RISK patterns (case-insensitive). Match -> "ask" (per-action approval). ----
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


def decide(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def classify(tool, tool_input):
    """Return the text to inspect for a recognized tool, or None if we can't (fail-closed upstream)."""
    if tool == "Bash":
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
        if KEYWORDS.search(raw):
            decide("deny", "unrecognized tool touching a protected surface (fail-closed)")
        sys.exit(0)
    for label, rx in PROTECTED:
        if rx.search(text):
            decide("ask", "HIGH-RISK (%s) — approve this exact action. No session-wide bypass." % label)
    sys.exit(0)  # clean, recognized, not protected -> allow via normal flow


if __name__ == "__main__":
    raw = sys.stdin.read()
    try:
        main(raw)
    except Exception as e:
        # FAIL CLOSED: couldn't parse/classify. Block only if it looks protected; else don't brick work.
        if KEYWORDS.search(raw or ""):
            decide("deny", "guard could not classify a protected-looking request (fail-closed): %s"
                   % type(e).__name__)
        sys.exit(0)
