#!/usr/bin/env python3
"""PreToolUse SECRET-LEAK guard (Hook 2) -- universal, every project.

Blocks a LIVE secret (API key, token, private key, DB URL with inline password) from being written
into a tracked file or hardcoded into a command -- i.e. anywhere other than the sanctioned secret
stores (secrets.py / .env / .bootstrap_token). Hard-blocks (exit 2) so it works even in bypass mode;
deliberate override via the same `#HIGHRISK-OK` marker. Scans only the text being WRITTEN
(new_string / content / command), never removed text, so deleting a secret is never blocked.

This complements highrisk_guard.py (which path-matches secret FILES). This one looks at CONTENT, so it
catches a key pasted into a normal source file or echoed into a command. Backstop only -- the real
rule (secrets live only in secrets.py, in the -secrets repo) still applies. Honest limit: a denylist
of key shapes is never complete; novel formats slip past.
"""
import sys
import json
import re
import os

OVERRIDE = "#HIGHRISK" + "-OK"

# Sanctioned secret stores: writing a secret HERE is legitimate -> never block.
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
    sys.stderr.write("SECRET-LEAK BLOCKED -- %s\n"
                     "A live secret looks like it is about to be written into a tracked file or "
                     "hardcoded into a command. Secrets belong ONLY in secrets.py / .env. This action "
                     "did NOT run. If it is a placeholder/example or genuinely intended, STOP, say why, "
                     "then re-issue the SAME action with `%s` appended.\n" % (reason, OVERRIDE))
    sys.exit(2)


def written_text(tool, ti):
    """Only the text being WRITTEN (never removed text), so deleting a secret is never blocked."""
    if tool in ("Bash", "PowerShell"):
        return ti.get("command", "") or ""
    if tool == "Write":
        return ti.get("content", "") or ""
    if tool == "Edit":
        return ti.get("new_string", "") or ""
    if tool == "MultiEdit":
        return "\n".join((e.get("new_string", "") or "") for e in (ti.get("edits") or []))
    return ""


def main(raw):
    data = json.loads(raw)
    tool = data.get("tool_name")
    ti = data.get("tool_input")
    if not tool or ti is None:
        raise ValueError("missing tool_name/tool_input")
    if OVERRIDE in raw:
        sys.exit(0)  # deliberate, per-action consent
    # Writes into the sanctioned secret store are legitimate.
    if tool in ("Write", "Edit", "MultiEdit"):
        if ALLOWED_BASENAMES.match(os.path.basename(ti.get("file_path") or "")):
            sys.exit(0)
    label = find_secret(written_text(tool, ti))
    if label:
        hard_block(label)
    sys.exit(0)


if __name__ == "__main__":
    raw = sys.stdin.read()
    try:
        main(raw)
    except Exception:
        # FAIL CLOSED only if a secret is visibly present and no deliberate override.
        if OVERRIDE not in (raw or "") and find_secret(raw or ""):
            hard_block("unparseable request containing a secret (fail-closed)")
        sys.exit(0)
