"""Global chart rules in the browser (G1 part 2; AC-39, AC-54, AC-55): table toggle on every Explorer figure, one y-axis,
tooltips on, zero baseline for bars, real-click cross-filter on bar and donut. Business and Map have their own tickets."""
from tests.test_browser import base, browser, dataset_path, open_page  # noqa: F401  (fixtures)
from tests.test_filter_browser import query, rows


def settle(page):
    page.wait_for_function("""() => { const p = [...document.querySelectorAll('.plot')];
        return p.length > 0 && p.every(e => e.classList.contains('js-plotly-plot')); }""")
    page.wait_for_selector('[data-kind="bar"] .barlayer .point')


def point_count(trace):
    return len(trace.get("labels") or trace.get("x") or trace.get("lon") or trace.get("locations") or [])


def test_global_rules_and_table_toggle(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    settle(page)
    info = page.evaluate("""() => [...document.querySelectorAll('.js-plotly-plot')].map(gd => ({
        id: gd.closest('figure').id, keys: Object.keys(gd._fullLayout), hover: gd._fullLayout.hovermode,
        sep: gd._fullLayout.separators, hoverinfo: gd.data.map(t => t.hoverinfo || null),
        n: gd.closest('figure').querySelectorAll('.table-toggle').length,
        trace: {labels: gd.data[0].labels, x: gd.data[0].x}}))""")
    assert len(info) == 4
    for i in info:
        assert "yaxis2" not in i["keys"] and i["hover"] is not False and i["sep"] == ".,"
        assert i["n"] == 1 and not set(i["hoverinfo"]) & {"none", "skip"}
    assert page.evaluate("""() => [...document.querySelectorAll('.js-plotly-plot')].every(gd =>
        Object.values(gd._fullLayout).every(a => !(a && typeof a === 'object' && a.overlaying)))""")
    for i in info:
        fig = page.locator("#" + i["id"])
        btn = fig.locator(".table-toggle")
        assert btn.inner_text() == "View as table" and btn.get_attribute("aria-pressed") == "false"
        btn.click()
        assert btn.get_attribute("aria-pressed") == "true" and fig.locator(".plot").is_hidden()
        assert fig.locator(".plot-table-wrap table.plot-table").count() == 1
        assert fig.locator("table.plot-table tbody tr").count() == point_count(i["trace"])
        btn.click()
        assert btn.get_attribute("aria-pressed") == "false" and fig.locator(".plot").is_visible()
        assert fig.locator(".plot-table-wrap").is_hidden()
    assert external == [] and errors == []


def test_table_numbers_have_separators(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    settle(page)
    fig = page.locator('[data-kind="bar"]')
    fig.locator(".table-toggle").click()
    cells = fig.locator("table.plot-table tbody tr td:nth-child(2)").all_inner_texts()
    assert cells and all(c.replace(",", "").replace(".", "").lstrip("-").isdigit() for c in cells)
    assert page.evaluate("document.querySelector('[data-kind=bar] .js-plotly-plot')._fullLayout.yaxis.hoverformat") == ","
    assert errors == []


def test_bar_axis_starts_at_zero_and_is_sorted(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    settle(page)
    got = page.evaluate("""() => { const gd = document.querySelector('[data-kind="bar"] .js-plotly-plot');
        return {range: gd._fullLayout.yaxis.range, mode: gd._fullLayout.yaxis.rangemode, y: gd.data[0].y}; }""")
    assert got["mode"] == "tozero" and got["range"][0] == 0
    assert got["y"] == sorted(got["y"], reverse=True)


def pie_point(page):
    """A point on the ring of the first slice (the bounding box centre of a slice can lie in the hole)."""
    return page.evaluate("""() => { const s = document.querySelector('[data-kind="donut"] .pielayer .slice path');
        s.scrollIntoView({block: 'center'});
        const r = s.getBoundingClientRect();
        for (let a = 0; a < 20; a++) for (let b = 0; b < 20; b++) {
            const x = r.left + r.width * (a + .5) / 20, y = r.top + r.height * (b + .5) / 20;
            if (document.elementsFromPoint(x, y).includes(s)) return [x, y]; } }""")


def test_real_bar_click_sets_then_removes_filter(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    settle(page)
    first = page.evaluate("document.querySelector('[data-kind=bar] .js-plotly-plot').data[0].x[0]")
    with page.expect_navigation():
        page.locator('[data-kind="bar"] .barlayer .point').first.click(force=True)
    assert query(page) == {"f.region": [first], "app": ["explorer"]}
    settle(page)
    assert page.locator("select[name='f.region']").input_value() == first and rows(page) != "6"
    with page.expect_navigation():
        page.locator('[data-kind="bar"] .barlayer .point').first.click(force=True)
    assert "f." not in page.url and rows(page) == "6"
    assert external == [] and errors == []


def test_real_donut_click_filter_removed_by_chip_and_clear(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    settle(page)
    for remove in (lambda: page.click(".chips a"), lambda: page.click("text=Clear filters")):
        page.wait_for_selector('[data-kind="donut"] .pielayer .slice path')
        x, y = pie_point(page)
        with page.expect_navigation():
            page.mouse.click(x, y)
        assert sorted(query(page)) == ["app", "f.region"] and rows(page) != "6"
        settle(page)
        with page.expect_navigation():
            remove()
        assert "f." not in page.url and rows(page) == "6"
        settle(page)
    assert external == [] and errors == []
