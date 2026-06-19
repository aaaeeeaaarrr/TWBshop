"""C3 stock-count gateway — pure unit tests (no Telegram / no DB).

Covers: the URL resolver (valid / unset / non-URL), the staff-facing card, and the menu
integration (button hidden until a URL is configured = WALK-READINESS).
"""
from gm_bot import stock_gateway
from gm_bot import attendance_ui as ui


# ---- URL resolution -----------------------------------------------------------

def test_stock_enabled_true_for_https(monkeypatch):
    monkeypatch.setenv("STOCK_APPSHEET_URL", "https://app.appsheet.com/abc")
    assert stock_gateway.appsheet_url() == "https://app.appsheet.com/abc"
    assert stock_gateway.stock_enabled() is True


def test_stock_disabled_when_unset(monkeypatch):
    monkeypatch.delenv("STOCK_APPSHEET_URL", raising=False)
    monkeypatch.setattr(stock_gateway.config, "STOCK_APPSHEET_URL", "", raising=False)
    assert stock_gateway.appsheet_url() == ""
    assert stock_gateway.stock_enabled() is False


def test_stock_disabled_for_non_url(monkeypatch):
    # a stray non-URL value must NOT create a broken Telegram URL button
    monkeypatch.setenv("STOCK_APPSHEET_URL", "coming soon")
    assert stock_gateway.appsheet_url() == ""
    assert stock_gateway.stock_enabled() is False


def test_config_fallback_when_env_absent(monkeypatch):
    monkeypatch.delenv("STOCK_APPSHEET_URL", raising=False)
    monkeypatch.setattr(stock_gateway.config, "STOCK_APPSHEET_URL",
                        "https://from.config", raising=False)
    assert stock_gateway.appsheet_url() == "https://from.config"


def test_stock_enabled_for_uppercase_scheme(monkeypatch):
    # case-insensitive scheme check, but the URL is returned exactly as written (path is case-sensitive)
    monkeypatch.setenv("STOCK_APPSHEET_URL", "HTTPS://App.AppSheet.com/Start/Abc")
    assert stock_gateway.stock_enabled() is True
    assert stock_gateway.appsheet_url() == "HTTPS://App.AppSheet.com/Start/Abc"


# ---- the staff-facing card ----------------------------------------------------

def test_gateway_message_has_working_url_button():
    _, kb = stock_gateway.gateway_message("https://app.example.com/stock")
    flat = [b for row in kb.inline_keyboard for b in row]
    url_btns = [b for b in flat if getattr(b, "url", None)]
    assert len(url_btns) == 1
    assert url_btns[0].url == "https://app.example.com/stock"
    # a real Back button that returns to the menu — no dead end
    assert any((b.callback_data or "") == "att:menu" for b in flat)


def test_gateway_message_is_bilingual():
    text, _ = stock_gateway.gateway_message("https://x.test")
    assert "Stock count" in text     # English
    assert "ស្តុក" in text            # Khmer


# ---- menu integration (hidden until configured) -------------------------------

_PERSONA = {"id": 11, "canonical_name": "Sao Visal", "call_name": "Visal",
            "work_start": "08:00", "work_end": "17:00", "org": "TWB", "status": "active",
            "_live": True}


def test_main_menu_hides_stock_when_disabled(monkeypatch):
    monkeypatch.setattr(stock_gateway, "stock_enabled", lambda: False)
    _, kb = ui.main_menu(_PERSONA)
    flat = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "att:stock" not in flat
    # the core menu is untouched
    for cd in ("att:ci", "att:late", "att:aw", "att:am"):
        assert cd in flat


def test_main_menu_shows_stock_when_enabled(monkeypatch):
    monkeypatch.setattr(stock_gateway, "stock_enabled", lambda: True)
    _, kb = ui.main_menu(_PERSONA)
    flat = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "att:stock" in flat


def test_main_menu_survives_gateway_failure(monkeypatch):
    # a stock-gateway problem must NEVER break the core staff menu (check-in is critical)
    def boom():
        raise RuntimeError("gateway broken")
    monkeypatch.setattr(stock_gateway, "stock_enabled", boom)
    _, kb = ui.main_menu(_PERSONA)   # must not raise
    flat = [b.callback_data for row in kb.inline_keyboard for b in row]
    for cd in ("att:ci", "att:late", "att:aw", "att:am"):
        assert cd in flat            # core menu intact
    assert "att:stock" not in flat   # broken gateway -> button simply absent
