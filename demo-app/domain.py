"""TableStory domain services: search, rails and the in-memory cookbook."""
from recipes import QUICK_MAX_MINUTES, total_minutes

RAIL_POPULAR = "Popular this week"
RAIL_QUICK = "Ready in 30 minutes"
RAIL_VEGETARIAN = "Vegetarian favourites"
RAIL_COOKBOOK = "My Cookbook"
RAIL_NAMES = (RAIL_POPULAR, RAIL_QUICK, RAIL_VEGETARIAN, RAIL_COOKBOOK)
MIN_RAIL_RECIPES = 2


def search_text(recipe):
    parts = [
        recipe["title"], recipe["description"], recipe["category"],
        *recipe["dietary_tags"], *recipe["ingredients"],
    ]
    return " ".join(parts).lower()


def search_recipes(recipes, q):
    needle = (q or "").strip().lower()
    return [r for r in recipes if needle in search_text(r)]


def build_rails(recipes, saved_ids):
    saved = set(saved_ids)
    selectors = (
        lambda r: r["featured"],
        lambda r: total_minutes(r) <= QUICK_MAX_MINUTES,
        lambda r: "Vegetarian" in r["dietary_tags"],
        lambda r: r["id"] in saved,
    )
    return [
        {"name": name, "recipe_ids": [r["id"] for r in recipes if select(r)]}
        for name, select in zip(RAIL_NAMES, selectors)
    ]


def validate_rails(rails, recipes):
    if [r.get("name") for r in rails] != list(RAIL_NAMES):
        raise ValueError(f"rails must be exactly {list(RAIL_NAMES)} in order")
    known = {r["id"] for r in recipes}
    for rail in rails:
        ids = rail["recipe_ids"]
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise ValueError(f"rail {rail['name']!r}: unknown recipe ids {unknown}")
        if rail["name"] != RAIL_COOKBOOK and len(ids) < MIN_RAIL_RECIPES:
            raise ValueError(
                f"rail {rail['name']!r} needs at least {MIN_RAIL_RECIPES} recipes"
            )


class CookbookStore:
    """Saved recipe ids for one app instance, always listed in collection order."""

    def __init__(self, recipes):
        self._recipes = list(recipes)
        self._known = {r["id"] for r in self._recipes}
        self._saved = set()

    def add(self, recipe_id):
        if not isinstance(recipe_id, str) or recipe_id not in self._known:
            return False
        self._saved.add(recipe_id)
        return True

    def remove(self, recipe_id):
        if isinstance(recipe_id, str):
            self._saved.discard(recipe_id)

    def contains(self, recipe_id):
        return isinstance(recipe_id, str) and recipe_id in self._saved

    def ids(self):
        return [r["id"] for r in self._recipes if r["id"] in self._saved]

    def recipes(self):
        return [r for r in self._recipes if r["id"] in self._saved]
