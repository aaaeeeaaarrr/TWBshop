"""Entry point for the B2B orders bot.

Usage:
    python run_b2b_bot.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from b2b_bot.bot import main

if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
