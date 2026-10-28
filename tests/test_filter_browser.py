"""Real-browser checks of the dashboard filters (J1; AC-38, AC-39): form submit, chips, Back, bar click cross-filter."""
from urllib.parse import parse_qs, urlparse

from tests.test_browser import base, browser, dataset_path, open_page  # noqa: F401  (fixtures)


def rows(page):
    return page.locator(".kpis div", has=page.locator("dt", has_text="Rows")).locator("dd").inner_text()


def query(page):
    return parse_qs(urlparse(page.url).query)


def bar_click(page, value):
    with page.expect_navigation():
        page.evaluate("""v => document.querySelector('[data-kind="bar"]').querySelector('.plot')
            .emit('plotly_click', {points: [{x: v, label: v, data: {}}]})""", value)
    page.wait_for_load_state("networkidle")


def test_form_chip_clear_and_back(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    start = page.url
    assert rows(page) == "6"
    page.select_option("select[name='f.region']", "South")
    page.click("form.filters button")
    page.wait_for_load_state("networkidle")
    assert query(page) == {"f.region": ["South"]} and "from" not in page.url and rows(page) == "2"
    page.go_back()
    page.wait_for_load_state("networkidle")
    assert page.url == start and rows(page) == "6"
    page.go_forward()
    page.click(".chips a")
    page.wait_for_load_state("networkidle")
    assert "f." not in page.url and rows(page) == "6"
    page.select_option("select[name='f.region']", "South")
    page.click("form.filters button")
    page.wait_for_load_state("networkidle")
    page.click("text=Clear filters")
    page.wait_for_load_state("networkidle")
    assert "f." not in page.url and rows(page) == "6"
    assert external == [] and errors == []


def test_charts_fetch_uses_page_query(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv") + "?f.region=South")
    page.wait_for_selector('[data-kind="line"] .plot svg.main-svg')
    assert page.locator('[data-kind="line"] .plot .scatterlayer .point, [data-kind="line"] .plot path.js-line').count() >= 1
    assert page.evaluate("fetch('/api/datasets/' + location.pathname.split('/')[2] + '/charts' + location.search)"
                         ".then(r => r.json()).then(b => b.charts[0].total)") == 2
    assert external == [] and errors == []


def test_bar_click_sets_then_removes_filter(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    page.wait_for_selector('[data-kind="bar"] .plot svg.main-svg')
    bar_click(page, "South")
    assert query(page) == {"f.region": ["South"]}
    assert page.locator("select[name='f.region']").input_value() == "South" and rows(page) == "2"
    page.wait_for_selector('[data-kind="bar"] .plot svg.main-svg')
    bar_click(page, "South")
    assert "f." not in page.url and rows(page) == "6"
    assert external == [] and errors == []
