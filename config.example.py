# Copy this file to config.py and fill in your values.
# config.py is gitignored — never commit it.

# Anthropic API — required for Phase 6 features (photo analysis, stock sheet OCR,
# staff message monitoring). Leave empty to run in manual-review-only mode.
ANTHROPIC_API_KEY = ""

# Claude model used for all AI analysis.
CLAUDE_MODEL = "claude-sonnet-4-6"

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"

# Telegram chat IDs (get them from @userinfobot or bot logs)
CUSTOMER_GROUP_ID = -100000000000   # group where customers place orders
STAFF_GROUP_ID = -100000000001      # group where staff receive summaries

# Staff Telegram user IDs. Leave as [] to allow anyone (useful during testing).
STAFF_USER_IDS: list[int] = []

# Display names for staff members — used in reminder messages.
# Add one entry per staff member: {telegram_user_id: "Name"}
STAFF_NAMES: dict[int, str] = {
    # 123456789: "Ahmed",
    # 987654321: "Sara",
}

# Photo types every staff member must submit each day.
# Remove a type to stop checking for it.
# Note: "stock_sheet" is intentionally excluded — stock sheets are submitted
# on-demand, not on a fixed daily schedule. The staff group is alerted
# automatically whenever one arrives.
REQUIRED_PHOTO_TYPES: list[str] = ["workstation", "fridge"]

# Time (UTC) to automatically post the daily production summary to the staff group.
SUMMARY_HOUR = 7
SUMMARY_MINUTE = 0

# Time (UTC) to check for missing photos and send a reminder if any are absent.
# Set this to after the expected submission deadline, e.g. end of morning shift.
REMINDER_HOUR = 10
REMINDER_MINUTE = 0

# Local paths
PHOTO_STORAGE_DIR = "photos"
LOG_DIR = "logs"
UNMATCHED_LOG = "logs/unmatched.log"

# ─── B2B Bot ──────────────────────────────────────────────────────────────────
# Separate bot token — create a second bot via @BotFather
B2B_BOT_TOKEN = "YOUR_B2B_BOT_TOKEN_HERE"

# Staff group where nightly B2B summaries are posted (can be the same as STAFF_GROUP_ID)
B2B_STAFF_GROUP_ID = -100000000002

# Staff user IDs allowed to trigger /summary manually. Leave [] to allow anyone.
B2B_STAFF_USER_IDS: list[int] = []
