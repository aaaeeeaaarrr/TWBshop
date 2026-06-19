"""Canonical stock catalog — the stock lane's owned seed data for `acc_items`.

Migrated (session 44 — C2) from GM's `_STOCK_SEED` + `_STOCK_CATEGORIES` (shared/database.py), the
existing curated ~50-item list, joined into one (name, category, unit, min_qty) table. This is the
stock lane's home for the catalog now; GM's constants are removed at the integrator cutover.
`tests/test_stock_catalog.py` asserts this stays faithful to the GM source until then.

`reorder_qty` is intentionally absent (NULL): it is not in the source data and is an owner tuning
field (the "order back up to" level). The order brain meanwhile computes a target from min + a
buffer, so reorder works without it. `aliases` are NOT here — supplier-name <-> catalog mapping is
the accountant's vendor-scoped `acc_item_aliases`, a later coordinated step (see stock_shared NOTE).

FUTURE: when the owner provides the full ~143-item reorder sheet (design E6), regenerate _ROWS from
that CSV (skip the [X] discontinued items) and drop the GM-fidelity test.
"""
from __future__ import annotations

# (name, category, unit, min_qty)
_ROWS: list[tuple[str, str, str, float]] = [
    ("Sugar",                        "Baking & Dry",         "kg",         5),
    ("Salt",                         "Baking & Dry",         "kg",         5),
    ("White sesame",                 "Baking & Dry",         "kg",         1),
    ("Black sesame",                 "Baking & Dry",         "kg",         4),
    ("Peanuts",                      "Baking & Dry",         "tin",        0.25),
    ("Milk powder",                  "Baking & Dry",         "packs",      2),
    ("Icing sugar",                  "Baking & Dry",         "packs",      2),
    ("Almond flakes",                "Baking & Dry",         "packs",      2),
    ("Almond ground",                "Baking & Dry",         "packs",      2),
    ("Beef gelatin powder",          "Baking & Dry",         "tubs",       2),
    ("Instant custard powder",       "Baking & Dry",         "tubs",       0.25),
    ("Baking powder",                "Baking & Dry",         "tub",        1),
    ("Vanilla essence",              "Baking & Dry",         "tub",        1),
    ("Molasses",                     "Baking & Dry",         "bottles",    2),
    ("Asian flour",                  "Baking & Dry",         "bags",       2),
    ("Eagle flour",                  "Baking & Dry",         "bags",       2),
    ("Cacao powder 1kg",             "Baking & Dry",         "bags",       3),
    ("Ireks Rogena 12.5kg",          "Baking & Dry",         "bag",        0.5),
    ("Yeast",                        "Baking & Dry",         "packs",      5),
    ("Strawberry puree",             "Baking & Dry",         "tubs",       2),
    ("Passion puree",                "Baking & Dry",         "tubs",       2),
    ("S500 acbplus bread improver",  "Baking & Dry",         "bags",       2),
    ("Red Velvet",                   "Baking & Dry",         "kg",         8),
    ("Corn Powder",                  "Baking & Dry",         "kg",         5),

    ("Eggs",                         "Dairy & Butter",       "eggs",       500),
    ("Milk condensed",               "Dairy & Butter",       "cans",       5),
    ("Fresh milk",                   "Dairy & Butter",       "cases",      4),
    ("GLF cream",                    "Dairy & Butter",       "cases",      4),
    ("Pilot butter",                 "Dairy & Butter",       "kg",         25),
    ("Croissant butter",             "Dairy & Butter",       "kg",         10),
    ("President butter 10g pack",    "Dairy & Butter",       "pc",         2),

    ("White chocolate",              "Chocolate",            "packs",      3),
    ("Black chocolate",              "Chocolate",            "kg",         10),
    ("Chocolate sticks",             "Chocolate",            "box",        1),

    ("Tomato Ketchup Heinz",         "Sauces & Condiments",  "tubs (5L)",  2),
    ("Ketchup packs",                "Sauces & Condiments",  "packs",      6),
    ("Tomato paste",                 "Sauces & Condiments",  "cans",       5),
    ("White Sauce",                  "Sauces & Condiments",  "pots",       1),
    ("Red Sauce",                    "Sauces & Condiments",  "pots",       1),
    ("Homemade Jam",                 "Sauces & Condiments",  "jars",       1),
    ("Baked beans",                  "Sauces & Condiments",  "cases",      4),
    ("Vegetable oil",                "Sauces & Condiments",  "tin",        1),

    ("Loaf Plastic",                 "Packaging",            "pack",       1),
    ("Croissant Plastic",            "Packaging",            "pack",       1),
    ("Burger Plastic",               "Packaging",            "pack",       1),
    ("Focaccia Plastic",             "Packaging",            "pack",       1),
    ("Soft Roll Plastic",            "Packaging",            "packs",      1),
    ("Chocolatin Plastic",           "Packaging",            "packs",      1),
    ("Aluminum",                     "Packaging",            "full roll",  1),

    ("Dish washing",                 "Cleaning",             "big can",    1),
]

# Display order for categories (mirrors GM's STOCK_CATEGORY_ORDER).
CATEGORY_ORDER: list[str] = [
    "Baking & Dry", "Dairy & Butter", "Chocolate",
    "Sauces & Condiments", "Packaging", "Cleaning",
]

CATALOG_ITEMS: list[dict] = [
    {"name": name, "category": category, "unit": unit, "min_qty": min_qty, "reorder_qty": None}
    for (name, category, unit, min_qty) in _ROWS
]
