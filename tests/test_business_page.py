"""Business page in a real browser (B2; AC-46, 48, 49, 50, 55, 57; Board gates 179, 180): cards, leaderboard, drill, crumbs,
change table, no pointer cursor on the last level or on the Other bar."""
import csv
import json
import re
import threading
import time
import urllib.request
from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse

import pytest
import uvicorn
from playwright.sync_api import sync_playwright


@contextmanager
def serve():
    from app.main import app
    s = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    t = threading.Thread(target=s.run, daemon=True)
    t.start()
    while not s.started:
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{s.servers[0].sockets[0].getsockname()[1]}"
    finally:
        s.should_exit = True
        t.join(10)


@pytest.fixture
def shop(archetypes_dir, make_client):
    make_client(archetypes_dir)
    with serve() as base:
        yield base, _id(base, "shop.csv")


@pytest.fixture
def wide(tmp_path, make_client):
    """12 values in `a` and 14 in `b`: the first drill level has an Other bar and drill is still on."""
    folder = tmp_path / "wide"
    folder.mkdir()
    rows = [(f"2024-{1 + i % 6:02d}-{5 + i % 20:02d}", f"a{i % 12:02d}", f"b{i % 14:02d}", 10 + i % 7 * 3) for i in range(168)]
    with open(folder / "wide.csv", "w", newline="") as f:
        csv.writer(f).writerows([("date", "a", "b", "amount"), *rows])
    make_client(folder)
    with serve() as base:
        yield base, _id(base, "wide.csv")


def _id(base, name):
    return next(d["id"] for d in json.load(urllib.request.urlopen(base + "/api/datasets")) if d["path"] == name)


@pytest.fixture
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def open_(browser, url, width=1280, plots=True):
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.errors = []
    page.on("console", lambda m: m.type == "error" and page.errors.append(m.text))
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.goto(url)
    settle(page) if plots else page.wait_for_load_state("networkidle")
    return page


def settle(page):
    page.wait_for_load_state("networkidle")
    page.wait_for_function("""() => { const p = [...document.querySelectorAll('.plot')];
        return p.length > 0 && p.every(e => e.classList.contains('js-plotly-plot')); }""")


def query(page):
    return parse_qs(urlparse(page.url).query)


def centre(page, label):
    """Viewport coordinates of the middle of the bar whose category is `label` (any trace), after scrolling it into view."""
    page.locator("[data-leaderboard] .plot").scroll_into_view_if_needed()
    return page.evaluate("""l => { const gd = document.querySelector('[data-leaderboard] .js-plotly-plot');
        for (let t = 0; t < gd.data.length; t++) { const i = gd.data[t].y.indexOf(l);
          if (i >= 0) { const r = gd.querySelectorAll('.barlayer .trace')[t].querySelectorAll('.point')[i].getBoundingClientRect();
            return {x: r.x + r.width / 2, y: r.y + r.height / 2}; } } }""", label)


def click_bar(page, label):
    c = centre(page, label)
    page.mouse.click(c["x"], c["y"])


def click_bar_to_navigate(page, label):
    with page.expect_navigation():
        click_bar(page, label)
    settle(page)


def cursor(page, label):
    c = centre(page, label)
    page.mouse.move(c["x"] - 2, c["y"] - 2)
    page.mouse.move(c["x"], c["y"])
    page.wait_for_timeout(300)  # let plotly_hover fire
    return page.evaluate("getComputedStyle(document.querySelector('[data-leaderboard] .nsewdrag')).cursor")


def title(page):
    return page.locator("[data-leaderboard] .chart-title").inner_text()


def crumbs(page):
    return page.locator("nav.crumbs li").all_inner_texts()


@pytest.mark.parametrize("width", [1280, 375])
def test_cards_have_arrow_percent_value_and_sparkline(shop, browser, width):
    base, i = shop
    page = open_(browser, f"{base}/datasets/{i}", width)
    cards = page.locator("ul.cards > li.card")
    assert cards.count() == 2
    first = cards.nth(0)
    assert first.locator(".card-label").inner_text() == "revenue" and first.locator(".card-value").inner_text() == "7,392"
    change = first.locator(".card-change")
    assert change.locator("span[aria-hidden=true]").inner_text() == "▲"
    assert change.inner_text().split() == ["▲", "+19.4%", "up"]
    assert first.locator("svg.spark polyline").count() == 1 and first.locator("svg.spark title").text_content() == "revenue, last 6 months"
    assert cards.nth(1).locator(".card-value").inner_text() == "72" and cards.nth(1).locator("svg.spark").count() == 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth") and page.errors == []


def test_card_without_a_full_period_says_na_and_has_no_arrow(shop, browser):
    base, i = shop
    page = open_(browser, f"{base}/datasets/{i}?from=2030-01-01", plots=False)
    cards = page.locator("ul.cards > li.card")
    assert cards.count() == 2
    for k in range(2):
        assert cards.nth(k).locator(".card-value").inner_text() == "n/a"
        assert cards.nth(k).locator(".card-change, svg.spark").count() == 0
        assert not set(cards.nth(k).inner_text()) & set("▲▼▶")
    assert page.errors == []


def test_page_order_and_markup(shop):
    base, i = shop
    html = urllib.request.urlopen(f"{base}/datasets/{i}").read().decode()
    marks = ['<ul class="cards">', '<form class="filters"', '<nav class="crumbs" aria-label="Drill path">', 'class="trends"',
             'data-leaderboard', '<table class="delta-table">', "<h2>Columns</h2>", "<h2>First 20 rows</h2>"]
    at = [html.index(m) for m in marks]
    assert at == sorted(at)
    main = re.search(r"<main.*?</main>", html, re.S).group(0)
    assert not re.search(r"<p[\s>]", main) and main.count('aria-current="page"') == 2  # the View-as link and the last crumb
    text = re.sub(r"<[^>]+>", " ", main)
    assert not re.search(r"(?<![\d.,-])\d{4,}(?![\d-])", re.sub(r"\d{4}-\d{2}-\d{2}", "", text))


@pytest.mark.parametrize("width", [1280, 375])
def test_leaderboard_labels_have_separators(shop, browser, width):
    base, i = shop
    page = open_(browser, f"{base}/datasets/{i}", width)
    texts = page.locator("[data-leaderboard] .barlayer text.bartext").evaluate_all("els => els.map(e => e.textContent)")
    assert texts == ["15,354", "15,276"]
    assert page.errors == []


def test_drill_down_crumbs_back_and_no_pointer_at_last_level(shop, browser):
    base, i = shop
    page = open_(browser, f"{base}/datasets/{i}")
    start = page.url
    assert title(page) == "revenue by channel" and crumbs(page) == ["All"]
    assert page.locator("[data-leaderboard]").get_attribute("data-drill") is None
    click_bar_to_navigate(page, "web")
    assert query(page) == {"f.channel": ["web"]} and title(page) == "revenue by store"
    assert crumbs(page) == ["All", "channel: web"]
    assert page.locator("nav.crumbs [aria-current=page]").inner_text() == "channel: web"
    assert page.evaluate("getComputedStyle(document.querySelector('nav.crumbs li + li'), '::before').content").startswith('"›"')
    click_bar_to_navigate(page, "North")
    assert query(page) == {"f.channel": ["web"], "f.store": ["North"]} and title(page) == "revenue by product"
    assert page.locator("[data-leaderboard]").get_attribute("data-drill") == "false"
    before = page.url
    assert cursor(page, "p11") == "default"
    click_bar(page, "p11")
    click_bar(page, "Other")
    page.wait_for_timeout(500)
    assert page.url == before and title(page) == "revenue by product"
    page.go_back()
    settle(page)
    assert query(page) == {"f.channel": ["web"]} and title(page) == "revenue by store"
    page.click("nav.crumbs >> text=All")
    settle(page)
    assert "f." not in page.url and title(page) == "revenue by channel"
    assert page.errors == []


def test_other_bar_is_muted_grey_and_has_no_pointer_or_click(wide, browser):
    base, i = wide
    page = open_(browser, f"{base}/datasets/{i}")
    lead = page.locator("[data-leaderboard]")
    assert title(page) == "amount by a" and lead.get_attribute("data-drill") is None
    fills = page.evaluate("""() => { const probe = document.createElement('i'); probe.style.color = 'var(--muted)'; document.body.append(probe);
        const muted = getComputedStyle(probe).color;
        return {muted, traces: [...document.querySelectorAll('[data-leaderboard] .barlayer .trace')].map(t =>
          [...t.querySelectorAll('.point path')].map(p => getComputedStyle(p).fill))}; }""")
    assert len(fills["traces"]) == 2 and fills["traces"][1] == [fills["muted"]]
    assert len(fills["traces"][0]) == 10 and set(fills["traces"][0]) != {fills["muted"]}
    assert page.locator("[data-leaderboard] .barlayer text.bartext").count() == 11
    assert cursor(page, "Other") == "default"
    first = page.evaluate("document.querySelector('[data-leaderboard] .js-plotly-plot').data[0].y[0]")
    assert cursor(page, first) == "pointer"
    assert cursor(page, "Other") == "default"
    before = page.url
    click_bar(page, "Other")
    page.wait_for_timeout(500)
    assert page.url == before
    click_bar_to_navigate(page, first)
    assert query(page) == {"f.a": [first]} and title(page) == "amount by b"
    assert page.errors == []


def test_change_table_cells_have_three_tints(shop, browser):
    base, i = shop
    page = open_(browser, f"{base}/datasets/{i}?f.channel=web&f.store=North")
    cells = page.evaluate("""() => { const probe = document.createElement('i'); probe.style.color = 'var(--div-mid)'; document.body.append(probe);
        return {mid: getComputedStyle(probe).color, cells: [...document.querySelectorAll('.delta-table td.delta')].map(td =>
          ({cls: td.className, text: td.textContent, bg: getComputedStyle(td).backgroundColor, t: td.style.getPropertyValue('--t')}))}; }""")
    by = {}
    for c in reversed(cells["cells"]):  # the first cell of each class
        by[c["cls"].split()[-1]] = c
    assert set(by) == {"pos", "neg", "zero"}
    assert by["pos"]["text"] == "+606" and by["neg"]["text"] == "-506" and by["zero"]["text"] == "0"
    assert by["zero"]["bg"] == cells["mid"] and len({c["bg"] for c in by.values()}) == 3
    assert by["pos"]["t"].strip() == "1.0" and page.errors == []
