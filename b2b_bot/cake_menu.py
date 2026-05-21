"""B2B cake & dessert menu — edit to add/remove items or update prices.

cake_category:
  A — whole cake ordered as full (unsliced) or sliced; customer must specify
  B — full tray OR by piece (brownie)
  C — single pieces only (éclairs, tarts)

price_full  — full cake B2B price (Category A)
price_slice — per-slice B2B price (Category A, retail reference)
price_tray  — full tray price (Category B)
price_piece — per-piece price (Category B and C)
standard_slices — default slices when customer orders sliced (Category A)
"""

B2B_CAKE_MENU: dict[str, dict] = {

    # ── Category A: full cake or sliced ───────────────────────────────────────
    "flan": {
        "aliases": ["flan", "flan vanilla", "vanilla flan"],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 13.20,
        "price_slice": 1.65,
    },
    "super chocolate cake": {
        "aliases": [
            "super chocolate cake", "chocolate cake", "choc cake",
            "super choc cake",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 18.00,
        "price_slice": 2.25,
    },
    "blueberry cheesecake": {
        "aliases": [
            "blueberry cheesecake", "blueberry cheese cake",
            "cheesecake blueberry",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 19.20,
        "price_slice": 2.40,
    },
    "baked cheesecake": {
        "aliases": [
            "baked cheesecake", "plain cheesecake", "cheesecake baked",
            "cheesecake",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 15.20,
        "price_slice": 1.90,
    },
    "chocobite cheesecake": {
        "aliases": [
            "chocobite cheesecake", "chocobite", "choco bite cheesecake",
            "chocolate bite cheesecake",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 15.20,
        "price_slice": 1.90,
    },
    "passion cheesecake": {
        "aliases": [
            "passion cheesecake", "cheesecake passion",
            "passion fruit cheesecake",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 15.20,
        "price_slice": 1.90,
    },
    "strawberry cheesecake": {
        "aliases": [
            "strawberry cheesecake", "cheesecake strawberry",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 15.20,
        "price_slice": 1.90,
    },
    "peanut cheesecake": {
        "aliases": [
            "peanut cheesecake", "peanut butter cheesecake",
            "cheesecake peanut",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 15.20,
        "price_slice": 1.90,
    },
    "tiramisu cake": {
        "aliases": [
            "tiramisu cake", "tiramisu", "tiramisu amaretto",
            "tiramisu amaretto cake",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 16.80,
        "price_slice": 2.10,
    },
    "almond caramel cheesecake": {
        "aliases": [
            "almond caramel cheesecake", "almond cheesecake",
            "caramel almond cheesecake", "almond caramel cake",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 15.20,
        "price_slice": 1.90,
    },
    "lemon cheesecake": {
        "aliases": [
            "lemon cheesecake", "cheesecake lemon", "lemon cheese cake",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 15.20,
        "price_slice": 1.90,
    },
    "chocolate tart": {
        "aliases": [
            "chocolate tart", "choc tart", "chocolate tarte",
            "tart chocolate",
        ],
        "cake_category": "A",
        "standard_slices": 8,
        "price_full": 14.00,
        "price_slice": 1.75,
    },

    # ── Category B: full tray or by piece ─────────────────────────────────────
    "brownie": {
        "aliases": ["brownie", "brownies", "brownie tray"],
        "cake_category": "B",
        "price_tray": 61.25,
        "price_piece": 1.75,
    },

    # ── Category C: single pieces only ────────────────────────────────────────
    "eclair chocolat": {
        "aliases": [
            "eclair chocolat", "eclair chocolate", "chocolate eclair",
            "eclair choc", "eclair", "eclairs",
        ],
        "cake_category": "C",
        "price_piece": 1.75,
    },
    "eclair caramel coffee": {
        "aliases": [
            "eclair caramel coffee", "caramel coffee eclair",
            "coffee eclair", "eclair caramel",
        ],
        "cake_category": "C",
        "price_piece": 1.75,
    },
    "chocolate caramel tart": {
        "aliases": [
            "chocolate caramel tart", "choc caramel tart",
            "caramel chocolate tart",
        ],
        "cake_category": "C",
        "price_piece": 1.90,
    },
    "lemon tart": {
        "aliases": ["lemon tart", "tarte citron", "lemon tarte"],
        "cake_category": "C",
        "price_piece": 1.75,
    },
}

# Flat lookup: alias → canonical name (built automatically — do not edit)
CAKE_ALIAS_MAP: dict[str, str] = {}
for _canonical, _data in B2B_CAKE_MENU.items():
    for _alias in _data["aliases"]:
        CAKE_ALIAS_MAP[_alias] = _canonical


def cake_menu_list_text() -> str:
    lines = []
    for name, data in B2B_CAKE_MENU.items():
        cat = data["cake_category"]
        if cat == "A":
            detail = f" — full ${data['price_full']:.2f} or sliced (${data['price_slice']:.2f}/slice)"
        elif cat == "B":
            detail = f" — tray ${data['price_tray']:.2f} or piece ${data['price_piece']:.2f}"
        else:
            detail = f" — ${data['price_piece']:.2f}/piece"
        lines.append(f"  • {name}{detail}")
    return "\n".join(lines)
