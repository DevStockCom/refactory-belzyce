import json
import sys
from pathlib import Path

root = Path(__file__).parent
sys.path.insert(0, str(root / "demo-app"))
import domain  # noqa: E402
from recipes import load_recipes  # noqa: E402

recipes = load_recipes()
queries = [
    "", "   ", "oats", "OATS", "Oats", "  oats  ", "\tChickpeas\n",
    "tomato", "TOMATO", "parmesan", "PARMESAN", "  Parmesan ", "smoked paprika",
    "pine nuts", "ginger", "salmon", "cinnamon", "maple syrup",
    "breakfast", "BREAKFAST", "dessert", "Dinner", "lunch",
    "vegan", "VEGAN", "vegetarian", "Gluten-Free", "gluten-free",
    "chocolate", "yoghurt", "Garden Herb", "xyzzy-no-such-dish", "  zzz  ",
]
fixture = {
    "texts": [{"id": r["id"], "search_text": domain.search_text(r)} for r in recipes],
    "cases": [
        {"query": q, "ids": [r["id"] for r in domain.search_recipes(recipes, q)]}
        for q in queries
    ],
}
out = root / "demo-app/static/tests/fixtures/search-parity.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
