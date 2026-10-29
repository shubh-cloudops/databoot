"""Monitoring page (MO2; AC-54, 65, 66, 67; Board gates 183, 184): period links, tiles with sparkline, the main line with
7-point mean and spike label, the cap note. monitor.csv: 120 days from 2024-01-01, one spike on 2024-04-10."""
import csv
import json
import re
import urllib.request

import pytest

from tests.test_business_page import _id, browser, open_, query, serve, settle  # noqa: F401


@pytest.fixture
def base(round6_dir, make_client):
    make_client(round6_dir)
    with serve() as b:
        yield b


def url(base, name, qs=""):
    return f"{base}/datasets/{_id(base, name)}{qs}"


def tiles(page):
    return {t.locator(".card-label").inner_text(): t for t in page.locator("ul.tiles > li.card.tile").all()}


def change(tile):
    return " ".join(tile.locator(".card-change").inner_text().split())


def test_periods_nav_default_and_hrefs(base):
    html = urllib.request.urlopen(url(base, "monitor.csv", "?from=2024-02-01&app=monitoring")).read().decode()
    nav = re.search(r'<nav class="periods" aria-label="Period">.*?</nav>', html, re.S).group(0)
    links = re.findall(r'<a href="([^"]*)"( aria-current="page")?>([^<]*)</a>', nav)
    assert [x[2] for x in links] == ["7 days", "30 days", "90 days", "All"]
    assert [bool(x[1]) for x in links] == [False, True, False, False]
    for (href, _, _), p in zip(links, ["7", "30", "90", "all"]):
        assert "from=2024-02-01" in href and "app=monitoring" in href and href.endswith(f"period={p}")
    # the filter form carries the picked period as a hidden input
    form = urllib.request.urlopen(url(base, "monitor.csv", "?period=90")).read().decode()
    assert re.search(r'<form class="filters".*?<input type="hidden" name="period" value="90">', form, re.S)


def test_period_bad_shows_30_and_seven_shows_range(base, browser):
    page = open_(browser, url(base, "monitor.csv", "?period=bad"))
    assert page.locator(".periods a[aria-current=page]").inner_text() == "30 days"
    page = open_(browser, url(base, "monitor.csv", "?period=7"))
    assert page.locator(".periods a[aria-current=page]").inner_text() == "7 days"
    # last 7 days of the series: i = 113..119, temperature 20 + i % 7 -> 20..26; humidity 50 + i % 5 -> 50..54
    t = tiles(page)["temperature"]
    assert t.locator(".tile-range").inner_text().split() == ["Min", "20", "Max", "26"]
    assert t.locator(".card-period").inner_text() == "latest 2024-04-29"
    assert page.errors == []


@pytest.mark.parametrize("width", [1280, 375])
def test_tiles_values_arrows_and_sparklines(base, browser, width):
    page = open_(browser, url(base, "monitor.csv"), width)
    t = tiles(page)
    assert list(t) == ["temperature", "humidity"]
    assert change(t["temperature"]) == "▲ +5.1% up"
    assert change(t["humidity"]) == "▶ 0.0% no change"
    assert t["temperature"].locator("svg.spark polyline").count() == 1 and t["temperature"].locator("svg.spark title").count() == 1
    assert t["temperature"].locator(".card-value").inner_text() == "20"  # latest reading, i = 119 -> 20 + 0
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth") and page.errors == []
    quiet = open_(browser, url(base, "quiet.csv"), width)
    assert change(tiles(quiet)["temperature"]) == "▼ -0.4% down"


def test_all_is_na_without_arrow(base, browser):
    page = open_(browser, url(base, "monitor.csv", "?period=all"))
    for t in tiles(page).values():
        assert t.locator(".card-change").inner_text() == "n/a" and t.locator(".card-change.na").count() == 1
        assert not set(t.inner_text()) & set("▲▼▶")
    assert page.errors == []


def test_period_click_url_back_and_reopen(base, browser):
    page = open_(browser, url(base, "monitor.csv"))
    page.get_by_role("link", name="90 days").click()
    page.wait_for_url(re.compile("period=90"))
    settle(page)
    assert query(page)["period"] == ["90"] and page.locator(".periods a[aria-current=page]").inner_text() == "90 days"
    page.go_back()
    settle(page)
    assert "period" not in query(page) and page.locator(".periods a[aria-current=page]").inner_text() == "30 days"
    again = open_(browser, url(base, "monitor.csv", "?period=90"))
    assert again.locator(".periods a[aria-current=page]").inner_text() == "90 days"


def plot_data(page):
    return page.evaluate("""() => { const g = document.querySelector('.js-plotly-plot');
        return {traces: g.data.map(t => ({name: t.name, mode: t.mode, dash: t.line && t.line.dash, yaxis: t.yaxis || 'y', text: t.text || null,
          pos: t.textposition || null})), legend: g.layout.showlegend, y2: !!g.layout.yaxis2,
          spikes: [...g.querySelectorAll('.textpoint text')].map(e => e.textContent)}; }""")


def test_main_line_traces_one_spike_and_quiet_none(base, browser):
    page = open_(browser, url(base, "monitor.csv", "?period=all"))
    d = plot_data(page)
    assert [t["name"] for t in d["traces"]] == ["temperature", "7-point mean", "spike"]
    assert d["traces"][1]["dash"] == "dash" and d["traces"][2]["mode"] == "markers+text" and d["traces"][2]["pos"] == "top center"
    assert {t["yaxis"] for t in d["traces"]} == {"y"} and d["legend"] and not d["y2"]
    assert d["spikes"] == ["spike"]
    assert page.errors == []
    q = plot_data(open_(browser, url(base, "quiet.csv", "?period=all")))
    assert [t["name"] for t in q["traces"]] == ["temperature", "7-point mean"] and q["spikes"] == []


def test_view_table_lists_time_value_mean_and_spike(base, browser):
    page = open_(browser, url(base, "monitor.csv", "?period=all"))
    page.get_by_role("button", name="View as table").click()
    head = page.locator(".plot-table thead th").all_inner_texts()
    assert head == ["time", "temperature", "7-point mean", "Spike"]
    rows = page.locator(".plot-table tbody tr")
    assert rows.count() == 120 and rows.nth(0).locator("td").all_inner_texts() == ["2024-01-01", "20", "20", ""]
    assert page.locator(".plot-table td", has_text="spike").count() == 1
    assert page.locator(".plot-table tbody tr", has_text="spike").locator("td").first.inner_text() == "2024-04-10"


def test_cap_note_and_layout_without_note(tmp_path, make_client, browser):
    folder = tmp_path / "wide"
    folder.mkdir()
    with open(folder / "wide.csv", "w", newline="") as f:
        csv.writer(f).writerows([("time", *[f"m{k}" for k in range(10)]),
                                 *[((f"2024-01-{i + 1:02d}"), *[i + k for k in range(10)]) for i in range(30)]])
    make_client(folder)
    with serve() as b:
        page = open_(browser, url(b, "wide.csv"))
        assert page.locator("ul.tiles > li.tile").count() == 8
        assert page.locator(".note").inner_text() == "8 of 10 measures"
        assert page.errors == []


def test_no_note_with_few_measures(base, browser):
    assert open_(browser, url(base, "monitor.csv")).locator(".note").count() == 0
