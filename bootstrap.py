"""
bootstrap.py — run on any new machine, or to sync latest secrets after a pull.

Modes:
  python bootstrap.py               — full setup (first time on a new machine)
  python bootstrap.py --sync        — refresh secrets + SSH key + global CLAUDE.md (silent)
  python bootstrap.py --push-global — push ~/.claude/CLAUDE.md to secrets repo via API (no cloning)

--sync runs automatically on every pull via the post-rewrite git hook.
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
    print("→ https://github.com/settings/tokens/new?scopes=repo&description=bootstrap")
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


def push_file(token, filename, content_bytes, message="sync"):
    """Update or create a file in the secrets repo via GitHub API. No cloning needed."""
    url = f"https://api.github.com/repos/{SECRETS_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    sha = None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as r:
            sha = json.loads(r.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            sys.exit(f"GitHub API error {e.code}: {e.reason}")
    body = {"message": message, "content": base64.b64encode(content_bytes).decode()}
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="PUT")
    with urllib.request.urlopen(req):
        pass


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


def sync(silent=False):
    """Download latest secrets, SSH key, and global CLAUDE.md. Fast and always safe to run."""
    token = get_token()
    os.makedirs(SSH_DIR, exist_ok=True)
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    for filename, dest in SYNC_FILES:
        if not silent:
            print(f"  Syncing {filename} ...", end=" ", flush=True)
        content = fetch_file(token, filename)
        with open(dest, "wb") as f:
            f.write(content)
        if "twbshop_server" in filename and ".pub" not in filename:
            set_permissions(dest, stat.S_IRUSR | stat.S_IWUSR)
        if not silent:
            print("done")
    _write_ssh_config()


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
    elif "--push-global" in sys.argv:
        token = get_token()
        claude_md = os.path.join(CLAUDE_DIR, "CLAUDE.md")
        with open(claude_md, "rb") as f:
            content = f.read()
        push_file(token, "global_claude.md", content, "sync global CLAUDE.md")
        print("global_claude.md updated in secrets repo.")
    else:
        full_setup()
