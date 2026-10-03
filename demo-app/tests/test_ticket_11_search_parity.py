"""Acceptance tests for ticket #11: client/server search parity fixture.

The shared fixture lives at static/tests/fixtures/search-parity.json. It maps
every recipe id to its search_text and lists query -> expected-ids cases.
"""
import json
from pathlib import Path

import domain

FIXTURE = Path(__file__).parents[1] / "static" / "tests" / "fixtures" / "search-parity.json"


def _load():
    assert FIXTURE.is_file(), f"missing parity fixture: {FIXTURE}"
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _texts(data):
    raw = data.get("texts", data.get("recipes"))
    assert raw is not None, "fixture needs a per-recipe search_text collection"
    if isinstance(raw, dict):
        return dict(raw)
    return {item["id"]: item["search_text"] for item in raw}


def _cases(data):
    raw = data.get("cases", data.get("queries"))
    assert raw, "fixture needs query cases"
    out = []
    for case in raw:
        ids = case.get("ids", case.get("expected_ids"))
        assert isinstance(ids, list), f"case without ids list: {case!r}"
        out.append((case["query"], ids))
    return out


def test_fixture_texts_cover_every_recipe_in_order(recipes):
    texts = _texts(_load())
    assert list(texts) == [r["id"] for r in recipes]


def test_search_text_matches_fixture_per_recipe(recipes):
    texts = _texts(_load())
    for recipe in recipes:
        assert domain.search_text(recipe) == texts[recipe["id"]], recipe["id"]


def test_search_recipes_matches_fixture_for_every_case(recipes):
    for query, ids in _cases(_load()):
        got = [r["id"] for r in domain.search_recipes(recipes, query)]
        assert got == ids, f"query {query!r}"


def test_api_recipes_q_matches_fixture_for_every_case(client):
    for query, ids in _cases(_load()):
        resp = client.get("/api/recipes", query_string={"q": query})
        assert resp.status_code == 200
        assert [r["id"] for r in resp.get_json()] == ids, f"query {query!r}"


def test_fixture_covers_required_query_kinds(recipes):
    cases = _cases(_load())
    queries = [q for q, _ in cases]
    by_query = dict(cases)

    assert by_query.get("") == [r["id"] for r in recipes], "empty query returns all"
    assert any(q.strip() and q != q.lower() for q in queries), "mixed-case query"
    assert any(q.strip() and q != q.strip() for q in queries), "padded whitespace query"
    assert any(q.strip() and ids == [] for q, ids in cases), "no-match query"

    def ingredient_only(q):
        needle = q.strip().lower()
        if not needle:
            return False
        hits = [r for r in recipes if needle in domain.search_text(r)]
        return bool(hits) and all(
            needle not in " ".join(
                [r["title"], r["description"], r["category"], *r["dietary_tags"]]
            ).lower()
            for r in hits
        )

    assert any(ingredient_only(q) for q in queries), "ingredient-only query"
    categories = {r["category"].lower() for r in recipes}
    assert any(q.strip().lower() in categories for q in queries), "category query"
    tags = {t.lower() for r in recipes for t in r["dietary_tags"]}
    assert any(q.strip().lower() in tags for q in queries), "tag query"


def test_case_and_padding_variants_agree_with_normalised_query():
    by_query = dict(_cases(_load()))
    for query, ids in by_query.items():
        normalised = query.strip().lower()
        if normalised in by_query:
            assert ids == by_query[normalised], f"variant {query!r}"


def test_fixture_would_detect_python_search_text_drift(recipes, monkeypatch):
    """Changing search_text alone must break the fixture comparison."""
    data = _load()
    texts = _texts(data)
    monkeypatch.setattr(
        domain, "search_text", lambda r: " ".join([r["title"], r["category"]]).lower()
    )
    assert any(domain.search_text(r) != texts[r["id"]] for r in recipes)
    assert any(
        [r["id"] for r in domain.search_recipes(recipes, q)] != ids
        for q, ids in _cases(data)
    )
