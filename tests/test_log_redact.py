"""Log hygiene — bot tokens must be redacted from log records."""
import logging

from shared.log_redact import REDACTED, RedactTokenFilter, install_log_hygiene, redact

FAKE = "bot8827684951:AAGa9y-2wZYGAB21uXMqT8wwWH5wJ5c4q3U"


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
