#!/usr/bin/env python3
"""PreToolUse SECRET-LEAK guard (Hook 2) — universal, every project.

Blocks a live secret (API key, token, private key, DB URL with password) from being written
into a tracked file or hardcoded into a command. Also scans staged changes before git commit
and unpushed commits before git push (Bedrock delta 3, 2026-06-10).

No override — Bedrock delta 1 removed the self-approval marker. Every block is unconditional.

Scans only text being WRITTEN (new_string / content / command), never removed text, so
deleting a secret is never blocked.

Honest limit: a denylist of key shapes is never complete; novel formats slip past. The real
rule — secrets live only in secrets.py / .env, in the -secrets repo — still applies.
"""
import sys
import json
import re
import os
import subprocess

# Sanctioned secret stores — writing a known-shaped secret here is legitimate; never block.
ALLOWED_BASENAMES = re.compile(r"^(secrets\.py|\.env|\.env\.[\w.-]+|\.bootstrap_token)$", re.I)

SECRET_PATTERNS = [
    ("private key block",  re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("AWS access key id",  re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Anthropic key",      re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI-style key",   re.compile(r"\bsk-[A-Za-z0-9]{40,}\b")),
    ("GitHub token",       re.compile(r"\bghp_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("Google API key",     re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Slack token",        re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Telegram bot token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b")),
    ("DB URL w/ password", re.compile(r"\b(postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s:/@]+:[^\s/@]+@", re.I)),
]


def find_secret(text):
    for label, rx in SECRET_PATTERNS:
        if rx.search(text):
            return label
    return None


def hard_block(reason):
    sys.stderr.write(
        "\U0001f6d1 SECRET-LEAK BLOCKED — %s\n"
        "A live secret looks like it is about to be written into a tracked file or command.\n"
        "Secrets belong ONLY in secrets.py / .env. This action did NOT run. No override exists.\n"
        % reason
    )
    sys.exit(2)


def written_text(tool, ti):
    """Only text being WRITTEN (never removed text) — deleting a secret is never blocked."""
    if tool in ("Bash", "PowerShell"):
        return ti.get("command", "") or ""
    if tool == "Write":
        return ti.get("content", "") or ""
    if tool == "Edit":
        return ti.get("new_string", "") or ""
    if tool == "MultiEdit":
        return "\n".join((e.get("new_string", "") or "") for e in (ti.get("edits") or []))
    return ""


def scan_git_diff(git_args, timeout=15):
    """Run a git diff command and scan added lines for secrets. Returns label or None."""
    try:
        result = subprocess.run(
            git_args, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        if result.returncode != 0:
            return None
        added = "\n".join(
            line[1:] for line in result.stdout.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        return find_secret(added) if added else None
    except Exception:
        return None


def main(raw):
    data = json.loads(raw)
    tool = data.get("tool_name")
    ti = data.get("tool_input")
    if not tool or ti is None:
        raise ValueError("missing tool_name / tool_input")

    # Before git commit: scan staged changes for secrets.
    # Before git push: scan unpushed commits for secrets.
    if tool in ("Bash", "PowerShell"):
        cmd = ti.get("command", "") or ""
        if re.search(r"\bgit\s+commit\b", cmd, re.IGNORECASE):
            label = scan_git_diff(["git", "diff", "--cached", "--unified=0"])
            if label:
                hard_block("staged changes contain a %s — commit blocked" % label)
        elif re.search(r"\bgit\s+push\b", cmd, re.IGNORECASE):
            label = scan_git_diff(
                ["git", "log", "--all", "--not", "--remotes", "-p", "--unified=0"],
                timeout=20,
            )
            if label:
                hard_block("unpushed commits contain a %s — push blocked" % label)

    # Writes into the sanctioned secret store are legitimate.
    if tool in ("Write", "Edit", "MultiEdit"):
        if ALLOWED_BASENAMES.match(os.path.basename(ti.get("file_path") or "")):
            sys.exit(0)

    label = find_secret(written_text(tool, ti))
    if label:
        hard_block(label)
    sys.exit(0)


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception:
        raw = sys.stdin.read()
    try:
        main(raw)
    except Exception:
        if find_secret(raw or ""):
            hard_block("unparseable request containing a secret (fail-closed)")
        sys.exit(0)
