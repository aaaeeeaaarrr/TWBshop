from secrets import ANTHROPIC_API_KEY, BOT_TOKEN, B2B_BOT_TOKEN, DATABASE_URL, TELETHON_API_ID, TELETHON_API_HASH, TELETHON_PHONE
try:
    from secrets import GM_BOT_TOKEN
except ImportError:
    GM_BOT_TOKEN = ""  # Add GM_BOT_TOKEN to twbshop-secrets to enable GM bot
try:
    from secrets import HIRE_BOT_TOKEN
except ImportError:
    HIRE_BOT_TOKEN = ""  # Add HIRE_BOT_TOKEN to twbshop-secrets to enable hire bot

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

# Staff listener account — receives [Arrived] / [Didn't come] buttons when an applicant is due.
# This is the person physically at the shop who confirms arrival in person.
HIRE_ARRIVAL_STAFF_ID: int = DISPATCH_REMINDER_TELEGRAM_ID

# Bakery coordinates — used as the origin for Grab Express delivery cost estimates.
# Get from Google Maps: long-press the bakery location → copy the numbers at the top.
BAKERY_LAT: float = 11.5387774
BAKERY_LNG: float = 104.9147998

# Path to shop QR code image — sent to customers when they pay to the wrong account.
# Leave empty string to skip sending the QR.
SHOP_QR_PATH: str = "photos/shop_qr.jpg"

# ─── GM Manager Bot ───────────────────────────────────────────────────────────

# Chat IDs the GM bot monitors for operational intelligence.
STOCK_CHECKS_CHAT_ID: int = -1003952029131  # "Stock Checks +Cleans +Mistakes"
SUPERVISORS_CHAT_ID: int  = -4980513319     # SUPERVISORS TWB
MANAGEMENT_CHAT_ID: int   = -865916135      # MANAGEMENT
COMMS_CHAT_ID: int        = -4248492531     # COMMS & Transfers
DAILY_REPORT_CHAT_ID: int = -5136886404     # TWB REPORT (daily staff reports, replaces Facebook Messenger)

# Test group where the GM bot posts during development (before going live).
# Create a private group, add the bot, paste the chat ID here.
GM_TEST_GROUP_ID: int = 0

# How many days of repeated low-stock alerts before flagging as a concern.
GM_LOW_STOCK_THRESHOLD_DAYS: int = 3

# Use AI (Haiku) meaning-based concern detection instead of the keyword scan.
# Falls back to the keyword scan automatically when ANTHROPIC_API_KEY is empty
# or on a per-message AI error, so the bot always works without the API.
GM_SEMANTIC_CONCERNS: bool = True

# Policy-reply repeat window. If the same approved policy is triggered again in
# the same group within this many hours, the GM still replies in-group as usual
# AND pings the owner privately ("this correction isn't landing").
GM_POLICY_REPEAT_HOURS: int = 72

# Telegram display name → real name mapping for GM bot output.
# Key = exact sender_name from ops_messages. Value = real name from salary sheet.
# Add unknowns as replies come in from staff.
STAFF_ALIAS_MAP: dict[str, str] = {
    # ── Confirmed from salary sheet ──────────────────────────────────────
    "FAI LYNN⚕️KAG LYNN":                  "Vann Failin",
    "SAM PHARM":                            "Chim Samphass",
    "LONG":                                 "Lim Kimlong",
    "Rath Phal":                            "Rath",
    "Hong Vannary":                         "Vannary",
    "Hong Vanary":                          "Vannary",
    "Thy Da":                               "Sen Vathanakthyda",
    "Sachak Anan":                          "Kiry Sachak Anan",
    "CHUN CHOMREUN":                        "Chun Chomruen",
    "Neat Kheak":                           "Neat Kheak",
    "Bad boy Somnang":                      "Sot Somnang",
    "Buy Vong Sakda":                       "Buy Vong Sakada",
    "Monyboth Sopheaknal":                  "Sopheak Nalmonyboth",
    "DET🌿":                                "Ret Det",
    "Khil Chantra":                         "Khil Chantra",
    "CHEA SEAVLUY":                         "Chea Seavluy",
    "Cheata Sok":                           "Cheata Sok",      # Delis supervisor
    "Met Solina":                           "Met Solina",
    "Pisey":                                "Khon Visalpisey",
    "Sao Visal":                            "Sao Visal",
    "Som Renaud":                           "Som Renaud",
    "Von Vichhka":                          "Von Vichhka",
    "An Davy":                              "An Davy",
    "Sie Sopheaktra":                       "Rom Sopheaktra",
    # ── Khmer-script names ───────────────────────────────────────────────
    "បាន ឈៀងម៉េង💨":                        "Ban Chheangmeng",
    'ពិសិដ្ឋ វិណាល់ Piseth Vinal "Hikaru"': "Vinal Piseth",
    "ម៉ន ពុទ្ធាវី":                          "Morn Putheavy",
    # ── Confirmed from staff self-ID in Stock Checks 2026-05-27 ─────────
    "Cat":                                  "Mon Chenda",
    "Nakk":                                 "Doeun Rothanak",
    "NY":                                   "Yi Sony",
    "O":                                    "Korn Chantrea",
    "Seth 🫵":                              "Phan Piseth",
    "Lina So":                              "Met Solina",
    "N. Norin":                             "Nao Norin",
    "Lim soleng 🌚":                        "Lim Soleng",
    "Phêák Trä":                            "Rom Sopheaktra",
    "Boss TT":                              "Tyty",
    "por Khmer Bruce PP":                   "Por",
    "por":                                  "Por",
}


def resolve_staff_name(telegram_name: str) -> str:
    """Return real name for a Telegram display name, or the original if unknown."""
    return STAFF_ALIAS_MAP.get(telegram_name, telegram_name)


# Telegram display name → the name WE CALL them by (nickname), from the staff
# self-ID roll-call in Stock Checks 2026-05-27 ("my name is X, call me Y").
# Used when the GM tags a staff member: it shows this call-name next to the
# account tag (unless the call-name already matches the account display name).
STAFF_CALL_NAME: dict[str, str] = {
    "Rath Phal":                            "Rath",
    "Hong Vannary":                         "Vannary",
    "Hong Vanary":                          "Vannary",
    "Lina So":                              "Lina",
    "Neat Kheak":                           "Kheak",
    "Seth 🫵":                              "Seth",
    "CHUN CHOMREUN":                        "Chomreun",
    "NY":                                   "Ny",
    "Nakk":                                 "Nak",
    "Sachak Anan":                          "Anan",
    "N. Norin":                             "Norin",
    "O":                                    "Chantrea",
    "បាន ឈៀងម៉េង💨":                        "Akalimeng",
    "Lim soleng 🌚":                        "Soleng",
    "SAM PHARM":                            "Samphass",
    "Cat":                                  "Chenda",
    "FAI LYNN⚕️KAG LYNN":                   "Failin",
    "Thy Da":                               "Thyda",
    "An Davy":                              "Davy",
    "Phêák Trä":                            "Pheak Tra",
    "Pisey":                                "Sey",
    'ពិសិដ្ឋ វិណាល់ Piseth Vinal "Hikaru"': "Piseth",
    "LONG":                                 "Long",
    "Sao Visal cv":                         "Visal",
}


def call_name_for(telegram_name: str) -> str | None:
    """Return the nickname we call this staff member by, or None if unknown."""
    return STAFF_CALL_NAME.get(telegram_name)


def display_for_call_name(call_name: str) -> str | None:
    """Reverse lookup: given a nickname we use (e.g. 'Seth'), return the Telegram
    display name (e.g. 'Seth 🫵'), so a free-text name can be resolved to an account."""
    if not call_name:
        return None
    cl = call_name.strip().lower()
    for display, nick in STAFF_CALL_NAME.items():
        if nick.lower() == cl:
            return display
    return None

