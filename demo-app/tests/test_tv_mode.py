"""TV mode page smoke tests: rails, card links and detail actions."""

TV_UA = "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) TV Safari/537.36"
RAILS = ["Popular this week", "Ready in 30 minutes", "Vegetarian favourites", "My Cookbook"]
EMPTY_COPY = "Your cookbook is empty. Save a recipe to see it here."


def test_tv_home_rail_names_in_order(client):
    for response in (client.get("/?mode=tv"), client.get("/", headers={"User-Agent": TV_UA})):
        html = response.get_data(as_text=True)
        positions = [html.index('data-rail="%s"' % name) for name in RAILS]
        assert positions == sorted(positions)
        assert 'data-mode="tv"' in html


def test_cookbook_rail_empty_then_saved(client, recipes):
    assert EMPTY_COPY in client.get("/?mode=tv").get_data(as_text=True)
    client.post("/api/cookbook", json={"id": recipes[0]["id"]})
    html = client.get("/?mode=tv").get_data(as_text=True)
    assert EMPTY_COPY not in html
    assert "/recipe/%s?mode=tv" % recipes[0]["id"] in html


def test_tv_detail_actions(client, recipes):
    html = client.get("/recipe/%s?mode=tv" % recipes[0]["id"]).get_data(as_text=True)
    assert 'data-action="back" href="/?mode=tv"' in html
    assert 'data-action="cookbook"' in html
    assert "tv-detail.js" in html


def test_tv_brand_link_keeps_tv_mode(client, recipes):
    pages = [
        client.get("/?mode=tv"),
        client.get("/", headers={"User-Agent": TV_UA}),
        client.get("/recipe/%s?mode=tv" % recipes[0]["id"]),
    ]
    for response in pages:
        assert 'class="brand" href="/?mode=tv"' in response.get_data(as_text=True)
    assert 'class="brand" href="/"' in client.get("/").get_data(as_text=True)


def test_tv_cards_link_with_mode_and_rails_have_cards(client):
    import re

    for response in (client.get("/?mode=tv"), client.get("/", headers={"User-Agent": TV_UA})):
        html = response.get_data(as_text=True)
        hrefs = re.findall(r'<a href="(/recipe/[^"]*)"', html)
        assert hrefs and all(href.endswith("?mode=tv") for href in hrefs)
        sections = re.split(r'<section class="tv-rail"', html)[1:]
        for section in sections[:3]:
            assert section.count('class="recipe-card"') >= 2


def test_tv_detail_toggle_label_and_stored_order(client, recipes):
    recipe = recipes[0]
    html = client.get("/recipe/%s?mode=tv" % recipe["id"]).get_data(as_text=True)
    assert 'aria-pressed="false"' in html
    assert 'aria-label="Save %s to My Cookbook"' % recipe["title"] in html
    for key in ("ingredients", "steps"):
        positions = [html.index(item) for item in recipe[key]]
        assert positions == sorted(positions)


def test_body_mode_mobile_on_mobile_page(client):
    assert 'data-mode="mobile"' in client.get("/").get_data(as_text=True)
