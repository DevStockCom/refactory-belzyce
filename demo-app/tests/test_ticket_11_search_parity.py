"""Ticket 11 acceptance: server search matches the shared client/server parity fixture.

Fixture contract (demo-app/static/tests/fixtures/search-parity.json):
  {"recipes": [{"id": str, "search_text": str}, ...],
   "cases":   [{"name": str, "query": str, "expected_ids": [str, ...]}, ...]}
"""
import json
from pathlib import Path

from domain import search_recipes, search_text

FIXTURE = Path(__file__).parents[1] / "static" / "tests" / "fixtures" / "search-parity.json"


def load_fixture():
    assert FIXTURE.is_file(), f"missing parity fixture: {FIXTURE}"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(data.get("recipes"), list) and data["recipes"], "fixture needs recipes"
    assert isinstance(data.get("cases"), list) and data["cases"], "fixture needs cases"
    return data


def test_fixture_exists_and_has_well_formed_entries():
    data = load_fixture()
    for entry in data["recipes"]:
        assert set(entry) == {"id", "search_text"}
        assert isinstance(entry["id"], str) and isinstance(entry["search_text"], str)
    names = [c["name"] for c in data["cases"]]
    assert len(names) == len(set(names)), "case names must be unique"
    for case in data["cases"]:
        assert set(case) == {"name", "query", "expected_ids"}
        assert isinstance(case["query"], str)
        assert isinstance(case["expected_ids"], list)


def test_fixture_covers_every_recipe_in_collection_order(recipes):
    data = load_fixture()
    assert [e["id"] for e in data["recipes"]] == [r["id"] for r in recipes]


def test_search_text_per_recipe_equals_fixture(recipes):
    data = load_fixture()
    by_id = {e["id"]: e["search_text"] for e in data["recipes"]}
    for recipe in recipes:
        assert search_text(recipe) == by_id[recipe["id"]], recipe["id"]


def test_search_recipes_ids_equal_fixture_for_every_case(recipes):
    for case in load_fixture()["cases"]:
        got = [r["id"] for r in search_recipes(recipes, case["query"])]
        assert got == case["expected_ids"], case["name"]


def test_api_recipes_q_ids_equal_fixture_for_every_case(client):
    for case in load_fixture()["cases"]:
        response = client.get("/api/recipes", query_string={"q": case["query"]})
        assert response.status_code == 200, case["name"]
        assert [r["id"] for r in response.get_json()] == case["expected_ids"], case["name"]


def test_fixture_expected_ids_reference_known_recipes_in_order():
    data = load_fixture()
    known = [e["id"] for e in data["recipes"]]
    for case in data["cases"]:
        assert set(case["expected_ids"]) <= set(known), case["name"]
        assert case["expected_ids"] == [i for i in known if i in case["expected_ids"]], case["name"]


def test_fixture_has_empty_and_nonsense_queries(recipes):
    data = load_fixture()
    by_query = {c["query"]: c for c in data["cases"]}
    assert "" in by_query, "empty query case required"
    assert by_query[""]["expected_ids"] == [r["id"] for r in recipes]
    assert any(c["expected_ids"] == [] and c["query"].strip() for c in data["cases"]), \
        "no-match query case required"


def test_fixture_has_padded_whitespace_query():
    data = load_fixture()
    padded = [c for c in data["cases"] if c["query"].strip() and c["query"] != c["query"].strip()]
    assert padded, "padded-whitespace query case required"
    by_query = {c["query"]: c for c in data["cases"]}
    for case in padded:
        assert case["expected_ids"], case["name"]
        stripped = by_query.get(case["query"].strip())
        if stripped:
            assert stripped["expected_ids"] == case["expected_ids"]


def test_fixture_has_mixed_case_variants_agreeing_with_lowercase():
    data = load_fixture()
    mixed = [c for c in data["cases"]
             if c["query"].strip() and c["query"].strip() != c["query"].strip().lower()]
    assert mixed, "mixed-case query case required"
    for case in mixed:
        assert case["expected_ids"], case["name"]
        twin = [c for c in data["cases"] if c["query"] == case["query"].strip().lower()]
        assert twin, f"lowercase twin for {case['query']!r} required"
        assert twin[0]["expected_ids"] == case["expected_ids"]


def test_fixture_has_ingredient_only_query(recipes):
    data = load_fixture()
    found = False
    for case in data["cases"]:
        needle = case["query"].strip().lower()
        if not needle:
            continue
        expected = set(case["expected_ids"])
        for r in recipes:
            head = " ".join([r["title"], r["description"], r["category"], *r["dietary_tags"]]).lower()
            if r["id"] in expected and needle not in head \
                    and any(needle in i.lower() for i in r["ingredients"]):
                found = True
    assert found, "a query matching a recipe only through its ingredients is required"


def test_fixture_has_category_and_tag_queries(recipes):
    data = load_fixture()
    needles = [c["query"].strip().lower() for c in data["cases"] if c["query"].strip()]
    categories = {r["category"].lower() for r in recipes}
    tags = {t.lower() for r in recipes for t in r["dietary_tags"]}
    assert any(n in categories for n in needles), "category query required"
    assert any(n in tags for n in needles), "dietary tag query required"


def test_fixture_cases_are_discriminating():
    data = load_fixture()
    total = len(data["recipes"])
    sizes = {len(c["expected_ids"]) for c in data["cases"]}
    assert 0 in sizes and total in sizes
    assert any(0 < s < total for s in sizes), "need a query narrowing to a strict subset"


def test_drift_in_python_search_text_is_detected(recipes, monkeypatch):
    """Gate sensitivity: a changed search_text must break the fixture comparison."""
    import domain
    data = load_fixture()
    by_id = {e["id"]: e["search_text"] for e in data["recipes"]}
    monkeypatch.setattr(domain, "search_text", lambda r: r["title"].lower())
    assert any(domain.search_text(r) != by_id[r["id"]] for r in recipes)
    drifted = [
        c for c in data["cases"]
        if [r["id"] for r in domain.search_recipes(recipes, c["query"])] != c["expected_ids"]
    ]
    assert drifted, "fixture cases must fail when search_text drifts"
