"""C3 — staff stock-count gateway (GM bot).

Stock architecture (session 43): staff use ONE bot (the GM bot) as the gateway to the AppSheet
stock app; GM owns NO stock data. This module is just that gateway — it routes a staffer to the
AppSheet stock app via a link button. The AppSheet app + its URL are produced by the STOCK lane
(build sequence C2); this is the GM-side seam (C3), built interface-first (Arch Rule 2) so it is
ready the moment the URL exists. No DB / no stock data lives here.

WALK-READINESS: the gateway is fully wired but INVISIBLE to staff until the AppSheet URL is
configured — `main_menu` only shows the button when `stock_enabled()` is true. So this can deploy
at any time without ever showing live staff a 'coming soon' stub.

CONFIGURING THE URL (owner / stock lane — no code change, no redeploy):
  - server: add `STOCK_APPSHEET_URL=https://...` to the gm service's systemd drop-in (same place
    TWBSHOP_ENV lives) and restart twbshop-gm; the button lights up on the next menu render.
  - local/staging: `export STOCK_APPSHEET_URL=https://...` (or set it in config.py).
A missing / non-URL value keeps the gateway hidden (never a broken Telegram URL button).
"""
from __future__ import annotations

import os

import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def appsheet_url() -> str:
    """The configured AppSheet stock-app URL, or '' if unset/invalid. Read at call time so setting
    the env var + restarting lights up the gateway with no redeploy. A value that is not an http(s)
    URL is treated as unset so we can never build a broken Telegram URL button."""
    u = (os.environ.get("STOCK_APPSHEET_URL")
         or getattr(config, "STOCK_APPSHEET_URL", "")
         or "").strip()
    return u if u.startswith(("http://", "https://")) else ""


def stock_enabled() -> bool:
    """True only when a valid AppSheet URL is configured — gates the menu button so staff never see
    a placeholder/dead 'coming soon' entry (WALK-READINESS)."""
    return bool(appsheet_url())


def gateway_message(url: str) -> tuple[str, InlineKeyboardMarkup]:
    """Pure: the staff-facing 'open the stock app' screen. `url` is the resolved AppSheet link
    (the caller guarantees it is non-empty — the button that reaches here is hidden otherwise)."""
    text = ("📦 Stock count · រាប់ស្តុក\n\n"
            "Tap below to open the stock app, then count each item and save.\n"
            "ចុចខាងក្រោម ដើម្បីបើកកម្មវិធីស្តុក រួចរាប់ទំនិញម្តងមួយៗ ហើយរក្សាទុក។")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Open stock app · បើកកម្មវិធីស្តុក", url=url)],
        [InlineKeyboardButton("← Back · ត្រឡប់ក្រោយ", callback_data="att:menu")],
    ])
    return text, kb
