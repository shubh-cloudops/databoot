"""Real-browser checks of the dashboard pages (AC-4, AC-5, AC-6, AC-9): every request off 127.0.0.1 is aborted."""
import re
import threading
import time
import urllib.request

import pytest
import uvicorn
from playwright.sync_api import sync_playwright


@pytest.fixture
def base(data_dir, make_client):
    make_client(data_dir)  # sets the env vars and clears the caches
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(10)


@pytest.fixture
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def open_page(browser, base):
    """open_page(path, width=1280) -> (page, external requests, console errors) once the charts settled."""
    def open_(path, width=1280):
        page = browser.new_page(viewport={"width": width, "height": 900})
        external, errors = [], []

        def route(r):
            if r.request.url.startswith(base):
                r.continue_()
            else:
                external.append(r.request.url)
                r.abort()
        page.route("**/*", route)
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + path)
        page.wait_for_load_state("networkidle")
        return page, external, errors
    return open_


def dataset_path(base, name):
    import json
    for d in json.load(urllib.request.urlopen(base + "/api/datasets")):
        if d["path"].endswith(name):
            return "/datasets/" + d["id"] + "?app=explorer"


def test_sales_draws_line_and_bar(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    page.wait_for_selector('[data-kind="line"] .plot svg.main-svg')
    assert page.locator('[data-kind="line"] .plot .scatterlayer path.js-line').count() == 1
    assert page.locator('[data-kind="bar"] .plot .barlayer .point').count() == 3
    assert page.locator(".plot.is-loading").count() == 0 and page.locator(".plot-error").count() == 0
    assert external == [] and errors == []


def test_points_draws_scatter3d_canvas(base, open_page):
    page, external, errors = open_page(dataset_path(base, "points.tsv"))
    page.wait_for_selector('[data-kind="map3d"] .plot canvas')
    assert page.locator('[data-kind="map3d"] .plot .gl-container').count() == 1
    assert external == [] and errors == []


def test_records_draws_country_map(base, open_page):
    page, external, errors = open_page(dataset_path(base, "records.json"))
    page.wait_for_selector('[data-kind="country_map"] .plot .geo .choroplethlayer path')
    assert page.locator('[data-kind="country_map"] .plot .geo path').count() > 3
    assert external == [] and errors == []


@pytest.mark.parametrize("width", [375, 1280])
@pytest.mark.parametrize("name", ["sales.csv", "points.tsv", "records.json"])
def test_no_horizontal_overflow(base, open_page, name, width):
    page, external, errors = open_page(dataset_path(base, name), width)
    page.wait_for_selector(".plot .main-svg")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert external == [] and errors == []


def test_failed_fetch_shows_note_error(base, browser):
    page = browser.new_page()
    page.route("**/api/datasets/*/app*", lambda r: r.fulfill(status=500, body="no"))
    page.goto(base + dataset_path(base, "sales.csv"))
    page.wait_for_selector(".plot .note-error")
    assert page.locator(".plot.is-loading").count() == 0


def test_every_asset_url_is_local_and_served(base):
    for path in ["/", dataset_path(base, "sales.csv")]:
        html = urllib.request.urlopen(base + path).read().decode()
        urls = re.findall(r'(?:src|href)="([^"]+)"', html)
        for u in (u for u in urls if not u.startswith("#")):
            assert u.startswith("/") and not u.startswith("//"), u
            assert urllib.request.urlopen(base + u).status == 200
    assert "/static/vendor/plotly/plotly.min.js" in html and "/static/js/dashboard.js" in html
    for f in ("world_110m.json", "LICENSE"):
        assert urllib.request.urlopen(base + "/static/vendor/topojson/" + f).status == 200


def test_modebar_visible_without_hover(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    page.wait_for_selector('[data-kind="line"] .plot .modebar-btn')
    bar = page.locator(".modebar").first
    assert bar.evaluate("e => getComputedStyle(e).opacity") == "1"
    assert bar.evaluate("e => getComputedStyle(e).visibility") == "visible"
    assert bar.bounding_box()["width"] > 0
    assert external == [] and errors == []


def test_tab_reaches_modebar_btn_and_enter_clicks(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    page.wait_for_selector('[data-kind="line"] .plot .modebar-btn')
    assert page.locator(".modebar-btn:not([tabindex='0'][role='button'])").count() == 0
    for _ in range(60):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.classList.contains('modebar-btn')"):
            break
    else:
        pytest.fail("Tab never reached a .modebar-btn")
    assert page.evaluate("getComputedStyle(document.activeElement).outlineWidth") == "3px"
    page.evaluate("window.n = 0; document.activeElement.addEventListener('click', () => window.n++)")
    page.keyboard.press("Enter")
    page.keyboard.press("Space")
    assert page.evaluate("window.n") == 2
    assert errors == [] and external == []


def test_map3d_z_axis_and_colorbar_titled_from_z_label(base, open_page):
    page, external, errors = open_page(dataset_path(base, "points.tsv"))
    page.wait_for_selector('[data-kind="map3d"] .plot canvas')
    got = page.evaluate("""() => { const g = document.querySelector('[data-kind="map3d"] .plot');
      return [g._fullLayout.scene.zaxis.title.text, g._fullData[0].marker.colorbar.title.text]; }""")
    assert got == ["value", "value"]
    assert external == [] and errors == []


@pytest.mark.parametrize("width", [1280, 375])
def test_map3d_lat_title_not_clipped_at_bottom(base, open_page, width):
    # Plotly draws 3D axis titles in the WebGL canvas, not the DOM: clipped text leaves ink on the canvas's last rows.
    page, external, errors = open_page(dataset_path(base, "points.tsv"), width)
    page.wait_for_selector('[data-kind="map3d"] .plot canvas')
    page.wait_for_timeout(1000)
    got = page.evaluate("""() => { const plot = document.querySelector('[data-kind="map3d"] .js-plotly-plot');
      const gl = plot.querySelector('.gl-container canvas'), w = gl.width, h = gl.height;
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const x = c.getContext('2d'); x.drawImage(gl, 0, 0);
      const rows = x.getImageData(0, h - 3, w, 3).data;
      let ink = 0; for (let i = 3; i < rows.length; i += 4) if (rows[i] > 0) ink++;
      return { ink: ink, title: plot._fullLayout.scene.yaxis.title.text, bottom: plot._fullLayout.margin.b,
               inside: plot.getBoundingClientRect().bottom >= gl.getBoundingClientRect().bottom }; }""")
    assert got["title"] == "Latitude" and got["bottom"] > 0 and got["inside"]
    assert got["ink"] == 0
    assert external == [] and errors == []
