"""B2B customer registry — maps Telegram group chat IDs to business names.

To add a new B2B customer:
  1. Add the bot to their Telegram group
  2. Get the group chat ID (check bot logs on first message, or use @userinfobot)
  3. Add one line below:  group_chat_id: "Business Name",
  4. Restart the bot

The business name is used in confirmations, the nightly summary, and delivery labels.
"""

# group_chat_id (integer) → business name (string)
B2B_CUSTOMERS: dict[int, str] = {
    # -1001234567890: "Restaurant XYZ",
    # -1009876543210: "Bar ABC",
}


def get_business_name(group_chat_id: int) -> str | None:
    return B2B_CUSTOMERS.get(group_chat_id)


def is_b2b_group(group_chat_id: int) -> bool:
    return group_chat_id in B2B_CUSTOMERS
