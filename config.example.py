# Copy this file to config.py and fill in your values.
# config.py is gitignored — never commit it.

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"

# Telegram chat IDs (get them from @userinfobot or bot logs)
CUSTOMER_GROUP_ID = -100000000000   # group where customers place orders
STAFF_GROUP_ID = -100000000001      # group where staff receive summaries

# Staff user IDs allowed to run /summary.
# Leave as empty list [] to allow anyone (useful during testing).
STAFF_USER_IDS: list[int] = []

# Time (UTC) to automatically post the daily production summary to the staff group.
# Example: 7, 0 = 07:00 UTC. Adjust to your local morning time.
SUMMARY_HOUR = 7
SUMMARY_MINUTE = 0

# Local paths
PHOTO_STORAGE_DIR = "photos"
LOG_DIR = "logs"
UNMATCHED_LOG = "logs/unmatched.log"
