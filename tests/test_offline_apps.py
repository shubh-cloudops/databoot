"""Offline check for the new apps (N1; AC-9, AC-58): a full walk through the Business page (shop.csv), the Map page
(places.csv), the Monitoring page (monitor.csv) and the Survey page (survey.csv) asks no host but the test server and gets no failed or 4xx/5xx local response."""
from urllib.parse import urlparse

from tests.test_business_page import (_id, browser, click_bar_to_navigate, crumbs, serve, settle, shop)  # noqa: F401  (fixtures)
from tests.test_map_page import click_point, details, places  # noqa: F401  (fixtures)
from tests.test_monitoring_page import base as r6_base  # noqa: F401  (fixture; monitor.csv, survey.csv)


def watch(page):
    """Route every request: count the off-host ones (and block them), let local ones through, note local failures."""
    page.off_host, page.failed, page.local = [], [], []

    def route(r):
        if urlparse(r.request.url).hostname == "127.0.0.1":
            page.local.append(r.request.url)
            return r.continue_()
        page.off_host.append(r.request.url)
        r.abort()
    page.route("**/*", route)
    page.on("requestfailed", lambda r: page.failed.append(r.url))
    page.on("response", lambda r: r.status >= 400 and page.failed.append(f"{r.status} {r.url}"))


def toggle_table(page, kind):
    f = page.locator(f"figure[data-kind={kind}]").first
    f.locator(".table-toggle").click()
    assert f.locator("table.plot-table tbody tr").count() > 0 and f.locator(".plot").is_hidden()
    f.locator(".table-toggle").click()
    assert f.locator(".plot").is_visible()


def test_business_page_walk_asks_no_off_host_url(shop, browser):
    base, i = shop
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    watch(page)
    page.goto(f"{base}/datasets/{i}")
    settle(page)
    click_bar_to_navigate(page, "web")
    click_bar_to_navigate(page, "North")
    assert crumbs(page) == ["All", "channel: web", "store: North"]
    page.go_back()
    settle(page)
    assert crumbs(page) == ["All", "channel: web"]
    page.click(".view-as >> text=Explorer")
    settle(page)
    assert page.locator(".view-as a[aria-current=page]").inner_text() == "Explorer"
    page.click(".view-as >> text=Business")
    settle(page)
    assert page.locator(".view-as a[aria-current=page]").inner_text() == "Business"
    toggle_table(page, "bar")
    assert len(page.local) > 5 and page.off_host == [] and page.failed == [] and page.errors == []


def test_map_page_walk_asks_no_off_host_url(places, browser):
    base, i = places
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    watch(page)
    page.goto(f"{base}/datasets/{i}")
    settle(page)
    click_point(page, 3)
    assert details(page)["pop"] == "4,000"
    btn = page.get_by_role("button", name="3D view")
    btn.click()
    page.wait_for_selector("figure[data-kind=map3d] .plot canvas")
    btn.click()
    page.wait_for_function("document.querySelector('figure[data-kind=map2d] .plot').getBoundingClientRect().width > 100")
    toggle_table(page, "map2d")
    assert len(page.local) > 5 and page.off_host == [] and page.failed == [] and page.errors == []


def walk_page(browser, url):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.errors = []
    page.on("console", lambda m: m.type == "error" and page.errors.append(m.text))
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    watch(page)
    page.goto(url)
    settle(page)
    return page


def clean(page):
    assert len(page.local) > 5 and page.off_host == [] and page.failed == [] and page.errors == []


def test_monitoring_page_walk_asks_no_off_host_url(r6_base, browser):
    page = walk_page(browser, f"{r6_base}/datasets/{_id(r6_base, 'monitor.csv')}")
    with page.expect_navigation():
        page.click(".periods >> text=7 days")
    settle(page)
    assert page.locator(".periods a[aria-current=page]").inner_text() == "7 days"
    toggle_table(page, "monitor")
    page.locator("figure[data-kind=monitor] .plot").scroll_into_view_if_needed()
    c = page.evaluate("""() => { const p = document.querySelector('figure[data-kind=monitor] .scatterlayer .trace .points path, figure[data-kind=monitor] .scatterlayer .trace .js-line');
        const r = p.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; }""")
    page.mouse.move(c["x"] - 3, c["y"])
    page.mouse.move(c["x"], c["y"])
    page.wait_for_selector("figure[data-kind=monitor] .hovertext")
    clean(page)


def test_survey_page_walk_asks_no_off_host_url(r6_base, browser):
    page = walk_page(browser, f"{r6_base}/datasets/{_id(r6_base, 'survey.csv')}")
    page.get_by_label("Column question").select_option("q_easy")
    page.wait_for_url("**col=q_easy*")
    settle(page)
    assert page.get_by_label("Column question").input_value() == "q_easy"
    toggle_table(page, "crosstab")
    page.locator("#chart-3 .plot").scroll_into_view_if_needed()
    c = page.evaluate("""() => { const r = document.querySelector('#chart-3 .barlayer .point').getBoundingClientRect();
        return {x: r.x + r.width / 2, y: r.y + r.height / 2}; }""")
    with page.expect_navigation():
        page.mouse.click(c["x"], c["y"])
    settle(page)
    assert "f.city=" in page.url
    clean(page)
