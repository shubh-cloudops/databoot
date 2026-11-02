"""Offline walk (AC-86; Board gate 190): open /, upload files, wait for /scan, open the workspace, drag and expand/close a tile,
toggle a table view and filter inside the overlay; every request goes to the app's own host."""
from urllib.parse import parse_qs, urlparse

from tests.test_browser import base, browser  # noqa: F401  (fixtures)
from tests.test_table_toggle import settle


def test_round7_walk_asks_only_the_app_host(base, browser, tmp_path):
    (tmp_path / "sales.csv").write_text("date,region,channel,amount\n" + "".join(  # business: the leaderboard drills because a second dimension is free
        f"2024-01-{1 + i % 6:02d},{('North', 'South', 'East')[i % 3]},{('web', 'shop')[i % 2]},{10 + i}\n" for i in range(12)))
    (tmp_path / "z_other.csv").write_text("x,y\n1,2\n3,4\n")
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    seen, errors = [], []
    page.on("request", lambda r: seen.append(r.url))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("response", lambda r: r.status >= 400 and errors.append(f"{r.status} {r.url}"))
    page.goto(base + "/")
    page.set_input_files("#pick-files", [str(tmp_path / "sales.csv"), str(tmp_path / "z_other.csv")])
    page.wait_for_url(base + "/scan")
    page.locator("#open-workspace").click()
    page.wait_for_url("**/datasets/**")
    settle(page)
    # drag the third tile onto the first, then expand the bar chart and close it again
    tiles = page.locator(".grid > .ws-tile")
    first = page.evaluate("[...document.querySelectorAll('.grid > .ws-tile')].map(t => t.dataset.tile)")
    tiles.nth(0).scroll_into_view_if_needed()
    tiles.nth(2).locator(".ws-move").drag_to(tiles.nth(0))
    assert page.evaluate("[...document.querySelectorAll('.grid > .ws-tile')].map(t => t.dataset.tile)") != first
    bar = page.locator(".grid > .ws-tile", has=page.locator("[data-kind=bar]")).first
    bar.locator(".ws-expand").click()
    page.wait_for_selector("dialog[open] [data-kind=bar] svg.main-svg")
    fig = page.locator("dialog[open] [data-kind=bar]")
    page.wait_for_timeout(300)  # the plot is drawn; give dashboard.js time to attach its click handler
    fig.locator(".table-toggle").click()
    assert fig.locator("table.plot-table tbody tr").count() > 0 and fig.locator(".plot").is_hidden()
    fig.locator(".table-toggle").click()
    with page.expect_navigation():  # a bar click is the filter; the page reloads and the tile opens again
        page.evaluate("""() => { const p = document.querySelector('dialog[open] [data-kind="bar"] .plot'), t = p.data[0];
            p.emit('plotly_click', {points: [{x: t.x && t.x[0], y: t.y[0], label: t.y[0], data: {orientation: t.orientation}}]}); }""")
    page.wait_for_selector("dialog[open] [data-kind=bar]")
    assert [k for k in parse_qs(urlparse(page.url).query) if k.startswith("f.")]
    page.locator("dialog[open] .ws-expand").click()
    page.wait_for_selector("dialog[open]", state="detached")
    own = urlparse(base).netloc
    assert len(seen) > 10 and [u for u in seen if urlparse(u).netloc != own and not u.startswith(("data:", "blob:"))] == []
    assert errors == []
