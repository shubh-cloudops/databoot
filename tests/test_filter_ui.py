"""Dashboard filter UI: KPI strip, filter form, chips, score captions, export links, grid layout (AC-34..38)."""
import html as htmllib
import re

import pytest

from tests.test_browser import base, browser, dataset_path, open_page  # noqa: F401  (fixtures)
from tests.test_pages import _ids

KPI = re.compile(r"<dt>([^<]*)</dt><dd>([^<]*)</dd>")


def _page(client, name, query="", **kw):
    i = _ids(client)[(name, None)]
    return i, client.get(f"/datasets/{i}?app=explorer{query.replace('?', '&')}").text


def _kpis(html):
    return dict(KPI.findall(html.split('<dl class="kpis">')[1].split("</dl>")[0]))


def test_form_for_categorical_and_temporal(make_client, data_dir):
    client = make_client(data_dir)
    _, h = _page(client, "sales.csv")
    form = h.split('<form class="filters" method="get">')[1].split("</form>")[0]
    assert '<select id="f1" name="f.region">' in form
    assert re.findall(r'<option value="(\w*)">', form) == ["", "East", "North", "South"]
    assert 'type="date" id="from" name="from"' in form and 'type="date" id="to" name="to"' in form
    assert "Apply</button>" in form and "chips-row" not in h
    _, n = _page(client, "notes.csv")
    assert "<form" not in n and "chips-row" not in n


def test_filtered_page_selected_chip_and_kpis(make_client, data_dir):
    client = make_client(data_dir)
    i, h = _page(client, "sales.csv", "?f.region=North")
    assert '<option value="North" selected>' in h
    assert '<a href="/datasets/%s?app=explorer" aria-label="Remove filter region = North">region = North</a>' % i in h
    assert f'<a class="btn" href="/datasets/{i}?app=explorer">Clear filters</a>' in h
    k = _kpis(h)
    assert k["Rows"] == "3" and k["amount (sum)"] == "16" and k["Columns"] == "3" and k["Missing"] == "0.0%"
    assert _kpis(_page(client, "sales.csv")[1])["Rows"] == "6"


def test_chip_removes_only_its_filter(make_client, data_dir):
    client = make_client(data_dir)
    i, h = _page(client, "sales.csv", "?f.region=North&from=2024-01-02")
    assert f'href="/datasets/{i}?from=2024-01-02&amp;app=explorer" aria-label="Remove filter region = North"' in h
    assert f'href="/datasets/{i}?f.region=North&amp;app=explorer" aria-label="Remove filter date from 2024-01-02"' in h
    assert 'name="from" value="2024-01-02"' in h


def test_score_in_caption_matches_api(make_client, data_dir):
    client = make_client(data_dir)
    i, h = _page(client, "sales.csv")
    api = client.get(f"/api/datasets/{i}/charts").json()["charts"]
    rules = re.findall(r'<span class="chart-rule">([^<]*)</span>', h)
    assert len(rules) == len(api) == h.count('class="chart-count"')
    for rule, c in zip(rules, api):
        assert rule.endswith(f" · score {c['score']:.2f}") and rule.startswith(c["rule"])
    last = h.rindex("</figure>")
    assert h.index("<caption><h2>Columns") > last and h.index("<caption><h2>First") > last
    assert "score" not in h.split('class="data-table"')[1]


def test_big_csv_kpi_and_export_links(make_client, big_csv, data_dir):
    client = make_client(big_csv)
    assert _kpis(_page(client, "big.csv")[1])["Rows"] == "60,000"
    client = make_client(data_dir)
    i, h = _page(client, "sales.csv", "?f.region=North")
    assert f'href="/datasets/{i}/export.pptx?f.region=North&amp;app=explorer"' in h and f'href="/datasets/{i}/export.xlsx?f.region=North&amp;app=explorer"' in h
    plain = client.get(f"/datasets/{i}").text  # no app param: round 4 URLs
    assert f'href="/datasets/{i}/export.pptx"' in plain


def test_grid_first_full_width_then_two_per_row(base, open_page):  # noqa: F811
    path = dataset_path(base, "sales.csv")
    page, _, errors = open_page(path, 1280)
    box = lambda s: page.locator(s).bounding_box()  # noqa: E731
    wrap, c1, c2, c3 = box(".charts"), box("#chart-1"), box("#chart-2"), box("#chart-3")
    assert c1["width"] > 0.95 * wrap["width"]
    assert abs(c2["y"] - c3["y"]) < 2 and c2["y"] > c1["y"]
    assert all(0.4 * wrap["width"] < c["width"] < 0.55 * wrap["width"] for c in (c2, c3))
    page, _, errors2 = open_page(path, 390)
    wrap = page.locator(".charts").bounding_box()
    for n in range(1, page.locator("figure.chart").count() + 1):
        assert page.locator(f"#chart-{n}").bounding_box()["width"] > 0.95 * wrap["width"]
    assert not errors and not errors2
