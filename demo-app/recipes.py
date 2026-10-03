"""TableStory recipe collection: fail-fast loader and validators."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
DIFFICULTIES = ("Easy", "Medium", "Confident Cook")
CATEGORIES = ("Breakfast", "Lunch", "Dinner", "Dessert")
REQUIRED_FIELDS = (
    "id", "title", "description", "category", "dietary_tags", "prep_minutes",
    "cook_minutes", "difficulty", "servings", "ingredients", "steps", "colors",
    "featured",
)

MIN_RECIPES = 12
QUICK_MAX_MINUTES = 30
_NUM = r"\s*[-+]?\d*\.?\d+%?\s*"
_COLOR = re.compile(
    r"^(#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}"
    r"|(rgb|hsl)a?\(" + _NUM + r"([,\s/]" + _NUM + r"){2,3}\))$"
)


def total_minutes(recipe):
    return recipe["prep_minutes"] + recipe["cook_minutes"]


def _fail(index, raw, message):
    label = raw.get("id") if isinstance(raw, dict) else None
    where = f"recipe {index}" + (f" ({label})" if isinstance(label, str) else "")
    raise ValueError(f"{where}: {message}")


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _text_list(value):
    return isinstance(value, list) and all(_is_text(item) for item in value)


def validate_recipe(raw, index):
    if not isinstance(raw, dict):
        _fail(index, raw, "must be an object")
    keys = set(raw)
    if keys != set(REQUIRED_FIELDS):
        missing = sorted(set(REQUIRED_FIELDS) - keys)
        extra = sorted(keys - set(REQUIRED_FIELDS))
        _fail(index, raw, f"fields must match exactly (missing {missing}, extra {extra})")
    if not (isinstance(raw["id"], str) and re.fullmatch(ID_PATTERN, raw["id"])):
        _fail(index, raw, "id must be a URL-safe slug")
    for name in ("title", "description"):
        if not _is_text(raw[name]):
            _fail(index, raw, f"{name} must be non-empty text")
    if raw["category"] not in CATEGORIES:
        _fail(index, raw, f"category must be one of {CATEGORIES}")
    tags = raw["dietary_tags"]
    if not (isinstance(tags, list) and all(isinstance(t, str) for t in tags)):
        _fail(index, raw, "dietary_tags must be a list of strings")
    if not _is_int(raw["prep_minutes"]) or raw["prep_minutes"] <= 0:
        _fail(index, raw, "prep_minutes must be a positive integer")
    if not _is_int(raw["cook_minutes"]) or raw["cook_minutes"] < 0:
        _fail(index, raw, "cook_minutes must be a non-negative integer")
    if raw["difficulty"] not in DIFFICULTIES:
        _fail(index, raw, f"difficulty must be one of {DIFFICULTIES}")
    if not _is_int(raw["servings"]) or raw["servings"] <= 0:
        _fail(index, raw, "servings must be a positive integer")
    if not _text_list(raw["ingredients"]) or not raw["ingredients"]:
        _fail(index, raw, "ingredients must be a non-empty list of text")
    if not _text_list(raw["steps"]) or len(raw["steps"]) < 3:
        _fail(index, raw, "steps must be a list of at least 3 text items")
    colors = raw["colors"]
    if not (isinstance(colors, list) and len(colors) == 2
            and all(isinstance(c, str) and _COLOR.match(c.strip()) for c in colors)):
        _fail(index, raw, "colors must be two valid CSS colors")
    if not isinstance(raw["featured"], bool):
        _fail(index, raw, "featured must be a boolean")
    return raw


def validate_collection(recipes):
    if len(recipes) < MIN_RECIPES:
        raise ValueError(f"collection needs at least {MIN_RECIPES} recipes")
    seen = {"id": set(), "title": set(), "description": set(), "content": set()}
    for index, recipe in enumerate(recipes):
        content = (tuple(recipe["ingredients"]), tuple(recipe["steps"]))
        for kind, value in (("id", recipe["id"]), ("title", recipe["title"]),
                            ("description", recipe["description"]), ("content", content)):
            if value in seen[kind]:
                _fail(index, recipe, f"duplicate {kind}")
            seen[kind].add(value)
    tags = [t for r in recipes for t in r["dietary_tags"]]
    categories = {r["category"] for r in recipes}
    if tags.count("Vegetarian") < 3:
        raise ValueError("collection needs at least 3 Vegetarian recipes")
    if tags.count("Vegan") < 2:
        raise ValueError("collection needs at least 2 Vegan recipes")
    if sum(total_minutes(r) <= QUICK_MAX_MINUTES for r in recipes) < 3:
        raise ValueError(f"collection needs at least 3 recipes of {QUICK_MAX_MINUTES} minutes or less")
    if sum(r["category"] == "Dessert" for r in recipes) < 2:
        raise ValueError("collection needs at least 2 Dessert recipes")
    for needed in ("Breakfast", "Lunch", "Dinner"):
        if needed not in categories:
            raise ValueError(f"collection needs a {needed} recipe")


def load_recipes(path=None):
    path = Path(path) if path is not None else ROOT / "recipes.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load recipes from {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("recipes file must contain a list")
    recipes = [validate_recipe(raw, i) for i, raw in enumerate(data)]
    validate_collection(recipes)
    return recipes
