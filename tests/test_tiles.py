"""Workspace shell and tiles, part 1 (W7a; AC-79, AC-80, AC-83; Board gate 190): tile macro, dataset tabs, archetype caption,
Explorer and Business grids, tile title case, and the round 6 API snapshot."""
import json
import re
import threading
import time
import urllib.request

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from app import config
from tests.test_pages import _ids

FIGURES = "figure.chart, ul.cards, ul.tiles, dl.kpis, table"


@pytest.fixture
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def serve(make_client):
    servers = []

    def start(folder):
        make_client(folder)
        from app.main import app
        s = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
        threading.Thread(target=s.run, daemon=True).start()
        while not s.started:
            time.sleep(0.05)
        servers.append(s)
        return f"http://127.0.0.1:{s.servers[0].sockets[0].getsockname()[1]}"
    yield start
    for s in servers:
        s.should_exit = True


def open_tiles(browser, base, name, query="", width=1280):
    ids = json.load(urllib.request.urlopen(base + "/api/datasets"))
    i = next(d["id"] for d in ids if d["path"] == name)
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.goto(f"{base}/datasets/{i}{query}")
    page.wait_for_selector(".js-plotly-plot")
    return page, errors


@pytest.mark.parametrize("folder,name,query", [("data_dir", "sales.csv", "?app=explorer"), ("archetypes_dir", "shop.csv", ""),
                                              ("archetypes_dir", "places.csv", ""), ("round6_dir", "monitor.csv", ""), ("round6_dir", "survey.csv", "")])
def test_every_figure_card_and_table_sits_in_a_named_region(request, serve, browser, folder, name, query):
    base = serve(request.getfixturevalue(folder))
    page, errors = open_tiles(browser, base, name, query)
    found = page.evaluate("""(sel) => [...document.querySelectorAll(sel)].map(el => {
        const t = el.closest('section.ws-tile');
        return t && {label: t.getAttribute('aria-label'), h2s: [...t.querySelectorAll('h2')].map(h => h.textContent.trim()),
                     move: !!t.querySelector('.ws-move'), expand: !!t.querySelector('.ws-expand'), grid: t.parentElement.matches('.grid[data-dataset][data-app]')}})""", FIGURES)
    assert len(found) >= 4 and all(found)
    for f in found:
        assert f["label"] in f["h2s"] and f["move"] and f["expand"] and f["grid"]
    for label in {f["label"] for f in found}:
        assert page.get_by_role("region", name=label, exact=True).count() == 1
    assert page.get_by_role("button", name="Expand Columns").get_attribute("aria-haspopup") == "dialog"
    assert page.get_by_role("button", name="Move Columns").count() == 1
    assert errors == []


@pytest.mark.parametrize("width,tracks", [(1280, 12), (375, 1)])
def test_grid_tracks_and_no_sideways_scroll(request, serve, browser, width, tracks):
    base = serve(request.getfixturevalue("archetypes_dir"))
    page, errors = open_tiles(browser, base, "shop.csv", width=width)
    cols = page.evaluate("getComputedStyle(document.querySelector('.grid')).gridTemplateColumns.split(' ').length")
    assert cols == tracks and page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert errors == []


def test_tile_titles_are_upper_case_and_the_rest_keeps_its_case(request, serve, browser):
    base = serve(request.getfixturevalue("data_dir"))
    page, _ = open_tiles(browser, base, "sales.csv", "?app=explorer")
    style = lambda sel: page.evaluate("s => { const c = getComputedStyle(document.querySelector(s)); return [c.textTransform, c.letterSpacing, c.fontFamily] }", sel)  # noqa: E731
    tt, spacing, family = style(".ws-head h2")
    assert tt == "uppercase" and spacing != "normal" and "mono" in family.lower()
    assert page.locator(".ws-head h2").first.inner_text() == "KEY FIGURES"
    for sel in (".chart-title", "table > caption > h2", "th"):
        assert style(sel)[0] == "none"
    assert page.locator("th").first.inner_text() == "Column"


def test_tabs_and_archetype(make_client, data_dir):
    client = make_client(data_dir)
    i = _ids(client)[("sales.csv", None)]
    html = client.get(f"/datasets/{i}").text
    header, main = html.split("<main", 1)
    assert 'aria-label="Datasets"' in header and 'aria-label="Datasets"' not in main
    links = re.findall(r'<a href="/datasets/(\w+)"( aria-current="page")?>([^<]*)</a>', header)
    names = [n for _, _, n in links]
    assert len(links) == len(_ids(client)) and "sub/book.xlsx - Lookup" in names
    assert [k for k, cur, _ in links if cur] == [i]
    assert main.count('id="tile-dialog"') == 1 and main.count('id="ws-live"') == 1 and 'aria-live="polite"' in main.split('id="ws-live"')[0][-40:] + main.split('id="ws-live"')[1][:40]


def test_archetype_caption_omits_g_when_zero(request, make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    ids = _ids(client)
    html = client.get(f"/datasets/{ids[('shop.csv', None)]}").text
    assert '<div class="archetype">APP: BUSINESS · RULE R2 · T1 N2 C3 · ' in html and " G" not in html.split('class="archetype">')[1].split("</div>")[0]
    geo = client.get(f"/datasets/{ids[('places.csv', None)]}").text
    assert re.search(r'class="archetype">APP: MAP · RULE R\d · T\d N\d C\d G2 · \d+ ROWS</div>', geo)


def test_headers_case_rule_is_scoped_to_th():
    css = (config.ROOT / "app/static/css/databoot.css").read_text(encoding="utf-8")
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S))
    assert any("text-transform" in body and "ws-head" in sel for sel, body in rules)
    assert not [sel for sel, body in rules if re.search(r"(^|[\s,>+~])th\b", sel) and re.search(r"uppercase|text-transform", body)]


GOLDEN = json.loads((config.ROOT / "tests/fixtures/round6_api.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("folder", ["data_dir", "archetypes_dir", "round6_dir"])
def test_api_responses_equal_the_round_6_snapshot(request, make_client, folder):
    client = make_client(request.getfixturevalue(folder))
    ids = _ids(client)
    mine = {k: v for k, v in GOLDEN.items() if k.startswith(folder + "/")}
    assert mine and len(ids) == len(mine)
    for key, want in mine.items():
        path, sheet = key.split("/", 1)[1].split("|")
        i = ids[(path, sheet or None)]
        for part in ("app", "charts"):
            got = client.get(f"/api/datasets/{i}/{part}").json()
            assert {k: v for k, v in got.items() if k != "dataset"} == {k: v for k, v in want[part].items() if k != "dataset"}, (key, part)


def test_shell_adds_no_height_outside_tiles(request, serve, browser):
    """The figure h2 (one 44px tile title row now) and the archetype line must not push the Map down (test_AC_59 hovers every point at 1280x900)."""
    base = serve(request.getfixturevalue("archetypes_dir"))
    page, errors = open_tiles(browser, base, "places.csv")
    h = page.evaluate("""() => { const t = document.querySelector('.map-layout .chart-title'), h = t.closest('.chart-h');
        const a = document.querySelector('.archetype'), b = document.querySelector('.app-badge');
        return [h.getBoundingClientRect().height - t.getBoundingClientRect().height, a.getBoundingClientRect().top - b.getBoundingClientRect().top] }""")
    assert h[0] <= 44 and abs(h[1]) <= 8, h
    assert errors == []
