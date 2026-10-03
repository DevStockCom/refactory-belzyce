"""Acceptance tests for ticket #1: validated recipe collection (recipes.json + loader)."""
import copy
import importlib
import json
import re
from pathlib import Path

import pytest

DEMO = Path(__file__).parents[1]
DATA = DEMO / "recipes.json"

FIELDS = [
    "id", "title", "description", "category", "dietary_tags", "prep_minutes",
    "cook_minutes", "difficulty", "servings", "ingredients", "steps", "colors",
    "featured",
]


def _module():
    assert (DEMO / "recipes.py").is_file(), "demo-app/recipes.py is missing"
    return importlib.import_module("recipes")


def _raw():
    assert DATA.is_file(), "demo-app/recipes.json is missing"
    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.fixture()
def recipes_mod():
    return _module()


@pytest.fixture()
def loaded(recipes_mod):
    return recipes_mod.load_recipes()


def _write(tmp_path, data):
    path = tmp_path / "recipes.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _total(r):
    return r["prep_minutes"] + r["cook_minutes"]


# --- shipped data ---------------------------------------------------------

def test_load_returns_enough_recipes_with_exact_keys(loaded):
    assert len(loaded) >= 12
    for recipe in loaded:
        assert sorted(recipe.keys()) == sorted(FIELDS)


def test_load_preserves_file_order(loaded):
    assert [r["id"] for r in loaded] == [r["id"] for r in _raw()]


def test_two_loads_are_identical(recipes_mod):
    first = recipes_mod.load_recipes()
    second = recipes_mod.load_recipes()
    assert first == second
    assert first is not second


def test_load_accepts_explicit_path(recipes_mod, tmp_path):
    path = _write(tmp_path, _raw())
    assert recipes_mod.load_recipes(path) == recipes_mod.load_recipes()


def test_constants(recipes_mod):
    assert re.fullmatch(recipes_mod.ID_PATTERN, "lemon-pasta")
    assert not re.fullmatch(recipes_mod.ID_PATTERN, "Lemon Pasta")
    assert set(recipes_mod.DIFFICULTIES) == {"Easy", "Medium", "Confident Cook"}
    assert {"Breakfast", "Lunch", "Dinner", "Dessert"} <= set(recipes_mod.CATEGORIES)
    assert sorted(recipes_mod.REQUIRED_FIELDS) == sorted(FIELDS)


def test_count_minimums(loaded):
    assert sum("Vegetarian" in r["dietary_tags"] for r in loaded) >= 3
    assert sum("Vegan" in r["dietary_tags"] for r in loaded) >= 2
    assert sum(_total(r) <= 30 for r in loaded) >= 3
    assert sum(r["category"] == "Dessert" for r in loaded) >= 2
    categories = {r["category"] for r in loaded}
    assert {"Breakfast", "Lunch", "Dinner"} <= categories


def test_shipped_recipes_satisfy_model(loaded, recipes_mod):
    ids = set()
    for r in loaded:
        assert re.fullmatch(recipes_mod.ID_PATTERN, r["id"])
        assert r["id"] not in ids
        ids.add(r["id"])
        assert r["difficulty"] in recipes_mod.DIFFICULTIES
        assert r["category"] in recipes_mod.CATEGORIES
        assert type(r["prep_minutes"]) is int and r["prep_minutes"] > 0
        assert type(r["cook_minutes"]) is int and r["cook_minutes"] >= 0
        assert type(r["servings"]) is int and r["servings"] > 0
        assert r["ingredients"] and all(isinstance(i, str) and i.strip() for i in r["ingredients"])
        assert len(r["steps"]) >= 3
        assert len(r["colors"]) == 2
        assert isinstance(r["featured"], bool)
    assert len({r["title"] for r in loaded}) == len(loaded)
    assert len({r["description"] for r in loaded}) == len(loaded)


def test_featured_has_at_least_two(loaded):
    assert sum(r["featured"] for r in loaded) >= 2


# --- total_minutes --------------------------------------------------------

def test_total_minutes(recipes_mod, loaded):
    for r in loaded:
        assert recipes_mod.total_minutes(r) == r["prep_minutes"] + r["cook_minutes"]
    assert recipes_mod.total_minutes({"prep_minutes": 7, "cook_minutes": 0}) == 7
    assert recipes_mod.total_minutes({"prep_minutes": 10, "cook_minutes": 25}) == 35


# --- banned terms ---------------------------------------------------------

def _strings(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _strings(v)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)
    elif isinstance(node, str):
        yield node


def test_no_banned_terms_in_recipes_json():
    data = _raw()
    banned = [
        "pocket" + " " + "cine" + "ma", "mo" + "vies?", "fi" + "lms?", "cine" + "ma",
        "watch" + "list", "pos" + "ters?", "run" + "time", "rat" + "ings?", "gen" + "res?",
    ]
    patterns = [re.compile(r"\b" + b + r"\b", re.IGNORECASE) for b in banned]
    patterns.append(re.compile(r"\bP" + "C\\b"))
    hits = [(s, p.pattern) for s in _strings(data) for p in patterns if p.search(s)]
    assert not hits


# --- bad fixtures ---------------------------------------------------------

def _set(key, value):
    def mutate(recipes):
        recipes[0][key] = value
    return mutate


def _dup_id(recipes):
    recipes[1]["id"] = recipes[0]["id"]


def _dup_title(recipes):
    recipes[1]["title"] = recipes[0]["title"]


def _dup_description(recipes):
    recipes[1]["description"] = recipes[0]["description"]


def _dup_steps_ingredients(recipes):
    recipes[1]["ingredients"] = list(recipes[0]["ingredients"])
    recipes[1]["steps"] = list(recipes[0]["steps"])


def _extra_key(recipes):
    recipes[0]["extra_field"] = "x"


def _missing_key(recipes):
    del recipes[0]["servings"]


BAD = {
    "bad-id-uppercase": _set("id", "Bad_ID"),
    "bad-id-space": _set("id", "not url safe"),
    "bad-id-empty": _set("id", ""),
    "bad-difficulty": _set("difficulty", "Hard"),
    "prep-zero": _set("prep_minutes", 0),
    "prep-negative": _set("prep_minutes", -5),
    "cook-negative": _set("cook_minutes", -1),
    "servings-zero": _set("servings", 0),
    "servings-negative": _set("servings", -2),
    "empty-ingredients": _set("ingredients", []),
    "two-steps": lambda recipes: recipes[0].__setitem__("steps", recipes[0]["steps"][:2]),
    "no-steps": _set("steps", []),
    "colors-not-css": _set("colors", ["nope", "alsonope"]),
    "colors-one": _set("colors", ["#FFF8ED"]),
    "colors-three": _set("colors", ["#FFF8ED", "#C9472D", "#3F6B4F"]),
    "bad-category": _set("category", "Snack"),
    "duplicate-id": _dup_id,
    "duplicate-title": _dup_title,
    "duplicate-description": _dup_description,
    "duplicate-content": _dup_steps_ingredients,
    "extra-key": _extra_key,
    "missing-key": _missing_key,
    "bool-prep": _set("prep_minutes", True),
    "bool-cook": _set("cook_minutes", False),
    "bool-servings": _set("servings", True),
    "featured-not-bool": _set("featured", 1),
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_bad_fixture_raises_value_error(recipes_mod, tmp_path, name):
    data = copy.deepcopy(_raw())
    BAD[name](data)
    path = _write(tmp_path, data)
    with pytest.raises(ValueError):
        recipes_mod.load_recipes(path)


def test_unmodified_copy_loads(recipes_mod, tmp_path):
    path = _write(tmp_path, copy.deepcopy(_raw()))
    assert len(recipes_mod.load_recipes(path)) >= 12


@pytest.mark.parametrize("content", ["{not json", "[]", "{}", "null"])
def test_malformed_files_raise_value_error(recipes_mod, tmp_path, content):
    path = tmp_path / "recipes.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        recipes_mod.load_recipes(path)


COLLECTION_BAD = {
    "too-few-recipes": lambda d: d[:11],
    "too-few-vegetarian": lambda d: [
        {**r, "dietary_tags": [t for t in r["dietary_tags"] if t != "Vegetarian"]} for r in d
    ],
    "no-breakfast": lambda d: [r for r in d if r["category"] != "Breakfast"],
    "no-lunch": lambda d: [r for r in d if r["category"] != "Lunch"],
    "no-dinner": lambda d: [r for r in d if r["category"] != "Dinner"],
    "too-few-desserts": lambda d: [r for r in d if r["category"] != "Dessert"],
    "too-few-vegan": lambda d: [
        {**r, "dietary_tags": [t for t in r["dietary_tags"] if t != "Vegan"]} for r in d
    ],
    "too-few-quick": lambda d: [{**r, "prep_minutes": 100} for r in d],
}


@pytest.mark.parametrize("name", sorted(COLLECTION_BAD))
def test_collection_minimums_enforced_at_load(recipes_mod, tmp_path, name):
    data = COLLECTION_BAD[name](copy.deepcopy(_raw()))
    path = _write(tmp_path, data)
    with pytest.raises(ValueError):
        recipes_mod.load_recipes(path)


# --- direct validators ----------------------------------------------------

def test_validate_recipe_accepts_valid_and_rejects_invalid(recipes_mod, loaded):
    good = copy.deepcopy(loaded[0])
    assert recipes_mod.validate_recipe(good, 0) == good
    bad = copy.deepcopy(loaded[0])
    bad["prep_minutes"] = 0
    with pytest.raises(ValueError):
        recipes_mod.validate_recipe(bad, 0)
    with pytest.raises(ValueError):
        recipes_mod.validate_recipe("not a recipe", 0)


def test_validate_collection(recipes_mod, loaded):
    assert recipes_mod.validate_collection(copy.deepcopy(loaded)) is None
    with pytest.raises(ValueError):
        recipes_mod.validate_collection(loaded[:5])
    dup = copy.deepcopy(loaded)
    dup[1]["id"] = dup[0]["id"]
    with pytest.raises(ValueError):
        recipes_mod.validate_collection(dup)
