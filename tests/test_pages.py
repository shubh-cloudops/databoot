"""Server-rendered pages: home tables, dashboards, figures, captions and thousands separators."""
import re

from app import catalog, config

FIGURE = re.compile(r'<figure class="chart" id="(chart-\d+)" data-kind="(\w+)"')


def _ids(client):
    return {(d["path"], d["sheet"]): d["id"] for d in client.get("/api/datasets").json()}


def _main(html):
    return html.split("<main", 1)[1].split("</main>", 1)[0]


def test_home_tables(make_client, data_dir):
    client = make_client(data_dir)
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    assert "<title>DataBoot</title>" in html and "<h1>DataBoot</h1>" in html and str(data_dir) in html
    ids = _ids(client)
    assert f'href="/datasets/{ids[("sales.csv", None)]}"' in html
    assert f'href="/datasets/{ids[("sub/book.xlsx", "Revenue")]}"' in html
    for caption in ("Datasets", "Could not be read", "Other files"):
        assert f"<caption>{caption}</caption>" in html
    assert "empty.csv" in html and "broken.xlsx" in html and "empty file" in html
    assert "manual.pdf" in html and 'href="/datasets/' not in html.split("manual.pdf")[1].split("</tr>")[0]
    assert "<td>pdf</td>" in html and ".hidden" not in html
    # no <p> in main except the folder path
    assert re.findall(r"<p[ >]", _main(html)) == ["<p "]


def test_home_empty_tables_are_hidden(make_client, tmp_path):
    html = make_client(tmp_path / "missing").get("/").text
    assert "<table" not in html and "<h1>DataBoot</h1>" in html and str(tmp_path / "missing") in html


def test_every_dashboard_has_types_and_at_most_20_rows(make_client, data_dir):
    client = make_client(data_dir)
    for d in catalog.scan(config.get().data).datasets:
        r = client.get(f"/datasets/{d.id}")
        assert r.status_code == 200, d.path
        html = r.text
        assert f"<h1>{d.path}" in html and "<caption>Columns</caption>" in html and "badge" in html
        assert f"/datasets/{d.id}/export.pptx" in html and f"/datasets/{d.id}/export.xlsx" in html
        rows = html.split('class="data-table"')[1].split("<tbody>")[1].count("<tr>")
        assert 1 <= rows <= 20
        assert not re.findall(r"<p[ >]", _main(html))
    assert client.get("/datasets/nope").status_code == 404


def test_sheet_in_heading_and_figure_captions(make_client, data_dir):
    client = make_client(data_dir)
    ids = _ids(client)
    html = client.get(f'/datasets/{ids[("sub/book.xlsx", "Lookup")]}').text
    assert '<span class="muted">Lookup</span>' in html
    html = client.get(f'/datasets/{ids[("sales.csv", None)]}').text
    api = client.get(f'/api/datasets/{ids[("sales.csv", None)]}/charts').json()["charts"]
    figs = FIGURE.findall(html)
    assert figs == [(c["id"], c["kind"]) for c in api] and {"line", "bar"} <= {k for _, k in figs}
    assert "6 of 6 points" in html and "6 of 6 rows" in html and html.count("<figcaption>") == len(api)
    for c in api:
        assert f'<span class="chart-title">{c["title"]}</span>' in html and c["rule"] in html


def test_no_rule_dataset_has_no_figure(make_client, data_dir):
    client = make_client(data_dir)
    r = client.get(f'/datasets/{_ids(client)[("notes.csv", None)]}')
    assert r.status_code == 200 and "<figure" not in r.text and "comment" in r.text
    assert "categorical" in r.text or "other" in r.text


def test_big_csv_counts_have_separators(make_client, big_csv):
    client = make_client(big_csv)
    assert "<td class=\"num\">60,000</td>" in client.get("/").text
    i = _ids(client)[("big.csv", None)]
    html = client.get(f"/datasets/{i}").text
    shown = client.get(f"/api/datasets/{i}/charts").json()["charts"][0]["shown"]
    assert 0 < shown <= 50_000 and f"{shown:,} of 60,000 points" in html and "60,000 of 60,000 rows" in html
    assert html.split('class="data-table"')[1].split("<tbody>")[1].count("<tr>") == 20
