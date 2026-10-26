"""One test per item in docs/acceptance.json, named after its id. They drive the app through its HTTP routes;
Playwright is used where only a browser can show the result (drawn charts).

AC-13 names Start-DataOS.ps1; Board gate 161 renamed it Start-DataBoot.ps1, and AC-13 / AC-6 ("Deck.gl") wording is
stale in acceptance.json. These tests follow the gate.

Board gate 162 asked the PM for AC ids for work items G-1..G-7 (docs/ARCHITECTURE.md "Work items without AC ids")
and docs/acceptance.json still has none. Their tests are named test_G_<n> after the work item and must be
renamed to the AC ids once the PM adds them. test_G_thousands is the Board's "thousands separators" item
(gate 161), which has no G number.
"""
import io
import json
import re
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ASSET = re.compile(r'(?:src|href)="([^"]+)"')


def _ids(client):
    return {(d["path"], d["sheet"]): d["id"] for d in client.get("/api/datasets").json()}


def _charts(client, name, sheet=None):
    i = _ids(client)[(name, sheet)]
    return i, client.get(f"/api/datasets/{i}/charts").json()["charts"]


@pytest.fixture
def live(data_dir, make_client):
    """Real uvicorn server on a free port serving data_dir."""
    make_client(data_dir)
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
    server.should_exit = True
    thread.join(10)


def _drawn(base, path, selector):
    """Open a page in Chromium with every off-host request aborted; return (selector count, external, errors)."""
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1280, "height": 900})
        external, errors = [], []

        def route(r):
            if r.request.url.startswith(base):
                r.continue_()
            else:
                external.append(r.request.url)
                r.abort()
        page.route("**/*", route)
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + path)
        page.wait_for_load_state("networkidle")
        if selector:
            page.wait_for_selector(selector, timeout=15000)
        n = page.locator(selector).count() if selector else 0
        b.close()
    return n, external, errors


def test_AC_1(make_client, data_dir):
    client = make_client(data_dir)
    html = client.get("/").text
    ids = _ids(client)
    expected = {("sales.csv", None): (6, 3), ("points.tsv", None): (4, 3), ("sub/records.json", None): (3, 2),
                ("sub/book.xlsx", "Revenue"): (6, 3), ("sub/book.xlsx", "Lookup"): (3, 2),
                ("sub/cities.geojson", None): (4, 3)}
    for (path, sheet), (rows, cols) in expected.items():
        assert (path, sheet) in ids, (path, sheet)
        row = [r for r in html.split("<tr") if f'/datasets/{ids[(path, sheet)]}"' in r]
        assert len(row) == 1, path
        assert path in row[0] and (sheet is None or sheet in row[0])
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row[0], re.S)
        assert str(rows) in " ".join(cells) and str(cols) in " ".join(cells), (path, cells)
    api = {(d["path"], d["sheet"]): d for d in client.get("/api/datasets").json()}
    for key, (rows, cols) in expected.items():
        assert (api[key]["rows"], api[key]["columns"]) == (rows, cols), key
    assert "sub/events.jsonl" in {p for p, _ in ids}


def test_AC_2(make_client, data_dir, tmp_path):
    client = make_client(data_dir)
    i = _ids(client)[("sales.csv", None)]
    r = client.get(f"/api/datasets/{i}/profile")
    assert r.status_code == 200
    got = r.json()
    assert list(got) == ["date", "region", "amount"]
    assert set(got.values()) <= {"geospatial", "temporal", "categorical", "numerical", "other"}
    assert got == {"date": "temporal", "region": "categorical", "amount": "numerical"}
    saved = list((tmp_path / "out").rglob("*.json"))
    assert saved and any(json.loads(f.read_text()) == got for f in saved)


def test_AC_3(make_client, data_dir, tmp_path):
    client = make_client(data_dir)
    ids = _ids(client)
    prof = lambda key: client.get(f"/api/datasets/{ids[key]}/profile").json()
    assert prof(("points.tsv", None)) == {"Latitude": "geospatial", "LON": "geospatial", "value": "numerical"}
    assert prof(("sub/book.xlsx", "Revenue")) == {"month": "temporal", "team": "categorical", "revenue": "numerical"}
    assert prof(("sales.csv", None))["amount"] == "numerical"
    # every geospatial header name, any case; integer and float columns numerical
    d = tmp_path / "geo"
    d.mkdir()
    (d / "g.csv").write_text("lat,Lon,lng,LATITUDE,Longitude,x,f\n1,2,3,4,5,1,1.5\n6,7,8,9,10,2,2.5\n")
    c2 = make_client(d)
    t = c2.get(f"/api/datasets/{c2.get('/api/datasets').json()[0]['id']}/profile").json()
    assert [t[k] for k in ("lat", "Lon", "lng", "LATITUDE", "Longitude")] == ["geospatial"] * 5
    assert t["x"] == t["f"] == "numerical"
    # text: <=50 distinct and <=50% distinct is categorical; otherwise other
    d = tmp_path / "txt"
    d.mkdir()
    rows = [f"{'abc'[i % 3]},u{i}" for i in range(100)]
    (d / "t.csv").write_text("cat,uniq\n" + "\n".join(rows) + "\n")
    c3 = make_client(d)
    t = c3.get(f"/api/datasets/{c3.get('/api/datasets').json()[0]['id']}/profile").json()
    assert t == {"cat": "categorical", "uniq": "other"}
    # more than 50 distinct values but well under 50%: other
    d = tmp_path / "many"
    d.mkdir()
    (d / "m.csv").write_text("k\n" + "\n".join(f"v{i % 60}" for i in range(1000)) + "\n")
    c4 = make_client(d)
    assert c4.get(f"/api/datasets/{c4.get('/api/datasets').json()[0]['id']}/profile").json() == {"k": "other"}


def test_AC_4(make_client, data_dir, live):
    client = make_client(data_dir)
    i, charts = _charts(client, "sales.csv")
    line = [c for c in charts if c["kind"] == "line"]
    assert len(line) == 1
    assert line[0]["data"]["x"][0] == "2024-01-01" and line[0]["data"]["y"] == [10, 20, 5, 7, 3, 1]
    html = client.get(f"/datasets/{i}").text
    assert 'data-kind="line"' in html
    n, external, errors = _drawn(live, f"/datasets/{i}", '[data-kind="line"] .plot .scatterlayer path.js-line')
    assert n == 1 and external == [] and errors == []


def test_AC_5(make_client, data_dir, live):
    client = make_client(data_dir)
    i, charts = _charts(client, "sales.csv")
    bar = [c for c in charts if c["kind"] == "bar"]
    assert len(bar) == 1
    sums = dict(zip(bar[0]["data"]["x"], bar[0]["data"]["y"]))
    assert sums == {"North": 16, "South": 23, "East": 7}  # 10+5+1, 20+3, 7
    assert 'data-kind="bar"' in client.get(f"/datasets/{i}").text
    n, external, errors = _drawn(live, f"/datasets/{i}", '[data-kind="bar"] .plot .barlayer .point')
    assert n == 3 and external == [] and errors == []


def test_AC_6(make_client, data_dir, live):
    client = make_client(data_dir)
    i, charts = _charts(client, "points.tsv")
    maps = [c for c in charts if c["kind"] == "map3d"]
    assert len(maps) == 1 and len(maps[0]["data"]["lat"]) == 4 and len(maps[0]["data"]["lon"]) == 4
    assert 'data-kind="map3d"' in client.get(f"/datasets/{i}").text
    n, external, errors = _drawn(live, f"/datasets/{i}", '[data-kind="map3d"] .plot canvas')
    assert n >= 1 and external == [] and errors == []
    # no lat/lon columns: no map, in the API or on the page
    for name in ("sales.csv", "notes.csv"):
        j, cs = _charts(client, name)
        assert all(c["kind"] != "map3d" for c in cs)
        assert 'data-kind="map3d"' not in client.get(f"/datasets/{j}").text


def test_AC_7(make_client, data_dir):
    client = make_client(data_dir)
    i, charts = _charts(client, "notes.csv")
    assert charts == []
    r = client.get(f"/datasets/{i}")
    assert r.status_code == 200
    assert "<figure" not in r.text and "comment" in r.text and "<caption>Columns</caption>" in r.text
    assert "free text number 0" in r.text
    assert "Chart could not be drawn" not in r.text and "Internal Server Error" not in r.text


def test_AC_8(make_client, data_dir):
    client = make_client(data_dir)
    for d in client.get("/api/datasets").json():
        r = client.get(f"/datasets/{d['id']}")
        assert r.status_code == 200, d["path"]
        html = r.text
        types = client.get(f"/api/datasets/{d['id']}/profile").json()
        cols = html.split("<caption>Columns</caption>")[1].split("</table>")[0]
        for col, kind in types.items():
            assert re.search(rf"<td[^>]*>{re.escape(col)}</td><td><span class=\"badge\">{kind}</span></td>", cols), (d["path"], col)
        body = html.split('class="data-table"')[1].split("<tbody>")[1]
        assert body.count("<tr>") == min(d["rows"], 20), d["path"]
    # more than 20 rows: exactly the first 20
    d = [x for x in client.get("/api/datasets").json() if x["path"] == "notes.csv"][0]
    html = client.get(f"/datasets/{d['id']}").text
    assert "free text number 19" in html and "free text number 20" not in html


def test_AC_9(make_client, data_dir):
    client = make_client(data_dir)
    pages = ["/"] + [f"/datasets/{d['id']}" for d in client.get("/api/datasets").json()]
    assets = set()
    for p in pages:
        r = client.get(p)
        assert r.status_code == 200, p
        for url in ASSET.findall(r.text):
            assert not re.match(r"(https?:)?//", url) and not url.startswith("data:"), (p, url)
            if url.startswith("/") and not url.startswith("/datasets/"):
                assets.add(url)
        assert not re.search(r"url\(\s*['\"]?(https?:)?//", r.text)
    assert any(a.endswith(".css") for a in assets) and any(a.endswith(".js") for a in assets)
    assert any("plotly" in a for a in assets)
    for a in assets:
        assert client.get(a).status_code == 200, a
    # the stylesheet and script must not point off-host either
    for a in assets:
        if a.endswith((".css", ".js")) and "plotly.min" not in a:
            body = client.get(a).text
            assert not re.search(r"https?://(?!127\.0\.0\.1|localhost)", body), a


def test_AC_10(make_client, big_csv):
    client = make_client(big_csv)
    i, charts = _charts(client, "big.csv")
    m = [c for c in charts if c["kind"] == "map3d"][0]
    cap = 50_000
    assert len(m["data"]["lat"]) == len(m["data"]["lon"]) <= cap
    assert m["shown"] == len(m["data"]["lat"]) and m["total"] == 60_000
    html = client.get(f"/datasets/{i}").text
    assert f"{m['shown']:,} of 60,000 points" in html


def test_AC_11(data_dir, monkeypatch):
    from app import launch
    monkeypatch.setenv("DATABOOT_DATA", "")
    urls = []
    got = threading.Event()

    def fake_open(url):
        urls.append(url)
        got.set()

    t = threading.Thread(target=launch.run, args=(data_dir, 8765, fake_open))
    t.start()
    try:
        assert got.wait(15)
        assert re.fullmatch(r"http://(127\.0\.0\.1|localhost):\d+/", urls[0]), urls
        with urllib.request.urlopen(urls[0]) as r:
            html = r.read().decode()
        assert r.status == 200 and "DataBoot" in html and "sales.csv" in html
    finally:
        deadline = time.time() + 5
        while launch.SERVER is None and time.time() < deadline:
            time.sleep(0.05)
        launch.SERVER.should_exit = True
        t.join(10)
    assert not t.is_alive() and len(urls) == 1


def test_AC_12(make_client, data_dir):
    client = make_client(data_dir)
    r = client.get("/")
    assert r.status_code == 200
    unread = r.text.split("<caption>Could not be read</caption>")[1].split("</table>")[0]
    assert "empty.csv" in unread and "broken.xlsx" in unread
    assert "could not be read" in r.text.lower() or "Could not be read" in r.text
    paths = {d["path"] for d in client.get("/api/datasets").json()}
    assert "empty.csv" not in paths and "broken.xlsx" not in paths
    assert {"sales.csv", "points.tsv", "sub/records.json"} <= paths
    for d in client.get("/api/datasets").json():
        assert client.get(f"/datasets/{d['id']}").status_code == 200, d["path"]


def test_AC_13():
    # Start-DataOS.ps1 was renamed Start-DataBoot.ps1 by Board gate 161.
    assert not (ROOT / ("Start-Data" + "OS.ps1")).exists()
    ps1 = (ROOT / "Start-DataBoot.ps1").read_text()
    for needle in ("docker info", 'docker run --rm -d -p 8765:8765', '-v "${Folder}:/data:ro"', "Start-Process http://localhost:8765/"):
        assert needle in ps1, needle
    assert ps1.index("docker info") < ps1.index("docker run") < ps1.index("Start-Process http://localhost:8765/")
    assert re.search(r"docker info.*\n?.*exit 1", ps1, re.S)
    docker = (ROOT / "Dockerfile").read_text()
    assert docker.startswith("FROM ") and "uvicorn" in docker and "app.main:app" in docker


# ---- Work items G-1..G-7 (gates 160-162), no AC ids yet ----

def _dir_with_parquet(data_dir):
    import shutil
    for f in (ROOT / "tests/fixtures").glob("*.parquet"):
        shutil.copy(f, data_dir / f.name)
    shutil.copy(ROOT / "tests/fixtures/flat.csv", data_dir / "flat.csv")
    return data_dir


def _rows_of(html, caption):
    """Text of each <td> row of the table with this caption."""
    table = re.search(rf"<caption>{caption}</caption>.*?</table>", html, re.S).group(0)
    return [re.sub(r"<[^>]+>", " ", r).split() for r in re.findall(r"<tr>(.*?)</tr>", table, re.S) if "<td" in r]


def test_G_1(make_client, data_dir):
    """File types: TSV, JSON, JSONL, GeoJSON and Parquet are listed with row and column counts."""
    client = make_client(_dir_with_parquet(data_dir))
    got = {d["path"]: (d["rows"], d["columns"]) for d in client.get("/api/datasets").json()}
    assert got["points.tsv"] == (4, 3)
    assert got["sub/records.json"] == (3, 2)
    assert got["sub/events.jsonl"] == (10, 2)
    assert got["sub/cities.geojson"] == (4, 3)
    parquets = [n for n in got if n.endswith(".parquet")]
    assert len(parquets) == 8  # every fixture except zstd.parquet, which G-7 covers
    home = client.get("/").text
    for name in parquets:
        assert got[name] == (40, 6) and name in home
    # a Parquet file gives the same profile and the same charts as its CSV twin
    ids = _ids(client)
    for name in ("plain", "gzip", "snappy", "dict", "int96", "groups"):
        a, b = ids[(f"{name}.parquet", None)], ids[("flat.csv", None)]
        assert client.get(f"/api/datasets/{a}/profile").json() == client.get(f"/api/datasets/{b}/profile").json()
        ca = [(c["kind"], c["data"]) for c in client.get(f"/api/datasets/{a}/charts").json()["charts"]]
        cb = [(c["kind"], c["data"]) for c in client.get(f"/api/datasets/{b}/charts").json()["charts"]]
        assert ca == cb and ca
        assert client.get(f"/datasets/{a}").status_code == 200


def test_G_2(make_client, data_dir):
    """File inventory: unrecognised files are listed with type, size and date, and have no dashboard."""
    (data_dir / "old.xls").write_bytes(b"xx")
    client = make_client(data_dir)
    home = client.get("/").text
    rows = _rows_of(home, "Other files")
    by_name = {r[0]: r for r in rows}
    assert by_name["manual.pdf"][1:3] == ["pdf", "9"]
    assert by_name["old.xls"][1:3] == ["xls", "2"]
    today = time.strftime("%Y-%m-%d", time.localtime((data_dir / "manual.pdf").stat().st_mtime))
    assert by_name["manual.pdf"][3] == today
    assert ".hidden.csv" not in home
    assert not any(d["path"] in ("manual.pdf", "old.xls") for d in client.get("/api/datasets").json())
    other = re.search(r"<caption>Other files</caption>.*?</table>", home, re.S).group(0)
    assert "<a " not in other


def test_G_3(make_client, data_dir):
    """Extra charts: donut, histogram, scatter, correlation heatmap and country map, max 8 per dataset."""
    (data_dir / "num.csv").write_text("a,b,c\n" + "".join(f"{i},{(i * 7) % 11},{2 * i + 1}\n" for i in range(12)))
    (data_dir / "many.csv").write_text("date,region,country,lat,lon,a,b,c\n" + "".join(
        f"2024-01-{i + 1:02d},{'NSEW'[i % 4]},{['France', 'Japan', 'Brazil'][i % 3]},{i * 3 - 20},{i * 5 - 30},{i},{(i * 7) % 11},{i * i}\n"
        for i in range(12)))
    client = make_client(data_dir)
    _, ev = _charts(client, "sub/events.jsonl")
    donut = next(c for c in ev if c["kind"] == "donut")
    assert dict(zip(donut["data"]["labels"], donut["data"]["values"])) == {"a": 5, "b": 5}
    hist = next(c for c in ev if c["kind"] == "histogram")
    assert sum(hist["data"]["counts"]) == 10 and len(hist["data"]["edges"]) == len(hist["data"]["counts"]) + 1
    assert hist["data"]["edges"][0] == 0 and hist["data"]["edges"][-1] == 9
    _, num = _charts(client, "num.csv")
    scatter = next(c for c in num if c["kind"] == "scatter")
    assert scatter["data"]["x"] == [float(i) for i in range(12)] and len(scatter["data"]["y"]) == 12
    heat = next(c for c in num if c["kind"] == "heatmap")
    z = heat["data"]["z"]
    assert heat["data"]["labels"] == ["a", "b", "c"] and [z[i][i] for i in range(3)] == [1, 1, 1]
    assert abs(z[0][2] - 1) < 1e-9 and abs(z[0][1] - z[1][0]) < 1e-12  # c = 2a + 1; symmetric
    _, rec = _charts(client, "sub/records.json")
    cmap = next(c for c in rec if c["kind"] == "country_map")
    assert dict(zip(cmap["data"]["locations"], cmap["data"]["values"])) == {"France": 68, "Japan": 125, "Brazil": 203}
    assert cmap["data"]["locationmode"] == "country names"
    i, many = _charts(client, "many.csv")
    assert 1 < len(many) <= 8
    assert client.get(f"/datasets/{i}").text.count("<figure") == len(many)


def test_G_4(make_client, data_dir):
    """Caption and text: one rule caption and one 'N of M' per figure; no other prose in <main>."""
    client = make_client(data_dir)
    for d in client.get("/api/datasets").json():
        if d["rows"] == 0:
            continue
        html = client.get(f"/datasets/{d['id']}").text
        charts = client.get(f"/api/datasets/{d['id']}/charts").json()["charts"]
        figs = re.findall(r"<figure.*?</figure>", html, re.S)
        assert len(figs) == len(charts), d["path"]
        for fig, c in zip(figs, charts):
            assert len(re.findall(r'class="chart-rule"', fig)) == 1
            assert c["rule"] in fig
            counts = re.findall(r'class="chart-count">([^<]*)<', fig)
            assert len(counts) == 1 and re.fullmatch(r"[\d,]+ of [\d,]+ (points|rows)", counts[0]), counts
        main = re.search(r"<main.*?</main>", html, re.S).group(0)
        main = re.sub(r"<figcaption.*?</figcaption>", "", main, flags=re.S)
        assert [p for p in re.findall(r"<p[ >].*", main) if "path" not in p and "folder" not in p.lower()] == [], d["path"]


def test_G_5(make_client, data_dir):
    """Exports: XLSX reopens in openpyxl and PPTX in python-pptx, each with native charts (count > 0)."""
    from openpyxl import load_workbook
    from pptx import Presentation
    (data_dir / "num.csv").write_text("a,b,c\n" + "".join(f"{i},{(i * 7) % 11},{2 * i + 1}\n" for i in range(12)))
    client = make_client(data_dir)
    ids = _ids(client)
    for name in ("sales.csv", "num.csv", "points.tsv"):
        i = ids[(name, None)]
        charts = client.get(f"/api/datasets/{i}/charts").json()["charts"]
        assert charts, name
        r = client.get(f"/datasets/{i}/export.xlsx")
        assert r.status_code == 200 and r.headers["content-type"].endswith("spreadsheetml.sheet"), name
        assert "attachment" in r.headers["content-disposition"] and name.rsplit(".", 1)[0] + ".xlsx" in r.headers["content-disposition"]
        wb = load_workbook(io.BytesIO(r.content))
        assert wb.sheetnames[0] == "Data" and len(wb.sheetnames) > 1, name
        assert [c.value for c in wb["Data"][1]] == list(client.get(f"/api/datasets/{i}/profile").json())
        assert sum(len(ws._charts) for ws in wb.worksheets) > 0, name
        r = client.get(f"/datasets/{i}/export.pptx")
        assert r.status_code == 200 and r.headers["content-type"].endswith("presentationml.presentation"), name
        prs = Presentation(io.BytesIO(r.content))
        assert len(prs.slides) == 1 + len(charts), name
        n = sum(1 for s in prs.slides for sh in s.shapes if sh.has_chart)
        assert n > 0, name


def test_G_6(make_client, data_dir):
    """Name: the product is called DataBoot in every page title and h1 where the page has no dataset name."""
    client = make_client(data_dir)
    home = client.get("/").text
    assert re.search(r"<title>DataBoot</title>", home) and re.search(r"<h1[^>]*>\s*DataBoot\s*</h1>", home)
    for d in client.get("/api/datasets").json():
        html = client.get(f"/datasets/{d['id']}").text
        assert re.search(r"<title>[^<]* - DataBoot</title>", html), d["path"]
    assert not re.search(r"DataOS", home + client.get(f"/datasets/{d['id']}").text, re.I)


def test_G_7(make_client, data_dir):
    """Parquet errors: a file the reader cannot decode is listed as unreadable with its reason, and others still open."""
    good = (ROOT / "tests/fixtures/plain.parquet").read_bytes()
    (data_dir / "bad.parquet").write_bytes(good[:4] + b"\x00" * 64 + good[-8:])  # magic and footer length, no real footer
    client = make_client(data_dir)
    home = client.get("/").text
    row = re.search(r"<tr><td[^>]*>bad\.parquet</td>.*?</tr>", home, re.S).group(0)
    assert "note-error" in row  # the reason text is ARCHITECTURE.md "Data access"
    assert ("bad.parquet", None) not in _ids(client)
    assert client.get("/").status_code == 200 and "sales.csv" in home
    assert client.get(f"/datasets/{_ids(client)[('sales.csv', None)]}").status_code == 200


def test_G_thousands(make_client, data_dir, big_csv):
    """Thousands separators on counts everywhere (1,234 of 56,789), including bytes and point counts."""
    client = make_client(big_csv)
    home = client.get("/").text
    row = _rows_of(home, "Datasets")[0]
    assert "60,000" in row and "60000" not in "".join(row)
    i = _ids(client)[("big.csv", None)]
    page = client.get(f"/datasets/{i}").text
    shown = next(c for c in client.get(f"/api/datasets/{i}/charts").json()["charts"] if c["kind"] == "map3d")["shown"]
    assert shown >= 1000 and f"{shown:,} of 60,000 points" in page
    text = re.sub(r"<[^>]+>", " ", re.search(r"<main.*?</main>", page, re.S).group(0))
    assert not re.search(r"(?<![\d.,-])\d{4,}(?![\d-])", re.sub(r"\d{4}-\d{2}-\d{2}", "", text)), "unseparated number in page text"
