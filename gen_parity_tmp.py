import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "demo-app"))
import domain  # noqa: E402
import recipes  # noqa: E402

rs = recipes.load_recipes()
texts = {r["id"]: domain.search_text(r) for r in rs}

if len(sys.argv) == 1:
    for r in rs:
        print(r["id"], r["category"], r["dietary_tags"], r["ingredients"][:5])
    sys.exit()

queries = json.loads(Path(sys.argv[1]).read_text())
cases = []
for name, q in queries:
    needle = q.strip().lower()
    cases.append({"name": name, "query": q, "ids": [i for i, t in texts.items() if needle in t]})
path = ROOT / "demo-app/static/tests/fixtures/search-parity.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({"recipes": texts, "cases": cases}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
for c in cases:
    print(c["name"], repr(c["query"]), len(c["ids"]))
