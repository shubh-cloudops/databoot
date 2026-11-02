"""Tile reorder (I7a; AC-81, AC-86) and expand, glow, entrance (I7b; AC-82, AC-84): pointer drag, Alt+Arrow on the move handle,
per-dataset order store, native expand dialog with reopen after a filter, pointer glow, entrance under 0.6 s, reduced motion and transparency."""
import json
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_business_page import _id, browser, open_, serve  # noqa: F401
from tests.test_survey_page import base  # noqa: F401


def order(page):
    return page.evaluate("[...document.querySelectorAll('.grid > .ws-tile')].map(t => t.dataset.tile)")


def test_drag_keyboard_reload_and_other_dataset(base, browser):
    survey, monitor = (f"{base}/datasets/{_id(base, n)}" for n in ("survey.csv", "monitor.csv"))
    page = open_(browser, survey)
    first = order(page)
    assert len(first) >= 3
    reqs = []
    page.on("request", lambda r: reqs.append(r.url) if not r.url.startswith(base) else None)
    key = page.evaluate("[document.querySelector('.grid').dataset.dataset, document.querySelector('.grid').dataset.app]")
    assert page.evaluate("getComputedStyle(document.querySelector('.ws-move')).touchAction") == "none"

    # drag from tile 3's title (its figcaption, or the header) onto tile 1
    src = page.locator(".grid > .ws-tile").nth(2).locator("figcaption .chart-title, .ws-head h2").first
    page.locator(".grid > .ws-tile").nth(0).scroll_into_view_if_needed()
    src.drag_to(page.locator(".grid > .ws-tile").nth(0))
    moved = [first[2], first[0], first[1], *first[3:]]
    assert order(page) == moved
    assert json.loads(page.evaluate("k => localStorage.getItem(k)", f"databoot.order.{key[0]}.{key[1]}")) == moved

    page.reload()
    page.wait_for_load_state("networkidle")
    assert order(page) == moved
    assert [e.get_attribute("data-tile") for e in page.query_selector_all("[data-tile]")][:3] == moved[:3]

    # another dataset keeps its default order
    other = open_(browser, monitor)
    assert order(other) == order(open_(browser, monitor))
    assert other.evaluate("Object.keys(localStorage).filter(k => k.startsWith('databoot.order.')).length") == 0

    # keyboard: tile 2 first, focus stays, live region speaks
    handle = page.locator(".grid > .ws-tile").nth(1).locator(".ws-move")
    handle.focus()
    page.keyboard.press("Alt+ArrowLeft")
    assert order(page) == [moved[1], moved[0], *moved[2:]]
    assert "position 1 of" in page.inner_text("#ws-live")
    assert page.evaluate("document.activeElement.classList.contains('ws-move')")
    assert page.evaluate("document.activeElement.closest('.ws-tile').dataset.tile") == moved[1]
    page.keyboard.press("Alt+ArrowDown")
    assert order(page) == moved
    assert "position 2 of" in page.inner_text("#ws-live")
    assert not reqs and not page.errors


@pytest.fixture
def sales(data_dir, make_client):
    make_client(data_dir)
    with serve() as b:
        yield f"{b}/datasets/{_id(b, 'sales.csv')}?app=explorer"


CHART = ".grid > .ws-tile[data-tile=chart-3]"  # the bar chart in the sales Explorer


def count(page):
    return page.locator(".chips").count(), page.locator(".kpis dd").first.inner_text()


def is_open(page):
    return page.evaluate("document.querySelector('dialog#tile-dialog').open")


def test_expand_esc_backdrop_and_button(sales, browser):
    page = open_(browser, sales)
    tile, btn = page.locator(CHART), page.locator(f"{CHART} .ws-expand")
    place = page.evaluate("[...document.querySelectorAll('.grid > .ws-tile')].map(t => t.dataset.tile)")
    assert not is_open(page)
    btn.click()
    settle_plots(page)
    assert is_open(page) and page.locator("dialog[open] #chart-3").count() == 1
    assert page.evaluate("document.querySelector('dialog[open] .js-plotly-plot').getBoundingClientRect().width") > 0.8 * 1280
    assert page.evaluate("document.querySelector('dialog[open] .js-plotly-plot').offsetWidth") > 0.8 * 1280
    assert tile.count() == 0  # it lives in the dialog now
    page.keyboard.press("Escape")
    tile.wait_for()  # the close event puts the tile back
    assert not is_open(page) and page.evaluate("[...document.querySelectorAll('.grid > .ws-tile')].map(t => t.dataset.tile)") == place
    assert page.evaluate("document.activeElement.classList.contains('ws-expand') && !!document.activeElement.closest('.grid')")
    settle_plots(page)
    assert page.evaluate("document.querySelector('#chart-3 .js-plotly-plot').offsetWidth") < 0.8 * 1280
    btn.click()
    assert is_open(page)
    page.mouse.click(4, 4)  # the backdrop
    tile.wait_for()
    assert not is_open(page)
    btn.click()
    page.locator("dialog[open] .ws-expand").click()  # the same button closes it
    tile.wait_for()
    assert not is_open(page) and page.evaluate("document.activeElement.classList.contains('ws-expand')")
    assert page.errors == []


def settle_plots(page):
    page.wait_for_function("[...document.querySelectorAll('.js-plotly-plot')].every(p => p.querySelector('svg.main-svg'))")
    page.wait_for_timeout(300)


def test_reopen_after_bar_click_in_overlay(sales, browser):
    page = open_(browser, sales)
    before = count(page)
    page.locator(f"{CHART} .ws-expand").click()
    settle_plots(page)
    with page.expect_navigation():
        page.evaluate("""() => document.querySelector('dialog[open] [data-kind="bar"] .plot')
            .emit('plotly_click', {points: [{x: 'South', label: 'South', data: {}}]})""")
    page.wait_for_load_state("networkidle")
    assert parse_qs(urlparse(page.url).query)["f.region"] == ["South"]
    assert count(page) == (1, "2") and before == (0, "6")
    page.wait_for_selector("dialog[open] #chart-3")
    assert page.evaluate("sessionStorage.getItem('databoot.expand')") is None  # entry deleted on load
    assert page.errors == []


def test_pagehide_stores_key_and_other_dataset_is_ignored(sales, browser):
    page = open_(browser, sales)
    page.locator(f"{CHART} .ws-expand").click()
    ds = page.evaluate("document.querySelector('.grid').dataset.dataset")
    page.evaluate("window.dispatchEvent(new Event('pagehide'))")
    assert page.evaluate("sessionStorage.getItem('databoot.expand')") == f"{ds}:chart-3"
    page.keyboard.press("Escape")
    page.evaluate("sessionStorage.setItem('databoot.expand', 'other:chart-3')")
    page.reload()
    page.wait_for_load_state("networkidle")
    assert not is_open(page) and page.errors == []
    assert page.evaluate("sessionStorage.getItem('databoot.expand')") is None


def test_glow_follows_pointer(sales, browser):
    page = open_(browser, sales)
    assert page.evaluate("document.querySelector('.ws-tile').style.getPropertyValue('--mx')") == ""
    page.locator(CHART).scroll_into_view_if_needed()
    box = page.locator(CHART).bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 30)
    page.mouse.move(box["x"] + 60, box["y"] + 50)
    got = page.evaluate("[...['--mx', '--my']].map(v => document.querySelector('.grid > .ws-tile[data-tile=chart-3]').style.getPropertyValue(v))")
    assert got == ["60px", "50px"]


def test_entrance_finishes_within_600ms(sales, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.add_init_script("""addEventListener('DOMContentLoaded', () => { window.__ends = document.getAnimations()
        .filter(a => a.effect.target && a.effect.target.classList.contains('ws-tile')).map(a => a.effect.getComputedTiming().endTime); })""")
    page.goto(sales)
    ends = page.evaluate("window.__ends")
    assert len(ends) >= 3 and max(ends) <= 600
    page.wait_for_timeout(700)
    assert page.evaluate("document.getAnimations().filter(a => a.effect.target.classList.contains('ws-tile') && a.playState !== 'finished').length") == 0


def test_reduced_motion_no_animation_no_glow(sales, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
    page.goto(sales)
    page.wait_for_load_state("networkidle")
    page.locator(CHART).scroll_into_view_if_needed()
    box = page.locator(CHART).bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 30)
    page.mouse.move(box["x"] + 60, box["y"] + 50)
    assert page.evaluate("document.getAnimations().length") == 0
    assert page.evaluate("document.querySelector('.grid > .ws-tile[data-tile=chart-3]').style.getPropertyValue('--mx')") == ""
    assert page.evaluate("getComputedStyle(document.querySelector('.ws-expand')).transitionDuration") == "0s"


def test_reduced_transparency_no_blur_and_opaque_tile(sales, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(sales)
    page.wait_for_load_state("networkidle")
    assert page.evaluate("getComputedStyle(document.querySelector('.ws-tile')).backdropFilter") != "none"
    page.context.new_cdp_session(page).send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-transparency", "value": "reduce"}]})
    page.locator(f"{CHART} .ws-expand").click()
    assert page.evaluate("[...document.querySelectorAll('*')].filter(e => getComputedStyle(e).backdropFilter !== 'none').length") == 0
    assert page.evaluate("getComputedStyle(document.querySelector('dialog[open]'), '::backdrop').backdropFilter") == "none"
    alpha = page.evaluate("getComputedStyle(document.querySelector('.ws-tile')).backgroundColor")
    assert alpha.startswith("rgb(") or alpha.endswith(", 1)")
