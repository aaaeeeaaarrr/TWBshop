"""Entry point for the Telegram bot.

Usage:
    python run_bot.py
"""
import asyncio
import sys
from pathlib import Path

if not Path("secrets.py").exists():
    print("\n  NEW MACHINE detected — secrets.py is missing.")
    print("  Run: python bootstrap.py\n")
    sys.exit(1)

# Make shared/ importable and telegram_bot/ modules importable without package prefix
_root = Path(__file__).parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "telegram_bot"))

from bot import main  # noqa: E402 — import after path setup

if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
