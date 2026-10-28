"""Page shell of round 5 (A2; AC-44, AC-45): app badge, View as, one body per app, links that keep `app`."""
import re
import threading
import time
from urllib.parse import parse_qs, urlparse

import pytest
import uvicorn
from playwright.sync_api import sync_playwright


def _page(client, name, query=""):
    i = next(d["id"] for d in client.get("/api/datasets").json() if d["path"] == name)
    return i, client.get(f"/datasets/{i}{query}").text


def _badge(html):
    return re.search(r'<span class="app-badge">([^<]*)</span>', html).group(1)


def _view_as(html):
    nav = re.search(r'<nav class="view-as" aria-label="View as">(.*?)</nav>', html, re.S)
    return nav and re.findall(r'<a href="([^"]*)"( aria-current="page")?>([^<]*)</a>', nav.group(1))


def test_shop_badge_and_view_as(make_client, archetypes_dir):
    i, html = _page(make_client(archetypes_dir), "shop.csv")
    assert _badge(html) == "App: Business (rule R2)"
    assert _view_as(html) == [(f"/datasets/{i}?app=business", ' aria-current="page"', "Business"),
                              (f"/datasets/{i}?app=explorer", "", "Explorer")]
    assert 'data-kind="line"' not in html and "<h2>Columns</h2>" in html and "<h2>First 20 rows</h2>" in html
    assert f'href="/datasets/{i}/export.xlsx"' in html  # no app param in the request: round 4 URLs


def test_measures_and_places_badges(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    html = _page(client, "measures.csv")[1]
    assert _badge(html) == "App: Explorer (rule R3)" and _view_as(html) is None and 'class="view-as"' not in html
    html = _page(client, "places.csv")[1]
    assert _badge(html) == "App: Map (rule R1)"
    assert [t for _, _, t in _view_as(html)] == ["Map", "Explorer"]


def test_app_param_switches_body_not_badge(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    i, html = _page(client, "shop.csv", "?app=explorer&f.store=North")
    assert _badge(html) == "App: Business (rule R2)"
    assert re.search(r'<a href="[^"]*" aria-current="page">Explorer</a>', html)
    assert 'class="kpis"' in html and 'data-kind="line"' in html
    assert f'href="/datasets/{i}?app=explorer" aria-label="Remove filter store = North"' in html
    assert f'href="/datasets/{i}?app=explorer">Clear filters' in html
    assert f'href="/datasets/{i}/export.xlsx?f.store=North&amp;app=explorer"' in html
    assert '<input type="hidden" name="app" value="explorer">' in html
    assert f'href="/datasets/{i}?f.store=North&amp;app=business">Business' in html
    # an app the dataset does not qualify for falls back to the detected one, and links stay as in round 4
    i, html = _page(client, "shop.csv", "?app=map&f.store=North")
    assert re.search(r'aria-current="page">Business<', html) and "app=map" not in html
    assert f'href="/datasets/{i}">Clear filters' in html


def test_explorer_figures_equal_charts(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    i, html = _page(client, "shop.csv", "?app=explorer")
    api = client.get(f"/api/datasets/{i}/charts").json()["charts"]
    assert client.get(f"/api/datasets/{i}/app?app=explorer").json()["charts"] == api
    assert re.findall(r'<figure class="chart" id="(chart-\d+)" data-kind="(\w+)"', html) == [(c["id"], c["kind"]) for c in api]


@pytest.fixture
def server(archetypes_dir, make_client):
    make_client(archetypes_dir)
    from app.main import app
    s = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    t = threading.Thread(target=s.run, daemon=True)
    t.start()
    while not s.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{s.servers[0].sockets[0].getsockname()[1]}"
    s.should_exit = True
    t.join(10)


def test_click_explorer_keeps_app_on_reload(server):
    import json
    import urllib.request
    i = next(d["id"] for d in json.load(urllib.request.urlopen(server + "/api/datasets")) if d["path"] == "shop.csv")
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        errors = []
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{server}/datasets/{i}")
        assert page.locator(".view-as a[aria-current=page]").inner_text() == "Business"
        with page.expect_navigation():
            page.click(".view-as >> text=Explorer")
        page.wait_for_selector('[data-kind="line"] .plot svg.main-svg')
        assert parse_qs(urlparse(page.url).query) == {"app": ["explorer"]}
        page.reload()
        page.wait_for_selector('[data-kind="line"] .plot svg.main-svg')
        assert parse_qs(urlparse(page.url).query) == {"app": ["explorer"]}
        assert page.locator(".view-as a[aria-current=page]").inner_text() == "Explorer"
        assert page.locator(".app-badge").inner_text() == "App: Business (rule R2)"
        assert page.locator(".plot-error").count() == 0 and errors == []
        b.close()
