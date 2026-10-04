"""Ticket 4 acceptance tests: mobile browse and detail pages (TableStory identity)."""
import re
from html.parser import HTMLParser
from pathlib import Path

from domain import search_text
from recipes import total_minutes

TEMPLATES = Path(__file__).parents[1] / "templates"
OWNED_TEMPLATES = (
    "base.html",
    "index.html",
    "detail.html",
    "_recipe_card.html",
    "_cookbook_toggle.html",
)
TAGLINE = "Good food, clearly told."
EMPTY_TEXT = "No recipes found. Try another ingredient or dish."
VOID = {"meta", "link", "input", "br", "hr", "img", "source", "area", "base", "col", "wbr"}

# Banned terms are assembled from fragments so this file does not contain them literally.
_BANNED_WORDS = [
    "pocket" + r"\s+" + "cinema",
    "mo" + "vies?",
    "fi" + "lms?",
    "cin" + "ema",
    "watch" + "list",
    "pos" + "ters?",
    "run" + "time",
    "rat" + "ings?",
    "gen" + "res?",
]
BANNED = [re.compile(r"\b" + w + r"\b", re.I) for w in _BANNED_WORDS]
BANNED.append(re.compile(r"\b" + "P" + "C" + r"\b"))
EXTERNAL_URL = re.compile(r"(?:https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}|\bhttps?://", re.I)


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []
        self.pieces = []

    def text(self):
        out = list(self.pieces)
        for child in self.children:
            out.append(child.text())
        return " ".join(" ".join(out).split())

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def find_all(self, tag=None, **attrs):
        return [
            n for n in self.walk()
            if (tag is None or n.tag == tag)
            and all(n.attrs.get(k.replace("_", "-")) == v for k, v in attrs.items())
        ]

    def classes(self):
        return (self.attrs.get("class") or "").split()


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [])
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, [(k, "" if v is None else v) for k, v in attrs], self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, [(k, "" if v is None else v) for k, v in attrs], self.cur)
        self.cur.children.append(node)

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.pieces.append(data)


def fetch(client, url, **kwargs):
    """GET a URL; a crash while rendering becomes a plain assertion failure."""
    try:
        response = client.get(url, **kwargs)
    except Exception:
        raise AssertionError(f"GET {url} did not render a page") from None
    return response


def page(client, url, expect=200):
    response = fetch(client, url)
    assert response.status_code == expect, f"GET {url} returned {response.status_code}"
    html = response.get_data(as_text=True)
    tree = Tree()
    tree.feed(html)
    return html, tree.root


def with_class(root, cls, tag=None):
    return [n for n in root.walk() if cls in n.classes() and (tag is None or n.tag == tag)]


def by_id(root, element_id):
    found = [n for n in root.walk() if n.attrs.get("id") == element_id]
    assert len(found) == 1, f"expected exactly one #{element_id}, found {len(found)}"
    return found[0]


def card_for(root, recipe):
    cards = [c for c in with_class(root, "recipe-card") if c.attrs.get("data-search") is not None]
    for card in cards:
        links = [a for a in card.find_all("a") if a.attrs.get("href") == f"/recipe/{recipe['id']}"]
        if links:
            return card
    raise AssertionError(f"no recipe card links to /recipe/{recipe['id']}")


def toggle_in(node):
    toggles = with_class(node, "cookbook-toggle")
    assert len(toggles) == 1, f"expected one cookbook toggle, found {len(toggles)}"
    return toggles[0]


def save(client, recipe_id):
    response = client.post("/api/cookbook", json={"id": recipe_id})
    assert response.status_code == 201


# ---- GET / : recipe cards -------------------------------------------------


def test_home_has_one_recipe_card_per_recipe(client, recipes):
    _, root = page(client, "/")
    cards = with_class(root, "recipe-card")
    assert len(cards) == len(recipes)
    hrefs = []
    for card in cards:
        links = [a.attrs["href"] for a in card.find_all("a") if a.attrs.get("href", "").startswith("/recipe/")]
        assert len(links) >= 1
        hrefs.append(links[0])
    assert hrefs == [f"/recipe/{r['id']}" for r in recipes]


def test_each_card_shows_title_time_difficulty_label_and_link(client, recipes):
    _, root = page(client, "/")
    for recipe in recipes:
        card = card_for(root, recipe)
        text = card.text()
        assert recipe["title"] in text, recipe["id"]
        total = total_minutes(recipe)
        assert total == recipe["prep_minutes"] + recipe["cook_minutes"]
        assert re.search(rf"(?<!\d){total}(?!\d)", text), f"{recipe['id']}: total {total} missing"
        assert recipe["difficulty"] in text, recipe["id"]
        labels = [recipe["category"], *recipe["dietary_tags"]]
        assert any(label in text for label in labels), f"{recipe['id']}: no category or tag label"


def test_each_card_carries_search_text_and_art_hooks(client, recipes):
    _, root = page(client, "/")
    for recipe in recipes:
        card = card_for(root, recipe)
        assert card.attrs["data-search"] == search_text(recipe)
        style = " ".join(n.attrs.get("style", "") for n in card.walk())
        assert "--art-a" in style and "--art-b" in style, recipe["id"]
        assert recipe["colors"][0] in style and recipe["colors"][1] in style
        assert recipe["title"][0].upper() in card.text()


def test_each_card_has_labelled_unsaved_toggle(client, recipes):
    _, root = page(client, "/")
    for recipe in recipes:
        toggle = toggle_in(card_for(root, recipe))
        assert toggle.attrs.get("data-recipe-id") == recipe["id"]
        assert toggle.attrs.get("data-recipe-title") == recipe["title"]
        assert toggle.attrs.get("aria-pressed") == "false"
        assert toggle.attrs.get("aria-label") == f"Save {recipe['title']} to My Cookbook"
        assert "Save" in toggle.text()


# ---- GET / : identity and page hooks --------------------------------------


def test_home_identity_tagline_intro_and_brand(client):
    html, root = page(client, "/")
    titles = root.find_all("title")
    assert len(titles) == 1 and "TableStory" in titles[0].text()
    assert TAGLINE in " ".join(root.text().split())
    main_text = root.text().lower()
    assert "everyday" in main_text and "cook" in main_text
    brand = [
        a for a in root.find_all("a")
        if a.attrs.get("href") == "/" and "TableStory" in (a.text() + a.attrs.get("aria-label", ""))
    ]
    assert brand, "header brand mark linking to / is missing"
    assert [n for n in root.walk() if n.tag == "header" and n.find_all("a", href="/")]


def test_home_search_count_and_empty_hooks(client, recipes):
    _, root = page(client, "/")
    search = by_id(root, "search")
    assert search.tag == "input"
    count = by_id(root, "count")
    assert count.attrs.get("role") == "status" or count.attrs.get("aria-live") == "polite" or any(
        a.attrs.get("aria-live") == "polite" or a.attrs.get("role") == "status"
        for a in _ancestors(count)
    )
    assert str(len(recipes)) in count.text()
    empty = by_id(root, "empty")
    assert "hidden" in empty.attrs
    assert empty.text() == EMPTY_TEXT


def _ancestors(node):
    node = node.parent
    while node is not None:
        yield node
        node = node.parent


def test_home_declares_mobile_mode_and_drops_old_chrome(client):
    html, root = page(client, "/")
    bodies = root.find_all("body")
    assert len(bodies) == 1 and bodies[0].attrs.get("data-mode") == "mobile"
    assert not with_class(root, "tabbar")
    assert not with_class(root, "avatar")
    assert "Open profile" not in html


# ---- GET /recipe/<id> ------------------------------------------------------


def test_detail_shows_all_metadata(client, recipes):
    for recipe in recipes:
        _, root = page(client, f"/recipe/{recipe['id']}")
        text = root.text()
        assert recipe["title"] in text
        assert recipe["description"] in text
        assert recipe["category"] in text
        for tag in recipe["dietary_tags"]:
            assert tag in text
        assert recipe["difficulty"] in text
        for number in (
            recipe["prep_minutes"], recipe["cook_minutes"],
            total_minutes(recipe), recipe["servings"],
        ):
            assert re.search(rf"(?<!\d){number}(?!\d)", text), f"{recipe['id']}: {number} missing"
        assert "TableStory" in root.find_all("title")[0].text()


def test_detail_lists_ingredients_and_numbered_steps_in_order(client, recipes):
    for recipe in recipes:
        _, root = page(client, f"/recipe/{recipe['id']}")
        lists = [n for n in root.walk() if n.tag in ("ul", "ol")]
        item_lists = [[li.text() for li in lst.find_all("li")] for lst in lists]
        assert recipe["ingredients"] in item_lists, f"{recipe['id']}: ingredient list differs"
        numbered = [
            [li.text() for li in ol.find_all("li")] for ol in root.walk() if ol.tag == "ol"
        ]
        assert recipe["steps"] in numbered, f"{recipe['id']}: numbered steps differ"


def test_detail_back_link_and_hooks_on_mobile(client, recipes):
    _, root = page(client, f"/recipe/{recipes[0]['id']}")
    back = root.find_all("a", data_action="back")
    assert len(back) == 1 and back[0].attrs.get("href") == "/"
    assert root.find_all("body")[0].attrs.get("data-mode") == "mobile"
    assert not with_class(root, "tabbar") and not with_class(root, "avatar")
    brand = [a for a in root.find_all("a") if a.attrs.get("href") == "/" and "TableStory" in a.text() + a.attrs.get("aria-label", "")]
    assert brand


def test_detail_unknown_id_is_404(client):
    html, root = page(client, "/recipe/no-such-recipe", expect=404)
    assert "TableStory" in html


# ---- saved vs unsaved ------------------------------------------------------


def test_card_toggle_reflects_saved_state(client, recipes):
    target, other = recipes[0], recipes[1]
    _, before = page(client, "/")
    unsaved = toggle_in(card_for(before, target))
    save(client, target["id"])
    _, after = page(client, "/")
    saved = toggle_in(card_for(after, target))
    assert saved.attrs.get("aria-pressed") == "true"
    assert unsaved.attrs.get("aria-pressed") == "false"
    assert saved.text() != unsaved.text()
    assert "✓" in saved.text() and "✓" not in unsaved.text()
    assert saved.attrs["aria-label"] == f"Remove {target['title']} from My Cookbook"
    assert saved.attrs["aria-label"] != unsaved.attrs["aria-label"]
    untouched = toggle_in(card_for(after, other))
    assert untouched.attrs.get("aria-pressed") == "false"


def test_detail_control_label_states_current_state(client, recipes):
    recipe = recipes[2]
    _, before = page(client, f"/recipe/{recipe['id']}")
    unsaved = [n for n in before.find_all(None, data_action="cookbook")]
    assert len(unsaved) == 1
    unsaved = unsaved[0]
    assert recipe["title"] in unsaved.attrs.get("aria-label", "")
    assert unsaved.attrs.get("aria-pressed") == "false"
    save(client, recipe["id"])
    _, after = page(client, f"/recipe/{recipe['id']}")
    saved = after.find_all(None, data_action="cookbook")[0]
    assert saved.attrs.get("aria-pressed") == "true"
    assert saved.attrs["aria-label"] == f"Remove {recipe['title']} from My Cookbook"
    assert saved.text() != unsaved.text()
    assert "✓" in saved.text() and "✓" not in unsaved.text()
    assert saved.attrs.get("data-recipe-id") == recipe["id"]
    assert saved.attrs.get("data-recipe-title") == recipe["title"]


# ---- terminology and external resources -----------------------------------


def test_owned_templates_exist():
    missing = [name for name in OWNED_TEMPLATES if not (TEMPLATES / name).is_file()]
    assert not missing, f"missing templates: {missing}"


def _banned_hits(text):
    return sorted({m.group(0) for pattern in BANNED for m in pattern.finditer(text)})


def test_templates_have_no_banned_terms_or_external_urls():
    for name in OWNED_TEMPLATES:
        path = TEMPLATES / name
        assert path.is_file(), f"{name} is missing"
        source = path.read_text(encoding="utf-8")
        assert not _banned_hits(source), f"{name}: {_banned_hits(source)}"
        assert not EXTERNAL_URL.search(source), f"{name}: external URL"


def test_rendered_pages_have_no_banned_terms_or_external_urls(client, recipes):
    urls = ["/", f"/recipe/{recipes[0]['id']}", f"/recipe/{recipes[-1]['id']}"]
    for url in urls:
        html, _ = page(client, url)
        assert not _banned_hits(html), f"{url}: {_banned_hits(html)}"
        assert not EXTERNAL_URL.search(html), f"{url}: external URL"
