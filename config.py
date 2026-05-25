from secrets import ANTHROPIC_API_KEY, BOT_TOKEN, B2B_BOT_TOKEN, DATABASE_URL

# Claude model used for all AI analysis.
CLAUDE_MODEL = "claude-sonnet-4-6"

# Telegram chat IDs (get them from @userinfobot or bot logs)
CUSTOMER_GROUP_ID = -100000000000   # group where customers place orders
STAFF_GROUP_ID = -1003457945308     # group where staff receive summaries

# Staff Telegram user IDs. Leave as [] to allow anyone (useful during testing).
STAFF_USER_IDS: list[int] = []

# Display names for staff members — used in reminder messages.
# Add one entry per staff member: {telegram_user_id: "Name"}
STAFF_NAMES: dict[int, str] = {
    # 123456789: "Ahmed",
    # 987654321: "Sara",
}

# Photo types every staff member must submit each day.
REQUIRED_PHOTO_TYPES: list[str] = ["workstation", "fridge"]

# Time (UTC) to automatically post the daily production summary to the staff group.
SUMMARY_HOUR = 7
SUMMARY_MINUTE = 0

# Time (UTC) to check for missing photos and send a reminder if any are absent.
REMINDER_HOUR = 10
REMINDER_MINUTE = 0

# Local paths
PHOTO_STORAGE_DIR = "photos"
LOG_DIR = "logs"
UNMATCHED_LOG = "logs/unmatched.log"

# ─── B2B Bot ──────────────────────────────────────────────────────────────────

# Staff group where nightly B2B summaries are posted (can be the same as STAFF_GROUP_ID)
B2B_STAFF_GROUP_ID = -1003457945308

# Staff user IDs allowed to trigger /summary manually. Leave [] to allow anyone.
B2B_STAFF_USER_IDS: list[int] = []

# Telegram user IDs allowed to add the B2B bot to new customer groups.
# Anyone else who adds the bot causes it to leave immediately.
B2B_ADMIN_USER_IDS: list[int] = [1271537077]

# Your personal Telegram user ID — payment screenshots are forwarded here for approval.
OWNER_TELEGRAM_ID: int = 1313155971

# Shop's Telegram (staff phone) — dispatch reminders (1h before fulfillment) are sent here.
DISPATCH_REMINDER_TELEGRAM_ID: int = 1271537077

# Bakery coordinates — used as the origin for Grab Express delivery cost estimates.
# Get from Google Maps: long-press the bakery location → copy the numbers at the top.
BAKERY_LAT: float = 11.5387774
BAKERY_LNG: float = 104.9147998

# Valid bank account numbers customers should pay to.
# Payments sent to any other account are flagged in the group and forwarded to OWNER_TELEGRAM_ID.
# Add the full account number exactly as it appears (digits only, no spaces or dashes).
# Leave empty [] to skip account validation.
VALID_BANK_ACCOUNTS: list[str] = []
