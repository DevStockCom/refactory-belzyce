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
