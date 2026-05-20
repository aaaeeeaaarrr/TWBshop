"""Menu items, aliases, and synonym tables."""

# Each item: canonical name → list of accepted aliases (all lowercase)
# Add plurals, common misspellings, and short forms here.
MENU = {
    "croissant": [
        "croissant", "croissants", "crossant", "crossants",
        "croissan", "crwason", "crwasons",
    ],
    "sourdough loaf": [
        "sourdough", "sourdoughs", "sourdough loaf", "sourdough loafs",
        "sourdough bread", "sour dough", "sour bread",
    ],
    "cinnamon roll": [
        "cinnamon roll", "cinnamon rolls", "cinamon roll", "cinamon rolls",
        "cinnamon", "cinnamon bun", "cinnamon buns",
    ],
    "baguette": [
        "baguette", "baguettes", "bagette", "bagettes", "french stick", "french sticks",
    ],
    "chocolate muffin": [
        "chocolate muffin", "chocolate muffins", "choc muffin", "choc muffins",
        "muffin", "muffins", "choc muffin",
    ],
    "almond danish": [
        "almond danish", "almond danishes", "danish", "danishes", "almond pastry",
        "almond pastries",
    ],
    "pain au chocolat": [
        "pain au chocolat", "pain au chocolats", "chocolate croissant",
        "chocolate croissants", "choc croissant", "choc croissants",
    ],
    "focaccia": [
        "focaccia", "focaccias", "focacia", "foccacia", "foccacias",
    ],
}

# Flat lookup: alias → canonical name
ALIAS_MAP: dict[str, str] = {}
for canonical, aliases in MENU.items():
    for alias in aliases:
        ALIAS_MAP[alias] = canonical


def menu_list_text() -> str:
    return "\n".join(f"  • {name}" for name in MENU)
