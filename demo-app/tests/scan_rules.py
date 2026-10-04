"""Partial-rebrand detector: banned terms, legacy routes and dependency checks.

Banned terms are assembled from fragments so this file never contains a literal
banned word and cannot flag itself.
"""
import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The independent acceptance file names every term literally, so it is skipped too.
OWN_FILES = frozenset({"scan_rules.py", "test_release_scan.py", "test_ticket_12_release_scan.py"})
SKIP_DIRS = frozenset({"__pycache__", "node_modules"})
TEXT_SUFFIXES = frozenset({".py", ".html", ".css", ".js", ".json", ".md", ".txt"})

_WORDS = [
    "po" + "cket\\s+cin" + "ema",
    "mov" + "ies?",
    "fil" + "ms?",
    "cin" + "ema",
    "watch" + "list",
    "pos" + "ters?",
    "run" + "time",
    "rat" + "ings?",
    "gen" + "res?",
]
_ABBREVIATION = "P" + "C"

LEGACY_ROUTES = ("/mov" + "ie", "/api/mov" + "ies", "/api/watch" + "list")
EXPECTED_REQUIREMENTS = frozenset({"Flask>=3.1,<4", "pytest>=8,<9"})
FORBIDDEN_PACKAGE_KEYS = ("dependencies", "devDependencies", "scripts")


@dataclass(frozen=True)
class ScanHit:
    source: str
    line: int | None
    term: str
    excerpt: str

    def __str__(self):
        return f"{self.source}:{self.line} {self.term} {self.excerpt}"


def banned_patterns():
    """Whole-word case-insensitive patterns plus case-sensitive standalone abbreviation."""
    patterns = [(w, re.compile(r"\b(?:%s)\b" % w, re.I)) for w in _WORDS]
    patterns.append((_ABBREVIATION, re.compile(r"\b%s\b" % _ABBREVIATION)))
    return patterns


def find_terms(text):
    return [m.group(0) for _, pattern in banned_patterns() for m in pattern.finditer(text)]


def _line_hits(text, source):
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        for term in find_terms(line):
            hits.append(ScanHit(source, number, term, line.strip()[:120]))
    return hits


def iter_files(root=ROOT, exclude=OWN_FILES):
    root = Path(root)
    excluded = {Path(item) for item in exclude}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if (
            path.is_file()
            and path.suffix in TEXT_SUFFIXES
            and not (set(rel.parts) & SKIP_DIRS)
            and path not in excluded
            and rel not in excluded
            and Path(path.name) not in excluded
        ):
            yield path


def scan_files(root=ROOT, exclude=OWN_FILES):
    hits = []
    for path in iter_files(root, exclude):
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits += _line_hits(text, str(path.relative_to(root)))
    return hits


def split_words(symbol):
    """Split an identifier on underscores, hyphens and camelCase boundaries."""
    parts = re.split(r"[_\-$]+", symbol)
    words = []
    for part in parts:
        words += re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", part)
    return words


def _symbol_hits(symbol, source, line):
    hits = []
    for word in split_words(symbol):
        if find_terms(word):
            hits.append(ScanHit(source, line, word, symbol))
    return hits


def _python_symbols(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno
        elif isinstance(node, ast.arg):
            yield node.arg, node.lineno
        elif isinstance(node, ast.Name):
            yield node.id, node.lineno
        elif isinstance(node, ast.Attribute):
            yield node.attr, node.lineno
        elif isinstance(node, ast.keyword) and node.arg:
            yield node.arg, getattr(node, "lineno", None)


_JS_DECLARATION = re.compile(r"\b(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)")
_JS_EXPORT_LIST = re.compile(r"\bexport\s*\{([^}]*)\}")
_CSS_NAME = re.compile(r"(?:[.#]|--)([A-Za-z_][\w-]*)")


def _js_symbols(text):
    for number, line in enumerate(text.splitlines(), 1):
        for m in _JS_DECLARATION.finditer(line):
            yield m.group(1), number
        for m in _JS_EXPORT_LIST.finditer(line):
            for name in re.findall(r"[A-Za-z_$][\w$]*", m.group(1)):
                yield name, number


def _css_symbols(text):
    for number, line in enumerate(text.splitlines(), 1):
        for m in _CSS_NAME.finditer(line):
            yield m.group(1), number


def scan_symbols(root=ROOT, exclude=OWN_FILES):
    hits = []
    for path in iter_files(root, exclude):
        source = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError as error:
                hits.append(ScanHit(source, error.lineno, "syntax-error", str(error)))
                continue
            symbols = _python_symbols(tree)
        elif path.suffix == ".js":
            symbols = _js_symbols(text)
        elif path.suffix == ".css":
            symbols = _css_symbols(text)
        else:
            continue
        for symbol, line in symbols:
            hits += _symbol_hits(symbol, source, line)
    return hits


def scan_json_keys(payload, source):
    hits = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = " ".join(split_words(str(key)))
            for term in find_terms(key_text):
                hits.append(ScanHit(source, None, term, "key " + str(key)))
            hits += scan_json_keys(value, source)
    elif isinstance(payload, list):
        for value in payload:
            hits += scan_json_keys(value, source)
    return hits


def rendered_paths(recipe_ids):
    paths = ["/", "/?mode=tv", "/api/recipes", "/api/cookbook", "/api/rails", "/no-such-page", "/api/no-such"]
    for recipe_id in recipe_ids:
        paths += [f"/recipe/{recipe_id}", f"/recipe/{recipe_id}?mode=tv", f"/api/recipes/{recipe_id}"]
    paths += ["/recipe/unknown-id", "/api/recipes/unknown-id"]
    return paths


def scan_rendered(client, recipe_ids):
    hits = []
    for path in rendered_paths(recipe_ids):
        response = client.get(path)
        source = f"GET {path}"
        if response.status_code not in (200, 404):
            hits.append(ScanHit(source, None, "status", str(response.status_code)))
            continue
        hits += _line_hits(response.get_data(as_text=True), source)
        if response.is_json:
            hits += scan_json_keys(response.get_json(), source)
    return hits


def check_no_new_dependencies(root=ROOT):
    problems = []
    lines = {l.strip() for l in (root / "requirements.txt").read_text().splitlines() if l.strip()}
    if lines != EXPECTED_REQUIREMENTS:
        problems.append(f"requirements.txt changed: {sorted(lines)}")
    package = json.loads((root / "package.json").read_text())
    for key in FORBIDDEN_PACKAGE_KEYS:
        if key in package:
            problems.append(f"package.json has {key}")
    return problems
