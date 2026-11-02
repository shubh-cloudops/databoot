"""Dark theme only (T7; AC-83, AC-84, AC-87; Board gate 190): the stylesheet and dashboard.js ignore the OS scheme, the
tokens resolve and keep contrast under a light and a dark emulated scheme, charts read the dark tokens, DESIGN.md names the terms."""
import re
from pathlib import Path

import pytest

from tests.test_browser import base, browser, dataset_path  # noqa: F401  (fixtures)
from tests.test_table_toggle import settle

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "app/static/css/databoot.css").read_text()
JS = (ROOT / "app/static/js/dashboard.js").read_text()


def test_css_and_js_have_no_os_scheme():
    assert "prefers-color-scheme" not in CSS and "@font-face" not in CSS
    for token in ("#050a12", "#4de1ff", "#ffb454", "color-scheme: dark", "monospace"):
        assert token in CSS
    assert "prefers-color-scheme" not in JS and "prefers-color-scheme" not in (ROOT / "app/static/js/tiles.js").read_text()
    assert re.findall(r"matchMedia\((\"[^\"]*\")\)", JS) == ['"(max-width: 599px)"']  # only the phone query is kept


def lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def lum(rgb):
    return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def over(top, alpha, under):
    return [t * alpha + u * (1 - alpha) for t, u in zip(top, under)]


def nums(s):
    return [float(x) for x in re.findall(r"[\d.]+", s)]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_dark_tokens_and_contrast_whatever_the_os_scheme(base, browser, scheme):
    page = browser.new_page(viewport={"width": 1280, "height": 900}, color_scheme=scheme)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
    page.goto(base + dataset_path(base, "sales.csv"))
    settle(page)
    got = page.evaluate("""() => { const root = getComputedStyle(document.documentElement), tile = document.querySelector('.ws-tile');
        const tint = e => getComputedStyle(e).color;
        return {bg: getComputedStyle(document.body).backgroundColor, body: tint(document.body), scheme: root.colorScheme,
          accent: root.getPropertyValue('--accent').trim(), amber: root.getPropertyValue('--amber').trim(),
          label: tint(document.querySelector('.chart-title, .ws-head h2')), muted: tint(document.querySelector('.muted, .chart-rule, .chart-count') || document.body),
          tile: getComputedStyle(tile).backgroundImage,
          font: document.querySelector('.js-plotly-plot')._fullLayout.font.color,
          fg: root.getPropertyValue('--fg').trim(), bar: document.querySelector('[data-kind=bar] .js-plotly-plot').data[0].marker.color}; }""")
    assert got["bg"] == "rgb(5, 10, 18)" and got["scheme"] == "dark"
    assert got["accent"] == "#4de1ff" and got["amber"] == "#ffb454"
    assert got["font"] == got["fg"] == "#e6f1fa" and got["bar"] == "#4de1ff"  # charts read --fg/--c1 through tokens()
    page_bg = nums(got["bg"])
    stops = [nums(s) for s in re.findall(r"rgba?\(([^)]*)\)", got["tile"])]
    assert len(stops) >= 2
    glow = [77, 225, 255]
    for s in stops:  # effective tile colour: the gradient over the page, and with the cursor glow at its peak
        eff = over(s[:3], s[3] if len(s) > 3 else 1, page_bg)
        for e in (eff, over(glow, 0.12, eff)):
            for key in ("body", "label", "muted"):
                assert ratio(nums(got[key])[:3], e) >= 4.5, (key, got[key], e)
    assert errors == []


def test_charts_keep_one_axis_and_sorted_bars_under_light(base, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900}, color_scheme="light")
    page.goto(base + dataset_path(base, "sales.csv"))
    settle(page)
    got = page.evaluate("""() => { const gd = document.querySelector('[data-kind=bar] .js-plotly-plot');
        return {keys: Object.keys(gd._fullLayout).filter(k => k.startsWith('yaxis')), range: gd._fullLayout.yaxis.range, y: gd.data[0].y}; }""")
    assert got["keys"] == ["yaxis"] and got["range"][0] == 0 and got["y"] == sorted(got["y"], reverse=True)


TERMS = ["#050a12", "#4de1ff", "#ffb454", "mono", "header", "drag handle", "expand", "table toggle", "12-column", "0.6 s",
         "reduced motion", "reduced transparency"]


def test_design_md_round7_section_names_the_terms():
    doc = (ROOT / "docs/DESIGN.md").read_text()
    heads = [m for m in re.finditer(r"^(#+) (.*)$", doc, re.M) if "round 7" in m.group(2).lower()]
    assert heads
    found = []
    for m in heads:  # a section runs to the next heading of the same or a higher level
        nxt = re.search(rf"^#{{1,{len(m.group(1))}}} ", doc[m.end():], re.M)
        found.append(doc[m.start(): m.end() + (nxt.start() if nxt else len(doc))].lower())
    text = max(found, key=len)
    assert [t for t in TERMS if t.lower() not in text] == []
    assert re.search(r"rings always turn", text)
