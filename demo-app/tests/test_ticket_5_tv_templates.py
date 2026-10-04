"""Acceptance tests for ticket #5: TV home rails and TV detail templates."""

import re
from html.parser import HTMLParser

import pytest

RAIL_NAMES = [
    "Popular this week",
    "Ready in 30 minutes",
    "Vegetarian favourites",
    "My Cookbook",
]
EMPTY_COPY = "Your cookbook is empty. Save a recipe to see it here."
TV_UA = "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/537.36 TV Safari/537.36"
VOID = {"meta", "link", "br", "img", "input", "hr"}


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []
        self.parts = []

    @property
    def classes(self):
        return (self.attrs.get("class") or "").split()

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def text(self):
        out = list(self.parts)
        for child in self.children:
            out.append(child.text())
        return " ".join(" ".join(out).split())

    def own_text(self):
        return " ".join(" ".join(self.parts).split())


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", [], None)
        self.cur = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.parts.append(data)

    def find_all(self, pred):
        return [n for n in self.root.walk() if pred(n)]


def fetch(client, path, **kwargs):
    """GET a page; a server-side failure (e.g. a missing template) is a behavior failure."""
    try:
        return client.get(path, **kwargs)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError("GET %s raised %s: %s" % (path, type(exc).__name__, exc)) from None


def tree(client, path, **kwargs):
    response = fetch(client, path, **kwargs)
    assert response.status_code == 200, "%s -> %s" % (path, response.status_code)
    return Tree(response.get_data(as_text=True)), response.get_data(as_text=True)


def rails_of(page):
    return page.find_all(lambda n: "tv-rail" in n.classes and "data-rail" in n.attrs)


def cards_of(rail):
    return [n for n in rail.walk() if "recipe-card" in n.classes]


def card_links(card):
    if card.tag == "a" and "href" in card.attrs:
        return [card.attrs["href"]]
    return [n.attrs["href"] for n in card.walk() if n.tag == "a" and "href" in n.attrs]


def rail_by_name(page, name):
    matches = [r for r in rails_of(page) if r.attrs["data-rail"] == name]
    assert len(matches) == 1, name
    return matches[0]


def tv_home(client):
    return tree(client, "/?mode=tv")[0]


def banned_patterns():
    frags = [("mo", "vie"), ("fi", "lm"), ("cin", "ema"), ("watch", "list"),
             ("pos", "ter"), ("run", "time"), ("rat", "ing"), ("gen", "re")]
    pats = [re.compile(r"\b%ss?\b" % (a + b), re.I) for a, b in frags]
    pats.append(re.compile(r"\bpocket\s+cinema\b", re.I))
    pats.append(re.compile(r"\bPC\b"))
    return pats


# --- TV home: rails -------------------------------------------------------


@pytest.mark.parametrize("kwargs", [
    {"path": "/?mode=tv"},
    {"path": "/", "headers": {"User-Agent": TV_UA}},
    {"path": "/?mode=TV"},
])
def test_tv_home_has_four_named_rails_in_order(client, kwargs):
    path = kwargs.pop("path")
    page, _ = tree(client, path, **kwargs)
    assert [r.attrs["data-rail"] for r in rails_of(page)] == RAIL_NAMES
    for rail in rails_of(page):
        assert rail.tag == "section"


def test_rail_names_are_visible_headings(client):
    page = tv_home(client)
    for rail in rails_of(page):
        name = rail.attrs["data-rail"]
        headings = [n.text() for n in rail.walk() if n.tag in {"h1", "h2", "h3"}]
        assert name in headings


def test_non_cookbook_rails_have_at_least_two_cards(client):
    page = tv_home(client)
    for name in RAIL_NAMES[:3]:
        assert len(cards_of(rail_by_name(page, name))) >= 2, name


def test_rail_membership_matches_api_rails(client):
    page = tv_home(client)
    api = {r["name"]: r["recipe_ids"] for r in client.get("/api/rails").get_json()}
    for name in RAIL_NAMES[:3]:
        ids = []
        for card in cards_of(rail_by_name(page, name)):
            ids.append(re.match(r"/recipe/([^?]+)", card_links(card)[0]).group(1))
        assert ids == api[name], name


def test_tv_home_is_not_the_mobile_page(client):
    page, _ = tree(client, "/?mode=tv")
    assert page.find_all(lambda n: n.attrs.get("id") == "search") == []


# --- Cards ------------------------------------------------------------------


def test_every_tv_card_is_a_link_with_mode_tv(client):
    page = tv_home(client)
    total = 0
    for rail in rails_of(page):
        for card in cards_of(rail):
            links = card_links(card)
            assert len(links) == 1
            assert re.fullmatch(r"/recipe/[a-z0-9-]+\?mode=tv", links[0]), links[0]
            total += 1
    assert total >= 6


def test_tv_cards_are_focusable_links(client):
    page = tv_home(client)
    for rail in rails_of(page):
        for card in cards_of(rail):
            anchors = [n for n in card.walk() if n.tag == "a"]
            focusable = [
                a for a in anchors + ([card] if card.tag == "a" else [])
                if "href" in a.attrs and a.attrs.get("tabindex") != "-1"
            ]
            assert focusable, "card has no focusable link"


def test_tv_card_links_resolve_to_tv_detail(client):
    page = tv_home(client)
    href = card_links(cards_of(rail_by_name(page, RAIL_NAMES[0]))[0])[0]
    detail, _ = tree(client, href)
    assert detail.find_all(lambda n: n.attrs.get("data-action") == "back")


# --- My Cookbook rail -----------------------------------------------------------


def test_cookbook_rail_shows_empty_copy_before_save(client):
    rail = rail_by_name(tv_home(client), "My Cookbook")
    assert cards_of(rail) == []
    assert EMPTY_COPY in rail.text()


def test_cookbook_rail_reflects_save_after_refresh(client, recipes):
    target = recipes[0]["id"]
    assert client.post("/api/cookbook", json={"id": target}).status_code == 201
    rail = rail_by_name(tv_home(client), "My Cookbook")
    cards = cards_of(rail)
    assert [card_links(c)[0] for c in cards] == ["/recipe/%s?mode=tv" % target]
    assert EMPTY_COPY not in rail.text()
    assert recipes[0]["title"] in rail.text()


def test_cookbook_rail_orders_by_collection_and_tracks_removal(client, recipes):
    first, second = recipes[0]["id"], recipes[1]["id"]
    for rid in (second, first):
        client.post("/api/cookbook", json={"id": rid})
    rail = rail_by_name(tv_home(client), "My Cookbook")
    assert [card_links(c)[0] for c in cards_of(rail)] == [
        "/recipe/%s?mode=tv" % first, "/recipe/%s?mode=tv" % second]
    client.delete("/api/cookbook/%s" % first)
    client.delete("/api/cookbook/%s" % second)
    rail = rail_by_name(tv_home(client), "My Cookbook")
    assert cards_of(rail) == []
    assert EMPTY_COPY in rail.text()


def test_other_rails_never_show_empty_copy(client):
    page = tv_home(client)
    for name in RAIL_NAMES[:3]:
        assert EMPTY_COPY not in rail_by_name(page, name).text()


# --- TV detail ------------------------------------------------------------------


def detail_page(client, recipe, **kwargs):
    return tree(client, "/recipe/%s?mode=tv" % recipe["id"], **kwargs)


def action(page, name):
    found = page.find_all(lambda n: n.attrs.get("data-action") == name)
    assert len(found) == 1, name
    return found[0]


def test_tv_detail_back_action(client, recipes):
    page, _ = detail_page(client, recipes[0])
    back = action(page, "back")
    assert back.tag == "a"
    assert back.attrs["href"] == "/?mode=tv"
    assert back.text()


def test_tv_detail_cookbook_action_state_and_label(client, recipes):
    recipe = recipes[0]
    page, _ = detail_page(client, recipe)
    btn = action(page, "cookbook")
    assert btn.attrs["aria-pressed"] == "false"
    assert recipe["title"] in btn.attrs["aria-label"]
    assert "My Cookbook" in btn.attrs["aria-label"]
    client.post("/api/cookbook", json={"id": recipe["id"]})
    page, _ = detail_page(client, recipe)
    btn = action(page, "cookbook")
    assert btn.attrs["aria-pressed"] == "true"
    assert recipe["title"] in btn.attrs["aria-label"]
    assert btn.attrs["aria-label"] != "Save %s to My Cookbook" % recipe["title"]


def test_tv_detail_via_user_agent(client, recipes):
    page, _ = tree(client, "/recipe/%s" % recipes[0]["id"], headers={"User-Agent": TV_UA})
    assert action(page, "back").attrs["href"] == "/?mode=tv"
    action(page, "cookbook")


def test_tv_detail_metadata(client, recipes):
    recipe = recipes[0]
    page, _ = detail_page(client, recipe)
    text = page.root.text()
    total = recipe["prep_minutes"] + recipe["cook_minutes"]
    assert recipe["title"] in [n.text() for n in page.find_all(lambda n: n.tag == "h1")]
    for value in (recipe["description"], recipe["category"], recipe["difficulty"],
                  str(recipe["prep_minutes"]), str(recipe["cook_minutes"]), str(total),
                  str(recipe["servings"])):
        assert value in text
    for tag in recipe["dietary_tags"]:
        assert tag in text


def in_order(text, items):
    pos = -1
    for item in items:
        nxt = text.find(item, pos + 1)
        assert nxt > pos, item
        pos = nxt


def test_tv_detail_ingredients_and_steps_in_stored_order(client, recipes):
    for recipe in recipes:
        page, _ = detail_page(client, recipe)
        lis = [n for n in page.find_all(lambda n: n.tag == "li")]
        texts = [li.text() for li in lis]
        in_order(" | ".join(texts), recipe["ingredients"])
        in_order(" | ".join(texts), recipe["steps"])
        ols = page.find_all(lambda n: n.tag == "ol")
        assert any([c.text() for c in ol.children if c.tag == "li"] == recipe["steps"]
                   for ol in ols), recipe["id"]
        containers = page.find_all(lambda n: n.tag in {"ol", "ul"})
        assert any([c.text() for c in ct.children if c.tag == "li"] == recipe["ingredients"]
                   for ct in containers), recipe["id"]


def test_tv_detail_loads_tv_detail_script(client, recipes):
    _, html = detail_page(client, recipes[0])
    assert "tv-detail.js" in html


def test_tv_home_loads_tv_browse_script(client):
    _, html = tree(client, "/?mode=tv")
    assert "tv-browse.js" in html


def test_unknown_recipe_in_tv_mode_is_404(client):
    assert client.get("/recipe/no-such-recipe?mode=tv").status_code == 404


# --- data-mode --------------------------------------------------------------------


def body_mode(page):
    bodies = page.find_all(lambda n: n.tag == "body")
    assert len(bodies) == 1
    return bodies[0].attrs.get("data-mode")


def test_body_data_mode_tv_pages(client, recipes):
    rid = recipes[0]["id"]
    assert body_mode(tree(client, "/?mode=tv")[0]) == "tv"
    assert body_mode(tree(client, "/", headers={"User-Agent": TV_UA})[0]) == "tv"
    assert body_mode(tree(client, "/recipe/%s?mode=tv" % rid)[0]) == "tv"


def test_body_data_mode_mobile_pages(client, recipes):
    rid = recipes[0]["id"]
    assert body_mode(tree(client, "/")[0]) == "mobile"
    assert body_mode(tree(client, "/recipe/%s" % rid)[0]) == "mobile"
    assert body_mode(tree(client, "/?mode=mobile", headers={"User-Agent": TV_UA})[0]) == "mobile"


# --- Terminology and external resources -------------------------------------------


def tv_paths(recipes):
    paths = ["/?mode=tv"]
    paths += ["/recipe/%s?mode=tv" % r["id"] for r in recipes]
    return paths


def test_tv_pages_have_no_banned_terms(client, recipes):
    client.post("/api/cookbook", json={"id": recipes[0]["id"]})
    for path in tv_paths(recipes):
        html = tree(client, path)[1]
        for pat in banned_patterns():
            hit = pat.search(html)
            assert hit is None, "%s: %s" % (path, hit.group(0) if hit else "")


def test_tv_pages_have_no_external_resources(client, recipes):
    for path in tv_paths(recipes):
        page, html = tree(client, path)
        for node in page.root.walk():
            for attr in ("src", "href", "poster", "action"):
                value = node.attrs.get(attr)
                if value:
                    assert not re.match(r"(?i)(https?:)?//", value), (path, value)
        assert not re.search(r"url\(\s*['\"]?(https?:)?//", html, re.I)
        assert not re.search(r"@import", html, re.I)
        assert not page.find_all(lambda n: n.tag == "img" and not (n.attrs.get("src") or "").startswith("/"))
