"""Log hygiene — bot tokens must be redacted from log records."""
import logging

from shared.log_redact import REDACTED, RedactTokenFilter, install_log_hygiene, redact

# Synthetic, same SHAPE as a Telegram token (digits:35-chars) — the redaction test only needs the shape.
# NEVER paste a real token here: a real one leaks into git history and must then be rotated via BotFather.
# The real GM token lives ONLY in secrets.py.
FAKE = "bot000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def test_redact_pure():
    out = redact("HTTP Request: POST https://api.telegram.org/%s/getUpdates" % FAKE)
    assert FAKE not in out and REDACTED in out


def test_redact_leaves_normal_text():
    assert redact("nothing secret here, just a robot") == "nothing secret here, just a robot"


def test_filter_mutates_record():
    # Faithful to how httpx logs it: the token arrives via ARGS, not the format string.
    f = RedactTokenFilter()
    rec = logging.LogRecord("x", logging.INFO, __file__, 1,
                            "HTTP Request: POST %s",
                            ("https://api.telegram.org/%s/getUpdates" % FAKE,), None)
    assert f.filter(rec) is True
    assert FAKE not in rec.getMessage() and REDACTED in rec.getMessage()


def test_install_is_idempotent():
    root = logging.getLogger()
    root.addHandler(logging.NullHandler())
    install_log_hygiene()
    install_log_hygiene()
    for h in root.handlers:
        assert sum(isinstance(x, RedactTokenFilter) for x in h.filters) <= 1
    assert logging.getLogger("httpx").level == logging.WARNING
