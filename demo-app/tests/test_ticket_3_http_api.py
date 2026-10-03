"""Ticket #3 acceptance tests: recipe JSON API, 404 handling, startup and cleanup."""

import json
import re
import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).parents[1]
sys.path.insert(0, str(DEMO))

import domain  # noqa: E402
from app import create_app  # noqa: E402
from recipes import load_recipes  # noqa: E402

RECIPES = load_recipes()
IDS = [r["id"] for r in RECIPES]
# Legacy names are built from fragments so this file never embeds them literally.
_M = "mo" + "vie"
_W = "watch" + "list"


@pytest.fixture()
def flask_app():
    return create_app(testing=True)


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


def ids_of(response):
    return [r["id"] for r in response.get_json()]


# ---- recipes -------------------------------------------------------------


def test_recipe_list_returns_all_in_collection_order(client):
    res = client.get("/api/recipes")
    assert res.status_code == 200
    assert res.get_json() == RECIPES


def test_recipe_detail_returns_full_object(client):
    res = client.get(f"/api/recipes/{IDS[3]}")
    assert res.status_code == 200
    assert res.get_json() == RECIPES[3]


@pytest.mark.parametrize("bad", ["nope", "x", _M])
def test_recipe_detail_unknown_is_404_with_exact_error(client, bad):
    res = client.get(f"/api/recipes/{bad}")
    assert res.status_code == 404
    assert res.get_json() == {"error": "Recipe not found"}


def _ingredient_only_term():
    """A word found in some recipe's ingredients but in none of its other searchable fields."""
    for recipe in RECIPES:
        for line in recipe["ingredients"]:
            word = line.split()[-1].strip(",.()").lower()
            if len(word) > 4 and word.isalpha():
                hits = domain.search_recipes(RECIPES, word)
                other = [
                    " ".join([h["title"], h["description"], h["category"], *h["dietary_tags"]]).lower()
                    for h in hits
                ]
                if hits and all(word not in text for text in other):
                    return word
    return RECIPES[0]["ingredients"][0].split()[-1].lower()


@pytest.mark.parametrize(
    "q",
    ["", "   ", "vegan", "VEGAN", "VeGaN", "  vegetarian  ", "dessert", "Breakfast", "zzzz-no-such-recipe"],
)
def test_search_matches_domain_for_case_variants(client, q):
    res = client.get("/api/recipes", query_string={"q": q})
    assert res.status_code == 200
    assert ids_of(res) == [r["id"] for r in domain.search_recipes(RECIPES, q)]


def test_search_matches_domain_for_ingredient_only_term(client):
    term = _ingredient_only_term()
    expected = [r["id"] for r in domain.search_recipes(RECIPES, term)]
    assert expected
    for variant in (term, term.upper(), term.title()):
        assert ids_of(client.get("/api/recipes", query_string={"q": variant})) == expected


def test_search_no_match_is_empty_list(client):
    res = client.get("/api/recipes?q=qqqqzzzz")
    assert res.status_code == 200
    assert res.get_json() == []


# ---- cookbook ------------------------------------------------------------


def test_cookbook_starts_empty(client):
    res = client.get("/api/cookbook")
    assert res.status_code == 200
    assert res.get_json() == []


def test_cookbook_post_returns_201_and_recipe_ids(client):
    res = client.post("/api/cookbook", json={"id": IDS[0]})
    assert res.status_code == 201
    assert res.get_json() == {"recipe_ids": [IDS[0]]}


def test_cookbook_get_returns_full_objects_in_collection_order(client):
    client.post("/api/cookbook", json={"id": IDS[5]})
    client.post("/api/cookbook", json={"id": IDS[1]})
    res = client.post("/api/cookbook", json={"id": IDS[1]})  # idempotent re-save
    assert res.status_code == 201
    assert res.get_json() == {"recipe_ids": [IDS[1], IDS[5]]}
    got = client.get("/api/cookbook")
    assert got.status_code == 200
    assert got.get_json() == [RECIPES[1], RECIPES[5]]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": {"id": "no-such-recipe"}},
        {"json": {}},
        {"json": {"id": 5}},
        {"json": {"id": None}},
        {"json": ["x"]},
        {"data": "not json", "content_type": "text/plain"},
        {"data": "{broken", "content_type": "application/json"},
    ],
)
def test_cookbook_post_unknown_or_malformed_is_400(client, kwargs):
    res = client.post("/api/cookbook", **kwargs)
    assert res.status_code == 400
    assert res.get_json() == {"error": "Unknown recipe"}
    assert client.get("/api/cookbook").get_json() == []


def test_cookbook_delete_removes_and_returns_recipe_ids(client):
    client.post("/api/cookbook", json={"id": IDS[0]})
    client.post("/api/cookbook", json={"id": IDS[2]})
    res = client.delete(f"/api/cookbook/{IDS[0]}")
    assert res.status_code == 200
    assert res.get_json() == {"recipe_ids": [IDS[2]]}
    assert client.get("/api/cookbook").get_json() == [RECIPES[2]]


@pytest.mark.parametrize("target", [IDS[0], "no-such-recipe"])
def test_cookbook_delete_is_idempotent(client, target):
    for _ in range(2):
        res = client.delete(f"/api/cookbook/{target}")
        assert res.status_code == 200
        assert res.get_json() == {"recipe_ids": []}


def test_cookbook_state_is_fresh_per_app_instance(client):
    client.post("/api/cookbook", json={"id": IDS[0]})
    other = create_app(testing=True).test_client()
    assert other.get("/api/cookbook").get_json() == []


def test_cookbook_store_lives_in_app_extensions(flask_app):
    assert "cookbook" in flask_app.extensions, "app.extensions['cookbook'] is missing"
    store = flask_app.extensions["cookbook"]
    assert isinstance(store, domain.CookbookStore)
    flask_app.test_client().post("/api/cookbook", json={"id": IDS[0]})
    assert store.ids() == [IDS[0]]
    assert store is not create_app(testing=True).extensions["cookbook"]


# ---- rails ---------------------------------------------------------------


def test_rails_returns_four_named_rails(client):
    res = client.get("/api/rails")
    assert res.status_code == 200
    rails = res.get_json()
    assert [r["name"] for r in rails] == list(domain.RAIL_NAMES)
    assert all(set(r) == {"name", "recipe_ids"} for r in rails)
    assert rails == domain.build_rails(RECIPES, [])
    assert rails[3]["recipe_ids"] == []
    assert all(len(r["recipe_ids"]) >= 2 for r in rails[:3])


def test_cookbook_rail_changes_after_save_and_remove(client):
    client.post("/api/cookbook", json={"id": IDS[4]})
    rails = client.get("/api/rails").get_json()
    assert rails[3] == {"name": "My Cookbook", "recipe_ids": [IDS[4]]}
    assert rails == domain.build_rails(RECIPES, [IDS[4]])
    client.delete(f"/api/cookbook/{IDS[4]}")
    assert client.get("/api/rails").get_json()[3]["recipe_ids"] == []


# ---- 404 handling --------------------------------------------------------

LEGACY = [
    f"/{_M}/x",
    f"/{_M}/inception",
    f"/api/{_M}s",
    f"/api/{_M}s/x",
    f"/api/{_W}",
    f"/api/{_W}/x",
    "/api/unknown",
    "/nope",
]


@pytest.mark.parametrize("path", LEGACY)
def test_legacy_and_unknown_paths_are_404_with_tablestory_body(client, path):
    res = client.get(path)
    assert res.status_code == 404
    body = res.get_data(as_text=True)
    assert body.strip()
    assert _M not in body.lower() and _W not in body.lower()
    assert "TableStory" in body or res.is_json


@pytest.mark.parametrize("path", [f"/api/{_M}s", f"/api/{_W}", f"/api/{_W}/x"])
def test_legacy_api_other_methods_do_not_succeed(client, path):
    assert client.post(path, json={"id": "x"}).status_code in (404, 405)
    assert client.delete(path).status_code in (404, 405)


@pytest.mark.parametrize("path", ["/api/unknown", f"/api/{_M}s/x", f"/api/{_W}"])
def test_api_404_is_json_with_error_text(client, path):
    res = client.get(path)
    assert res.status_code == 404
    assert res.is_json
    assert isinstance(res.get_json().get("error"), str) and res.get_json()["error"]


def test_page_404_uses_html_template_and_tablestory_wording(client):
    res = client.get("/nope")
    assert res.status_code == 404
    assert "text/html" in res.content_type
    assert "TableStory" in res.get_data(as_text=True)


@pytest.mark.parametrize(
    "path", ["/zebra-marker-path", f"/{_M}/zebra-marker", "/api/zebra-marker-path", "/recipe/zebra-marker"]
)
def test_404_never_echoes_request_path(client, path):
    res = client.get(path)
    assert res.status_code == 404
    assert "zebra-marker" not in res.get_data(as_text=True)


def test_registered_routes_are_only_the_recipe_surface(flask_app):
    rules = {r.rule for r in flask_app.url_map.iter_rules()}
    assert not [r for r in rules if _M in r or _W in r]
    assert {
        "/",
        "/recipe/<recipe_id>",
        "/api/recipes",
        "/api/recipes/<recipe_id>",
        "/api/cookbook",
        "/api/cookbook/<recipe_id>",
        "/api/rails",
    } <= rules


# ---- startup validation --------------------------------------------------


def _bad_data(tmp_path, monkeypatch, mutate):
    data = json.loads((DEMO / "recipes.json").read_text())
    mutate(data)
    (tmp_path / "recipes.json").write_text(json.dumps(data))
    import recipes as recipes_module

    monkeypatch.setattr(recipes_module, "ROOT", tmp_path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d[0].update(difficulty="Impossible"),
        lambda d: d[0].update(steps=["only one"]),
        lambda d: d.__delitem__(slice(3, None)),
        lambda d: d.append(dict(d[0])),
        lambda d: d[1].update(prep_minutes=0),
    ],
)
def test_app_refuses_to_start_on_invalid_data(tmp_path, monkeypatch, mutate):
    _bad_data(tmp_path, monkeypatch, mutate)
    with pytest.raises(ValueError):
        create_app(testing=True)


def test_app_refuses_to_start_on_invalid_rails(monkeypatch):
    import app as app_module

    def bad_rails(recipes, saved_ids):
        return [{"name": n, "recipe_ids": []} for n in domain.RAIL_NAMES]

    monkeypatch.setattr(domain, "build_rails", bad_rails)
    monkeypatch.setattr(app_module, "build_rails", bad_rails, raising=False)
    with pytest.raises(ValueError):
        create_app(testing=True)


# ---- cleanup -------------------------------------------------------------


def test_legacy_catalog_and_test_module_are_removed():
    assert not (DEMO / "catalog.json").exists()
    assert not (DEMO / "tests" / "test_app.py").exists()


def test_app_source_has_no_legacy_symbols():
    source = (DEMO / "app.py").read_text()
    assert not re.search(_M + "|" + _W + "|catalog", source, re.IGNORECASE)


def test_test_sources_have_no_legacy_symbols():
    pattern = re.compile(r"\b(" + _M + r"s?|" + _W + r")\b", re.IGNORECASE)
    for path in (DEMO / "tests").glob("*.py"):
        if path.name.startswith("test_ticket_3"):
            continue  # acceptance files build the legacy names from fragments
        assert not pattern.search(path.read_text()), path.name
