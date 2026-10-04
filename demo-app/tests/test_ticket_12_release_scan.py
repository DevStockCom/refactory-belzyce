"""Acceptance tests for ticket 12: release scan, dependency check, README.

Self-contained: banned terms are assembled from fragments so this file never
trips the repository-wide scan it helps protect.
"""
import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

_WORDS = [
    "pocket" + r"\s+" + "cin" + "ema",
    "mo" + "vies?",
    "fi" + "lms?",
    "cin" + "ema",
    "watch" + "list",
    "pos" + "ters?",
    "run" + "time",
    "rat" + "ings?",
    "gen" + "res?",
]
BANNED = [re.compile(r"\b" + w + r"\b", re.I) for w in _WORDS]
STANDALONE_UPPER = re.compile(r"\b" + "P" + "C" + r"\b")
LEGACY = ["/mo" + "vie", "/api/mo" + "vies", "/api/watch" + "list"]
OWN = {"scan_rules.py", "test_release_scan.py", "test_ticket_12_release_scan.py"}
TEXT_SUFFIXES = {".py", ".html", ".css", ".js", ".json", ".md", ".txt"}


def hits_in(text):
    found = [p.pattern for p in BANNED if p.search(text)]
    if STANDALONE_UPPER.search(text):
        found.append("upper")
    return found


def split_words(name):
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ").replace("-", " ")
    return spaced


def shipped_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        parts = set(path.relative_to(ROOT).parts)
        if parts & {"__pycache__", "node_modules"}:
            continue
        if path.name in OWN and path.parent == TESTS:
            continue
        yield path


# --- scanner guards (behavioural contract of the scan patterns) -------------

@pytest.mark.parametrize("text", ["integrating the steps", "generate a list", "Filmore Street"])
def test_guard_words_do_not_hit(text):
    assert hits_in(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "Pocket " + "Cin" + "ema",
        "a mo" + "vie night",
        "Fi" + "lm",
        "the cin" + "ema",
        "my Watch" + "list",
        "a pos" + "ter",
        "run" + "time",
        "a rat" + "ing",
        "a gen" + "re",
        "my " + "P" + "C",
    ],
)
def test_true_positives(text):
    assert hits_in(text)


def test_standalone_upper_is_case_sensitive():
    assert hits_in("pc") == []
    assert hits_in("PCs") == []


def test_scan_modules_exist_and_expose_scanner():
    path = TESTS / "scan_rules.py"
    assert path.is_file(), "demo-app/tests/scan_rules.py is missing"
    assert (TESTS / "test_release_scan.py").is_file()
    spec = importlib.util.spec_from_file_location("scan_rules_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("banned_patterns", "scan_files", "scan_rendered", "scan_json_keys",
                 "scan_symbols", "check_no_new_dependencies"):
        assert hasattr(module, name), name


# --- real scan -------------------------------------------------------------

def test_no_banned_terms_in_files():
    problems = []
    for path in shipped_files():
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            for hit in hits_in(line):
                problems.append(f"{path.relative_to(ROOT)}:{number} {hit}")
    assert problems == []


def test_no_banned_words_in_symbols():
    problems = []
    for path in shipped_files():
        text = path.read_text(errors="ignore")
        names = []
        if path.suffix == ".py":
            tree = ast.parse(text)
            for node in ast.walk(tree):
                for attr in ("name", "id", "arg", "attr"):
                    value = getattr(node, attr, None)
                    if isinstance(value, str):
                        names.append(value)
        elif path.suffix in {".js", ".css"}:
            names = re.findall(r"[A-Za-z_][\w-]*", text)
        for name in names:
            if hits_in(split_words(name)):
                problems.append(f"{path.relative_to(ROOT)} {name}")
    assert sorted(set(problems)) == []


def test_no_references_to_legacy_routes_in_files():
    problems = []
    for path in shipped_files():
        text = path.read_text(errors="ignore")
        for route in LEGACY:
            if route in text:
                problems.append(f"{path.relative_to(ROOT)} {route}")
    assert problems == []


def _walk_keys(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key
            yield from _walk_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_keys(item)


def test_rendered_pages_and_api_have_no_banned_terms(client, recipes):
    paths = ["/", "/?mode=tv", "/api/recipes", "/api/cookbook", "/api/rails",
             "/recipe/not-a-real-recipe", "/api/recipes/not-a-real-recipe",
             "/missing-page", "/api/missing"]
    for recipe in recipes:
        rid = recipe["id"]
        paths += [f"/recipe/{rid}", f"/recipe/{rid}?mode=tv", f"/api/recipes/{rid}"]
    problems = []
    for path in paths:
        response = client.get(path)
        body = response.get_data(as_text=True)
        for hit in hits_in(body):
            problems.append(f"GET {path} {hit}")
        if response.is_json:
            for key in _walk_keys(response.get_json()):
                if hits_in(split_words(str(key))):
                    problems.append(f"GET {path} key {key}")
    assert problems == []


@pytest.mark.parametrize("route", LEGACY)
def test_legacy_routes_return_404(client, route):
    for suffix in ("", "/1", "/anything"):
        assert client.get(route + suffix).status_code == 404
    assert client.post(route, json={"id": "x"}).status_code == 404
    assert client.delete(route + "/1").status_code == 404


# --- dependency check ------------------------------------------------------

def test_requirements_unchanged():
    lines = [l.strip() for l in (ROOT / "requirements.txt").read_text().splitlines() if l.strip()]
    assert lines == ["Flask>=3.1,<4", "pytest>=8,<9"]


def test_package_json_has_no_dependency_keys():
    data = json.loads((ROOT / "package.json").read_text())
    for key in ("dependencies", "devDependencies", "scripts"):
        assert key not in data


# --- README ----------------------------------------------------------------

def test_readme_content():
    readme = ROOT / "README.md"
    assert readme.is_file(), "demo-app/README.md is missing"
    text = readme.read_text()
    assert "TableStory" in text
    assert "pip install -r demo-app/requirements.txt" in text
    assert "python demo-app/app.py" in text
    assert "http://127.0.0.1:5000/" in text
    assert "http://127.0.0.1:5000/?mode=tv" in text
    assert "pytest -q demo-app/tests" in text
    assert "node --test demo-app/static/tests/*.test.js" in text
    assert hits_in(text) == []
