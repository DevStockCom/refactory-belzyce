"""Ticket 11 acceptance: server search agrees with the shared parity fixture.

Fixture contract (demo-app/static/tests/fixtures/search-parity.json):
  {"recipes": {"<recipe id>": "<search_text>", ...},      # or [{"id", "search_text"}]
   "cases":   [{"name": str, "query": str, "ids": [..]}]}  # ids in collection order
"""
import json
from urllib.parse import quote

import pytest

import domain

FIXTURE = (
    __import__("pathlib").Path(__file__).parents[1]
    / "static" / "tests" / "fixtures" / "search-parity.json"
)


def _load():
    assert FIXTURE.is_file(), f"missing parity fixture: {FIXTURE}"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    texts = data["recipes"]
    if isinstance(texts, list):
        texts = {item["id"]: item["search_text"] for item in texts}
    return texts, data["cases"]


def _ids_of(case):
    return case["ids"] if "ids" in case else case["expected_ids"]


def _case_params():
    if not FIXTURE.is_file():
        return [pytest.param({"name": "missing-fixture", "query": "", "ids": []}, id="missing-fixture")]
    _, cases = _load()
    return [pytest.param(c, id=c.get("name", repr(c["query"]))) for c in cases]


def test_fixture_exists_and_covers_every_recipe(recipes):
    texts, cases = _load()
    assert list(texts) == [r["id"] for r in recipes]
    assert cases, "fixture has no cases"


def test_search_text_per_recipe_matches_fixture(recipes):
    texts, _ = _load()
    for recipe in recipes:
        assert domain.search_text(recipe) == texts[recipe["id"]], recipe["id"]


@pytest.mark.parametrize("case", _case_params())
def test_search_recipes_ids_match_fixture(recipes, case):
    _load()
    got = [r["id"] for r in domain.search_recipes(recipes, case["query"])]
    assert got == _ids_of(case)


@pytest.mark.parametrize("case", _case_params())
def test_api_recipes_q_ids_match_fixture(client, case):
    _load()
    response = client.get("/api/recipes?q=" + quote(case["query"], safe=""))
    assert response.status_code == 200
    assert [r["id"] for r in response.get_json()] == _ids_of(case)


def test_fixture_expected_ids_follow_trim_lower_substring_rule():
    """Independent reference: the fixture itself must encode the documented rule."""
    texts, cases = _load()
    for case in cases:
        needle = case["query"].strip().lower()
        expected = [i for i, t in texts.items() if needle in t]
        assert _ids_of(case) == expected, case.get("name")


def test_fixture_covers_required_query_kinds():
    texts, cases = _load()
    queries = [c["query"] for c in cases]
    ids = {c["query"]: _ids_of(c) for c in cases}
    all_ids = list(texts)
    assert any(q != q.lower() for q in queries), "needs a mixed-case query"
    assert any(q != q.strip() and q.strip() for q in queries), "needs a padded-whitespace query"
    assert "" in queries and ids[""] == all_ids, "needs an empty query returning every recipe"
    assert any(q.strip() and not ids[q] for q in queries), "needs a no-match query"
    # lowercase/mixed-case variants of one term agree
    by_lower = {}
    for q in queries:
        by_lower.setdefault(q.strip().lower(), set()).add(tuple(ids[q]))
    assert any(len(v) == 1 for k, v in by_lower.items() if k and sum(
        1 for q in queries if q.strip().lower() == k) > 1), "needs case/whitespace variants of one term"
    # ingredient-only: a matching query whose text appears in no title/description/category/tag
    recipes_by_id = {r["id"]: r for r in __import__("recipes").load_recipes()}
    def ingredient_only(q):
        needle = q.strip().lower()
        if not needle or not ids[q]:
            return False
        for rid in ids[q]:
            r = recipes_by_id[rid]
            other = " ".join([r["title"], r["description"], r["category"], *r["dietary_tags"]]).lower()
            if needle in other:
                return False
        return True
    assert any(ingredient_only(q) for q in queries), "needs an ingredient-only query"
    # category and tag queries
    cats = {r["category"].lower() for r in recipes_by_id.values()}
    tags = {t.lower() for r in recipes_by_id.values() for t in r["dietary_tags"]}
    assert any(q.strip().lower() in cats for q in queries), "needs a category query"
    assert any(q.strip().lower() in tags for q in queries), "needs a dietary tag query"


def test_drift_in_search_text_is_detected(recipes, monkeypatch):
    """A changed Python search_text must make the fixture comparison fail."""
    texts, _ = _load()
    monkeypatch.setattr(domain, "search_text", lambda r: r["title"].lower())
    assert any(domain.search_text(r) != texts[r["id"]] for r in recipes)
