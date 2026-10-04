"""Server search matches the shared client/server parity fixture."""
import json
from pathlib import Path

import pytest

from domain import search_recipes, search_text

FIXTURE = Path(__file__).parents[1] / "static" / "tests" / "fixtures" / "search-parity.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
CASES = DATA["cases"]


def test_search_text_per_recipe_matches_fixture(recipes):
    assert [(r["id"], search_text(r)) for r in recipes] == [
        (e["id"], e["search_text"]) for e in DATA["recipes"]
    ]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_search_recipes_matches_fixture(recipes, case):
    assert [r["id"] for r in search_recipes(recipes, case["query"])] == case["expected_ids"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_api_recipes_query_matches_fixture(client, case):
    response = client.get("/api/recipes", query_string={"q": case["query"]})
    assert response.status_code == 200
    assert [r["id"] for r in response.get_json()] == case["expected_ids"]
