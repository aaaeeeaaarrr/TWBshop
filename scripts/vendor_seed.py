"""Curated supplier-vendor -> Telegram-group seed for acc_vendors (P0 populate).

Built from LIVE ops_messages on 2026-06-18 (the static price_list_fetcher.SUPPLIER_CHATS
was stale — missing Song Heng Gas and ~10 other groups). Owner-reviewed the same day.
NOTHING is written by importing this file; the seeder runs only on the owner's go-ahead.

OWNER DECISIONS (2026-06-18) — keep in sync with docs/REPORT_SYSTEM_DESIGN.md:
- B2B-prefixed groups = CUSTOMERS, never suppliers (filter rule). Excluded here:
  Melbourne Coffee, Steakhouse Pochentong, Coala/Toss-it (owner renaming the last two
  with a leading "B2B " so the filter catches them automatically).
- Atlas Ice = CASH, staff-managed, no group → NOT a vendor here.
- Dormant suppliers are KEPT: owner wants to broadcast "send latest prices" to selected
  suppliers, then a DM command shows which now beat our current prices (pure-Python, NO
  API) and updates them → the price-comparison feature (future, P4).
- ABA TWB (-1002813660308) = QR-paid signal ONLY (regular bank transfers never appear
  there) → not a vendor; a PARTIAL paid-signal source for P2.
- Indoguna "Special Pricing" group (-1002552050270) = price-watch (their CEO is in it) →
  listener monitors it for deals on items we use; it is NOT Indoguna's payment group
  (the main group -680277978 is). See PRICE_WATCH below.
- Services (security / AC / maintenance) ARE vendors: some paid by ABA, some by staff
  cash with a receipt photo into the Expense group.
- Listener listens for PROMOS on ALL supplier groups (they post promo photos or ask
  "interested in X at price Y?"): text promos = free keyword/regex; photo promos =
  SELECTIVE OCR (API-light). Feeds the price-watch (P4). See BROADCAST.
- Broadcast groups: do NOT bulk-store their photos (some hammer hundreds); extraction is
  selective. Worthless pure-broadcast groups (staff auto-added, never left) -> owner leaves.
- POSFlow Support = our POS supplier, recurring $25 (TWB) + $25 (Delis) monthly. See RECURRING.

status: active = seed live | dormant = keep for price-broadcast (seeded active=FALSE)
"""

# (canonical_name, tg_group_id, category, status)
VENDORS = [
    # --- Tier 1: confirmed by receipts in TWB REPORT (3-wk window) ---
    ("Indoguna",               -680277978,     "imports/dairy",   "active"),
    ("Dan Meat",               -575036689,     "meat",            "active"),
    ("Buonissimo",             -5218925376,    "imports/deli",    "active"),
    ("ThaiHuot",               -4718285919,    "groceries",       "active"),
    ("SOMA Eggs",              -605607029,     "eggs",            "active"),
    ("Tiger Beer",             -740456627,     "beverage/beer",   "active"),
    ("Grand Place Chocolate",  -777054775,     "chocolate",       "active"),
    ("Betagro",                -4695033653,    "meat/frozen",     "active"),
    ("The Warehouse Wine",     -593114368,     "wine",            "active"),
    ("Makro",                  -598194187,     "wholesale",       "active"),
    # --- Tier 2: active supplier groups, no receipt this window ---
    ("Lee's",                  -514657145,     "groceries",       "active"),
    ("LSH",                    -771475820,     "groceries",       "active"),
    ("AMN Belle France",       -766343069,     "imports/grocery", "active"),
    ("Packaging Supply Store", -1001670757206, "packaging",       "active"),
    ("Koh Kong Smoked Chicken",-556644892,     "meat",            "active"),
    ("Drink Shop",             -580139431,     "beverage",        "active"),
    ("SHG Mozzarella",         -610951371,     "dairy/cheese",    "active"),
    ("Flour Supplier",         -4200448600,    "flour/baking",    "active"),
    ("Annam Cambodia",         -510737793,     "imports/grocery", "active"),
    ("Supply Lee's",           5278321965,     "groceries",       "active"),
    ("VVC Chocolate",          6332752724,     "chocolate",       "active"),
    # --- Tier 3: supplier groups the stale static map was MISSING ---
    ("Song Heng Gas",          -5264511208,    "gas/utilities",   "active"),
    ("Repertoire Culinaire",   -1003618379150, "cheese/fine food","active"),
    ("Big C Wine",             -4854814745,    "wine",            "active"),
    ("Home Top Market",        -5161136592,    "groceries",       "active"),
    ("Greco Yogurt",           -4842130851,    "dairy",           "active"),
    ("Hispania",               -4749398810,    "imports",         "active"),
    ("Flamin Coffee Beans",    -5196167824,    "coffee",          "active"),
    ("Kingdom Beer",           -5259028723,    "beverage/beer",   "active"),
    ("Pasta Box",              -5095770356,    "packaging",       "active"),
    ("Cleanbodia ECO Bags",    -843531530,     "packaging",       "active"),
    ("Printing Paper",         -709015026,     "printing",        "active"),
    # --- Services (vendors per owner; ABA or staff-cash w/ receipt) ---
    ("Dynamic Security",       -5023412915,    "service/security","active"),
    ("LG AC Service",          -4849581234,    "service/ac",      "active"),
    ("Water/Elec/AC Maint",    -1002137628627, "service/maint",   "active"),
    # --- Dormant: keep for the price-broadcast / comparison feature ---
    ("Auskhmer Dairy",         -436441225,     "dairy",           "dormant"),
    ("Khmer Ingredients",      -4229214115,    "ingredients",     "dormant"),
    ("OSTRA Fine Foods",       -430839748,     "fine food",       "dormant"),
    ("LIM Pasta Boxes",        -659134937,     "packaging",       "dormant"),
    ("Chicken pfoods",         -949802815,     "meat",            "dormant"),
    ("Coffee Bean",            843614398,      "coffee",          "dormant"),
    ("Choronai",               1018669211,     "unknown",         "dormant"),
    ("Choronai Hotline",       1138296296,     "unknown",         "dormant"),
    ("FPC Packaging",          -711904445,     "packaging",       "dormant"),
    # --- Resolved 2026-06-18 (owner): all four ARE vendors ---
    ("Pork Market",            -1002359586520, "meat",            "active"),
    ("Medical/Gloves Supply",  -1003903503411, "supplies",        "active"),
    ("C Bakery Store",         -1001580490615, "baking",          "active"),
    ("POSFlow Support",        -4132634268,    "service/pos",     "active"),
]

# Extra group_ids the LISTENER watches for price deals (NOT the payment group).
PRICE_WATCH = {
    "Indoguna": -1002552050270,  # "INDOGUNA WineB (Special Pricing)" — CEO present
}

# Broadcast-heavy groups: the vendor hammers product photos. Do NOT bulk-store their photos;
# price/promo extraction is SELECTIVE + API-light. The dormant pure-broadcast ones are
# leave-candidates (staff got auto-added and never left).
BROADCAST = {
    -1001580490615: "C Bakery Store (~25k product photos; group, not channel)",
    -1001670757206: "Packaging Supply Store",
    6332752724:     "VVC Chocolate (88% one-sender)",
    -1002359586520: "Pork Market",
    -1003903503411: "Medical/Gloves",
    1018669211:     "Choronai (dormant + pure broadcast -> leave candidate)",
    1138296296:     "Choronai Hotline (dormant + pure broadcast -> leave candidate)",
}

# Known recurring/expected charges (design C3-D) — so the report covers the predictable,
# not only what got photographed.  (label, amount_cents, period)
RECURRING = {
    "POSFlow Support": [("TWB POS", 2500, "monthly"), ("Delis POS", 2500, "monthly")],
}

# Recorded so they are never mistaken for vendors.
NOT_VENDORS = {
    -1002813660308: "ABA TWB — QR-payment signal only (regular transfers don't appear)",
}

# B2B CUSTOMERS — RETAINED as customers (the B2B subsystem's domain); only excluded from the
# supplier vendor list. Owner adding a leading 'B2B ' to the unmarked ones so the filter catches them.
B2B_CUSTOMERS = {
    -4026357686: "B2B Melbourne Coffee",
    -4232386441: "Steakhouse Pochentong (rename: add 'B2B ')",
    -4259217507: "Coala/Toss-it (rename: add 'B2B ')",
}
