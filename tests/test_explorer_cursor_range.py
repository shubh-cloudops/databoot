"""Explorer-only score, bar cursor and automatic line y-range (F3, F4, F5; Board gate 181 items 3-5; AC-35, AC-61, AC-62)."""
import csv
import re
from pathlib import Path

from tests.test_app_pages import _page
from tests.test_business_page import _id, browser, open_, serve, shop  # noqa: F401  (fixtures and helpers)


def rules(html):
    return re.findall(r'<span class="chart-rule">([^<]*)</span>', html)


def test_score_only_in_explorer_captions(make_client, archetypes_dir, round6_dir):
    client = make_client(archetypes_dir)
    i, html = _page(client, "shop.csv", "?app=explorer")
    api = client.get(f"/api/datasets/{i}/charts").json()["charts"]
    assert rules(html) and all(r.endswith(f" · score {c['score']:.2f}") for r, c in zip(rules(html), api))
    for name in ("shop.csv", "places.csv"):
        _, html = _page(client, name)
        assert rules(html) and not any("score" in r for r in rules(html)), name
    client = make_client(round6_dir)
    for name in ("monitor.csv", "survey.csv"):
        assert not any("score" in r for r in rules(_page(client, name)[1])), name


def test_design_text_for_cursor_and_zero_baseline():
    text = (Path(__file__).parent.parent / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "Explorer" in text and "bar-click" in text
    assert "zero baseline" in text and "bars only" in text


def test_explorer_bars_get_bar_click_and_pointer(shop, browser):
    base, i = shop
    page = open_(browser, f"{base}/datasets/{i}?app=explorer")
    sel = '[data-kind="bar"] .js-plotly-plot'
    names = page.eval_on_selector_all("form.filters select", "e => e.map(s => s.name)")
    bars = page.evaluate("""() => [...document.querySelectorAll('[data-kind="bar"]')].map(f => f.id)""")
    hit = None
    for fid in bars:
        label = page.evaluate("id => document.querySelector('#' + id + ' .js-plotly-plot')._fullLayout.xaxis.title.text", fid)
        if "f." + label in names:
            hit = fid
    assert hit, (names, bars)
    page.locator(f"#{hit} .plot").scroll_into_view_if_needed()
    c = page.evaluate("""id => { const r = document.querySelector('#' + id + ' .barlayer .point').getBoundingClientRect();
        return {x: r.x + r.width / 2, y: r.y + r.height / 2}; }""", hit)
    page.mouse.move(c["x"] - 2, c["y"] - 2)
    page.mouse.move(c["x"], c["y"])
    page.wait_for_timeout(300)
    assert "bar-click" in page.get_attribute(f"#{hit}", "class")
    assert page.evaluate("id => getComputedStyle(document.querySelector('#' + id + ' .nsewdrag')).cursor", hit) == "pointer"
    assert page.errors == []


def test_business_trend_auto_range_and_bars_from_zero(tmp_path, make_client, browser):
    folder = tmp_path / "flat"
    folder.mkdir()
    # 8 months (month grain): two rows each, month sums 14,000 .. 16,000 (the line must not be pulled down to 0)
    rows = [(f"2024-{m:02d}-{d:02d}", s, 7000 + 1000 * (m - 1) // 7) for m in range(1, 9) for d, s in ((3, "N"), (17, "S"))]
    with open(folder / "flat.csv", "w", newline="") as f:
        csv.writer(f).writerows([("date", "store", "amount"), *rows])
    make_client(folder)
    with serve() as base:
        page = open_(browser, f"{base}/datasets/{_id(base, 'flat.csv')}?app=business&period=all")
        got = page.evaluate("""() => { const ax = s => { const l = document.querySelector(s).layout || document.querySelector(s)._fullLayout;
              return [document.querySelector(s)._fullLayout.yaxis.range, l.yaxis.rangemode]; };
            return {line: ax('.trends .js-plotly-plot'), bars: [...document.querySelectorAll('[data-kind="bar"] .js-plotly-plot')]
              .map(g => g._fullLayout.xaxis.range[0] + ':' + g._fullLayout.yaxis.range[0])}; }""")
        assert got["line"][0][0] > 0 and got["line"][1] != "tozero", got
        assert got["bars"] and all(b.startswith("0:") or b.endswith(":0") for b in got["bars"]), got
        assert page.errors == []
