"""Ticket #3 acceptance tests: TV-mode detection."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

import app as app_module  # noqa: E402
import domain  # noqa: E402
from app import create_app  # noqa: E402
from recipes import load_recipes, total_minutes  # noqa: E402

ORDINARY_UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36",
    "curl/8.4.0",
    "",
    None,
]

TV_UAS = [
    "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/537.36 Samsung Internet",
    "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 Chrome/79 Safari/537.36 WebAppManager",
    "Mozilla/5.0 (Linux; Tizen 5.5) AppleWebKit/537.36 TV Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; BRAVIA 4K) AppleWebKit/537.36 Chrome/90 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 9; AFTB Build/PS7233) AppleWebKit/537.36 Silk/80",
    "Mozilla/5.0 (Linux; Android 10; Android TV) AppleWebKit/537.36 Chrome/88",
    "Roku/DVP-9.10 (519.10E04111A)",
    "AppleTV11,1/11.1",
    "Mozilla/5.0 (X11; Linux armv7l) GoogleTV/092754",
    "Mozilla/5.0 (Linux; VIERA 2020) AppleWebKit/537.36",
    "Mozilla/5.0 (Linux; HbbTV/1.5.1) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux aarch64) CrKey/1.56.500000",
    "mozilla/5.0 (linux; tizen 6.0) applewebkit/537.36 SMARTTV",
]


def test_is_tv_request_is_exposed_by_app_module():
    assert callable(getattr(app_module, "is_tv_request", None)), "app.is_tv_request is missing"


def test_mode_tv_query_is_tv():
    assert app_module.is_tv_request({"mode": "tv"}, "Mozilla/5.0 Safari") is True
    assert app_module.is_tv_request({"mode": "tv"}, None) is True
    assert app_module.is_tv_request({"mode": "TV"}, "") is True


@pytest.mark.parametrize("ua", TV_UAS)
def test_tv_user_agent_hints_are_tv(ua):
    assert app_module.is_tv_request({}, ua) is True


@pytest.mark.parametrize("ua", ORDINARY_UAS)
def test_ordinary_user_agents_are_not_tv(ua):
    assert app_module.is_tv_request({}, ua) is False


@pytest.mark.parametrize("ua", TV_UAS[:4] + ORDINARY_UAS[:2])
def test_mode_mobile_opts_out(ua):
    assert app_module.is_tv_request({"mode": "mobile"}, ua) is False


@pytest.mark.parametrize("mode", ["", "desktop", "tvx"])
def test_other_mode_values_do_not_enable_tv(mode):
    assert app_module.is_tv_request({"mode": mode}, ORDINARY_UAS[0]) is False


def test_result_is_a_real_bool():
    assert isinstance(app_module.is_tv_request({}, None), bool)
    assert isinstance(app_module.is_tv_request({"mode": "tv"}, None), bool)


def test_template_helpers_are_registered():
    flask_app = create_app(testing=True)
    assert "total_minutes" in flask_app.jinja_env.filters
    assert "search_text" in flask_app.jinja_env.filters
    recipe = load_recipes()[0]
    assert flask_app.jinja_env.filters["total_minutes"](recipe) == total_minutes(recipe)
    assert flask_app.jinja_env.filters["search_text"](recipe) == domain.search_text(recipe)
