"""
Read-time enforcement for bilingual reading blocks.

Because buttons are stacked (EN top, KH bottom), compare elapsed time
against the clicked language only — not combined word count.
"""


def min_read_seconds(text: str) -> int:
    """words / 3, clamped to 5–45 seconds."""
    words = len(text.split())
    return max(5, min(45, words // 3))


def get_block_minimums(text_en: str, text_km: str) -> dict:
    """Returns per-language minimum read times for a reading block."""
    return {
        "en": min_read_seconds(text_en),
        "km": min_read_seconds(text_km),
    }


def check_read_honest(elapsed_seconds: float, clicked_language: str,
                      block_minimums: dict) -> bool:
    """
    Returns True if the candidate read for long enough.
    clicked_language: 'en' or 'km'
    block_minimums: output of get_block_minimums()
    """
    required = block_minimums.get(clicked_language, 5)
    return elapsed_seconds >= required


def too_fast_message(clicked_language: str, block_minimums: dict) -> dict:
    """Bilingual message shown when candidate clicks too fast."""
    required = block_minimums.get(clicked_language, 5)
    return {
        "en": (
            f"Please read this section carefully before confirming.\n"
            f"You need at least {required} seconds to read this part.\n"
            f"Read honestly before you click."
        ),
        "km": (
            f"សូមអានផ្នែកនេះដោយយកចិត្តទុកដាក់ មុនពេលបញ្ជាក់។\n"
            f"ប្អូនត្រូវការយ៉ាងហោចណាស់ {required} វិនាទី ដើម្បីអានផ្នែកនេះ។\n"
            f"អានដោយស្មោះត្រង់ មុននឹងចុច។"
        ),
    }
