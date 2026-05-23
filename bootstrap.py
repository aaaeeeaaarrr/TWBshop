"""
bootstrap.py — run this once on any new machine to set up TWBshop.

What it does:
  1. Downloads secrets.py (API keys, tokens) → project root
  2. Downloads SSH private key → ~/.ssh/twbshop_server  (chmod 600)
  3. Installs pip requirements
  4. Creates required directories (logs/, photos/)

You need ONE thing: a GitHub Personal Access Token (PAT) with 'repo' scope.
Create one at: https://github.com/settings/tokens
The token is stored locally in .bootstrap_token (gitignored) so you only type it once per machine.
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
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

FILES = [
    # (filename in secrets repo, destination path)
    ("secrets.py",        os.path.join(PROJECT_DIR, "secrets.py")),
    ("twbshop_server",    os.path.join(SSH_DIR, "twbshop_server")),
    ("twbshop_server.pub",os.path.join(SSH_DIR, "twbshop_server.pub")),
]


def get_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            token = f.read().strip()
        if token:
            return token
    print("\nA GitHub Personal Access Token (PAT) with 'repo' scope is required.")
    print("Create one at: https://github.com/settings/tokens\n")
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
            sys.exit("GitHub token rejected (401). Deleted cached token — run bootstrap.py again with a valid token.")
        if e.code == 404:
            sys.exit(f"File '{filename}' not found in {SECRETS_REPO}. Check the secrets repo.")
        sys.exit(f"GitHub API error {e.code}: {e.reason}")
    return base64.b64decode(data["content"])


def set_permissions(path, mode):
    if platform.system() != "Windows":
        os.chmod(path, mode)


def main():
    print("=" * 55)
    print("  TWBshop Bootstrap")
    print("=" * 55)

    token = get_token()

    # 1. Download files
    os.makedirs(SSH_DIR, exist_ok=True)
    for filename, dest in FILES:
        print(f"Downloading {filename} ...", end=" ", flush=True)
        content = fetch_file(token, filename)
        with open(dest, "wb") as f:
            f.write(content)
        if "twbshop_server" in filename and ".pub" not in filename:
            set_permissions(dest, stat.S_IRUSR | stat.S_IWUSR)  # chmod 600
        print("done")

    # 2. Install requirements
    req_file = os.path.join(PROJECT_DIR, "requirements.txt")
    if os.path.exists(req_file):
        print("\nInstalling pip requirements ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file, "-q"])
        print("done")

    # 3. Create required directories
    for d in ["logs", "photos"]:
        os.makedirs(os.path.join(PROJECT_DIR, d), exist_ok=True)

    # 4. Activate git hook so future pulls remind you if secrets go missing
    subprocess.call(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=PROJECT_DIR
    )

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
    main()
