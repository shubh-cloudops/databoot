"""Offline check for the new apps (N1; AC-58): a full walk through the Business page (shop.csv) and the Map page
(places.csv) asks no host but the test server and gets no failed or 4xx/5xx local response."""
from urllib.parse import urlparse

from tests.test_business_page import (_id, browser, click_bar_to_navigate, crumbs, serve, settle, shop)  # noqa: F401  (fixtures)
from tests.test_map_page import click_point, details, places  # noqa: F401  (fixtures)


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
