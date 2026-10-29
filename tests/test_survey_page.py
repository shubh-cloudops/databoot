"""Survey page (SU2; AC-54, 68, 69, 70): question grid, Likert bars, cross-tab form and heatmap, Respondents. survey.csv: 40 rows."""
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


def url(base, qs=""):
    return f"{base}/datasets/{_id(base, 'survey.csv')}{qs}"


def html(base, qs=""):
    return urllib.request.urlopen(url(base, qs)).read().decode()


def test_server_html_order_form_and_no_prose(base):
    h = html(base)
    order = [h.index(x) for x in ('<form class="filters"', '<div class="questions">', "<h2>Cross-tab</h2>", '<form class="crosstab"',
                                  "<h2>Respondents</h2>", "<h2>Columns</h2>", "<h2>First")]
    assert order == sorted(order)
    grid = re.search(r'<div class="questions">(.*?)\n</div>', h, re.S).group(1)
    kinds = re.findall(r'data-kind="(\w+)"', grid)
    assert kinds == ["bar", "bar", "bar", "likert", "likert", "likert", "likert"]  # gender, region, city, q_service..q_score
    form = re.search(r'<form class="crosstab".*?</form>', h, re.S).group(0)
    assert re.findall(r'<label for="[^"]*">([^<]*)</label>', form) == ["Row question", "Column question"]
    assert re.findall(r'name="(row|col)"', form) == ["row", "col"] and 'type="submit">Apply' in form
    assert len(re.findall(r'<option value="[^"]*"', form)) == 14 and re.findall(r'<option value="(\w+)" selected', form) == ["gender", "region"]
    assert not re.search(r"· score \d", h)


def test_pick_in_page_and_hidden_filters(base):
    h = html(base, "?row=q_easy&col=gender&f.region=East&app=survey")
    form = re.search(r'<form class="crosstab".*?</form>', h, re.S).group(0)
    assert re.findall(r'<option value="(\w+)" selected', form) == ["q_easy", "gender"]
    assert '<input type="hidden" name="f.region" value="East">' in form and '<input type="hidden" name="app" value="survey">' in form
    bad = re.search(r'<form class="crosstab".*?</form>', html(base, "?row=nope&col=gender"), re.S).group(0)
    assert re.findall(r'<option value="(\w+)" selected', bad) == ["gender", "region"]


def tops(page):
    return page.evaluate("[...document.querySelectorAll('.questions figure.chart')].map(f => [f.id, Math.round(f.getBoundingClientRect().top + scrollY)])")


def test_grid_two_per_row_at_1280_and_one_at_375(base, browser):
    page = open_(browser, url(base))
    t = tops(page)
    assert t[0][1] == t[1][1] and t[2][1] > t[0][1] and t[3][1] == t[2][1]  # gender+region share a top, city+q_service next
    assert page.locator(".questions > .chart").count() == 8  # 7 questions + the age histogram in its own grid
    assert page.locator("section.block h2", has_text="Respondents").count() == 1
    assert page.locator("section.block:has(h2:text-is('Respondents')) figure[data-kind=histogram]").count() == 1
    assert page.errors == []
    phone = open_(browser, url(base), 375)
    ys = [y for _, y in tops(phone)]
    assert ys == sorted(set(ys)) and phone.evaluate("document.documentElement.scrollWidth <= innerWidth") and phone.errors == []
    heights = phone.evaluate("[...document.querySelectorAll('.questions .chart[data-leaderboard] .plot')].map(p => p.offsetHeight)")
    assert set(heights) == {280}


def test_bar_cursor_and_other_stays_no_pointer(base, browser):
    page = open_(browser, url(base))
    page.locator("#chart-3 .plot").scroll_into_view_if_needed()
    pos = lambda label: page.evaluate("""l => { const gd = document.querySelector('#chart-3 .js-plotly-plot');
        for (let t = 0; t < gd.data.length; t++) { const i = gd.data[t].y.indexOf(l);
          if (i >= 0) { const r = gd.querySelectorAll('.barlayer .trace')[t].querySelectorAll('.point')[i].getBoundingClientRect();
            return {x: r.x + r.width / 2, y: r.y + r.height / 2}; } } }""", label)
    cursor = lambda: page.evaluate("getComputedStyle(document.querySelector('#chart-3 .nsewdrag')).cursor")
    p = pos("Other")
    page.mouse.move(p["x"], p["y"])
    page.wait_for_timeout(300)
    assert page.locator("#chart-3.no-pointer").count() == 1 and cursor() == "default"
    p = pos("city00")
    page.mouse.move(p["x"], p["y"])
    page.wait_for_timeout(300)
    assert page.locator("#chart-3.bar-click").count() == 1 and cursor() == "pointer"
    with page.expect_navigation():
        page.mouse.click(p["x"], p["y"])
    assert query(page)["f.city"] == ["city00"]


def hue(c):
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return None
    d = mx - mn
    h = ((g - b) / d % 6 if mx == r else (b - r) / d + 2 if mx == g else (r - g) / d + 4) * 60
    return h


def test_likert_stacked_bar_levels_colours_and_hover(base, browser):
    page = open_(browser, url(base))
    d = page.evaluate("""() => { const gd = document.querySelector('#chart-4 .js-plotly-plot'), css = getComputedStyle(document.documentElement);
        return {layout: [gd.layout.barmode, gd._fullLayout.xaxis.range, gd._fullLayout.xaxis.ticksuffix, Object.keys(gd._fullLayout).filter(k => /^yaxis\\d/.test(k))],
          traces: gd.data.map(t => [t.name, t.x[0], t.customdata[0], t.marker.color, t.hovertemplate]),
          mid: css.getPropertyValue('--div-mid').trim(), neg: css.getPropertyValue('--div-neg').trim(), pos: css.getPropertyValue('--div-pos').trim()}; }""")
    assert d["layout"] == ["stack", [0, 100], "%", []]
    assert [t[0] for t in d["traces"]] == ["Very dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very satisfied"]
    assert [t[2] for t in d["traces"]] == [6, 6, 6, 16, 6]  # hand values, ARCHITECTURE "Round 6: Survey app"
    assert abs(sum(t[1] for t in d["traces"]) - 100) < 1e-9
    assert d["traces"][2][3] == d["mid"] and d["traces"][0][3] == d["neg"] and d["traces"][4][3] == d["pos"]
    assert abs(hue(d["neg"]) - hue(d["pos"])) > 60 and "%{fullData.name}: %{customdata} (%{x:.1f}%)" in d["traces"][0][4]
    page.locator("#chart-4 .plot").scroll_into_view_if_needed()
    box = page.locator("#chart-4 .barlayer .point").nth(3).bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_selector("#chart-4 .hovertext")
    assert page.locator("#chart-4 .hovertext").first.text_content().replace("\xa0", " ").startswith("Satisfied: 16 (40.0%)")
    # a filter that empties levels keeps every level's trace
    f = open_(browser, url(base, "?f.gender=female"))
    assert f.evaluate("document.querySelector('#chart-4 .js-plotly-plot').data.length") == 5


def crosstab(page):
    return page.evaluate("""() => { const gd = document.querySelector('figure[data-kind=crosstab] .js-plotly-plot'), t = gd.data[0];
        return {n: gd.data.length, type: t.type, text: t.text, tt: t.texttemplate, bar: gd._fullData[0].colorbar.title.text,
          scale: t.colorscale, y2: !!gd._fullLayout.yaxis2, text_shown: [...gd.querySelectorAll('.heatmaplayer .textpoint, .heatmaplayer text')].map(e => e.textContent)}; }""")


def test_crosstab_default_text_one_hue_colour_bar(base, browser):
    page = open_(browser, url(base))
    d = crosstab(page)
    assert d["n"] == 1 and d["type"] == "heatmap" and d["tt"] == "%{text}" and d["bar"] == "count" and not d["y2"]
    assert d["text"][0] == ["3 (21.4%)", "4 (28.6%)", "3 (21.4%)", "4 (28.6%)"]  # female x (East, North, South, West)
    assert "3 (21.4%)" in d["text_shown"] and all(re.fullmatch(r"\d+ \(\d+\.\d%\)", s) for s in d["text_shown"])
    assert len(d["scale"]) == 2 and page.errors == []


def test_crosstab_select_change_submits_pick_in_url(base, browser):
    page = open_(browser, url(base))
    page.get_by_label("Column question").select_option("q_easy")
    page.wait_for_url(re.compile("col=q_easy"))
    settle(page)
    assert query(page)["col"] == ["q_easy"] and query(page)["row"] == ["gender"]
    assert page.get_by_label("Column question").input_value() == "q_easy"
    d = crosstab(page)
    assert all(re.fullmatch(r"\d+ \(\d+\.\d%\)", s) for s in d["text_shown"]) and page.errors == []
    pair = open_(browser, url(base, "?row=q_easy&col=gender"))
    assert pair.get_by_label("Row question").input_value() == "q_easy" and pair.get_by_label("Column question").input_value() == "gender"
    assert crosstab(pair)["text"][0][0] == "3 (37.5%)"
    bad = open_(browser, url(base, "?row=zz&col=yy"))
    assert bad.get_by_label("Row question").input_value() == "gender"


def test_apply_button_works_without_js(base, browser):
    ctx = browser.new_context(java_script_enabled=False)
    page = ctx.new_page()
    page.goto(url(base, "?f.region=East"))
    page.get_by_label("Column question").select_option("q_easy")
    page.get_by_role("button", name="Apply").last.click()
    q = query(page)
    assert q["col"] == ["q_easy"] and q["row"] == ["gender"] and q["f.region"] == ["East"]
    ctx.close()


@pytest.mark.parametrize("width", [1280, 375])
def test_every_figure_one_y_axis_tooltip_and_table_toggle(base, browser, width):
    page = open_(browser, url(base), width)
    n = page.locator("figure.chart").count()
    assert n == 9
    info = page.evaluate("""() => [...document.querySelectorAll('.js-plotly-plot')].map(g => ({
        axes: Object.keys(g._fullLayout).filter(k => /^yaxis\\d+$/.test(k)).length, over: Object.keys(g._fullLayout).filter(k => /axis/.test(k) && g._fullLayout[k] && g._fullLayout[k].overlaying).length,
        hover: g._fullLayout.hovermode !== false && g._fullData.every(t => t.hoverinfo !== 'none' && t.hoverinfo !== 'skip'), points: g._fullData.reduce((s, t) => s + (t.type === 'heatmap' ? t.z.length * t.z[0].length : (t.y || []).length), 0)}))""")
    assert len(info) == n and all(i["axes"] == 0 and i["over"] == 0 and i["hover"] for i in info)
    for i in range(n):
        fig = page.locator("figure.chart").nth(i)
        fig.scroll_into_view_if_needed()
        fig.get_by_role("button", name="View as table").click()
        assert fig.locator("table.plot-table tbody tr").count() == info[i]["points"]
        fig.get_by_role("button", name="View as table").click()
        assert fig.locator("table.plot-table").count() == 1 and fig.locator(".plot").is_visible()
    assert page.errors == []


def test_respondents_absent_without_numbers_and_crosstab_scrolls_on_phone(base, browser):
    page = open_(browser, url(base), 375)
    assert page.evaluate("(() => { const f = document.querySelector('figure[data-kind=crosstab]'); return f.scrollWidth >= f.clientWidth; })()")
    assert page.evaluate("document.querySelector('figure[data-kind=crosstab] .js-plotly-plot')._fullData[0].colorbar.orientation") == "h"
    assert "<h2>Respondents</h2>" in html(base)
