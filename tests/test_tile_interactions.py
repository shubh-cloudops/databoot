"""Tile reorder (I7a; AC-81, AC-86): pointer drag, Alt+Arrow on the move handle, per-dataset order store."""
import json

from tests.test_business_page import _id, browser, open_  # noqa: F401
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
