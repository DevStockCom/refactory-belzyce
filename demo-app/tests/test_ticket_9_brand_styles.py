"""Acceptance tests for ticket #9: brand tokens and mobile layout (static/styles.css)."""
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
    """Return [(selector_text, body)] for flat and @media-nested rules."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css_text):
        out.append((" ".join(m.group(1).split()), m.group(2)))
    return out


def declarations(body):
    decls = {}
    for part in body.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            decls[k.strip().lower()] = v.strip()
    return decls


def normalize_hex(h):
    h = h.lower()
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    return h


def tokens(css_text):
    root = {}
    for sel, body in rules(css_text):
        if sel == ":root":
            for k, v in declarations(body).items():
                if k.startswith("--"):
                    root[k] = v
    return root


def resolve(value, toks):
    m = re.fullmatch(r"var\((--[\w-]+)\)", value.strip())
    if m:
        return resolve(toks.get(m.group(1), ""), toks)
    return value.strip().lower()


def luminance(hex_color):
    h = normalize_hex(hex_color)
    chans = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _meets_aa(fg, bg):
    return round(contrast(fg, bg), 2) >= 4.5


def rules_for(css_text, pattern):
    return [(s, declarations(b)) for s, b in rules(css_text) if re.search(pattern, s)]


# --- Criterion 1: approved tokens only, no external resources -----------------

def test_palette_tokens_defined_in_root(css):
    values = {resolve(v, {}) for v in tokens(css).values()}
    normalized = {normalize_hex(v) for v in values if v.startswith("#")}
    assert APPROVED <= normalized, f"missing palette tokens: {APPROVED - normalized}"


def test_only_approved_hex_values_used(css):
    found = {normalize_hex(h) for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", css)}
    assert found, "stylesheet defines no hex colors"
    assert found <= APPROVED, f"unapproved hex colors: {found - APPROVED}"


def test_no_external_font_image_or_url(css):
    assert "url(" not in css.lower()
    assert "@import" not in css.lower()
    assert "@font-face" not in css.lower()
    assert not re.search(r"https?:|//[\w.-]+\.\w{2,}", css)


def test_brand_colors_are_applied_not_just_defined(css):
    uses = css.count("var(--")
    assert uses >= 10, "tokens should be consumed via var(--...)"
    toks = tokens(css)
    used_names = set(re.findall(r"var\((--[\w-]+)\)", css))
    for color in (CREAM, TOMATO, HERB, CHARCOAL):
        names = [k for k, v in toks.items() if normalize_hex(resolve(v, toks)) == color]
        assert any(n in used_names for n in names), f"{color} token never used"


def test_golden_yellow_is_decorative_only(css):
    toks = tokens(css)
    gold_names = {k for k, v in toks.items() if resolve(v, toks) == GOLD}
    assert gold_names, "golden yellow token missing"
    for sel, decls in ((s, declarations(b)) for s, b in rules(css)):
        color = decls.get("color")
        if color is None:
            continue
        assert normalize_hex(resolve(color, toks)) != GOLD, f"{sel} uses golden yellow as text color"


# --- Criterion 2: WCAG AA contrast by calculation ---------------------------------

@pytest.mark.parametrize("fg,bg,label", [
    (CHARCOAL, CREAM, "body text"),
    (CREAM, TOMATO, "button text (cream on tomato)"),
    (CREAM, HERB, "saved state (cream on herb green)"),
    (HERB, CREAM, "herb green text on cream"),
    (TOMATO, CREAM, "tomato text on cream"),
])
def test_palette_pairs_meet_aa(fg, bg, label):
    assert _meets_aa(fg, bg), f"{label}: {contrast(fg, bg):.2f}"


def test_body_uses_charcoal_on_cream(css):
    toks = tokens(css)
    body = [d for s, d in rules_for(css, r"^(html,\s*)?body\b") if "color" in d or "background" in d]
    merged = {}
    for d in body:
        merged.update(d)
    fg = normalize_hex(resolve(merged.get("color", ""), toks))
    bg = normalize_hex(resolve(merged.get("background", merged.get("background-color", "")), toks))
    assert (fg, bg) == (CHARCOAL, CREAM)


def _resolved_pair(css_text, selector_regex):
    toks = tokens(css_text)
    fg = bg = None
    for _, d in rules_for(css_text, selector_regex):
        if "color" in d:
            fg = normalize_hex(resolve(d["color"], toks))
        for key in ("background", "background-color"):
            if key in d and d[key].strip().startswith(("var(", "#")):
                bg = normalize_hex(resolve(d[key], toks))
    return fg, bg


def test_saved_toggle_text_meets_aa(css):
    fg, bg = _resolved_pair(css, r"\.cookbook-toggle\.saved(?![\w-])")
    assert fg and bg, "saved toggle must set explicit text and background colors"
    assert {fg, bg} <= APPROVED
    assert _meets_aa(fg, bg)


def test_unsaved_toggle_text_meets_aa(css):
    fg, bg = _resolved_pair(css, r"\.cookbook-toggle(?![\w-])(?!\.saved)")
    assert fg and bg, "toggle must set explicit text and background colors"
    assert _meets_aa(fg, bg)


# --- Criterion 3: 375px layout without horizontal scroll (static guarantees) ------

def test_viewport_meta_present_in_base():
    assert "width=device-width" in (TEMPLATES / "base.html").read_text(encoding="utf-8")


def test_border_box_and_no_horizontal_overflow_guards(css):
    assert re.search(r"box-sizing\s*:\s*border-box", css)
    assert re.search(r"overflow-x\s*:\s*(hidden|clip)", css) or re.search(
        r"max-width\s*:\s*100%", css
    )


def test_no_fixed_widths_wider_than_375_outside_tv_and_wide_media(css):
    # Strip media queries with a min-width >= 376px and TV-mode rules.
    stripped = re.sub(r"@media[^{]*min-width\s*:\s*(\d+)px[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}",
                      lambda m: "" if int(m.group(1)) >= 376 else m.group(0), css)
    for sel, body in rules(stripped):
        if 'data-mode="tv"' in sel or "data-mode=tv" in sel or ".tv-" in sel:
            continue
        for prop in ("width", "min-width"):
            m = re.search(rf"(?<![\w-]){prop}\s*:\s*(\d+)px", body)
            if m:
                assert int(m.group(1)) <= 375, f"{sel} {prop}:{m.group(1)}px exceeds 375px"


def test_card_grid_cannot_force_overflow(css):
    grid = rules_for(css, r"\.recipe-grid")
    assert grid, ".recipe-grid rule missing"
    joined = " ".join(f"{k}:{v}" for _, d in grid for k, v in d.items())
    assert "grid" in joined
    assert "minmax(0" in joined or "1fr" in joined
    card = rules_for(css, r"\.recipe-card(?![\w-])")
    assert any(d.get("min-width") == "0" or "overflow" in d for _, d in card)


def test_long_text_wraps_on_detail(css):
    assert re.search(r"overflow-wrap\s*:\s*(anywhere|break-word)|word-break\s*:\s*break-word", css)


# --- Criterion 4: saved vs unsaved without colour; visible focus --------------------

def test_saved_state_differs_by_more_than_colour(css):
    toks = tokens(css)
    base = {}
    for _, d in rules_for(css, r"\.cookbook-toggle(?![\w-])(?!\.saved|\[)"):
        base.update(d)
    saved = {}
    for _, d in rules_for(css, r"\.cookbook-toggle(\.saved|\[aria-pressed=[\"']?true[\"']?\])(?![\w-])"):
        saved.update(d)
    assert saved, "no saved-state rule for .cookbook-toggle"
    non_colour = 0
    for prop in ("border", "border-style", "border-width", "font-weight", "text-decoration",
                 "outline", "box-shadow"):
        if prop in saved and saved[prop] != base.get(prop):
            non_colour += 1
    if "content" in saved:
        non_colour += 1
    assert non_colour >= 1, "saved state must differ by border/weight/etc., not colour alone"


def test_saved_border_style_differs_from_unsaved(css):
    base = {}
    for _, d in rules_for(css, r"\.cookbook-toggle(?![\w-])(?!\.saved|\[)"):
        base.update(d)
    saved = {}
    for _, d in rules_for(css, r"\.cookbook-toggle(\.saved|\[aria-pressed=[\"']?true[\"']?\])(?![\w-])"):
        saved.update(d)
    assert "border" in base or "border-style" in base or "border-width" in base, "unsaved toggle needs a border"

    def border_shape(d):
        b = d.get("border", "")
        style = re.search(r"\b(solid|dashed|dotted|double|none)\b", b)
        width = re.search(r"\b(\d+)px\b", b)
        return (d.get("border-style") or (style and style.group(1)),
                d.get("border-width") or (width and width.group(1)))

    assert border_shape(saved) != border_shape(base) or saved.get("font-weight") != base.get("font-weight")


def test_toggle_icon_and_text_hooks_styled(css):
    assert ".toggle-icon" in css and ".toggle-text" in css


def test_focus_visible_defined_with_outline(css):
    focus = rules_for(css, r":focus-visible")
    assert focus, ":focus-visible rule missing"
    for _, d in focus:
        outline = d.get("outline", "")
        assert outline and not re.search(r"\b(none|0)\b(?!\.)", outline.replace("0.", "x")), outline
    joined = " ".join(s for s, _ in focus)
    for target in (r"a\b", r"button|\.cookbook-toggle", r"input|\.search", r"\.recipe-card"):
        assert re.search(target, joined) or re.search(r"(^|,)\s*:focus-visible", joined), target


def test_focus_outline_is_thick_and_brand_coloured(css):
    toks = tokens(css)
    for _, d in rules_for(css, r":focus-visible"):
        width = re.search(r"(\d+)px", d.get("outline", ""))
        assert width and int(width.group(1)) >= 3
        colour = re.search(r"var\((--[\w-]+)\)|#[0-9a-fA-F]{3,6}", d["outline"])
        assert colour
        resolved = normalize_hex(resolve(colour.group(0), toks))
        assert resolved in {TOMATO, CHARCOAL, HERB}


def test_no_unconditional_outline_removal(css):
    for sel, body in rules(css):
        d = declarations(body)
        if re.search(r"outline\s*:\s*(0|none)\b", body) and ":focus-visible" not in sel:
            # Allowed only if the control gets a visible replacement indicator.
            assert d.get("box-shadow") or "border" in body, f"{sel} removes outline with no replacement"


# --- Criterion 5: artwork --------------------------------------------------------

def test_recipe_art_uses_art_variables(css):
    art = rules_for(css, r"\.recipe-art(?![\w-])")
    assert art, ".recipe-art rule missing"
    joined = " ".join(v for _, d in art for v in d.values())
    assert "var(--art-a)" in joined and "var(--art-b)" in joined
    assert "gradient" in joined


def test_art_initial_is_large_and_styled(css):
    initial = rules_for(css, r"\.art-initial")
    assert initial, ".art-initial rule missing"
    size = [d.get("font-size", "") for _, d in initial]
    assert any(re.search(r"(\d+)(px|rem)|clamp|vw", s) for s in size)
    px = [int(m.group(1)) for s in size for m in [re.search(r"(\d+)px", s)] if m]
    assert not px or max(px) >= 48


def test_art_vars_are_not_fixed_in_stylesheet(css):
    # --art-a/--art-b come from each card's inline style; the sheet must not pin them
    # on shared selectors (that would make every card look identical).
    for sel, body in rules(css):
        if sel == ":root":
            continue
        assert not re.search(r"--art-[ab]\s*:", body), f"{sel} hard-codes artwork variables"


def test_rendered_cards_carry_distinct_art_vars(client, recipes):
    html = client.get("/").get_data(as_text=True)
    pairs = set(re.findall(r"--art-a:([^;\"]+);--art-b:([^;\"]+)", html))
    assert len(pairs) >= 6
    assert html.count('class="art-initial"') >= len(recipes)


# --- Criterion 6: renamed classes / variables, detail layout ----------------------

@pytest.mark.parametrize("old", ["mo" + "vie", "pos" + "ter", "watch" + "list", "--pos" + "ter-"])
def test_no_legacy_names_in_stylesheet(css, old):
    assert not re.search(old, css, re.I), f"legacy name {old!r} still in styles.css"


@pytest.mark.parametrize("selector", [
    r"\.recipe-card", r"\.recipe-art", r"\.cookbook-toggle", r"\.recipe-grid",
])
def test_renamed_classes_are_styled(css, selector):
    assert rules_for(css, selector), f"{selector} not styled"


def test_stylesheet_targets_classes_templates_emit(css):
    emitted = set()
    for tpl in TEMPLATES.glob("*.html"):
        for cls in re.findall(r'class="([^"{]*)', tpl.read_text(encoding="utf-8")):
            emitted.update(cls.split())
    for cls in ("recipe-card", "recipe-art", "cookbook-toggle"):
        assert cls in emitted
    for cls in ("facts", "ingredients", "steps"):
        assert cls in emitted
        assert re.search(rf"\.{cls}(?![\w-])", css), f".{cls} (detail layout) not styled"


def test_cards_are_rounded_and_spaced(css):
    art = {}
    for _, d in rules_for(css, r"\.recipe-art(?![\w-])"):
        art.update(d)
    radius = re.search(r"(\d+)px", art.get("border-radius", ""))
    assert radius and int(radius.group(1)) >= 12
    grid = {}
    for _, d in rules_for(css, r"\.recipe-grid"):
        grid.update(d)
    assert "gap" in grid


def test_brand_header_and_typography_rules(css):
    for sel in (r"\.brand(?![\w-])", r"\.brand-mark", r"\.hero", r"\.search", r"\.section-heading"):
        assert rules_for(css, sel), f"{sel} not styled"
    font = " ".join(d.get("font-family", "") + d.get("font", "") for _, d in rules_for(css, r"^(html,\s*)?body\b"))
    assert font and "serif" in font or "sans-serif" in font
    assert "http" not in font


def test_detail_numbered_steps_and_ingredient_list_styled(css):
    steps = " ".join(f"{k}:{v}" for _, d in rules_for(css, r"\.steps") for k, v in d.items())
    assert "counter" in steps or "list-style" in steps, "numbered steps need counter or list styling"
    chips = " ".join(s for s, _ in rules_for(css, r"\.facts|\.label"))
    assert chips
