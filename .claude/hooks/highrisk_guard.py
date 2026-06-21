#!/usr/bin/env python3
"""PreToolUse HIGH-RISK guard (Hook 1) — universal, every project.

Hard-blocks dangerous WRITES. No self-approval marker exists — Bedrock delta 1 (2026-06-10) removed it.
EXCEPTION (2026-06-21): a READ-ONLY command (no write-SQL verb anywhere) is allowed through the
payroll/staff rule only — a SELECT can't corrupt payroll, so read-only investigations no longer need a
manual run. Every WRITE, and every OTHER rule (secrets, rm-rf, prod-restart, destructive-SQL, KHQR…),
stays an unconditional hard block the owner runs manually.

When this guard fires Claude MUST lead the reply with:
  \U0001f6d1 NEEDS YOU — run in your terminal: ! <exact command>

Tool coverage:
  Bash / PowerShell     -> command string  -> CMD_PROTECTED
  Edit / Write / MultiEdit / NotebookEdit  -> file path  -> PATH_PROTECTED

Keeping command-string and file-path checks separate prevents read-only Bash operations
(cat, grep, python) from false-positive blocking on protected filenames.

Honest limit: a denylist is never complete. The real lock for prod data is a staging
Postgres so prod creds are absent from dev. This guard stops accidents and reflexes.
"""
import sys
import json
import re

RX = re.IGNORECASE

# ── Patterns applied to COMMAND strings (Bash / PowerShell) ──────────────────
CMD_PROTECTED = [
    ("destructive SQL",
     re.compile(r"\b(drop\s+table|truncate\b|delete\s+from|drop\s+database|alter\s+table\b.*\bdrop\b)", RX)),
    ("DB migration",
     re.compile(r"\b(alembic\s+(?:upgrade|downgrade|stamp)\b|init_attendance_db\b|psql\b[^|;&\n]*\.sql\b)", RX)),
    ("rm -rf / recursive del",
     re.compile(r"\brm\s+-[a-z]*r[a-z]*f\b|\brm\s+-[a-z]*f[a-z]*r\b|\brm\s+-rf\b|remove-item\b.*-recurse", RX)),
    ("force / destructive git",
     re.compile(r"git\s+push\b[^|;&\n]*--force|git\s+reset\s+--hard|git\s+clean\s+-[a-z]*f|filter-branch", RX)),
    ("prod stop/disable, or restart of a non-app service",
     re.compile(r"systemctl\s+(?:stop|disable)\s+(?!twbshop-)\S"            # stop/disable anything stays blocked
                r"|systemctl\s+restart\s+(?!twbshop-)\S"    # restart of a NON-twbshop service
                r"|\bservice\s+\S+\s+(restart|stop)\b",     # old init-style service mgmt
                RX)),
    ("write to secret / session / guard file via shell",
     re.compile(
         r"(?:set-content|out-file|add-content)\b[^\n|;]*"
         r"(?:secrets\.py|\.env\b|\.bootstrap_token|\.session\b|\.claude[\\/])"
         r"|>+\s*['\"]?[^\n|;]*?(?:secrets\.py|\.env\b|\.bootstrap_token|\.session\b|\.claude[\\/])"
         r"|\btee\b[^\n|;]*(?:secrets\.py|\.env|\.bootstrap_token|\.session|\.claude[\\/])"
         r"|\bsed\s+-i\b[^\n|;]*(?:secrets\.py|config\.py|\.session\b)"
         r"|\bcopy-item\b[^\n|;]*\.claude[\\/]"            # block Copy-Item into .claude (close the loophole)
         r"|\bcp\b[^\n|;]*\.claude[\\/]",
         RX)),
    ("payments / KHQR / Bakong",
     re.compile(r"\b(khqr|bakong)\b", RX)),
    ("payroll / salary / staff_registry",
     re.compile(r"\b(payroll|salary|first_pay|second_pay|bonus_usd|staff_registry)\b", RX)),
    ("permissions / ban / offboard",
     re.compile(r"\b(ban_chat_member|kickchatmember|unban|exstaff|offboard|ban_users?)\b", RX)),
]

# A command is READ-ONLY when it carries no write-SQL verb. Read-only staff/payroll lookups are allowed
# (a SELECT can't corrupt payroll); any write keeps the hard block. Word boundaries keep 'updated_at' /
# 'created_at' / 'deleted' from counting as writes, while UPDATE/INSERT/DELETE/DROP/… anywhere do.
WRITE_SQL = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|merge|upsert|replace|copy)\b"
    r"|on\s+conflict", RX)

# Only this rule may be bypassed for a read-only command (a SELECT can't corrupt it). Everything else
# (secrets, rm-rf, prod-restart, destructive-SQL, KHQR, permissions) hard-blocks even on a read.
READONLY_BYPASS = ("payroll",)

# ── Patterns applied to FILE PATHS (Edit / Write / MultiEdit / NotebookEdit) ─
PATH_PROTECTED = [
    ("write to secret store",
     re.compile(r"(?:^|[\\/])(secrets\.py|\.bootstrap_token|\.env\b|\.env\.[^/\\\s]+)$", RX)),
    ("write to .claude guard / settings",
     re.compile(r"\.claude[\\/](settings\.json|hooks[\\/])", RX)),
    ("write to .session",
     re.compile(r"(?:^|[\\/])\.session\b", RX)),
    ("write to config.py",
     re.compile(r"(?:^|[\\/])config\.py$", RX)),
]

# Broad keyword fallback — only for fail-closed on unrecognized tools
KEYWORDS = re.compile(
    r"(drop\s+table|truncate|delete\s+from|\brm\s+-[a-z]*[rf]|--force|reset\s+--hard|"
    r"systemctl\s+(restart|stop)|secrets\.py|\.session|payroll|salary|"
    r"khqr|bakong|migrate|staff_registry|\.claude[\\/]settings)",
    RX)


def _descan_commit(cmd):
    """A git commit MESSAGE is descriptive text, not an action — but it lives in the command string,
    so words like 'rm -rf' or 'systemctl stop' inside it false-trigger the action patterns. For a
    `git commit`, blank the LITERAL message text so it isn't scanned, while leaving everything ELSE
    fully scanned (a real `; <danger>` after the commit is still caught). Blanked (literal — nothing
    executes inside): a cat-fed command-substitution heredoc "$(cat <<'EOF' ... EOF)"; a single-quoted
    -m '...'; a double-quoted -m "..." with NO substitution. NOT touched: a double-quoted -m holding
    $(...)/`...`, and any heredoc not fed to cat (psql/bash heredocs stay scanned). Only suppresses
    false positives — it never hides an executed command."""
    if not re.search(r"\bgit\s+commit\b", cmd, RX):
        return cmd
    cmd = re.sub(r"\$\(\s*cat\s+<<-?\s*'(\w+)'[^\n]*\n.*?\n[ \t]*\1\b",
                 "$(cat <<'MSG'\nMSG", cmd, flags=re.S)
    cmd = re.sub(r"(--message|-m)(=|\s+)'[^']*'", r"\1\2''", cmd)
    cmd = re.sub(r'(--message|-m)(=|\s+)"([^"`]*)"',
                 lambda m: m.group(0) if ("$(" in m.group(3) or "${" in m.group(3))
                 else '%s%s""' % (m.group(1), m.group(2)), cmd)
    return cmd


def hard_block(reason, cmd=""):
    cmd = (cmd or "").strip()
    paste = ("  ! " + cmd + "\n") if cmd else ""
    sys.stderr.write(
        "\U0001f6d1 HIGH-RISK BLOCKED — %s\n"
        "This action did NOT run. No override exists — owner must run it manually.\n"
        "%s"
        % (reason, paste)
    )
    sys.exit(2)


def main(raw):
    data = json.loads(raw)
    tool = data.get("tool_name")
    ti = data.get("tool_input")
    if not tool or ti is None:
        raise ValueError("missing tool_name / tool_input")

    if tool in ("Bash", "PowerShell"):
        cmd = ti.get("command", "") or ""
        scan = _descan_commit(cmd)   # a git-commit MESSAGE is prose, not an action — don't scan it
        readonly = WRITE_SQL.search(scan) is None   # a pure read — no write-SQL verb anywhere
        for label, rx in CMD_PROTECTED:
            if rx.search(scan):
                # Read-only staff/payroll LOOKUPS are safe (a SELECT can't corrupt payroll) — allow them
                # so investigations don't need a manual run; every WRITE + every other rule stays blocked.
                if readonly and label.startswith(READONLY_BYPASS):
                    continue
                hard_block(label, cmd)

    elif tool in ("Edit", "Write", "MultiEdit"):
        path = ti.get("file_path", "") or ""
        for label, rx in PATH_PROTECTED:
            if rx.search(path):
                hard_block(label, "# Attempted write: " + path)

    elif tool == "NotebookEdit":
        path = ti.get("notebook_path", "") or ""
        for label, rx in PATH_PROTECTED:
            if rx.search(path):
                hard_block(label, "# Attempted notebook write: " + path)

    else:
        if KEYWORDS.search(raw):
            hard_block("unrecognized tool touching a protected surface (fail-closed)", "")

    sys.exit(0)


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception:
        raw = sys.stdin.read()
    try:
        main(raw)
    except Exception as e:
        if KEYWORDS.search(raw or ""):
            hard_block(
                "guard could not classify a protected-looking request: %s" % type(e).__name__, ""
            )
        sys.exit(0)
