"""Accountant TWB — finance / expense / payment lane (separate twbshop-accountant bot).

Design record: docs/REPORT_SYSTEM_DESIGN.md (read it first — the locked decisions + phases).
Schema + data layer: accountant/db.py.

Lane discipline: this package owns its own db module; shared/database.py provides only the
connection pool (one DB, the fail-closed TWBSHOP_ENV switch). Finance logic stays self-contained
so the bot is a thin Telegram shell over pure modules.
"""
