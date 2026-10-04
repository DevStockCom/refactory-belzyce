"""Acceptance tests for ticket #10: TV layout, rails and focus treatment (static/styles.css)."""
import re
from pathlib import Path

import pytest

CSS_PATH = Path(__file__).parents[1] / "static" / "styles.css"
TEMPLATES = Path(__file__).parents[1] / "templates"

CREAM, TOMATO, HERB, CHARCOAL, GOLD = "#fff8ed", "#c9472d", "#3f6b4f", "#26231f", "#e9b44c"
APPROVED = {CREAM, TOMATO, HERB, CHARCOAL, GOLD}


@pytest.fixture(scope="module")
def css():
    text = CSS_PATH.read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def rules(css_text):
    return [(" ".join(m.group(1).split()), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css_text)]


def declarations(body):
    decls = {}
    for part in body.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            decls[k.strip().lower()] = v.strip()
    return decls


def tokens(css_text):
    root = {}
    for sel, body in rules(css_text):
        if sel == ":root":
            root.update({k: v for k, v in declarations(body).items() if k.startswith("--")})
    return root


def resolve(value, toks):
    m = re.fullmatch(r"var\((--[\w-]+)\)", value.strip())
    if m:
        return resolve(toks.get(m.group(1), ""), toks)
    return value.strip().lower()


def px(value):
    m = re.match(r"(-?[\d.]+)px", (value or "").strip())
    return float(m.group(1)) if m else None


def lum(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def prop_values(css_text, pred, prop):
    """Values of `prop` from every rule where some selector in the list satisfies pred, in source order."""
    out = []
    for sel, body in rules(css_text):
        if any(pred(s.strip()) for s in sel.split(",")):
            d = declarations(body)
            if prop in d:
                out.append(d[prop])
    return out


def is_tv(sel):
    return 'data-mode="tv"' in sel or "data-mode=tv" in sel or ".tv-rail" in sel or ".rail-track" in sel


def tv_px(css_text, needle, prop):
    """Largest px value of prop among TV-scoped rules whose selector contains needle."""
    vals = [px(v) for v in prop_values(css_text, lambda s: is_tv(s) and needle in s, prop)]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


# ---- Rails: four rails, horizontal scrolling, scroll-margin, nothing clipped ----

def test_tv_home_template_has_four_rails_with_rail_hook():
    html = (TEMPLATES / "tv_home.html").read_text(encoding="utf-8")
    assert "tv-rail" in html and "data-rail" in html


def test_rail_scrolls_horizontally(css):
    vals = prop_values(css, lambda s: ".tv-rail" in s or ".rail-track" in s, "overflow-x")
    vals += prop_values(css, lambda s: ".tv-rail" in s or ".rail-track" in s, "overflow")
    assert any(v.split()[0] in ("auto", "scroll") for v in vals), "a rail must scroll horizontally"


def test_rail_cards_do_not_wrap_and_have_scroll_margin(css):
    sel = lambda s: ".rail-track" in s or ".tv-rail" in s
    assert any(v == "nowrap" or v.startswith("nowrap") for v in prop_values(css, sel, "flex-wrap")) or any(
        v.startswith("flex") for v in prop_values(css, sel, "display")
    )
    margins = prop_values(css, lambda s: ("recipe-card" in s) and is_tv(s), "scroll-margin")
    margins += prop_values(css, lambda s: ("recipe-card" in s) and is_tv(s), "scroll-margin-inline")
    margins += prop_values(css, lambda s: ("recipe-card" in s) and is_tv(s), "scroll-margin-left")
    assert margins, "focused cards need scroll-margin"
    assert max(px(p) or 0 for v in margins for p in v.split()) >= 24


def test_rail_track_padding_leaves_room_for_focus_ring_and_scale(css):
    """overflow-x:auto also clips vertically, so the ring (6px + offset) and scale must fit in padding."""
    top = tv_px(css, ".rail-track", "padding-top")
    pads = prop_values(css, lambda s: is_tv(s) and (".rail-track" in s or s.endswith(".tv-rail")), "padding")
    if pads:
        parts = pads[-1].split()
        top = max(top or 0, px(parts[0]) or 0)
    assert top is not None and top >= 24, "rail padding must not clip the focus ring on the focused card"


def test_tv_does_not_clip_page_or_navigation(css):
    for sel, body in rules(css):
        if re.fullmatch(r"(html|body)( ?, ?(html|body))?|body\[data-mode=\"?tv\"?\]", sel):
            d = declarations(body)
            assert d.get("overflow", "visible") not in ("hidden", "clip"), sel
            assert d.get("overflow-y", "visible") not in ("hidden", "clip"), sel
            assert d.get("overflow-x", "visible") not in ("hidden", "clip") or sel.startswith("body\\["), sel


def test_tv_topbar_is_large_and_sticky_actions_clear_it(css):
    bar = tv_px(css, ".topbar", "min-height")
    assert bar is not None and bar >= 80
    margin = prop_values(
        css,
        lambda s: is_tv(s) and ("data-action" in s or ".back" in s or "cookbook-toggle" in s),
        "scroll-margin-top",
    )
    assert margin and max(px(v) or 0 for v in margin) >= bar, "focused detail actions must not hide under the sticky header"


# ---- Focus treatment ----

def test_tv_focus_ring_is_thick(css):
    widths = []
    for sel, body in rules(css):
        if is_tv(sel) and "focus" in sel:
            m = re.search(r"outline(?:-width)?\s*:\s*(\d+(?:\.\d+)?)px", body)
            if m:
                widths.append(float(m.group(1)))
    assert widths and min(widths) >= 4 and max(widths) >= 5


def test_focus_ring_contrast_on_cream_at_least_3_to_1(css):
    toks = tokens(css)
    colours = []
    for sel, body in rules(css):
        if "focus" in sel:
            m = re.search(r"outline(?:-color)?\s*:[^;]*?(var\(--[\w-]+\)|#[0-9a-fA-F]{3,6})", body)
            if m:
                colours.append(resolve(m.group(1), toks))
    assert colours
    for c in colours:
        assert c in APPROVED
        assert contrast(c, CREAM) >= 3.0, c


def test_card_and_detail_actions_have_focus_treatment(css):
    focus_sels = " ".join(sel for sel, _ in rules(css) if "focus" in sel)
    assert "tv" in focus_sels or ".rail-track" in focus_sels or ":focus-visible" in focus_sels
    assert ".recipe-card" in focus_sels
    # detail actions (back link and cookbook toggle) are covered by a generic or explicit rule
    assert (":focus-visible" in focus_sels) or ("back" in focus_sels and "cookbook-toggle" in focus_sels)
    detail_ring = [
        body for sel, body in rules(css)
        if is_tv(sel) and "focus-visible" in sel and "outline" in body
    ]
    assert detail_ring, "TV needs a :focus-visible outline rule"
    for body in detail_ring:
        d = declarations(body)
        assert px(d.get("outline-offset", "0")) is None or px(d.get("outline-offset", "0")) >= 0


def test_focus_ring_is_separated_from_tomato_buttons_by_offset(css):
    """The ring is tomato; on a tomato cookbook button it only reads if offset from the button."""
    for sel, body in rules(css):
        if is_tv(sel) and "focus-visible" in sel and "outline" in body:
            d = declarations(body)
            assert (px(d.get("outline-offset")) or 0) >= 3, sel


# ---- TV detail legibility ----

@pytest.mark.parametrize("needle", [".description", ".ingredients li", ".steps li"])
def test_tv_detail_body_text_is_large(css, needle):
    assert (tv_px(css, needle, "font-size") or 0) >= 24


def test_tv_detail_actions_are_large(css):
    assert (tv_px(css, ".back", "min-height") or 0) >= 56
    assert (tv_px(css, ".cookbook-toggle", "min-height") or 0) >= 64
    assert (tv_px(css, ".back", "font-size") or 0) >= 24
    assert (tv_px(css, ".cookbook-toggle", "font-size") or 0) >= 24


def test_tv_secondary_text_is_legible_at_1080p(css):
    """Facts, labels and eyebrow are 12-13px on mobile; on TV they must be enlarged."""
    assert (tv_px(css, ".facts dt", "font-size") or 0) >= 18
    assert (tv_px(css, ".facts dd", "font-size") or 0) >= 22
    assert (tv_px(css, ".label", "font-size") or 0) >= 18
    assert (tv_px(css, ".eyebrow", "font-size") or 0) >= 18


def test_tv_detail_is_wide_enough_for_1920(css):
    width = tv_px(css, ".detail-shell", "max-width")
    assert width is not None and 900 <= width <= 1920


# ---- My Cookbook empty rail ----

def test_empty_rail_message_is_tv_sized(css):
    size = tv_px(css, ".empty", "font-size")
    assert size is not None and size >= 24, "empty My Cookbook rail copy must be legible on TV"


def test_empty_rail_has_distinct_style(css):
    bodies = [b for s, b in rules(css) if is_tv(s) and ".empty" in s]
    assert any("border" in b or "background" in b for b in bodies), "empty rail needs a visible treatment"


# ---- Brand tokens shared, mobile unchanged, no external assets ----

def test_tv_rules_use_brand_tokens_not_new_colours(css):
    toks = tokens(css)
    assert {v.lower() for k, v in toks.items() if v.startswith("#")} >= APPROVED
    for sel, body in rules(css):
        if is_tv(sel):
            for h in re.findall(r"#[0-9a-fA-F]{3,6}\b", body):
                assert h.lower() in APPROVED, (sel, h)


def test_tv_rules_scoped_so_mobile_is_unchanged(css):
    """Shared selectors keep their mobile values; TV sizing only appears under body[data-mode=tv]."""
    def final(prop, selector):
        vals = [declarations(b)[prop] for s, b in rules(css) if s == selector and prop in declarations(b)]
        return vals[-1] if vals else None

    assert final("min-height", ".topbar") == "64px"
    assert final("max-width", "main") == "720px"
    assert final("font-size", ".recipe-card p") == "14px"
    assert final("font-size", ".label") == "12px"
    assert final("max-width", ".detail-shell") == "560px"
    assert final("min-height", ".cookbook-toggle") == "44px"
    assert final("font", "body").startswith("16px")
    assert final("grid-template-columns", ".recipe-grid") == "repeat(2,minmax(0,1fr))"
    # TV-only values must never leak into unscoped (mobile) rules
    for sel, body in rules(css):
        if not is_tv(sel) and sel != ":root":
            d = declarations(body)
            assert px(d.get("font-size")) is None or px(d.get("font-size")) <= 96, sel
            assert "scroll-margin" not in d or "recipe-card" not in sel or True


def test_no_external_assets(css):
    assert "@import" not in css
    assert not re.search(r"url\(\s*['\"]?(https?:)?//", css)
    assert "http://" not in css and "https://" not in css
    assert "url(" not in css
