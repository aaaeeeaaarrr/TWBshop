"""B2B bread menu — edit this file to add/remove items, change grams, prices, or attributes.

Fields:
  price           — B2B price per unit (or per standard gram size for buns)
  price_by_grams  — gram → price lookup for items sold in custom gram sizes
  requires_grams  — True if customer can specify grams (pulled from history or standard)
  standard_grams  — default gram size when customer doesn't specify
  unit            — display label when sold in fixed units (e.g. "2pc", "200g")
  order_note      — shown in confirmation when special conditions apply
  min_quantity    — minimum pieces per order (bot rejects orders below this)
  advance_hours   — minimum hours before delivery the order must be placed
  attributes      — dict of customisable options (e.g. sesame type)
"""

# Gram → price lookup shared by all brioche bun/roll items
_BUN_PRICE_BY_GRAMS: dict[int, float] = {
    10: 0.15, 15: 0.15, 20: 0.15, 25: 0.15,
    30: 0.15, 35: 0.15, 40: 0.17, 45: 0.19,
    50: 0.20, 55: 0.23, 60: 0.25, 65: 0.27,
    70: 0.28, 75: 0.31, 80: 0.33, 90: 0.38,
    100: 0.43, 110: 0.48, 120: 0.53,
}

B2B_MENU: dict[str, dict] = {

    # ── Breads ────────────────────────────────────────────────────────────────
    "french baguette": {
        "aliases": [
            "french baguette", "french baguettes", "baguette", "baguettes",
            "french bread", "french stick", "french sticks",
        ],
        "price": 0.65,
        "requires_grams": False,
        "standard_grams": None,
        "attributes": {},
    },
    "multigrain baguette": {
        "aliases": [
            "multigrain baguette", "multigrain baguettes",
            "multi grain baguette", "multigrain", "multi baguette",
            "wholegrain baguette",
        ],
        "price": 0.85,
        "requires_grams": False,
        "standard_grams": None,
        "attributes": {},
    },
    "focaccia": {
        "aliases": ["focaccia", "focaccias", "focacia", "foccacia", "foccacias"],
        "price": 0.80,
        "requires_grams": False,
        "standard_grams": None,
        "unit": "2pc",
        "attributes": {},
    },
    "multigrain loaf": {
        "aliases": [
            "multigrain loaf", "multigrain loafs", "multigrain bread",
            "multi grain loaf", "loaf", "loafs",
        ],
        "price": 1.10,
        "requires_grams": False,
        "standard_grams": None,
        "attributes": {},
    },
    "bagel": {
        "aliases": ["bagel", "bagels"],
        "price": 1.25,
        "requires_grams": False,
        "standard_grams": None,
        "attributes": {},
    },

    # ── By weight (sold per 200g bag) ─────────────────────────────────────────
    "croutons": {
        "aliases": ["crouton", "croutons"],
        "price": 1.00,
        "requires_grams": False,
        "standard_grams": None,
        "unit": "200g",
        "attributes": {},
    },
    "rusk": {
        "aliases": ["rusk", "rusks"],
        "price": 1.00,
        "requires_grams": False,
        "standard_grams": None,
        "unit": "200g",
        "attributes": {},
    },

    # ── Pastries ──────────────────────────────────────────────────────────────
    "croissant": {
        "aliases": [
            "croissant", "croissants", "crossant", "crossants", "croissan",
        ],
        "price": 0.66,
        "requires_grams": False,
        "standard_grams": None,
        "attributes": {},
    },
    "pain au chocolat": {
        "aliases": [
            "pain au chocolat", "pain au chocolats",
            "chocolatin", "chocolatine", "chocolatins",
            "chocolate croissant", "chocolate croissants",
            "choc croissant", "choc croissants",
        ],
        "price": 0.77,
        "requires_grams": False,
        "standard_grams": None,
        "attributes": {},
    },

    # ── Mini pastries (min. 100pc, 48h advance order) ─────────────────────────
    "mini croissant": {
        "aliases": ["mini croissant", "mini croissants"],
        "price": 0.49,
        "requires_grams": False,
        "standard_grams": None,
        "min_quantity": 100,
        "advance_hours": 48,
        "attributes": {},
    },
    "mini chocolatin": {
        "aliases": [
            "mini chocolatin", "mini chocolatins",
            "mini pain au chocolat", "mini chocolate croissant",
        ],
        "price": 0.59,
        "requires_grams": False,
        "standard_grams": None,
        "min_quantity": 100,
        "advance_hours": 48,
        "attributes": {},
    },
    "mini almond croissant": {
        "aliases": [
            "mini almond croissant", "mini almond croissants",
        ],
        "price": 0.90,
        "requires_grams": False,
        "standard_grams": None,
        "min_quantity": 100,
        "advance_hours": 48,
        "attributes": {},
    },
    "mini almond chocolatin": {
        "aliases": [
            "mini almond chocolatin", "mini almond chocolatins",
            "mini almond chocolate croissant",
        ],
        "price": 0.96,
        "requires_grams": False,
        "standard_grams": None,
        "min_quantity": 100,
        "advance_hours": 48,
        "attributes": {},
    },
    "mini ham cheese croissant": {
        "aliases": [
            "mini ham cheese croissant", "mini ham cheese croissants",
            "mini ham croissant", "mini cheese croissant",
        ],
        "price": 1.00,
        "requires_grams": False,
        "standard_grams": None,
        "min_quantity": 100,
        "advance_hours": 48,
        "attributes": {},
    },

    # ── Brioche buns & rolls (customers can specify grams) ────────────────────
    "burger bun": {
        "aliases": [
            "burger bun", "burger buns", "brioche bun", "brioche buns",
            "hamburger bun", "hamburger buns", "brioche burger bun",
        ],
        "price": 0.28,
        "price_by_grams": _BUN_PRICE_BY_GRAMS,
        "requires_grams": True,
        "standard_grams": 70,
        "attributes": {},
    },
    "slider bun": {
        "aliases": [
            "slider bun", "slider buns", "slider", "sliders",
            "brioche slider",
        ],
        "price": 0.19,
        "price_by_grams": _BUN_PRICE_BY_GRAMS,
        "requires_grams": True,
        "standard_grams": 40,
        "attributes": {},
    },
    "hotdog roll": {
        "aliases": [
            "hotdog roll", "hotdog rolls", "hot dog roll", "hot dog rolls",
            "soft roll", "soft rolls", "hotdog bun", "hotdog buns",
            "hot dog bun",
        ],
        "price": 0.23,
        "price_by_grams": _BUN_PRICE_BY_GRAMS,
        "requires_grams": True,
        "standard_grams": 55,
        "attributes": {},
    },
}

# Items that get an instant bakery-group notification when ordered (in addition to 10pm summary)
INSTANT_BREAD_ITEMS: frozenset[str] = frozenset({"croissant", "pain au chocolat"})

# Items with ordering restrictions (min_quantity / advance_hours) — derived automatically
MINI_ITEMS: frozenset[str] = frozenset(
    name for name, data in B2B_MENU.items()
    if data.get("min_quantity") or data.get("advance_hours")
)

# Flat lookup: alias → canonical name (built automatically — do not edit)
ALIAS_MAP: dict[str, str] = {}
for _canonical, _data in B2B_MENU.items():
    for _alias in _data["aliases"]:
        ALIAS_MAP[_alias] = _canonical


def menu_list_text() -> str:
    lines = []
    for name, data in B2B_MENU.items():
        if data.get("requires_grams"):
            detail = f" — specify grams (standard {data['standard_grams']}g, ${data['price']:.2f})"
        elif data.get("unit"):
            detail = f" — per {data['unit']} (${data['price']:.2f})"
        else:
            detail = f" — ${data['price']:.2f} each"
        note = f"  [{data['order_note']}]" if data.get("order_note") else ""
        lines.append(f"  • {name}{detail}{note}")
    return "\n".join(lines)
