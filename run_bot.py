"""Entry point for the Telegram bot.

Usage:
    python run_bot.py
"""
import sys
from pathlib import Path

# Make shared/ importable and telegram_bot/ modules importable without package prefix
_root = Path(__file__).parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "telegram_bot"))

from bot import main  # noqa: E402 — import after path setup

if __name__ == "__main__":
    main()
