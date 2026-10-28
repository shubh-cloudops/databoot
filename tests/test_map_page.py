"""Map page part 1 in a real browser (M2a; AC-51, AC-52; Board gate 180): 70vh scattergeo with sequential point colours,
hexagon cells as one choropleth, no console errors."""
import json
import urllib.request

import pytest

from tests.test_business_page import _id, browser, open_, serve  # noqa: F401  (fixtures)


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
        customdata: t.customdata, n: (t.lon || t.locations).length, geojson: t.geojson && t.geojson.features.length})); }""")


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
    assert "points" in tr[0]["hovertemplate"] and "%{z:,}" in tr[0]["hovertemplate"]
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
