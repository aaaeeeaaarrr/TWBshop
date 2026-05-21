# New PC Setup Guide

Complete setup from a brand new empty PC.

---

## 1. Install Software

Install in this order:

1. **Python 3.11+** — https://python.org
   - During install, tick **"Add Python to PATH"** — don't skip this
2. **Git** — https://git-scm.com
   - Includes Git Bash. Use all default options during install.
3. **VS Code** — https://code.visualstudio.com

---

## 2. Install VS Code Extensions

Open VS Code, go to Extensions (Ctrl+Shift+X), install:

- **Python** (by Microsoft)
- **Pylance** (by Microsoft)
- **GitLens** (by GitKraken)

---

## 3. Configure Git

Open any terminal (Git Bash, PowerShell, or VS Code terminal) and run:

```
git config --global user.name "your name"
git config --global user.email "your email"
```

---

## 4. GitHub Authentication

GitHub does not accept your password — you need a Personal Access Token.

1. Go to github.com → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)
2. Generate new token → tick **repo** scope → copy the token
3. When git asks for your password during clone or push, paste this token

---

## 5. Clone the Repo

```
git clone https://github.com/aaaeeeaaarrr/TWBshop.git
cd TWBshop
```

---

## 6. Install Python Packages

```
pip install -r requirements.txt
```

---

## 7. Create secrets.py

Create a file called `secrets.py` in the root of the project (same folder as `run_bot.py`).
Copy this and fill in your real tokens:

```python
ANTHROPIC_API_KEY = "your-anthropic-key"
BOT_TOKEN = "your-retail-bot-token"
B2B_BOT_TOKEN = "your-b2b-bot-token"
```

Get tokens from:
- Anthropic key: console.anthropic.com → API Keys
- Bot tokens: Telegram → @BotFather → /mybots

---

## 8. Run the Bots

Open two terminal windows in the project folder and run one bot in each:

```
python run_bot.py
```

```
python run_b2b_bot.py
```

---

## Important Rules

- **Only run the bots on ONE PC at a time.** Running on two PCs simultaneously causes a 409 Conflict error — Telegram only allows one instance per bot.
- `secrets.py` is gitignored and never syncs. Keep your tokens somewhere safe (password manager, private note).
- Everything else syncs automatically via `git pull`.

---

## Day-to-Day Workflow (after first setup)

```
git pull
python run_bot.py
python run_b2b_bot.py
```
