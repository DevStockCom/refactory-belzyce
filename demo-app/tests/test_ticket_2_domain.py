"""Acceptance tests for ticket #2: domain services (search, rails, cookbook store)."""
import ast
import importlib
import re
from pathlib import Path

import pytest

from recipes import load_recipes, total_minutes

DOMAIN_PATH = Path(__file__).parents[1] / "domain.py"
BANNED = [
    "mo" + "vie", "fi" + "lm", "cin" + "ema", "watch" + "list",
    "pos" + "ter", "run" + "time", "rat" + "ing", "gen" + "re",
]


def _domain():
    assert DOMAIN_PATH.exists(), "demo-app/domain.py must exist"
    return importlib.import_module("domain")


def _recipe(rid, title="Dish", description="A dish.", category="Dinner",
            tags=(), ingredients=("water",), prep=10, cook=10, featured=False):
    return {
        "id": rid, "title": title, "description": description,
        "category": category, "dietary_tags": list(tags),
        "prep_minutes": prep, "cook_minutes": cook, "difficulty": "Easy",
        "servings": 2, "ingredients": list(ingredients),
        "steps": ["a", "b", "c"], "colors": ["#fff", "#000"],
        "featured": featured,
    }


@pytest.fixture()
def shipped():
    return load_recipes()


@pytest.fixture()
def small():
    return [
        _recipe("alpha-soup", "Alpha Soup", "Warming bowl.", "Lunch",
                ["Vegan", "Vegetarian"], ["Saffron threads", "water"],
                prep=5, cook=10, featured=True),
        _recipe("beta-stew", "Beta Stew", "Slow beef.", "Dinner",
                [], ["beef", "carrot"], prep=20, cook=60, featured=False),
        _recipe("gamma-cake", "Gamma Cake", "Sweet.", "Dessert",
                ["Vegetarian"], ["flour", "sugar"], prep=15, cook=15,
                featured=True),
    ]


# --- module shape -----------------------------------------------------------

def test_domain_module_exists_and_exports_api():
    d = _domain()
    for name in ("search_text", "search_recipes", "build_rails",
                 "validate_rails", "CookbookStore", "RAIL_NAMES"):
        assert hasattr(d, name), name


def test_domain_has_no_flask_import():
    assert DOMAIN_PATH.exists(), "demo-app/domain.py must exist"
    tree = ast.parse(DOMAIN_PATH.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(a.name.split(".")[0] != "flask" for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "flask"


def test_domain_symbols_have_no_banned_terms():
    assert DOMAIN_PATH.exists(), "demo-app/domain.py must exist"
    tree = ast.parse(DOMAIN_PATH.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    for name in names:
        for term in BANNED:
            assert term not in name.lower(), f"{name} contains {term}"


# --- search -----------------------------------------------------------------

def test_search_text_is_lowercase_and_covers_all_fields(small):
    d = _domain()
    text = d.search_text(small[0])
    assert text == text.lower()
    for part in ("alpha soup", "warming bowl", "lunch", "vegan",
                 "vegetarian", "saffron threads", "water"):
        assert part in text


@pytest.mark.parametrize("q,expected", [
    ("alpha", ["alpha-soup"]),                 # title
    ("SLOW BEEF", ["beta-stew"]),              # description, case
    ("dessert", ["gamma-cake"]),               # category
    ("vegan", ["alpha-soup"]),                 # dietary tag
    ("  Saffron  ".strip(), ["alpha-soup"]),   # ingredient-only
    ("   carrot   ", ["beta-stew"]),           # whitespace trimmed
    ("VEGETARIAN", ["alpha-soup", "gamma-cake"]),  # collection order
])
def test_search_recipes_matches(small, q, expected):
    d = _domain()
    assert [r["id"] for r in d.search_recipes(small, q)] == expected


@pytest.mark.parametrize("q", [None, "", "   ", "\t\n"])
def test_search_recipes_blank_returns_all(small, q):
    d = _domain()
    assert [r["id"] for r in d.search_recipes(small, q)] == [
        r["id"] for r in small]


def test_search_recipes_no_match_returns_empty_list(small):
    d = _domain()
    assert d.search_recipes(small, "zzzznothing") == []


def test_search_recipes_on_shipped_data_ingredient_only(shipped):
    d = _domain()
    ingredient = shipped[0]["ingredients"][0]
    needle = ingredient.upper()
    got = d.search_recipes(shipped, f"  {needle}  ")
    assert shipped[0]["id"] in [r["id"] for r in got]
    assert [r["id"] for r in got] == [
        r["id"] for r in shipped
        if ingredient.lower() in d.search_text(r)]


# --- rails ------------------------------------------------------------------

def test_rail_constants_and_order():
    d = _domain()
    assert tuple(d.RAIL_NAMES) == (
        "Popular this week", "Ready in 30 minutes",
        "Vegetarian favourites", "My Cookbook")


def test_build_rails_shape_and_membership(small):
    d = _domain()
    rails = d.build_rails(small, {"beta-stew"})
    assert [r["name"] for r in rails] == list(d.RAIL_NAMES)
    assert all(set(r) == {"name", "recipe_ids"} for r in rails)
    assert rails[0]["recipe_ids"] == ["alpha-soup", "gamma-cake"]
    assert rails[1]["recipe_ids"] == ["alpha-soup", "gamma-cake"]
    assert rails[2]["recipe_ids"] == ["alpha-soup", "gamma-cake"]
    assert rails[3]["recipe_ids"] == ["beta-stew"]


def test_build_rails_quick_boundary_is_inclusive():
    d = _domain()
    recipes = [
        _recipe("a-30", prep=10, cook=20),
        _recipe("b-31", prep=10, cook=21),
        _recipe("c-29", prep=29, cook=0),
    ]
    quick = d.build_rails(recipes, [])[1]["recipe_ids"]
    assert quick == ["a-30", "c-29"]


def test_build_rails_collection_order_not_saved_order(small):
    d = _domain()
    rails = d.build_rails(small, ["gamma-cake", "alpha-soup"])
    assert rails[3]["recipe_ids"] == ["alpha-soup", "gamma-cake"]


def test_build_rails_empty_cookbook_is_empty_list(small):
    d = _domain()
    assert d.build_rails(small, set())[3] == {
        "name": "My Cookbook", "recipe_ids": []}


def test_build_rails_on_shipped_data(shipped):
    d = _domain()
    rails = d.build_rails(shipped, set())
    assert [r["name"] for r in rails] == [
        "Popular this week", "Ready in 30 minutes",
        "Vegetarian favourites", "My Cookbook"]
    order = [r["id"] for r in shipped]
    for rail in rails[:3]:
        assert len(rail["recipe_ids"]) >= 2
        assert rail["recipe_ids"] == [i for i in order
                                      if i in rail["recipe_ids"]]
    by_id = {r["id"]: r for r in shipped}
    assert rails[0]["recipe_ids"] == [r["id"] for r in shipped if r["featured"]]
    assert rails[1]["recipe_ids"] == [
        r["id"] for r in shipped if total_minutes(r) <= 30]
    assert rails[2]["recipe_ids"] == [
        i for i in order if "Vegetarian" in by_id[i]["dietary_tags"]]
    d.validate_rails(rails, shipped)


def test_validate_rails_accepts_valid(shipped):
    d = _domain()
    assert d.validate_rails(d.build_rails(shipped, set()), shipped) is None


def test_validate_rails_rejects_wrong_count(shipped):
    d = _domain()
    rails = d.build_rails(shipped, set())
    with pytest.raises(ValueError):
        d.validate_rails(rails[:3], shipped)
    with pytest.raises(ValueError):
        d.validate_rails(rails + [rails[0]], shipped)


def test_validate_rails_rejects_wrong_order(shipped):
    d = _domain()
    rails = d.build_rails(shipped, set())
    swapped = [rails[1], rails[0], rails[2], rails[3]]
    with pytest.raises(ValueError):
        d.validate_rails(swapped, shipped)


def test_validate_rails_rejects_short_non_cookbook_rail(shipped):
    d = _domain()
    for idx in range(3):
        rails = d.build_rails(shipped, set())
        rails[idx] = {"name": rails[idx]["name"],
                      "recipe_ids": rails[idx]["recipe_ids"][:1]}
        with pytest.raises(ValueError):
            d.validate_rails(rails, shipped)


def test_validate_rails_allows_short_cookbook_rail(shipped):
    d = _domain()
    rails = d.build_rails(shipped, [shipped[0]["id"]])
    d.validate_rails(rails, shipped)


def test_validate_rails_rejects_unknown_id(shipped):
    d = _domain()
    rails = d.build_rails(shipped, set())
    rails[0] = {"name": rails[0]["name"],
                "recipe_ids": rails[0]["recipe_ids"] + ["no-such-recipe"]}
    with pytest.raises(ValueError):
        d.validate_rails(rails, shipped)
    rails = d.build_rails(shipped, set())
    rails[3] = {"name": "My Cookbook", "recipe_ids": ["no-such-recipe"]}
    with pytest.raises(ValueError):
        d.validate_rails(rails, shipped)


def test_validate_rails_fails_on_shrunken_collection(small):
    d = _domain()
    shrunk = small[:1]
    with pytest.raises(ValueError):
        d.validate_rails(d.build_rails(shrunk, set()), shrunk)


# --- cookbook store ---------------------------------------------------------

def test_store_add_valid_returns_true_and_contains(small):
    d = _domain()
    store = d.CookbookStore(small)
    assert store.add("beta-stew") is True
    assert store.contains("beta-stew") is True
    assert store.contains("alpha-soup") is False


@pytest.mark.parametrize("bad", ["nope", "", None, 5, ["alpha-soup"],
                                 {"id": "alpha-soup"}, b"alpha-soup"])
def test_store_add_rejects_unknown_or_non_string(small, bad):
    d = _domain()
    store = d.CookbookStore(small)
    assert store.add(bad) is False
    assert store.ids() == []
    assert store.recipes() == []


def test_store_add_is_idempotent(small):
    d = _domain()
    store = d.CookbookStore(small)
    assert store.add("alpha-soup") is True
    assert store.add("alpha-soup") is True
    assert store.ids() == ["alpha-soup"]


def test_store_remove_is_idempotent_and_never_raises(small):
    d = _domain()
    store = d.CookbookStore(small)
    store.add("alpha-soup")
    store.remove("alpha-soup")
    store.remove("alpha-soup")
    store.remove("unknown-id")
    store.remove(None)
    assert store.ids() == []
    assert store.contains("alpha-soup") is False


def test_store_lists_follow_collection_order(small):
    d = _domain()
    store = d.CookbookStore(small)
    for rid in ("gamma-cake", "beta-stew", "alpha-soup"):
        store.add(rid)
    assert store.ids() == ["alpha-soup", "beta-stew", "gamma-cake"]
    assert [r["id"] for r in store.recipes()] == store.ids()
    assert store.recipes()[0] == small[0]
    store.remove("beta-stew")
    assert store.ids() == ["alpha-soup", "gamma-cake"]


def test_store_instances_do_not_share_state(small):
    d = _domain()
    one, two = d.CookbookStore(small), d.CookbookStore(small)
    one.add("alpha-soup")
    assert two.ids() == []
    assert two.contains("alpha-soup") is False
    two.add("beta-stew")
    assert one.ids() == ["alpha-soup"]


def test_store_with_shipped_data(shipped):
    d = _domain()
    store = d.CookbookStore(shipped)
    last, first = shipped[-1]["id"], shipped[0]["id"]
    assert store.add(last) and store.add(first)
    assert store.ids() == [first, last]
    rails = d.build_rails(shipped, store.ids())
    assert rails[3]["recipe_ids"] == [first, last]
