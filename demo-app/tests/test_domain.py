"""Unit tests for domain services using shipped data and a small fixture."""
import pytest

from domain import (
    RAIL_NAMES, CookbookStore, build_rails, search_recipes, search_text,
    validate_rails,
)
from recipes import load_recipes


def _recipe(rid, tags=(), ingredients=("water",), prep=10, cook=10, featured=False):
    return {
        "id": rid, "title": rid.title(), "description": "A dish.",
        "category": "Dinner", "dietary_tags": list(tags),
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
        _recipe("one", ["Vegetarian"], ["saffron"], featured=True),
        _recipe("two", [], ["beef"], prep=40, cook=20),
        _recipe("three", ["Vegetarian"], ["flour"], featured=True),
    ]


def test_search_text_lowercase(small):
    assert search_text(small[0]) == search_text(small[0]).lower()
    assert "saffron" in search_text(small[0])


def test_search_case_whitespace_and_ingredient(small):
    assert [r["id"] for r in search_recipes(small, "  SAFFRON ")] == ["one"]
    assert [r["id"] for r in search_recipes(small, "vegetarian")] == ["one", "three"]


def test_search_blank_and_no_match(small):
    assert len(search_recipes(small, None)) == 3
    assert len(search_recipes(small, "  ")) == 3
    assert search_recipes(small, "zzz") == []


def test_shipped_rails_meet_minimum(shipped):
    rails = build_rails(shipped, set())
    assert [r["name"] for r in rails] == list(RAIL_NAMES)
    assert all(len(r["recipe_ids"]) >= 2 for r in rails[:3])
    validate_rails(rails, shipped)


def test_rails_membership(small):
    rails = build_rails(small, {"two"})
    assert rails[0]["recipe_ids"] == ["one", "three"]
    assert rails[1]["recipe_ids"] == ["one", "three"]
    assert rails[3]["recipe_ids"] == ["two"]


def test_validate_rails_errors(small):
    rails = build_rails(small, set())
    with pytest.raises(ValueError):
        validate_rails(rails[:3], small)
    with pytest.raises(ValueError):
        validate_rails([rails[1], rails[0], rails[2], rails[3]], small)
    short = [dict(rails[0], recipe_ids=["one"]), *rails[1:]]
    with pytest.raises(ValueError):
        validate_rails(short, small)
    bad = [*rails[:3], {"name": "My Cookbook", "recipe_ids": ["ghost"]}]
    with pytest.raises(ValueError):
        validate_rails(bad, small)


def test_store_add_remove_idempotent_and_ordered(small):
    store = CookbookStore(small)
    assert store.add("ghost") is False
    assert store.add(None) is False
    assert store.add("three") and store.add("three") and store.add("one")
    assert store.ids() == ["one", "three"]
    assert [r["id"] for r in store.recipes()] == ["one", "three"]
    store.remove("one")
    store.remove("one")
    assert not store.contains("one")


def test_stores_are_independent(small):
    a, b = CookbookStore(small), CookbookStore(small)
    a.add("one")
    assert b.ids() == []
