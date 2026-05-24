"""B2B customer registry.

New customers are registered automatically when a trusted admin
(see config.B2B_ADMIN_USER_IDS) adds the bot to their group.
The group is stored in the b2b_customers DB table using the
cleaned Telegram group title as the business name.

Legacy: B2B_CUSTOMERS dict entries are seeded to the DB on startup
for backwards compatibility.
"""

import re

# group_chat_id (integer) → business name (string)
# Only kept for legacy seeding — new customers come in via auto-registration.
B2B_CUSTOMERS: dict[int, str] = {
    -5252815001: "Test Customer",
}

_STRIP_WORDS = {"b2b", "wholesale", "bakery", "order", "orders", "wine"}
_STRIP_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in _STRIP_WORDS) + r')\b',
    flags=re.IGNORECASE,
)


def clean_group_title(title: str) -> str:
    """Strip noise words from a Telegram group title to get a clean business name."""
    cleaned = _STRIP_PATTERN.sub('', title)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -–—|·,.')
    return cleaned or title


def is_b2b_group(group_chat_id: int) -> bool:
    from shared.database import get_b2b_customer
    row = get_b2b_customer(group_chat_id)
    return bool(row and row.get("business_name"))


def get_business_name(group_chat_id: int) -> str | None:
    from shared.database import get_b2b_customer
    row = get_b2b_customer(group_chat_id)
    return row["business_name"] if row and row.get("business_name") else None
