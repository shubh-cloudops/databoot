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
        assert f"<caption><h2>{caption}</h2></caption>" in html
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
        r = client.get(f"/datasets/{d.id}?app=explorer")
        assert r.status_code == 200, d.path
        html = r.text
        assert f"<h1>{d.path}" in html and "<caption><h2>Columns</h2></caption>" in html and "badge" in html
        assert f"/datasets/{d.id}/export.pptx" in html and f"/datasets/{d.id}/export.xlsx" in html
        rows = html.split('class="data-table"')[1].split("<tbody>")[1].count("<tr>")
        assert 1 <= rows <= 20
        assert re.search(r"<caption><h2>First [\d,]+ rows?</h2></caption>", html)
        assert not re.findall(r"<p[ >]", _main(html))
    assert client.get("/datasets/nope").status_code == 404


def test_sheet_in_heading_and_figure_captions(make_client, data_dir):
    client = make_client(data_dir)
    ids = _ids(client)
    html = client.get(f'/datasets/{ids[("sub/book.xlsx", "Lookup")]}').text
    assert '<span class="muted">Lookup</span>' in html
    html = client.get(f'/datasets/{ids[("sales.csv", None)]}?app=explorer').text
    api = client.get(f'/api/datasets/{ids[("sales.csv", None)]}/charts').json()["charts"]
    figs = FIGURE.findall(html)
    assert figs == [(c["id"], c["kind"]) for c in api] and {"line", "bar"} <= {k for _, k in figs}
    assert "6 of 6 points" in html and "6 of 6 rows" in html and html.count("<figcaption>") == len(api)
    for c in api:
        assert f'<span class="chart-title">{c["title"]}</span>' in html and f'{c["rule"]} · score {c["score"]:.2f}</span>' in html


def test_no_rule_dataset_has_no_figure(make_client, data_dir):
    client = make_client(data_dir)
    r = client.get(f'/datasets/{_ids(client)[("notes.csv", None)]}')
    assert r.status_code == 200 and "<figure" not in r.text and "comment" in r.text
    assert "categorical" in r.text or "other" in r.text


def test_big_csv_counts_have_separators(make_client, big_csv):
    client = make_client(big_csv)
    assert "<td class=\"num\">60,000</td>" in client.get("/").text
    i = _ids(client)[("big.csv", None)]
    html = client.get(f"/datasets/{i}?app=explorer").text
    shown = next(c for c in client.get(f"/api/datasets/{i}/charts").json()["charts"] if c["kind"] == "map3d")["shown"]
    assert 0 < shown <= 50_000 and f"{shown:,} of 60,000 points" in html and "60,000 of 60,000 rows" in html
    assert html.split('class="data-table"')[1].split("<tbody>")[1].count("<tr>") == 20


def test_headers_keep_their_case():
    assert "uppercase" not in (config.ROOT / "app/static/css/databoot.css").read_text(encoding="utf-8")


def test_orders_first_rows_keep_ids_and_years_plain(make_client, round6_dir):
    client = make_client(round6_dir)
    html = client.get(f"/datasets/{_ids(client)[('orders.csv', None)]}?app=explorer").text
    cells = html.split('class="data-table"')[1].split("<tbody>")[1]
    assert "<td>10045</td>" in cells and "<td>2024</td>" in cells and "<td>12,345</td>" in cells
    assert "2,024" not in html and "10,045" not in html


def test_counts_are_singular_at_one(make_client, tmp_path):
    from app.main import templates
    (tmp_path / "one.csv").write_text("a,b\n1,2\n")
    client = make_client(tmp_path)
    html = client.get(f"/datasets/{_ids(client)[('one.csv', None)]}?app=explorer").text
    assert "<h2>First 1 row</h2>" in html and not re.search(r"\b1 (points|rows)\b", html)
    fig = templates.get_template("_figure.html").module.figure
    count = lambda kind, shown, total: re.search(r'chart-count">([^<]*)<', fig(dict(id="c", kind=kind, title="t", rule="r", shown=shown, total=total))).group(1)
    assert count("bar", 1, 1) == "1 of 1 row" and count("line", 1, 1) == "1 of 1 point"
    assert count("bar", 0, 5) == "0 of 5 rows" and count("monitor", 0, 5) == "0 of 5 points" and count("scatter", 2, 5) == "2 of 5 points"
