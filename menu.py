"""Menu items, aliases, and synonym tables."""

# Each item: canonical name → list of accepted aliases (lowercase)
MENU = {
    "croissant": ["croissant", "crossant", "croissan", "crwason"],
    "sourdough loaf": ["sourdough", "sourdough loaf", "sour dough", "sour bread"],
    "cinnamon roll": ["cinnamon roll", "cinnamon", "cinamon roll", "cinamon"],
    "baguette": ["baguette", "bagette", "french stick"],
    "chocolate muffin": ["chocolate muffin", "choc muffin", "muffin"],
    "almond danish": ["almond danish", "danish", "almond pastry"],
}

# Flat lookup: alias → canonical name
ALIAS_MAP: dict[str, str] = {}
for canonical, aliases in MENU.items():
    for alias in aliases:
        ALIAS_MAP[alias] = canonical
