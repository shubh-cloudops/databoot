"""Keyboard chart marks (K7; AC-85): bars and donut slices are Tab stops with a focus ring; Enter and Space filter like a click."""
import pytest

from tests.test_browser import base, dataset_path, open_page  # noqa: F401  (fixtures)
from tests.test_business_page import _id, browser, open_, query, serve, settle, wide  # noqa: F401  (fixtures)

MARK = 'path[role=button][tabindex="0"]'



def reach(page, scope):
    """Tab from the top of the page until a mark inside `scope` has focus; returns its aria-label."""
    page.evaluate("document.activeElement.blur(); window.scrollTo(0, 0)")
    for _ in range(150):
        page.keyboard.press("Tab")
        label = page.evaluate("""s => { const a = document.activeElement;
            return a && a.matches('path[role=button]') && a.closest(s) ? a.getAttribute('aria-label') : null; }""", scope)
        if label:
            return label
    raise AssertionError("Tab never reached a mark in " + scope)


def navigate(page, key):
    with page.expect_navigation():
        page.keyboard.press(key)
    page.wait_for_load_state("networkidle")


def check(page, scope, drills=False):
    """Tab to a mark, see its ring, Enter filters; on the filtered page Space on the same mark removes the filter
    (a drilling leaderboard shows the next column there, so Space adds that column's filter instead)."""
    column, category = reach(page, scope).split(": ", 1)
    width, style = page.evaluate("(() => { const s = getComputedStyle(document.activeElement); return [parseFloat(s.outlineWidth), s.outlineStyle]; })()")
    assert width == 3 and style == "solid"
    navigate(page, "Enter")
    assert query(page)["f." + column] == [category]
    settle(page)
    if drills:
        column2, category2 = reach(page, scope).split(": ", 1)
        navigate(page, "Space")
        assert query(page)["f." + column2] == [category2] and column2 != column
        return
    page.evaluate("""l => [...document.querySelectorAll('path[role=button]')].find(p => p.getAttribute('aria-label') === l).focus()""",
                  f"{column}: {category}")
    navigate(page, "Space")
    assert "f." + column not in query(page)


def test_explorer_bars_and_donut(base, open_page):
    page, external, errors = open_page(dataset_path(base, "sales.csv"))
    page.wait_for_selector('[data-kind="bar"] .plot svg.main-svg')
    page.wait_for_selector('[data-kind="donut"] .plot svg.main-svg')
    assert page.locator('[data-kind="bar"] path[role=button]').count() == 3
    check(page, '[data-kind="bar"]')
    page.wait_for_selector('[data-kind="donut"] .slice path[role=button]')
    check(page, '[data-kind="donut"]')
    assert errors == []


def test_business_leaderboard(archetypes_dir, make_client, browser):
    make_client(archetypes_dir)
    with serve() as b:
        page = open_(browser, f"{b}/datasets/{_id(b, 'shop.csv')}")
        check(page, "[data-leaderboard]", drills=True)
        assert page.errors == []


def test_last_level_bars_and_other_bar_have_no_stop(archetypes_dir, make_client, browser):
    make_client(archetypes_dir)
    with serve() as b:
        page = open_(browser, f"{b}/datasets/{_id(b, 'shop.csv')}?f.channel=web&f.store=North")
        assert page.locator("[data-drill=false] .barlayer .point path").count() > 0
        assert page.locator("[data-leaderboard] path[role=button], [data-leaderboard] path[tabindex]").count() == 0


def test_other_bar_has_no_stop(wide, browser):
    base, i = wide
    page = open_(browser, f"{base}/datasets/{i}")
    assert page.locator("[data-leaderboard] .barlayer .point path").count() == 11
    assert page.locator("[data-leaderboard] path[role=button]").count() == 10
    assert page.locator("[data-leaderboard] .barlayer .trace:nth-child(2) path[tabindex]").count() == 0


def test_survey_question_bars(round6_dir, make_client, browser):
    make_client(round6_dir)
    with serve() as b:
        page = open_(browser, f"{b}/datasets/{_id(b, 'survey.csv')}")
        check(page, '.questions [data-kind="bar"]')
        assert page.errors == []


def test_map_top_regions_are_not_clickable_so_have_no_stop(archetypes_dir, make_client, browser):
    """Gate 179: the Map top-regions bar has drill false (no click, no pointer), so it gets no keyboard stop either."""
    make_client(archetypes_dir)
    with serve() as b:
        page = open_(browser, f"{b}/datasets/{_id(b, 'places.csv')}")
        assert page.locator(".map-panel .barlayer .point path").count() == 4
        assert page.locator(".map-panel path[role=button], .map-panel path[tabindex]").count() == 0
        assert page.errors == []
