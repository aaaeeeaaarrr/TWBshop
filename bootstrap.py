"""
bootstrap.py — run on any new machine, or to sync latest secrets after a pull.

Modes:
  python bootstrap.py                — full setup (first time on a new machine)
  python bootstrap.py --sync         — refresh secrets + SSH key + global CLAUDE.md (silent)
  python bootstrap.py --push-global  — push ~/.claude/CLAUDE.md to secrets repo via API (no cloning)
  python bootstrap.py --push-secrets — push THIS machine's secrets.py up to the secrets repo so
                                       every other machine gets it on the next pull. Run this any
                                       time you add/change a key in secrets.py.

--sync runs automatically on every pull via the post-rewrite git hook.
--sync REFUSES to overwrite a local secrets.py whose keys are missing from the repo copy
(prevents silently losing a secret you added locally but forgot to --push-secrets).
"""

import base64
import json
import os
import platform
import stat
import subprocess
import sys
import urllib.request

SECRETS_REPO = "aaaeeeaaarrr/twbshop-secrets"
TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".bootstrap_token")
SSH_DIR = os.path.expanduser("~/.ssh")
SSH_CONFIG = os.path.expanduser("~/.ssh/config")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.path.expanduser("~/.claude")

SSH_CONFIG_ENTRY = """
Host twbshop
    HostName 129.212.228.102
    User root
    IdentityFile ~/.ssh/twbshop_server
    AddKeysToAgent yes
    StrictHostKeyChecking no
"""

# Files synced on every pull (--sync mode). .pub not needed — key is on the server already.
SYNC_FILES = [
    ("secrets.py",       os.path.join(PROJECT_DIR, "secrets.py")),
    ("twbshop_server",   os.path.join(SSH_DIR, "twbshop_server")),
    ("global_claude.md", os.path.join(CLAUDE_DIR, "CLAUDE.md")),
]


def get_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            token = f.read().strip()
        if token:
            return token
    print("\nA GitHub Personal Access Token (PAT) is required.")
    print("Create one here (repo scope pre-checked, just click Generate Token):")
    print("-> https://github.com/settings/tokens/new?scopes=repo&description=bootstrap")
    print("  Set expiry to: No expiration\n")
    token = input("Paste your GitHub PAT here: ").strip()
    if not token:
        sys.exit("No token provided. Aborting.")
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    print(f"Token saved to {TOKEN_FILE} (gitignored — stays on this machine only).\n")
    return token


def fetch_file(token, filename):
    url = f"https://api.github.com/repos/{SECRETS_REPO}/contents/{filename}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            os.remove(TOKEN_FILE)
            sys.exit("GitHub token rejected (401). Deleted cached token — run bootstrap.py again.")
        if e.code == 404:
            sys.exit(f"File '{filename}' not found in {SECRETS_REPO}.")
        sys.exit(f"GitHub API error {e.code}: {e.reason}")
    return base64.b64decode(data["content"])


def set_permissions(path, mode):
    if platform.system() != "Windows":
        os.chmod(path, mode)


def _write_ssh_config():
    """Add twbshop SSH alias to ~/.ssh/config if not already there."""
    existing = ""
    if os.path.exists(SSH_CONFIG):
        with open(SSH_CONFIG, encoding="utf-8") as f:
            existing = f.read()
    if "Host twbshop" not in existing:
        with open(SSH_CONFIG, "a", encoding="utf-8") as f:
            f.write(SSH_CONFIG_ENTRY)


# Guard hooks installed GLOBALLY (filename in .claude/hooks/, matcher). Source of truth = this repo.
# To add a future guardrail: drop its script in .claude/hooks/ and append one line here.
GLOBAL_GUARDS = [
    ("highrisk_guard.py", "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit"),
    ("secret_guard.py",   "Bash|PowerShell|Edit|Write|MultiEdit"),
]


def _ensure_global_guards():
    """Install the guard hooks GLOBALLY so every project on this machine inherits them.

    Copies each repo guard script to ~/.claude/hooks/ and merges its PreToolUse hook into
    ~/.claude/settings.json. Idempotent (refreshes in place, never duplicates) and non-destructive
    (preserves every other setting/hook; backs up to settings.json.bak first). BEST-EFFORT: any
    failure is swallowed so it can NEVER break a pull (this runs on every pull via --sync). Guards
    activate on the NEXT session start (Claude loads hook config at startup). Same scripts also live
    in TWBshop/.claude/ as self-contained copies.
    """
    try:
        hooks_dir = os.path.join(CLAUDE_DIR, "hooks")
        os.makedirs(hooks_dir, exist_ok=True)
        installed = []  # (matcher, dest)
        for name, matcher in GLOBAL_GUARDS:
            src = os.path.join(PROJECT_DIR, ".claude", "hooks", name)
            if not os.path.exists(src):
                continue
            dest = os.path.join(hooks_dir, name)
            with open(src, "rb") as f:
                data = f.read()
            with open(dest, "wb") as f:
                f.write(data)
            installed.append((matcher, dest))
        if not installed:
            return

        settings_path = os.path.join(CLAUDE_DIR, "settings.json")
        settings = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path, encoding="utf-8") as f:
                    settings = json.load(f)
            except (ValueError, OSError):
                return  # unreadable/corrupt -> do NOT risk clobbering it
            try:  # one-time backup before we touch it
                with open(settings_path, encoding="utf-8") as f:
                    raw = f.read()
                with open(settings_path + ".bak", "w", encoding="utf-8") as f:
                    f.write(raw)
            except OSError:
                pass

        our_files = {n for n, _ in GLOBAL_GUARDS}
        hooks = settings.setdefault("hooks", {})
        pre = hooks.get("PreToolUse", [])
        # Drop any prior entry for ANY of our guards (idempotent + path refresh); keep all others.
        pre = [e for e in pre
               if not any(any(fn in h.get("command", "") for fn in our_files)
                          for h in e.get("hooks", []))]
        for matcher, dest in installed:
            pre.append({
                "matcher": matcher,
                "hooks": [{"type": "command", "command": 'python "%s"' % dest.replace(os.sep, "/")}],
            })
        hooks["PreToolUse"] = pre

        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass  # never break a pull


def _secret_keys(content):
    """Top-level assignment names in a secrets.py (bytes) — e.g. {'DATABASE_URL', ...}."""
    import re
    text = content.decode("utf-8", "replace")
    return set(re.findall(r"(?m)^([A-Z_][A-Z0-9_]*)\s*=", text))


def sync(silent=False):
    """Download latest secrets, SSH key, and global CLAUDE.md. Fast and always safe to run."""
    token = get_token()
    os.makedirs(SSH_DIR, exist_ok=True)
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    for filename, dest in SYNC_FILES:
        if not silent:
            print(f"  Syncing {filename} ...", end=" ", flush=True)
        content = fetch_file(token, filename)
        # Guard: never silently clobber a secret this machine has but the repo doesn't.
        if filename == "secrets.py" and os.path.exists(dest):
            with open(dest, "rb") as f:
                local_keys = _secret_keys(f.read())
            missing = local_keys - _secret_keys(content)
            if missing:
                if not silent:
                    print("SKIPPED")
                print("\n  ⚠ Local secrets.py has keys the repo copy is MISSING: "
                      + ", ".join(sorted(missing)))
                print("    NOT overwriting (would lose them). Run: python bootstrap.py "
                      "--push-secrets  to upload them first, then pull again.\n")
                continue
        with open(dest, "wb") as f:
            f.write(content)
        if "twbshop_server" in filename and ".pub" not in filename:
            set_permissions(dest, stat.S_IRUSR | stat.S_IWUSR)
        if not silent:
            print("done")
    _write_ssh_config()
    _ensure_global_guards()


def full_setup():
    """Full first-time machine setup."""
    print("=" * 55)
    print("  TWBshop Bootstrap")
    print("=" * 55)

    print("\nDownloading secrets and keys...")
    sync(silent=False)

    req_file = os.path.join(PROJECT_DIR, "requirements.txt")
    if os.path.exists(req_file):
        print("\nInstalling pip requirements ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file, "-q"])
        print("done")

    for d in ["logs", "photos"]:
        os.makedirs(os.path.join(PROJECT_DIR, d), exist_ok=True)

    subprocess.call(["git", "config", "core.hooksPath", ".githooks"], cwd=PROJECT_DIR)

    print("\n" + "=" * 55)
    print("  Bootstrap complete!")
    print("=" * 55)
    print("\nAll secrets and SSH key are in place.")
    print("Git hook activated — future pulls will remind you automatically.")
    print("\nNext steps:")
    print("  Retail bot : python run_bot.py")
    print("  B2B bot    : python run_b2b_bot.py")
    print()


if __name__ == "__main__":
    if "--sync" in sys.argv:
        sync(silent=True)
    elif "--push-secrets" in sys.argv:
        local_secrets = os.path.join(PROJECT_DIR, "secrets.py")
        with open(local_secrets, "rb") as f:
            raw = f.read()
        content = base64.b64encode(raw).decode()
        sha_result = subprocess.run(
            ["gh", "api", f"/repos/{SECRETS_REPO}/contents/secrets.py", "--jq", ".sha"],
            capture_output=True, text=True,
        )
        sha = sha_result.stdout.strip()
        args = ["gh", "api", "--method", "PUT",
                f"/repos/{SECRETS_REPO}/contents/secrets.py",
                "-f", "message=sync secrets.py",
                "-f", f"content={content}"]
        if sha:
            args += ["-f", f"sha={sha}"]
        subprocess.check_call(args, stdout=subprocess.DEVNULL)
        print(f"secrets.py pushed to {SECRETS_REPO} ({len(_secret_keys(raw))} keys). "
              "Other machines get it on next pull.")
    elif "--push-global" in sys.argv:
        claude_md = os.path.join(CLAUDE_DIR, "CLAUDE.md")
        with open(claude_md, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        # Get current SHA (required by GitHub API for updates)
        sha_result = subprocess.run(
            ["gh", "api", f"/repos/{SECRETS_REPO}/contents/global_claude.md", "--jq", ".sha"],
            capture_output=True, text=True,
        )
        sha = sha_result.stdout.strip()
        args = ["gh", "api", "--method", "PUT",
                f"/repos/{SECRETS_REPO}/contents/global_claude.md",
                "-f", "message=sync global CLAUDE.md",
                "-f", f"content={content}"]
        if sha:
            args += ["-f", f"sha={sha}"]
        subprocess.check_call(args, stdout=subprocess.DEVNULL)
        print("global_claude.md updated in secrets repo.")
    else:
        full_setup()
