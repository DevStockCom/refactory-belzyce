"""Release scan: no banned terms, no legacy routes, no new dependencies."""
import pytest
from app import create_app
from scan_rules import (
    LEGACY_ROUTES,
    ROOT,
    check_no_new_dependencies,
    find_terms,
    scan_files,
    scan_json_keys,
    scan_rendered,
    scan_symbols,
    split_words,
)

POSITIVES = [
    "Pocket " + "Cin" + "ema", "mo" + "vie", "Mo" + "vies", "fi" + "lm", "FI" + "LMS", "cin" + "ema",
    "watch" + "list", "pos" + "ter", "run" + "time", "rat" + "ing", "gen" + "res", "P" + "C",
]
GUARDS = ["integrating", "generate", "generated", "Fil" + "more", "P" + "Cs", "p" + "c", "operating"]


@pytest.fixture()
def client():
    return create_app(testing=True).test_client()


def fail_with(hits):
    return "\n".join(str(hit) for hit in hits)


@pytest.mark.parametrize("term", POSITIVES)
def test_scanner_true_positives(term):
    assert find_terms(f"the {term} here"), term


@pytest.mark.parametrize("text", GUARDS)
def test_scanner_false_positive_guards(text):
    assert find_terms(text) == [], text


def test_symbol_splitting():
    assert split_words("matchesFilm") == ["matches", "Film"]
    assert split_words("saved_ids") == ["saved", "ids"]
    assert [h.term for h in scan_json_keys({"a": [{"recipe_ids": 1}]}, "x")] == []
    assert [h.term for h in scan_json_keys({"a": [{"rat" + "ing": 1}]}, "x")] == ["rat" + "ing"]


def test_files_have_no_banned_terms():
    hits = scan_files()
    assert not hits, fail_with(hits)


def test_symbols_have_no_banned_terms():
    hits = scan_symbols()
    assert not hits, fail_with(hits)


def test_rendered_pages_and_api_payloads_are_clean(client):
    recipe_ids = [r["id"] for r in client.get("/api/recipes").get_json()]
    hits = scan_rendered(client, recipe_ids)
    assert not hits, fail_with(hits)


@pytest.mark.parametrize("legacy", LEGACY_ROUTES)
def test_legacy_routes_return_404(client, legacy):
    for suffix in ["", "/1", "/anything"]:
        assert client.get(legacy + suffix).status_code == 404
        assert client.post(legacy + suffix, json={"id": "x"}).status_code in (404, 405)
        assert client.delete(legacy + suffix).status_code in (404, 405)


def test_no_new_dependencies():
    problems = check_no_new_dependencies()
    assert not problems, "\n".join(problems)


def test_readme_documents_tablestory_and_is_clean():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for needle in [
        "TableStory",
        "python -m pip install -r demo-app/requirements.txt",
        "python demo-app/app.py",
        "http://127.0.0.1:5000/",
        "http://127.0.0.1:5000/?mode=tv",
        "pytest -q demo-app/tests",
        "node --test demo-app/static/tests/*.test.js",
    ]:
        assert needle in text, needle
    assert find_terms(text) == []
