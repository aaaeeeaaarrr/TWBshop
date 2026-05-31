"""Tests for gm_bot/mentions.py — staff tagging convention. Pure, no DB/Telegram."""

from gm_bot import mentions


def test_distinct_call_name_prefixes_tag():
    # "Cat" account display, call-name "Chenda" -> genuinely different, prefix kept.
    out = mentions.format_mention(42, "Cat", "Chenda")
    assert out == 'Chenda <a href="tg://user?id=42">Cat</a>'


def test_emoji_only_difference_counts_as_same():
    # "Seth 🫵" vs call "Seth" -> only an emoji differs, so show the tag alone.
    out = mentions.format_mention(42, "Seth 🫵", "Seth")
    assert out == '<a href="tg://user?id=42">Seth 🫵</a>'


def test_call_name_equal_to_display_shows_tag_only():
    # "Norin" account display, call-name "Norin" -> no redundant prefix.
    out = mentions.format_mention(7, "Norin", "Norin")
    assert out == '<a href="tg://user?id=7">Norin</a>'


def test_equality_ignores_case_and_punctuation():
    # "N. Norin" vs call "Norin" are NOT the same -> prefix kept.
    out = mentions.format_mention(7, "N. Norin", "Norin")
    assert out.startswith("Norin <a ")
    # "davy" vs "Davy" ARE the same -> tag only.
    out2 = mentions.format_mention(7, "Davy", "davy")
    assert out2 == '<a href="tg://user?id=7">Davy</a>'


def test_no_uid_falls_back_to_plain_escaped():
    out = mentions.format_mention(None, "Dara & Co", "Dara")
    assert out == "Dara Dara &amp; Co"  # call-name prefix + escaped plain display
    out2 = mentions.format_mention(None, "Dara", "Dara")
    assert out2 == "Dara"


def test_html_escaping_of_display():
    out = mentions.format_mention(1, "a<b>c", None)
    assert out == '<a href="tg://user?id=1">a&lt;b&gt;c</a>'


def test_no_call_name_shows_tag_only():
    out = mentions.format_mention(9, "Some Person", None)
    assert out == '<a href="tg://user?id=9">Some Person</a>'


def test_empty_display_defaults_to_staff():
    out = mentions.format_mention(None, "", None)
    assert out == "Staff"


def test_mention_wrapper_uses_config_call_name():
    # "Cat" -> call-name "Chenda" from config roll-call map.
    out = mentions.mention(5, "Cat")
    assert out == 'Chenda <a href="tg://user?id=5">Cat</a>'


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception as e:
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
