"""Log hygiene — keep bot TOKENS out of the log files (owner, 2026-06-21).

python-telegram-bot's httpx layer logs every `getUpdates` at INFO as
  HTTP Request: POST https://api.telegram.org/bot<TOKEN>/getUpdates "HTTP/1.1 200 OK"
which writes the bot token in plaintext to logs/*.log. Two defenses, both installed by
install_log_hygiene(): (1) a Filter that redacts any `bot<id>:<token>` substring on every record
(defense-in-depth — catches the token wherever it appears, e.g. an error URL); (2) raise the httpx /
httpcore / telegram.request loggers to WARNING, which removes the routine getUpdates spam entirely
(it's noise as well as a leak). Logging-only; no bot behavior changes.
"""
import logging
import re

# bot<6+ digits>:<>=20 token chars> — Telegram bot tokens. Conservative bounds avoid false hits.
_TOKEN_RX = re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}")
REDACTED = "bot<REDACTED>"


class RedactTokenFilter(logging.Filter):
    """Scrub bot tokens from a log record's rendered message (never raises into logging)."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 (logging API name)
        try:
            msg = record.getMessage()
            if "bot" in msg and _TOKEN_RX.search(msg):
                record.msg = _TOKEN_RX.sub(REDACTED, msg)
                record.args = ()
        except Exception:
            pass
        return True


def redact(text: str) -> str:
    """Pure helper (testable): replace any bot token in `text` with the redacted marker."""
    return _TOKEN_RX.sub(REDACTED, text or "")


def install_log_hygiene() -> None:
    """Attach the redaction filter to every root handler + quiet the token-leaking httpx spam.
    Idempotent: re-running won't stack duplicate filters."""
    root = logging.getLogger()
    for h in root.handlers:
        if not any(isinstance(f, RedactTokenFilter) for f in h.filters):
            h.addFilter(RedactTokenFilter())
    for name in ("httpx", "httpcore", "telegram.request"):
        logging.getLogger(name).setLevel(logging.WARNING)
