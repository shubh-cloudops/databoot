"""Map page in a real browser (M2a, M2b; AC-51, AC-52, AC-53, AC-55; Board gate 180): 70vh scattergeo with sequential point colours,
hexagon cells as one choropleth, click-to-details panel, top regions, 3D view toggle, no console errors."""
import json
import re
import urllib.request

import pytest

from tests.test_business_page import _id, browser, click_bar, cursor, open_, serve  # noqa: F401  (fixtures)


@pytest.fixture
def places(archetypes_dir, make_client):
    make_client(archetypes_dir)
    with serve() as base:
        yield base, _id(base, "places.csv")


@pytest.fixture
def big(big_csv, make_client):
    make_client(big_csv)
    with serve() as base:
        yield base, _id(base, "big.csv")


def traces(page):
    return page.evaluate("""() => { const g = document.querySelector('.map-layout .js-plotly-plot');
        return g.data.map(t => ({type: t.type, z: t.z, marker: t.marker, hovertemplate: t.hovertemplate,
        customdata: t.customdata, text: t.text, n: (t.lon || t.locations).length, geojson: t.geojson && t.geojson.features.length})); }""")


def test_points_are_coloured_by_the_primary_numeric(places, browser):
    base, i = places
    page = open_(browser, f"{base}/datasets/{i}")
    tr = traces(page)
    assert len(tr) == 1 and tr[0]["type"] == "scattergeo" and tr[0]["n"] == 20
    m = tr[0]["marker"]
    assert m["color"] == [1000 * (k + 1) for k in range(20)]
    assert m["colorbar"]["title"]["text"] == "pop" and len(m["colorscale"]) == 2
    assert (m["size"], m["opacity"], m["line"]["width"]) == (6, 0.8, 0.5)
    assert tr[0]["customdata"] == list(range(20)) and "marker.color:," in tr[0]["hovertemplate"]
    assert page.locator("figure[data-kind=map2d] .chart-count").inner_text() == "20 of 20 rows"
    assert page.locator("aside.map-panel[aria-live=polite]").count() == 1 and page.locator("main p").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.errors == []


def test_rows_without_a_value_form_a_muted_second_trace(archetypes_dir, make_client, browser):
    (archetypes_dir / "places.csv").write_text("lat,lon,pop\n10,10,5\n20,20,\n30,30,7\n")
    make_client(archetypes_dir)
    with serve() as base:
        page = open_(browser, f"{base}/datasets/{_id(base, 'places.csv')}")
        tr = traces(page)
        assert [t["n"] for t in tr] == [2, 1]
        assert tr[1]["marker"]["color"] == page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--muted').trim()")
        assert tr[0]["customdata"] == [0, 2] and tr[1]["customdata"] == [1]
        assert page.errors == []


@pytest.mark.parametrize("width,height", [(1280, 900), (390, 844)])
def test_plot_is_about_70vh_and_the_phone_map_does_not_drag(places, browser, width, height):
    base, i = places
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto(f"{base}/datasets/{i}")
    page.wait_for_function("document.querySelector('.map-layout .js-plotly-plot')")
    h = page.evaluate("document.querySelector('.map-layout .plot').getBoundingClientRect().height")
    assert 0.65 <= h / height <= 0.75
    assert page.evaluate("document.querySelector('.map-layout .js-plotly-plot').layout.dragmode") == (False if width < 600 else "pan")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_big_csv_draws_hexagon_cells_as_one_choropleth(big, browser):
    base, i = big
    page = open_(browser, f"{base}/datasets/{i}")
    tr = traces(page)
    assert len(tr) == 1 and tr[0]["type"] == "choropleth"
    assert sum(tr[0]["z"]) == 60_000 and len(tr[0]["z"]) < 60_000 and tr[0]["geojson"] == len(tr[0]["z"])
    assert tr[0]["marker"]["line"]["width"] == 0.5
    assert page.evaluate("document.querySelector('.map-layout .js-plotly-plot').data[0].colorbar.title.text") == "Points per cell"
    assert page.evaluate("document.querySelectorAll('.map-layout .scattergeo, .map-layout .point').length") == 0
    assert tr[0]["hovertemplate"] == "%{text}<extra></extra>" and tr[0]["text"][0].endswith((" point", " points"))
    assert tr[0]["text"] == [f"{n:,} point" + ("" if n == 1 else "s") for n in tr[0]["z"]]
    assert page.locator("figure[data-kind=map2d] .chart-count").inner_text() == "60,000 of 60,000 rows"
    assert page.errors == []


def test_hex_hover_label_has_a_separator(big, browser):
    base, i = big
    page = open_(browser, f"{base}/datasets/{i}")
    cells = page.locator(".map-layout .choroplethlayer path")
    cells.nth(cells.count() // 2).scroll_into_view_if_needed()
    box = cells.nth(cells.count() // 2).bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_selector(".hoverlayer .hovertext")
    label = page.locator(".hoverlayer .hovertext").text_content()
    n = int(label.replace(",", "").split()[0])
    assert label.split()[1] == "points" and (f"{n:,}" in label)


def test_offline_map_makes_no_external_request(places, browser):
    base, i = places
    page = browser.new_page()
    seen = []
    page.on("request", lambda r: seen.append(r.url))
    page.goto(f"{base}/datasets/{i}")
    page.wait_for_load_state("networkidle")
    assert all(u.startswith(base) or u.startswith("data:") for u in seen)
    assert json.load(urllib.request.urlopen(f"{base}/api/datasets/{i}/app"))["shown"] == "map"


def click_point(page, k):
    point = page.locator("figure[data-kind=map2d] .js-plotly-plot .point").nth(k)
    point.scroll_into_view_if_needed()
    box = point.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def details(page):
    page.wait_for_selector(".map-panel dl")
    return dict(zip(page.locator(".map-panel dl dt").all_inner_texts(), page.locator(".map-panel dl dd").all_inner_texts()))


@pytest.mark.parametrize("width", [1280, 375])
def test_click_a_point_fills_the_panel_without_a_request(places, browser, width):
    base, i = places
    page = open_(browser, f"{base}/datasets/{i}", width)
    seen = []
    page.on("request", lambda r: seen.append(r.url))
    assert "Click a point" in page.locator(".map-panel .panel-empty").inner_text()
    click_point(page, 3)
    assert details(page) == {"lat": "-28", "lon": "-84", "country": "Kenya", "pop": "4,000"}
    click_point(page, 9)
    assert details(page)["pop"] == "10,000" and page.locator(".map-panel dl").count() == 1
    assert not [u for u in seen if "/api/" in u]
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth") and page.errors == []


def test_regions_figure_ranks_countries_by_sum_of_pop_with_labels(places, browser):
    base, i = places
    page = open_(browser, f"{base}/datasets/{i}")
    got = page.evaluate("""() => { const g = document.querySelector('.map-panel .js-plotly-plot');
        return {data: g.data.map(t => ({x: t.x, y: t.y, o: t.orientation, text: t.texttemplate})),
                y2: !!g.layout.yaxis2, tick: g.layout.xaxis.tickformat}; }""")
    sums = {c: sum(1000 * (k + 1) for k in range(20) if k % 4 == n) for n, c in enumerate(["France", "Japan", "Brazil", "Kenya"])}
    ranked = sorted(sums.items(), key=lambda kv: -kv[1])
    assert len(got["data"]) == 1 and got["data"][0]["o"] == "h" and got["data"][0]["text"] == "%{x:,}"
    assert got["data"][0]["y"] == [k for k, _ in ranked] and got["data"][0]["x"] == [v for _, v in ranked]
    assert not got["y2"] and got["tick"] == ","
    assert page.locator(".map-panel figure[data-drill=false]").count() == 1
    label = page.locator(".map-panel .barlayer .bartext").first.text_content()
    assert label == f"{ranked[0][1]:,}"
    top = ranked[0][0]
    assert cursor(page, top) == "default"
    url = page.url
    click_bar(page, top)
    page.wait_for_timeout(400)
    assert page.url == url and page.errors == []


def test_regions_other_is_a_muted_trace_that_does_nothing(archetypes_dir, make_client, browser):
    (archetypes_dir / "places.csv").write_text("lat,lon,town,n\n" + "".join(f"{i % 80},{i},t{i % 12:02d},{1000 + i}\n" for i in range(24)))
    make_client(archetypes_dir)
    with serve() as base:
        page = open_(browser, f"{base}/datasets/{_id(base, 'places.csv')}")
        got = page.evaluate("""() => { const g = document.querySelector('.map-panel .js-plotly-plot');
            return [g.data.map(t => t.y), g.data[1].marker.color, getComputedStyle(document.documentElement).getPropertyValue('--muted').trim()]; }""")
        assert got[0][1] == ["Other"] and len(got[0][0]) == 10 and got[1] == got[2]
        assert cursor(page, "Other") == "default" and cursor(page, got[0][0][0]) == "default"
        url = page.url
        click_bar(page, "Other")
        page.wait_for_timeout(400)
        assert page.url == url and page.errors == []


def test_table_toggle_on_the_map_and_the_regions(places, browser):
    base, i = places
    page = open_(browser, f"{base}/datasets/{i}")
    for fig, head, rows in (("map2d", ["lon", "lat", "pop"], 20), ("bar", ["country", "pop (sum)"], 4)):
        f = page.locator(f"figure[data-kind={fig}]")
        f.locator(".table-toggle").click()
        assert f.locator(".plot").is_hidden() and f.locator(".table-toggle").get_attribute("aria-pressed") == "true"
        assert f.locator("table.plot-table th").all_inner_texts() == head
        assert f.locator("table.plot-table tbody tr").count() == rows
        assert "20,000" in f.locator("table.plot-table").inner_text() or fig == "bar"
        f.locator(".table-toggle").click()
        assert f.locator(".plot").is_visible()
    assert page.evaluate("[...document.querySelectorAll('.js-plotly-plot')].every(g => !g.layout.yaxis2)")
    assert page.errors == []


@pytest.mark.parametrize("width", [1280, 375])
def test_3d_view_swaps_the_figures_and_back(places, browser, width):
    base, i = places
    page = open_(browser, f"{base}/datasets/{i}", width)
    flat, three, btn = page.locator("figure[data-kind=map2d]"), page.locator("figure[data-kind=map3d]"), page.get_by_role("button", name="3D view")
    assert three.is_hidden() and three.count() == 1 and btn.get_attribute("aria-pressed") == "false"
    btn.click()
    page.wait_for_selector("figure[data-kind=map3d] .plot canvas")
    assert three.is_visible() and flat.is_hidden() and btn.get_attribute("aria-pressed") == "true"
    h = page.evaluate("document.querySelector('figure[data-kind=map3d] .plot').getBoundingClientRect().height")
    assert 0.65 <= h / 900 <= 0.75
    tr = page.evaluate("""() => { const g = document.querySelector('figure[data-kind=map3d] .js-plotly-plot');
        return {type: g.data[0].type, z: g.data[0].z, c: g.data[0].marker.color, bar: g.data[0].marker.colorbar.title.text,
                zt: g.layout.scene.zaxis.title.text, eye: g.layout.scene.camera.eye}; }""")
    assert tr["type"] == "scatter3d" and tr["c"] == tr["z"] == [1000 * (k + 1) for k in range(20)] and tr["bar"] == tr["zt"] == "pop"
    assert tr["eye"]["x"] == (3 if width < 600 else 1.8)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    btn.click()
    assert flat.is_visible() and three.is_hidden() and btn.get_attribute("aria-pressed") == "false"
    page.wait_for_function("document.querySelector('figure[data-kind=map2d] .plot').getBoundingClientRect().width > 100")
    click_point(page, 0)
    assert details(page)["pop"] == "1,000"
    assert page.errors == []


def test_3d_is_coloured_by_revenue_for_an_inline_file(archetypes_dir, make_client, browser):
    (archetypes_dir / "places.csv").write_text("lat,lon,a,revenue\n" + "".join(f"{i},{2 * i},{i % 7},{1500 + 10 * i}\n" for i in range(12)))
    make_client(archetypes_dir)
    with serve() as base:
        page = open_(browser, f"{base}/datasets/{_id(base, 'places.csv')}")
        page.get_by_role("button", name="3D view").click()
        page.wait_for_selector("figure[data-kind=map3d] .plot canvas")
        got = page.evaluate("""() => { const g = document.querySelector('figure[data-kind=map3d] .js-plotly-plot');
            return [g.data[0].marker.color, g.data[0].marker.colorbar.title.text, g.layout.scene.zaxis.title.text]; }""")
        assert got == [[1500 + 10 * i for i in range(12)], "revenue", "revenue"] and page.errors == []


def test_no_bare_four_digit_number_in_main_on_the_map_page(places, browser):
    base, i = places
    page = open_(browser, f"{base}/datasets/{i}")
    click_point(page, 19)
    details(page)
    text = page.inner_text("main")
    assert "20,000" in text
    assert not re.search(r"(?<![\d.,-])\d{4,}(?![\d-])", re.sub(r"\d{4}-\d{2}-\d{2}", "", text))


def test_click_a_hex_cell_shows_the_points_in_it(big, browser):
    base, i = big
    page = open_(browser, f"{base}/datasets/{i}")
    cells = page.locator(".map-layout .choroplethlayer path")
    cells.nth(cells.count() // 2).scroll_into_view_if_needed()
    box = cells.nth(cells.count() // 2).bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_function("document.querySelector('.map-panel .panel-detail').textContent.startsWith('Points in cell: ')")
    n = int(page.locator(".map-panel .panel-detail").inner_text().split(": ")[1].replace(",", ""))
    assert 1 <= n <= 60_000 and page.locator(".map-panel dl").count() == 0 and page.errors == []


def test_plain_axes_print_without_separators(round6_dir, make_client, browser):
    make_client(round6_dir)
    with serve() as base:
        i = _id(base, "orders.csv")
        charts = json.load(urllib.request.urlopen(f"{base}/api/datasets/{i}/charts"))["charts"]
        page = open_(browser, f"{base}/datasets/{i}?app=explorer")
        got = page.evaluate("""() => [...document.querySelectorAll('.js-plotly-plot')].map(g => ({
            x: g.layout.xaxis && [g.layout.xaxis.title.text, g.layout.xaxis.hoverformat],
            y: g.layout.yaxis && [g.layout.yaxis.title.text, g.layout.yaxis.hoverformat]}))""")
        plain = {c["x_label"] for c in charts if "x" in c.get("plain", [])}
        assert plain and {"order_id", "year"} & plain
        for g in got:
            if g["x"] and g["x"][0] in plain:
                assert g["x"][1] == ""
            if g["x"] and g["x"][0] == "amount":
                assert g["x"][1] == ","
        assert any(g["x"] and g["x"][0] in plain for g in got) and page.errors == []
