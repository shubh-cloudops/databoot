"""One test per item in docs/acceptance.json, named after its id. They drive the app through its HTTP routes;
Playwright is used where only a browser can show the result (drawn charts).

Board gate 165 gave the work items G-1..G-7 and the thousands-separator item the ids AC-14..AC-21; AC-13 and
AC-6 were reworded in acceptance.json (Start-DataBoot.ps1, Plotly 3D scatter).
"""
import io
import json
import re
import threading
import time
import urllib.request
from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse
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
    html = client.get(f"/datasets/{i}?app=explorer").text
    assert 'data-kind="line"' in html
    n, external, errors = _drawn(live, f"/datasets/{i}?app=explorer", '[data-kind="line"] .plot .scatterlayer path.js-line')
    assert n == 1 and external == [] and errors == []


def test_AC_5(make_client, data_dir, live):
    client = make_client(data_dir)
    i, charts = _charts(client, "sales.csv")
    bar = [c for c in charts if c["kind"] == "bar"]
    assert len(bar) == 1
    sums = dict(zip(bar[0]["data"]["x"], bar[0]["data"]["y"]))
    assert sums == {"North": 16, "South": 23, "East": 7}  # 10+5+1, 20+3, 7
    assert 'data-kind="bar"' in client.get(f"/datasets/{i}?app=explorer").text
    n, external, errors = _drawn(live, f"/datasets/{i}?app=explorer", '[data-kind="bar"] .plot .barlayer .point')
    assert n == 3 and external == [] and errors == []


def test_AC_6(make_client, data_dir, live):
    client = make_client(data_dir)
    i, charts = _charts(client, "points.tsv")
    maps = [c for c in charts if c["kind"] == "map3d"]
    assert len(maps) == 1 and len(maps[0]["data"]["lat"]) == 4 and len(maps[0]["data"]["lon"]) == 4
    assert 'data-kind="map3d"' in client.get(f"/datasets/{i}?app=explorer").text
    n, external, errors = _drawn(live, f"/datasets/{i}?app=explorer", '[data-kind="map3d"] .plot canvas')
    assert n >= 1 and external == [] and errors == []
    # no lat/lon columns: no map, in the API or on the page
    for name in ("sales.csv", "notes.csv"):
        j, cs = _charts(client, name)
        assert all(c["kind"] != "map3d" for c in cs)
        assert 'data-kind="map3d"' not in client.get(f"/datasets/{j}?app=explorer").text


def test_AC_7(make_client, data_dir):
    client = make_client(data_dir)
    i, charts = _charts(client, "notes.csv")
    assert charts == []
    r = client.get(f"/datasets/{i}?app=explorer")
    assert r.status_code == 200
    assert "<figure" not in r.text and "comment" in r.text and "<caption><h2>Columns</h2></caption>" in r.text
    assert "free text number 0" in r.text
    assert "Chart could not be drawn" not in r.text and "Internal Server Error" not in r.text


def test_AC_8(make_client, data_dir):
    client = make_client(data_dir)
    for d in client.get("/api/datasets").json():
        r = client.get(f"/datasets/{d['id']}?app=explorer")
        assert r.status_code == 200, d["path"]
        html = r.text
        types = client.get(f"/api/datasets/{d['id']}/profile").json()
        cols = html.split("<caption><h2>Columns</h2></caption>")[1].split("</table>")[0]
        for col, kind in types.items():
            assert re.search(rf"<td[^>]*>{re.escape(col)}</td><td><span class=\"badge\">{kind}</span></td>", cols), (d["path"], col)
        body = html.split('class="data-table"')[1].split("<tbody>")[1]
        assert body.count("<tr>") == min(d["rows"], 20), d["path"]
    # more than 20 rows: exactly the first 20
    d = [x for x in client.get("/api/datasets").json() if x["path"] == "notes.csv"][0]
    html = client.get(f"/datasets/{d['id']}?app=explorer").text
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
    html = client.get(f"/datasets/{i}?app=explorer").text
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
    unread = r.text.split("<caption><h2>Could not be read</h2></caption>")[1].split("</table>")[0]
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
    table = re.search(rf"<caption><h2>{caption}</h2></caption>.*?</table>", html, re.S).group(0)
    return [re.sub(r"<[^>]+>", " ", r).split() for r in re.findall(r"<tr>(.*?)</tr>", table, re.S) if "<td" in r]


def test_AC_14(make_client, data_dir):
    """File types: TSV, JSON, JSONL, GeoJSON and Parquet are listed with row and column counts."""
    client = make_client(_dir_with_parquet(data_dir))
    got = {d["path"]: (d["rows"], d["columns"]) for d in client.get("/api/datasets").json()}
    assert got["points.tsv"] == (4, 3)
    assert got["sub/records.json"] == (3, 2)
    assert got["sub/events.jsonl"] == (10, 2)
    assert got["sub/cities.geojson"] == (4, 3)
    parquets = [n for n in got if n.endswith(".parquet")]
    assert len(parquets) == 9  # every fixture, zstd.parquet too
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


def test_AC_15(make_client, data_dir):
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
    other = re.search(r"<caption><h2>Other files</h2></caption>.*?</table>", home, re.S).group(0)
    assert "<a " not in other


def test_AC_16(make_client, data_dir):
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
    assert client.get(f"/datasets/{i}?app=explorer").text.count("<figure") == len(many)


def test_AC_17(make_client, data_dir):
    """Caption and text: one rule caption and one 'N of M' per figure; no other prose in <main>."""
    client = make_client(data_dir)
    for d in client.get("/api/datasets").json():
        if d["rows"] == 0:
            continue
        html = client.get(f"/datasets/{d['id']}?app=explorer").text
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


def test_AC_18(make_client, data_dir):
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
        r = client.get(f"/datasets/{i}/export.xlsx?app=explorer")
        assert r.status_code == 200 and r.headers["content-type"].endswith("spreadsheetml.sheet"), name
        assert "attachment" in r.headers["content-disposition"] and name.rsplit(".", 1)[0] + ".xlsx" in r.headers["content-disposition"]
        wb = load_workbook(io.BytesIO(r.content))
        assert wb.sheetnames[0] == "Data" and len(wb.sheetnames) > 1, name
        assert [c.value for c in wb["Data"][1]] == list(client.get(f"/api/datasets/{i}/profile").json())
        assert sum(len(ws._charts) for ws in wb.worksheets) > 0, name
        r = client.get(f"/datasets/{i}/export.pptx?app=explorer")
        assert r.status_code == 200 and r.headers["content-type"].endswith("presentationml.presentation"), name
        prs = Presentation(io.BytesIO(r.content))
        assert len(prs.slides) == 1 + len(charts), name
        n = sum(1 for s in prs.slides for sh in s.shapes if sh.has_chart)
        assert n > 0, name


def test_AC_19(make_client, data_dir):
    """Name: the product is called DataBoot in every page title and h1 where the page has no dataset name."""
    client = make_client(data_dir)
    home = client.get("/").text
    assert re.search(r"<title>DataBoot</title>", home) and re.search(r"<h1[^>]*>\s*DataBoot\s*</h1>", home)
    for d in client.get("/api/datasets").json():
        html = client.get(f"/datasets/{d['id']}?app=explorer").text
        assert re.search(r"<title>[^<]* - DataBoot</title>", html), d["path"]
    assert not re.search(r"DataOS", home + client.get(f"/datasets/{d['id']}?app=explorer").text, re.I)


def test_AC_20(make_client, data_dir):
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


def test_AC_21(make_client, data_dir, big_csv):
    """Thousands separators on counts everywhere (1,234 of 56,789), including bytes and point counts."""
    client = make_client(big_csv)
    home = client.get("/").text
    row = _rows_of(home, "Datasets")[0]
    assert "60,000" in row and "60000" not in "".join(row)
    i = _ids(client)[("big.csv", None)]
    page = client.get(f"/datasets/{i}?app=explorer").text
    shown = next(c for c in client.get(f"/api/datasets/{i}/charts").json()["charts"] if c["kind"] == "map3d")["shown"]
    assert shown >= 1000 and f"{shown:,} of 60,000 points" in page
    text = re.sub(r"<[^>]+>", " ", re.search(r"<main.*?</main>", page, re.S).group(0))
    assert not re.search(r"(?<![\d.,-])\d{4,}(?![\d-])", re.sub(r"\d{4}-\d{2}-\d{2}", "", text)), "unseparated number in page text"


def _page(base, path, width=1280):
    """Open a page in Chromium; return (page, browser context closer). Caller must call close()."""
    p = sync_playwright().start()
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": width, "height": 900})
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + path)
    page.wait_for_load_state("networkidle")
    return page, errors, lambda: (b.close(), p.stop())


def test_AC_22(live, data_dir):
    home_tables = ["Datasets", "Could not be read", "Other files"]
    ids = _ids_http(live)
    page, errors, close = _page(live, "/")
    try:
        caps = page.locator("table > caption > h2").all_inner_texts()
        assert caps == home_tables
        assert page.locator("table > caption:not(:has(> h2))").count() == 0
    finally:
        close()
    page, errors, close = _page(live, "/datasets/" + ids[("points.tsv", None)] + "?app=explorer")
    try:
        caps = page.locator("table > caption > h2").all_inner_texts()
        assert caps == ["Columns", "First 4 rows"]
        # column headers keep the case of the column names ("Latitude", "LON"), as the browser renders them
        heads = page.locator("table th[scope=col]").all_inner_texts()
        assert "Latitude" in heads and "LON" in heads
        assert page.locator("table th").first.evaluate("e => getComputedStyle(e).textTransform") == "none"
    finally:
        close()


def _ids_http(base):
    return {(d["path"], d["sheet"]): d["id"] for d in json.load(urllib.request.urlopen(base + "/api/datasets"))}


def test_AC_23(make_client, data_dir):
    import subprocess
    import warnings
    from openpyxl import load_workbook
    pins = dict(l.strip().split("==") for l in (ROOT / "requirements.txt").read_text().split() if "==" in l)
    assert {k: pins.get(k) for k in ("xlsxwriter", "python-pptx", "openpyxl", "pyarrow")} == {
        "xlsxwriter": "3.3.0", "python-pptx": "1.0.2", "openpyxl": "3.1.5", "pyarrow": "26.0.0"}
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.lower().split("\n")
    for lib in ("xlsxwriter", "openpyxl", "pptx", "pyarrow"):
        assert not [f for f in tracked if f.startswith(lib) or f"/{lib}/" in f or f"site-packages/{lib}" in f], lib
    client = make_client(data_dir)
    i = _ids(client)[("sales.csv", None)]
    r = client.get(f"/datasets/{i}/export.xlsx?app=explorer")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_workbook(io.BytesIO(r.content))
    assert not [w for w in caught if "no default style" in str(w.message)]


def test_AC_24(live):
    ids = _ids_http(live)
    page, errors, close = _page(live, "/datasets/" + ids[("sales.csv", None)] + "?app=explorer")
    try:
        page.wait_for_selector('[data-kind="line"] .plot .modebar-btn')
        bar = page.locator(".modebar").first
        assert bar.evaluate("e => getComputedStyle(e).opacity") == "1"  # no hover has happened
        assert bar.evaluate("e => getComputedStyle(e).visibility") == "visible"
        assert bar.bounding_box()["width"] > 0
        for _ in range(60):
            page.keyboard.press("Tab")
            if page.evaluate("document.activeElement.classList.contains('modebar-btn')"):
                break
        else:
            pytest.fail("Tab never reached a .modebar-btn")
        page.evaluate("window.n = 0; document.activeElement.addEventListener('click', () => window.n++)")
        page.keyboard.press("Enter")
        assert page.evaluate("window.n") == 1
        assert errors == []
    finally:
        close()


def test_AC_25(make_client, data_dir):
    # A sheet with no header row cannot be read; its sibling sheet must still list and open.
    # (A sheet whose XML is truncated makes openpyxl fail the whole workbook: see open_questions.)
    from tests.conftest import write_xlsx
    write_xlsx(data_dir / "book2.xlsx", {"Revenue": [("month", "revenue"), ("a", 1), ("b", 2)], "Lookup": []})
    client = make_client(data_dir)
    home = client.get("/").text
    unread = home.split("<caption><h2>Could not be read</h2></caption>")[1].split("</table>")[0]
    assert re.search(r'<td class="path">book2\.xlsx - Lookup</td>', unread)
    ids = _ids(client)
    assert ("book2.xlsx", "Lookup") not in ids
    assert ("book2.xlsx", "Revenue") in ids and "book2.xlsx" in home
    assert client.get(f"/datasets/{ids[('book2.xlsx', 'Revenue')]}").status_code == 200
    assert client.get(f"/api/datasets/{ids[('book2.xlsx', 'Revenue')]}/charts").json()["charts"]


def test_AC_26(make_client, data_dir):
    (data_dir / "bad.json").write_text("{not json")
    (data_dir / "bad.jsonl").write_text('{"a": 1}\nnope\n')
    (data_dir / "obj.json").write_text('{"a": 1}')
    client = make_client(data_dir)
    unread = client.get("/").text.split("<caption><h2>Could not be read</h2></caption>")[1].split("</table>")[0]
    rows = {r[0]: " ".join(r[1:]) for r in (re.sub(r"<[^>]+>", " ", x).split() for x in re.findall(r"<tr>(.*?)</tr>", unread, re.S) if "<td" in x)}
    assert rows["bad.json"] == "invalid JSON"
    assert rows["bad.jsonl"] == "invalid JSON"
    assert rows["obj.json"] == "not a list of records"
    assert not {"bad.json", "bad.jsonl", "obj.json"} & {d["path"] for d in client.get("/api/datasets").json()}


def test_AC_27(live, data_dir):
    ids = _ids_http(live)
    charts = json.load(urllib.request.urlopen(f"{live}/api/datasets/{ids[('sub/records.json', None)]}/charts"))["charts"]
    cmap = next(c for c in charts if c["kind"] == "country_map")
    assert cmap["data"]["values"] == sorted(cmap["data"]["values"], reverse=True) == [203, 125, 68]
    assert cmap["data"]["locations"] == ["Brazil", "Japan", "France"]
    bar = next(c for c in json.load(urllib.request.urlopen(f"{live}/api/datasets/{ids[('sales.csv', None)]}/charts"))["charts"] if c["kind"] == "bar")
    assert bar["data"]["y"] == sorted(bar["data"]["y"], reverse=True)  # same order rule as the bar chart
    page, errors, close = _page(live, "/datasets/" + ids[("points.tsv", None)] + "?app=explorer")
    try:
        page.wait_for_selector('[data-kind="map3d"] .plot canvas')
        got = page.evaluate("""() => { const g = document.querySelector('[data-kind="map3d"] .plot');
          return [g._fullLayout.scene.zaxis.title.text, g._fullData[0].marker.colorbar.title.text]; }""")
        assert got == ["value", "value"]  # the z column of points.tsv
        assert errors == []
    finally:
        close()


def _ps1():
    return (ROOT / "Start-DataBoot.ps1").read_text()


def _candidates(ps1):
    line = next(l for l in ps1.splitlines() if l.strip().startswith("$Candidates ="))
    return re.findall(r'@\("py", "(-3\.\d+)"\)|@\("(python)"\)', line)


def test_AC_28():
    ps1 = _ps1()
    assert [a or b for a, b in _candidates(ps1)] == ["-3.13", "-3.12", "-3.11", "python"]
    # every candidate, python included, goes through the 3.11-3.13 version check
    cond = re.search(r'sys\.exit\(0 if (.+?) else 1\)', ps1).group(1)
    ok = [v for v in range(8, 16) if eval(cond, {"sys": type("S", (), {"version_info": (3, v, 0)})})]
    assert ok == [11, 12, 13]
    loop = ps1[ps1.index("foreach ($c in $Candidates)"):ps1.index("if (-not $py)")]
    assert "-c $Check" in loop and "$py = $c; break" in loop
    # a machine with 3.12 and 3.14 only: 3.13 and 3.11 fail, 3.12 is the first that passes
    installed = {"-3.12": (3, 12), "python": (3, 14)}
    picked = next(k for k in ["-3.13", "-3.12", "-3.11", "python"] if k in installed and 11 <= installed[k][1] <= 13)
    assert picked == "-3.12"
    assert "-m venv .venv" in ps1 and "& $py[0] @rest -m venv .venv" in ps1


def test_AC_29():
    ps1 = _ps1()
    body = ps1[ps1.index("function Fail"):]
    body = body[:body.index("\n}")]
    pos = [body.index(s) for s in ("Write-Host $Message", "Remove-Item -Recurse -Force .venv", "Read-Host", "exit 1")]
    assert pos == sorted(pos)
    assert 'if (-not $py) { Fail "DataBoot needs Python 3.12.' in ps1
    launch = ps1.index(".venv\\Scripts\\python.exe -m app.launch")
    for marker in ("-m venv .venv", "--no-index --find-links wheels -r requirements.txt",
                   "\n        .venv\\Scripts\\python.exe -m pip install -r requirements.txt"):
        assert ps1.index(marker) < launch
        nxt = ps1[ps1.index(marker) + len(marker):].split("\n", 2)[1]  # the line directly after the command
        assert "$LASTEXITCODE -ne 0" in nxt and re.search(r'Fail "[^"]{10,}"', nxt), marker
    assert ps1.count("Fail \"") == 4 and ps1.rindex("Fail ") < launch


def test_AC_30():
    ps1 = _ps1()

    def hardcoded(script):  # the check the AC asks for: fewer than 3.13, 3.12 and 3.11 in the candidate list
        return not all(v in " ".join(a or b for a, b in _candidates(script)) for v in ("-3.13", "-3.12", "-3.11"))

    assert not hardcoded(ps1)
    only311 = re.sub(r'(\$Candidates = ).*', r'\1@(@("py", "-3.11"))', ps1)
    assert hardcoded(only311)
    assert not re.search(r"py -3\.1\d+ -m venv", ps1)


def test_AC_31(make_client, data_dir):
    from tests.conftest import write_xlsx
    rows = [("month", "revenue"), ("a", 1), ("b", 2)]
    for name, bad in (("book.xlsx", b"<<not xml"), ("trunc.xlsx", b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"')):
        write_xlsx(data_dir / name, {"Bad": bad, "Good": rows})  # corrupt sheet first, so it cannot hide behind a good one
    client = make_client(data_dir)
    home = client.get("/").text
    unread = home.split("<caption><h2>Could not be read</h2></caption>")[1].split("</table>")[0]
    ids = _ids(client)
    for name in ("book.xlsx", "trunc.xlsx"):
        row = re.search(rf'<tr>(?:(?!</tr>).)*{name} - Bad(?:(?!</tr>).)*</tr>', unread, re.S)
        assert row and "not a valid xlsx" in row.group(0), name
        assert (name, "Bad") not in ids
        assert (name, "Good") in ids
        page = client.get(f"/datasets/{ids[(name, 'Good')]}")
        assert page.status_code == 200
        assert client.get(f"/api/datasets/{ids[(name, 'Good')]}/charts").json()["charts"]


# ---- Round 4: score, order, layout, KPIs, filters, exports, speed (AC-32..AC-42) ----

STAFF_DEPTS = ("Engineering dept", "Customer support", "Human resources")  # labels > 12 chars -> horizontal bar


def _staff(folder):
    """40 rows; the first categorical column has long labels (horizontal bar, donut); region has 4 short ones."""
    regs = ("North", "South", "East", "West")
    lines = ["department,date,region,amount,hours"] + [
        f"{STAFF_DEPTS[i % 3]},2024-01-{i % 28 + 1:02d},{regs[i % 4]},{i * 3 + 1},{(i * 7) % 13}" for i in range(40)]
    (folder / "staff.csv").write_text("\n".join(lines) + "\n")


def _path(base, name):
    return "/datasets/" + next(d["id"] for d in json.load(urllib.request.urlopen(base + "/api/datasets")) if d["path"] == name) + "?app=explorer"


@contextmanager
def _open(base, path, width=1280):
    """Chromium page on `path` with off-host requests aborted; yields (page, external, errors) once the plots drew."""
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": width, "height": 900})
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
        _settle(page)
        yield page, external, errors
        b.close()


def _settle(page):
    page.wait_for_load_state("networkidle")
    page.wait_for_function("""() => document.querySelectorAll('figure.chart').length ===
        document.querySelectorAll('figure.chart .plot.js-plotly-plot').length && !document.querySelector('.plot.is-loading')""")


def _click_nav(page, fig_kind, mouse_xy=None):
    """Click the first bar (or the given point) of the figure and wait for the reload it causes."""
    with page.expect_navigation():
        if mouse_xy:
            page.mouse.click(*mouse_xy)
        else:
            page.locator(f'[data-kind="{fig_kind}"] .barlayer .point').first.click(force=True)
    _settle(page)


def _kpi(page):
    return {page.locator(".kpis dt").nth(i).inner_text(): page.locator(".kpis dd").nth(i).inner_text()
            for i in range(page.locator(".kpis dt").count())}


def _ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def _pearson(x, y):
    import statistics
    return statistics.correlation(x, y)


def _gini(v):
    n, s = len(v), sum(v)
    return sum(abs(a - b) for a in v for b in v) / (2 * n * s)


def _api(client, i, query=""):
    return client.get(f"/api/datasets/{i}/charts{query}").json()


def test_AC_32(make_client, data_dir):
    import statistics
    (data_dir / "num.csv").write_text("a,b,c\n" + "".join(f"{i},{(i * 7) % 11},{2 * i + 1}\n" for i in range(12)))
    (data_dir / "const.csv").write_text("date,region,amount\n2024-01-01,A,5\n2024-01-02,B,5\n2024-01-03,A,5\n2024-01-04,B,5\n")
    (data_dir / "one.csv").write_text("date,region,amount\n2024-01-01,A,5\n")
    client = make_client(data_dir)
    ids = _ids(client)
    # sales.csv by hand: amounts per date, region totals {South 23, North 16, East 7}, region counts {3, 2, 1}
    amounts = [10, 20, 5, 7, 3, 1]
    kind = {c["kind"]: c for c in _charts(client, "sales.csv")[1]}
    assert all(isinstance(c["score"], float) and 0 <= c["score"] <= 1 for c in kind.values())
    rho = _pearson(_ranks(list(range(6))), _ranks(amounts))  # Spearman = Pearson of the ranks
    assert kind["line"]["score"] == round(abs(rho), 2) == 0.89
    m = statistics.mean(amounts)
    m2 = sum((a - m) ** 2 for a in amounts) / 6
    g1 = sum((a - m) ** 3 for a in amounts) / 6 / m2 ** 1.5
    assert kind["histogram"]["score"] == round(min(1, abs(g1) / 3), 2)
    assert kind["bar"]["score"] == round(_gini([23, 16, 7]), 2) == 0.23
    assert kind["donut"]["score"] == round(_gini([3, 2, 1]), 2) == 0.22
    # scatter = |Pearson r| of its own two columns, heatmap = largest off-diagonal |r|
    cols = {"a": list(range(12)), "b": [(i * 7) % 11 for i in range(12)], "c": [2 * i + 1 for i in range(12)]}
    got = _charts(client, "num.csv")[1]
    scatters = [c for c in got if c["kind"] == "scatter"]
    assert scatters
    for c in scatters:
        assert c["score"] == round(abs(_pearson(cols[c["x_label"]], cols[c["y_label"]])), 2), c["title"]
    (heat,) = [c for c in got if c["kind"] == "heatmap"]
    off = [abs(_pearson(cols[p], cols[q])) for p, q in (("a", "b"), ("a", "c"), ("b", "c"))]
    assert heat["score"] == round(max(off), 2) == 1.0
    # maps are fixed at 0.6
    assert {c["kind"]: c["score"] for c in _charts(client, "points.tsv")[1]}["map3d"] == 0.6
    (country,) = [c for c in _charts(client, "sub/records.json")[1] if c["kind"] == "country_map"]
    assert country["score"] == 0.6
    # constant values and a single value give 0 (the chart is still drawn or absent, never a score above 0)
    const = _charts(client, "const.csv")[1]
    assert const and all(c["score"] == 0 for c in const)
    assert all(c["score"] == 0 for c in _charts(client, "one.csv")[1])


def test_AC_33(make_client, data_dir):
    (data_dir / "geo.csv").write_text("lat,lon,country,v\n51.5,-0.1,FRA,3\n48.8,2.3,JPN,4\n40.7,-74,BRA,9\n")
    _staff(data_dir)
    client = make_client(data_dir)
    order = ["map3d", "country_map", "line", "bar", "donut", "histogram", "scatter", "heatmap"]
    ids = _ids(client)
    tied = False
    for key, i in ids.items():
        first = client.get(f"/api/datasets/{i}/charts").json()
        again = client.get(f"/api/datasets/{i}/charts").json()
        assert first == again, key  # same order and scores on a second load
        cs = first["charts"]
        assert [c["id"] for c in cs] == [f"chart-{n}" for n in range(1, len(cs) + 1)], key
        for a, b in zip(cs, cs[1:]):
            assert a["score"] >= b["score"], key
            if a["score"] == b["score"]:
                tied = True
                if a["kind"] != b["kind"]:
                    assert order.index(a["kind"]) < order.index(b["kind"]), key
        html = client.get(f"/datasets/{i}?app=explorer").text
        assert re.findall(r'<figure class="chart" id="[^"]+" data-kind="([^"]+)"', html) == [c["kind"] for c in cs], key
    assert tied
    geo = [c["kind"] for c in _charts(client, "geo.csv")[1]]
    assert geo[:2] == ["map3d", "country_map"]  # both 0.6: fixed chart order breaks the tie
    staff = _charts(client, "staff.csv")[1]
    assert [c["kind"] for c in staff].count("line") == 2 and staff[0]["kind"] == "line"


def test_AC_34(live):
    path = _path(live, "sales.csv")
    for width in (1280, 375):
        with _open(live, path, width) as (page, external, errors):
            wrap = page.locator(".charts").bounding_box()
            boxes = [page.locator(f"#chart-{n}").bounding_box() for n in range(1, page.locator("figure.chart").count() + 1)]
            assert len(boxes) == 4
            assert boxes[0]["width"] > 0.95 * wrap["width"]
            if width == 1280:
                assert abs(boxes[1]["y"] - boxes[2]["y"]) < 2 and boxes[1]["y"] > boxes[0]["y"]
                assert abs(boxes[2]["y"] - boxes[3]["y"]) > 2 or boxes[3]["x"] != boxes[2]["x"]
                assert all(0.4 * wrap["width"] < b["width"] < 0.55 * wrap["width"] for b in boxes[1:])
            else:
                assert all(b["width"] > 0.95 * wrap["width"] for b in boxes)
                assert all(boxes[k + 1]["y"] > boxes[k]["y"] for k in range(3))
            table = page.locator("table.data-table").bounding_box()
            assert table["y"] > max(b["y"] + b["height"] for b in boxes) - 1
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert external == [] and errors == []
    client_html = urllib.request.urlopen(live + path).read().decode()
    assert client_html.index('class="data-table"') > client_html.rindex("</figure>")


def test_AC_35(live):
    base_charts = {}
    for name in ("sales.csv", "points.tsv"):
        path = _path(live, name)
        api = json.load(urllib.request.urlopen(live + path.split("?")[0].replace("/datasets/", "/api/datasets/") + "/charts"))["charts"]
        with _open(live, path) as (page, external, errors):
            rules = [page.locator(f"#{c['id']} .chart-rule").inner_text() for c in api]
            assert len(rules) == len(api) >= 1
            for text, c in zip(rules, api):
                assert re.search(r" · score \d\.\d\d$", text), text
                assert text.endswith(f" · score {c['score']:.2f}") and text.startswith(c["rule"])
            assert errors == []
    html = urllib.request.urlopen(live + _path(live, "sales.csv")).read().decode()
    assert "· score 0.89" in html


def test_AC_36(make_client, data_dir):
    rows = ["region,n1,n2,n3,n4"] + [
        f"{'AB'[i % 2]},{1000 + i},{2 * i},{i % 7},{'' if i % 10 == 0 else 5}" for i in range(1200)]
    (data_dir / "kpi.csv").write_text("\n".join(rows) + "\n")
    client = make_client(data_dir)
    i = _ids(client)[("kpi.csv", None)]

    def kpis(query=""):
        html = client.get(f"/datasets/{i}{query}").text
        return dict(re.findall(r"<dt>([^<]*)</dt><dd>([^<]*)</dd>", html.split('<dl class="kpis">')[1].split("</dl>")[0]))

    full = kpis()
    assert list(full) == ["Rows", "Columns", "Missing", "n1 (sum)", "n2 (sum)", "n3 (sum)"]  # first 3 numerical only
    assert full == {"Rows": "1,200", "Columns": "5", "Missing": "2.0%",
                    "n1 (sum)": f"{sum(1000 + k for k in range(1200)):,}",
                    "n2 (sum)": f"{sum(2 * k for k in range(1200)):,}", "n3 (sum)": f"{sum(k % 7 for k in range(1200)):,}"}
    rows_a = [k for k in range(1200) if k % 2 == 0]
    a = kpis("?f.region=A")
    assert a["Rows"] == "600" and a["n1 (sum)"] == f"{sum(1000 + k for k in rows_a):,}"
    assert a["n2 (sum)"] == f"{sum(2 * k for k in rows_a):,}" and a["Columns"] == "5"
    assert a["Missing"] == "4.0%"  # every 10th row is even, so all 120 blanks sit in 600 x 5 = 3,000 cells
    assert client.get(f"/api/datasets/{i}/charts?f.region=A").json()["kpis"]["rows"] == 600


def test_AC_37(make_client, data_dir):
    _staff(data_dir)
    client = make_client(data_dir)
    ids = _ids(client)
    i = ids[("staff.csv", None)]
    html = client.get(f"/datasets/{i}?app=explorer").text
    form = html.split('<form class="filters" method="get">')[1].split("</form>")[0]
    assert re.findall(r'<select id="\w+" name="([^"]+)"', form) == ["f.department", "f.region"]  # one per categorical
    assert 'type="date" id="from"' in form and 'type="date" id="to"' in form
    for name in ("points.tsv", "sub/records.json"):  # no categorical or temporal column: no control
        assert "<form" not in client.get(f"/datasets/{ids[(name, None)]}?app=explorer").text
    s = client.get(f"/datasets/{ids[('sales.csv', None)]}?app=explorer").text.split('<form class="filters"')[1]
    assert s.count("<select") == 1 and 'name="from"' in s
    book = client.get(f"/datasets/{ids[('sub/book.xlsx', 'Revenue')]}?app=explorer").text.split('<form class="filters"')[1]
    assert 'name="from"' in book and 'name="f.team"' in book
    base = _api(client, i)
    assert base["kpis"]["rows"] == 40 and base["filters"] == []
    for query, rows in (("?f.region=North", 10), ("?f.department=Customer+support", 13),
                        ("?f.region=North&f.department=Customer+support", None), ("?from=2024-01-10&to=2024-01-12", 6)):  # days 10-12: rows 9-11 and 37-39
        got = _api(client, i, query)
        want = rows if rows is not None else sum(1 for k in range(40) if k % 4 == 0 and k % 3 == 1)
        assert got["kpis"]["rows"] == want, query
        assert len(got["filters"]) == query.count("=") if "from" not in query else len(got["filters"]) == 2
        for c in got["charts"]:
            before = next(b for b in base["charts"] if b["kind"] == c["kind"])
            assert c["total"] < before["total"], (query, c["kind"])
            if c["kind"] in ("histogram", "bar"):
                assert c["total"] == want, (query, c["kind"])
        page = client.get(f"/datasets/{i}?app=explorer{query.replace('?', '&')}").text
        assert f"{want} of {want} rows" in page


def test_AC_38(live):
    path = _path(live, "sales.csv")
    with _open(live, path + "&f.region=North&from=2024-01-02") as (page, external, errors):
        # opening the URL restores the state: dropdown, date, KPI and one chip per filter
        assert page.locator("select[name='f.region']").input_value() == "North"
        assert page.locator("input[name='from']").input_value() == "2024-01-02"
        assert _kpi(page)["Rows"] == "2" and page.locator(".chips a").count() == 2
        assert page.locator("text=Clear filters").count() == 1
        # a chip removes only its own filter
        page.locator(".chips a", has_text="region = North").click()
        _settle(page)
        assert "f.region" not in page.url and "from=2024-01-02" in page.url
        assert _kpi(page)["Rows"] == "5" and page.locator(".chips a").count() == 1
        page.select_option("select[name='f.region']", "South")
        page.click("form.filters button")
        _settle(page)
        assert "f.region=South" in page.url and "from=2024-01-02" in page.url and _kpi(page)["Rows"] == "2"
        page.click("text=Clear filters")
        _settle(page)
        assert urlparse(page.url).query == "app=explorer" and _kpi(page)["Rows"] == "6" and page.locator(".chips a").count() == 0
        assert external == [] and errors == []


def _plot_values(page, kind):
    return page.evaluate("k => { const d = document.querySelector(`[data-kind=\"${k}\"] .plot`).data[0];"
                         " return [d.orientation || 'v', d.orientation === 'h' ? d.y : (d.x || d.labels), d.orientation === 'h' ? d.x : (d.y || d.values)]; }", kind)


def test_AC_39(live, data_dir):
    _staff(data_dir)  # written before the first request, so the scan sees it
    sales = _path(live, "sales.csv")
    staff = _path(live, "staff.csv")
    # vertical bar: sales.csv regions (short labels); click the first bar, then the active bar again
    with _open(live, sales) as (page, external, errors):
        orient, labels, _ = _plot_values(page, "bar")
        assert orient == "v"
        _click_nav(page, "bar")
        want = labels[0]
        assert parse_qs(urlparse(page.url).query) == {"f.region": [want], "app": ["explorer"]}
        n = {"South": 2, "North": 3, "East": 1}[want]
        assert page.locator("select[name='f.region']").input_value() == want and _kpi(page)["Rows"] == str(n)
        assert page.locator(".chips a").count() == 1
        for fig in page.locator("figure.chart").all():  # every chart is on the filtered rows
            count = fig.locator(".chart-count").inner_text()
            assert count.split(" of ")[0] == count.split(" of ")[1].split(" ")[0]
            if fig.get_attribute("data-kind") in ("bar", "histogram"):
                assert count.startswith(f"{n} of {n} ")
        _click_nav(page, "bar")
        assert urlparse(page.url).query == "app=explorer" and _kpi(page)["Rows"] == "6"
        assert errors == [] and external == []
    # horizontal bar (labels > 12 chars): same set and toggle, plus a second filter on another column ANDs
    with _open(live, staff) as (page, external, errors):
        orient, labels, _ = _plot_values(page, "bar")
        assert orient == "h" and max(map(len, labels)) > 12
        _click_nav(page, "bar")
        want = labels[0]
        assert parse_qs(urlparse(page.url).query) == {"f.department": [want], "app": ["explorer"]}
        n = sum(1 for k in range(40) if STAFF_DEPTS[k % 3] == want)
        assert page.locator("select[name='f.department']").input_value() == want and _kpi(page)["Rows"] == str(n)
        page.select_option("select[name='f.region']", "North")
        page.click("form.filters button")
        _settle(page)
        assert set(parse_qs(urlparse(page.url).query)) - {"app"} == {"f.department", "f.region"} and page.locator(".chips a").count() == 2
        _click_nav(page, "bar")  # the bar of the clicked column is still drawn: clicking it removes only that filter
        assert set(parse_qs(urlparse(page.url).query)) - {"app"} == {"f.region"} and page.locator(".chips a").count() == 1
        assert errors == [] and external == []
    with _open(live, staff + "&f.department=Customer+support") as (page, external, errors):
        orient, labels, _ = _plot_values(page, "bar")
        assert orient == "h" and labels == ["Customer support"]
        _click_nav(page, "bar")  # second click on the active horizontal bar
        assert urlparse(page.url).query == "app=explorer" and _kpi(page)["Rows"] == "40"
        assert errors == [] and external == []
    # donut: a real click on a slice sets the filter
    with _open(live, staff) as (page, external, errors):
        fig = page.locator('[data-kind="donut"]')
        fig.scroll_into_view_if_needed()
        want = _plot_values(page, "donut")[1][0]
        x, y = page.evaluate("""() => {
            const paths = [...document.querySelectorAll('[data-kind="donut"] .pielayer .slice > path')];
            const bs = paths.map(p => p.getBoundingClientRect());
            const l = Math.min(...bs.map(b => b.left)), r = Math.max(...bs.map(b => b.right));
            const t = Math.min(...bs.map(b => b.top)), u = Math.max(...bs.map(b => b.bottom));
            const cx = (l + r) / 2, cy = (t + u) / 2, rm = Math.min(r - l, u - t) / 2 * 0.78;
            let sx = 0, sy = 0;
            for (let a = 0; a < 360; a += 2) {
              const px = cx + rm * Math.cos(a * Math.PI / 180), py = cy + rm * Math.sin(a * Math.PI / 180);
              if (document.elementsFromPoint(px, py).includes(paths[0])) { sx += Math.cos(a * Math.PI / 180); sy += Math.sin(a * Math.PI / 180); }
            }
            const m = Math.hypot(sx, sy) || 1;
            return [cx + rm * sx / m, cy + rm * sy / m];
        }""")
        _click_nav(page, "donut", (x, y))
        assert parse_qs(urlparse(page.url).query) == {"f.department": [want], "app": ["explorer"]}
        assert _kpi(page)["Rows"] == str(sum(1 for k in range(40) if STAFF_DEPTS[k % 3] == want))
        assert page.locator('[data-kind="donut"]').count() == 0  # a one-value column drops out of the donuts
        assert errors == [] and external == []


def test_AC_40(make_client, data_dir):
    from openpyxl import load_workbook
    from pptx import Presentation
    client = make_client(data_dir)
    i = _ids(client)[("sales.csv", None)]
    query = "?f.region=North&from=2024-01-02"  # North rows on 01-03 and 01-06
    labels = _api(client, i, query)["filters"]
    assert len(labels) == 2

    def xlsx(q):
        r = client.get(f"/datasets/{i}/export.xlsx?app=explorer{q.replace('?', '&')}")
        assert r.status_code == 200
        return load_workbook(io.BytesIO(r.content))

    def pptx(q):
        r = client.get(f"/datasets/{i}/export.pptx?app=explorer{q.replace('?', '&')}")
        assert r.status_code == 200
        return Presentation(io.BytesIO(r.content))

    def texts(slide):
        return [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]

    full, cut = xlsx(""), xlsx(query)
    for wb in (full, cut):
        assert wb.sheetnames[0] == "Data" and wb.sheetnames[-1] == "Summary"
    assert full["Data"].max_row == 7 and cut["Data"].max_row == 3  # header + rows
    cells = lambda wb: [str(c.value) for row in wb["Summary"].iter_rows() for c in row if c.value is not None]  # noqa: E731
    assert "Filters: none" in cells(full)
    assert all(any(label in c for c in cells(cut)) for label in labels) and "Filters: none" not in cells(cut)

    def bar_sum(wb):
        ws = wb[next(n for n in wb.sheetnames if n.endswith(" bar"))]
        return sum(r[1] for r in ws.iter_rows(min_row=2, values_only=True) if isinstance(r[1], (int, float)))
    assert bar_sum(full) == 46 and bar_sum(cut) == 6  # 5 + 1
    assert sum(len(ws._charts) for ws in cut.worksheets) > 0

    def bar_values(prs):
        for s in prs.slides:
            for sh in s.shapes:
                if sh.has_chart and "North" in list(sh.chart.plots[0].categories):
                    return sum(sh.chart.plots[0].series[0].values)
    p_full, p_cut = pptx(""), pptx(query)
    t_full, t_cut = texts(p_full.slides[0]), texts(p_cut.slides[0])
    assert t_full == ["Data overview", "sales.csv", "Rows: 6, 3 columns", "Filters: none"]
    assert "Rows: 6, 3 columns" in t_full and "Filters: none" in t_full
    assert "Rows: 2 of 6, 3 columns" in t_cut and "Filters: none" not in " ".join(t_cut)
    assert all(label in " ".join(t_cut) for label in labels)
    assert bar_values(p_full) == 46 and bar_values(p_cut) == 6


def test_AC_41(big_sales_csv, make_client):
    client = make_client(big_sales_csv)
    i = client.get("/api/datasets").json()[0]["id"]
    assert client.get(f"/api/datasets/{i}/charts").status_code == 200  # warm: the file is read and typed
    for query, rows in (("?f.region=North", 50_000), ("?f.product=p3", 10_000)):
        start = time.perf_counter()
        r = client.get(f"/api/datasets/{i}/charts{query}")
        took = time.perf_counter() - start
        print(f"AC-41 {query}: {took:.2f} s")
        assert r.status_code == 200 and r.json()["kpis"]["rows"] == rows
        assert took < 1.0, (query, took)


def test_AC_42(big_sales_csv, make_client, tmp_path):
    for url in ("/api/datasets/{id}/charts", "/datasets/{id}"):
        client = make_client(big_sales_csv)  # clears the caches; the file stays on disk
        i = client.get("/api/datasets").json()[0]["id"]  # scan only
        start = time.perf_counter()
        r = client.get(url.format(id=i))
        took = time.perf_counter() - start
        print(f"AC-42 cold {url}: {took:.2f} s")
        assert r.status_code == 200 and took <= 5.0, (url, took)
        if "api" in url:  # charts and KPIs cover all 200,000 loaded rows
            body = r.json()
            assert body["kpis"]["rows"] == 200_000 and any(c["kind"] == "histogram" and c["total"] == 200_000 for c in body["charts"])
        else:
            # Business page has no row count, so check that the cards use all 200,000 rows: latest full period is Nov
            # (month = i % 12 + 1, last date is 28 Dec), amount = i % 997, qty = i % 9 + 1; hand sums over every row
            assert "rule R2" in r.text
            card = lambda col: re.search(rf'<div class="card-label">{col}</div>\s*<div class="card-value">([^<]*)</div>', r.text)
            assert card("amount") and card("amount").group(1) == f"{sum(i % 997 for i in range(200_000) if i % 12 == 10):,}"
            assert card("qty") and card("qty").group(1) == f"{sum(i % 9 + 1 for i in range(200_000) if i % 12 == 10):,}"
    # types come from the first 10,000 rows only: later text does not change them
    folder = tmp_path / "late"
    folder.mkdir()
    (folder / "late.csv").write_text("n,k\n" + "".join(f"{i},{i % 3}\n" for i in range(10_000)) + "".join(f"abc,{i % 3}\n" for i in range(2_000)))
    client = make_client(folder)
    i = client.get("/api/datasets").json()[0]["id"]
    assert client.get(f"/api/datasets/{i}/profile").json()["n"] == "numerical"
    assert client.get(f"/api/datasets/{i}/charts").json()["kpis"]["rows"] == 12_000


# ---- Round 5: Business and Map apps (AC-43 .. AC-58) -------------------------------------------------------------
# Helpers are copies of the engineers' browser helpers; expected values are hand-computed from conftest.shop_rows().

PLACES_POP = [1000 * (k + 1) for k in range(20)]
COUNTRIES = ["France", "Japan", "Brazil", "Kenya"]


def _app_id(client, name):
    return next(d["id"] for d in client.get("/api/datasets").json() if d["path"] == name)


def _html(client, name, query=""):
    return client.get(f"/datasets/{_app_id(client, name)}{query}").text


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.search(r"<main.*?</main>", html, re.S).group(0)))


@pytest.fixture
def arch(archetypes_dir, make_client):
    """Server on archetypes_dir (shop.csv, places.csv, measures.csv, sparse.csv); yields (base, ids by file name)."""
    client = make_client(archetypes_dir)
    ids = {d["path"]: d["id"] for d in client.get("/api/datasets").json()}
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}", ids
    server.should_exit = True
    thread.join(10)


@contextmanager
def _browse(url, width=1280, height=900, draw=True):
    """Chromium page with off-host requests aborted; page.errors / external / local / failed are filled while it runs."""
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": width, "height": height})
        page.errors, page.external, page.local, page.failed = [], [], [], []
        base = urlparse(url).scheme + "://" + urlparse(url).netloc

        def route(r):
            if r.request.url.startswith(base) or r.request.url.startswith("data:"):
                page.local.append(r.request.url)
                r.continue_()
            else:
                page.external.append(r.request.url)
                r.abort()
        page.route("**/*", route)
        page.on("console", lambda m: m.type == "error" and page.errors.append(m.text))
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.on("requestfailed", lambda r: page.failed.append(r.url))
        page.on("response", lambda r: r.status >= 400 and page.failed.append(f"{r.status} {r.url}"))
        page.goto(url)
        _settle(page) if draw else page.wait_for_load_state("networkidle")
        yield page
        b.close()


def _settle(page):
    page.wait_for_load_state("networkidle")
    page.wait_for_function("""() => { const p = [...document.querySelectorAll('.plot')].filter(e => !e.closest('[hidden]'));
        return p.length > 0 && p.every(e => e.classList.contains('js-plotly-plot')); }""")


def _hover(page, target):
    """Hover the middle of a locator once its box has stopped moving (entrance animations, scroll); return the tooltip text."""
    target.scroll_into_view_if_needed()
    handle = target.element_handle()
    page.wait_for_function("""([e, n]) => { const r = e.getBoundingClientRect(), k = r.x + ',' + r.y + ',' + r.width + ',' + r.height;
        e.__k = e.__k && e.__k[0] === k ? [k, e.__k[1] + 1] : [k, 0]; return e.__k[1] >= n; }""", arg=[handle, 6], polling=50)
    box = target.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(1, 1)
    page.wait_for_function("document.querySelectorAll('.hoverlayer .hovertext').length === 0")  # a previous tooltip is gone
    page.mouse.move(x - 3, y)
    page.mouse.move(x, y, steps=4)
    page.wait_for_selector(".hoverlayer .hovertext")
    return page.locator(".hoverlayer .hovertext").first.text_content()


def _query(page):
    return parse_qs(urlparse(page.url).query)


def _bar_centre(page, label):
    page.locator("[data-leaderboard] .plot").scroll_into_view_if_needed()
    return page.evaluate("""l => { const gd = document.querySelector('[data-leaderboard] .js-plotly-plot');
        for (let t = 0; t < gd.data.length; t++) { const i = gd.data[t].y.indexOf(l);
          if (i >= 0) { const r = gd.querySelectorAll('.barlayer .trace')[t].querySelectorAll('.point')[i].getBoundingClientRect();
            return {x: r.x + r.width / 2, y: r.y + r.height / 2}; } } }""", label)


def _click_bar(page, label, navigates=True):
    c = _bar_centre(page, label)
    if navigates:
        with page.expect_navigation():
            page.mouse.click(c["x"], c["y"])
        _settle(page)
    else:
        page.mouse.click(c["x"], c["y"])
        page.wait_for_timeout(500)


def _bar_cursor(page, label):
    c = _bar_centre(page, label)
    page.mouse.move(c["x"] - 2, c["y"] - 2)
    page.mouse.move(c["x"], c["y"])
    page.wait_for_timeout(300)
    return page.evaluate("getComputedStyle(document.querySelector('[data-leaderboard] .nsewdrag')).cursor")


def _crumbs(page):
    return page.locator("nav.crumbs li").all_inner_texts()


def _click_point(page, k):
    point = page.locator("figure[data-kind=map2d] .js-plotly-plot .point").nth(k)
    point.scroll_into_view_if_needed()
    box = point.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def _details(page):
    page.wait_for_selector(".map-panel dl")
    return dict(zip(page.locator(".map-panel dl dt").all_inner_texts(), page.locator(".map-panel dl dd").all_inner_texts()))


def _folder(tmp_path, name, header, rows):
    import csv
    root = tmp_path / name
    root.mkdir()
    with open(root / f"{name}.csv", "w", newline="") as f:
        csv.writer(f).writerows([header, *rows])
    return root


def test_AC_43(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    want = {"places.csv": ("map", "R1", ["map", "explorer"]), "shop.csv": ("business", "R2", ["business", "explorer"]),
            "measures.csv": ("explorer", "R3", ["explorer"]),
            "sparse.csv": ("explorer", "R3", ["explorer"])}  # lat/lon + 3 numericals, coordinates in 4 of 10 rows
    for name, (app, rule, qualifies) in want.items():
        url = f"/api/datasets/{_app_id(client, name)}/app"
        got = client.get(url).json()
        assert (got["app"], got["rule"], got["qualifies"]) == (app, rule, qualifies), name
        for _ in range(2):  # repeated requests answer the same
            again = client.get(url).json()
            assert (again["app"], again["rule"], again["qualifies"]) == (app, rule, qualifies), name


def test_AC_44(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    badge = lambda name: re.search(r'<span class="app-badge">([^<]*)</span>', _html(client, name)).group(1)
    assert badge("shop.csv") == "App: Business (rule R2)"
    assert badge("measures.csv") == "App: Explorer (rule R3)"
    assert badge("places.csv") == "App: Map (rule R1)"
    # the badge shows the detected app, also when another qualifying app is viewed
    html = _html(client, "shop.csv", "?app=explorer")
    assert 'class="app-badge">App: Business (rule R2)<' in html


def test_AC_45(arch, make_client, archetypes_dir):
    base, ids = arch
    client = make_client(archetypes_dir)
    nav = lambda html: (lambda m: m and re.findall(r'<a href="([^"]*)"[^>]*>([^<]*)</a>', m.group(1)))(
        re.search(r'<nav class="view-as" aria-label="View as">(.*?)</nav>', html, re.S))
    assert [t for _, t in nav(_html(client, "shop.csv"))] == ["Business", "Explorer"]
    assert [t for _, t in nav(_html(client, "places.csv"))] == ["Map", "Explorer"]
    assert nav(_html(client, "measures.csv")) is None and 'view-as' not in _html(client, "measures.csv")
    # an app the dataset does not qualify for shows the detected app instead
    assert 'aria-current="page">Business<' in _html(client, "shop.csv", "?app=map")
    assert 'class="cards"' not in _html(client, "measures.csv", "?app=business")
    with _browse(f"{base}/datasets/{ids['shop.csv']}") as page:
        assert page.locator(".view-as a[aria-current=page]").inner_text() == "Business"
        assert page.locator("ul.cards").count() == 1
        with page.expect_navigation():
            page.click(".view-as >> text=Explorer")
        _settle(page)
        assert _query(page) == {"app": ["explorer"]}
        assert page.locator("ul.cards").count() == 0 and page.locator("[data-kind=line]").count() >= 1
        page.reload()  # opening the URL shows the same app
        _settle(page)
        assert page.locator(".view-as a[aria-current=page]").inner_text() == "Explorer"
        assert page.errors == []


def test_AC_46(arch, tmp_path, make_client):
    base, ids = arch
    # hand math (shop_rows): June revenue 7,392 vs May 6,192 = +19.4 %; units 72 vs 60 = +20.0 %; units has no name-rule match
    with _browse(f"{base}/datasets/{ids['shop.csv']}") as page:
        cards = page.locator("ul.cards > li.card")
        assert cards.count() == 2
        assert cards.nth(0).locator(".card-label").inner_text() == "revenue"
        assert cards.nth(0).locator(".card-value").inner_text() == "7,392"
        assert cards.nth(0).locator(".card-change").inner_text().split() == ["▲", "+19.4%", "up"]
        assert cards.nth(1).locator(".card-label").inner_text() == "units"
        assert cards.nth(1).locator(".card-value").inner_text() == "72"
        assert cards.nth(1).locator(".card-change").inner_text().split() == ["▲", "+20.0%", "up"]
        assert all(cards.nth(k).locator("svg.spark polyline").count() == 1 for k in range(2))
        assert page.errors == []
    # no previous value: n/a and no arrow
    with _browse(f"{base}/datasets/{ids['shop.csv']}?from=2030-01-01", draw=False) as page:
        cards = page.locator("ul.cards > li.card")
        assert cards.count() == 2
        for k in range(2):
            assert cards.nth(k).locator(".card-value").inner_text() == "n/a"
            assert cards.nth(k).locator(".card-change, svg.spark").count() == 0
            assert not set(cards.nth(k).inner_text()) & set("▲▼▶")
    # down and no change: Feb -> Mar (span 198 days = month grain; the last date is a month end, so March is the latest full period)
    rows = [("2023-09-15", "a", 90, 50), ("2024-02-10", "a", 40, 50), ("2024-02-20", "b", 60, 50), ("2024-03-15", "a", 30, 50),
            ("2024-03-31", "b", 50, 50)]
    client = make_client(_folder(tmp_path, "mini", ("date", "kind", "amount", "price"), rows))
    mini = _app_id(client, "mini.csv")
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        url = f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}/datasets/{mini}"
        with _browse(url) as page:
            cards = page.locator("ul.cards > li.card")
            assert cards.nth(0).locator(".card-value").inner_text() == "80"  # amount: Mar 30+50 vs Feb 40+60
            assert cards.nth(0).locator(".card-change").inner_text().split() == ["▼", "-20.0%", "down"]
            assert cards.nth(1).locator(".card-value").inner_text() == "100"  # price: 50+50 in both months
            assert cards.nth(1).locator(".card-change").inner_text().split()[-2:] == ["no", "change"]
    finally:
        server.should_exit = True
        thread.join(10)


def test_AC_47(arch, tmp_path, make_client):
    base, ids = arch
    months = {m: sum(r[5] for r in __import__("tests.conftest", fromlist=["shop_rows"]).shop_rows() if r[0][5:7] == f"{m:02d}") for m in range(1, 7)}
    with _browse(f"{base}/datasets/{ids['shop.csv']}") as page:
        figs = page.locator(".trends figure")
        assert figs.count() == 2  # one trend per measure (revenue, units)
        got = page.evaluate("""() => [...document.querySelectorAll('.trends .js-plotly-plot')].map(g =>
            ({x: g.data[0].x, y: g.data[0].y, keys: Object.keys(g._fullLayout).filter(k => /^yaxis\\d*$/.test(k)), n: g.data.length}))""")
        assert [g["keys"] for g in got] == [["yaxis"], ["yaxis"]] and [g["n"] for g in got] == [1, 1]
        assert got[0]["x"] == [f"2024-{m:02d}-01" for m in range(1, 7)]  # month grain for a 187-day span
        assert got[0]["y"] == [months[m] for m in range(1, 7)]
        assert got[1]["y"] == [12.0 * m for m in range(1, 7)]
        assert page.errors == []
    # grain follows the date span: 20 days -> day, 2 years -> month or year; checked through the payload
    client = make_client(_folder(tmp_path, "days", ("date", "kind", "amount"), [(f"2024-03-{d:02d}", "ab"[d % 2], d) for d in range(1, 21)]))
    got = client.get(f"/api/datasets/{_app_id(client, 'days.csv')}/app").json()
    assert got["grain"] == "day" and got["charts"][0]["data"]["y"] == [float(d) for d in range(1, 21)]
    assert len(got["cards"]) == 1


def test_AC_48(arch, make_client, tmp_path):
    base, ids = arch
    with _browse(f"{base}/datasets/{ids['shop.csv']}") as page:
        # hand math: revenue by channel over all 78 rows: web 15,276, shop 15,354 (sorted descending)
        assert page.evaluate("document.querySelector('[data-leaderboard] .js-plotly-plot').data[0].y") == ["shop", "web"]
        assert page.locator("[data-leaderboard] .barlayer text.bartext").evaluate_all("e => e.map(x => x.textContent)") == ["15,354", "15,276"]
    # 12 categories: top 10 sorted descending, then one Other bar holding the sum of the rest (2 x (100 + 200) = 600... below)
    rows = [(f"2024-01-{5 + k:02d}", f"k{k:02d}", 200 * (k + 1)) for k in range(12)] + [(f"2024-02-{5 + k:02d}", f"k{k:02d}", 200 * (k + 1)) for k in range(12)]
    client = make_client(_folder(tmp_path, "wide", ("date", "k", "amount"), rows))
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        url = f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}/datasets/{_app_id(client, 'wide.csv')}"
        with _browse(url) as page:
            got = page.evaluate("""() => { const g = document.querySelector('[data-leaderboard] .js-plotly-plot');
                return g.data.map(t => ({y: t.y, x: t.x})); }""")
            ys = [y for t in got for y in t["y"]]
            xs = [x for t in got for x in t["x"]]
            # k11 .. k02 are the top 10: each category sums 2 x 200 x (k + 1); Other = k00 + k01 = 400 + 800
            assert ys == [f"k{k:02d}" for k in range(11, 1, -1)] + ["Other"]
            assert xs == [400.0 * (k + 1) for k in range(11, 1, -1)] + [1200.0] and xs[:10] == sorted(xs[:10], reverse=True)
            assert page.locator("[data-leaderboard] .barlayer text.bartext").evaluate_all("e => e.map(x => x.textContent)") == [
                f"{int(x):,}" for x in xs]
            assert page.errors == []
    finally:
        server.should_exit = True
        thread.join(10)


def test_AC_49(arch):
    base, ids = arch
    # drill order for shop.csv: channel (2 values), store (3), product (12)
    with _browse(f"{base}/datasets/{ids['shop.csv']}") as page:
        title = lambda: page.locator("[data-leaderboard] .chart-title").inner_text()
        assert title() == "revenue by channel" and _crumbs(page) == ["All"]
        _click_bar(page, "web")
        assert _query(page) == {"f.channel": ["web"]} and title() == "revenue by store"
        assert _crumbs(page) == ["All", "channel: web"]
        _click_bar(page, "North")
        assert _query(page) == {"f.channel": ["web"], "f.store": ["North"]} and title() == "revenue by product"
        # last categorical level: bars are not clickable and show no pointer
        before = page.url
        assert _bar_cursor(page, "p11") == "default"
        _click_bar(page, "p11", navigates=False)
        _click_bar(page, "Other", navigates=False)
        assert page.url == before
        page.go_back()
        _settle(page)
        assert _query(page) == {"f.channel": ["web"]} and title() == "revenue by store"
        page.click("nav.crumbs >> text=All")
        _settle(page)
        assert "f." not in page.url and title() == "revenue by channel"
        assert page.errors == []


def test_AC_50(arch):
    base, ids = arch
    # web/North: previous (May) vs latest (June) revenue. Hand math from shop_rows: deltas +606 (store North web)
    with _browse(f"{base}/datasets/{ids['shop.csv']}?f.channel=web&f.store=North") as page:
        head = page.locator("table.delta-table thead th").all_inner_texts()
        assert len(head) == 4 and head[0].lower() == "category" and head[3].lower() == "delta"
        cells = page.evaluate("""() => { const probe = document.createElement('i'); probe.style.color = 'var(--div-mid)'; document.body.append(probe);
            return {mid: getComputedStyle(probe).color, cells: [...document.querySelectorAll('.delta-table td.delta')].map(td =>
              ({cls: td.className.split(' ').pop(), text: td.textContent, bg: getComputedStyle(td).backgroundColor}))}; }""")
        by = {c["cls"]: c for c in cells["cells"]}
        assert set(by) == {"pos", "neg", "zero"}
        assert by["pos"]["text"].startswith("+") and by["neg"]["text"].startswith("-") and by["zero"]["text"] == "0"
        assert by["zero"]["bg"] == cells["mid"] and len({c["bg"] for c in by.values()}) == 3
        assert page.errors == []


def _map_checks(arch, width, height):
    base, ids = arch
    with _browse(f"{base}/datasets/{ids['places.csv']}", width, height) as page:
        h = page.evaluate("document.querySelector('.map-layout .plot').getBoundingClientRect().height")
        assert 0.65 <= h / height <= 0.75, (width, h)
        m = page.evaluate("document.querySelector('.map-layout .js-plotly-plot').data[0].marker")
        assert m["color"] == PLACES_POP and m["colorbar"]["title"]["text"] == "pop"
        assert len(m["colorscale"]) == 2  # one hue: light to dark
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth") and page.errors == []


def test_AC_51(arch):
    for size in ((1280, 900), (390, 844)):
        _map_checks(arch, *size)


def test_AC_52(arch, big_csv, make_client, tmp_path):
    base, ids = arch
    with _browse(f"{base}/datasets/{ids['places.csv']}") as page:  # 20 rows: one mark per point
        t = page.evaluate("document.querySelector('.map-layout .js-plotly-plot').data.map(t => [t.type, t.lon.length])")
        assert t == [["scattergeo", 20]]
    # 5,000 coordinates draw points; 5,001 draw hexagon cells whose counts sum to the rows
    for n, hexed in ((5000, False), (5001, True)):
        client = make_client(_folder(tmp_path, f"n{n}", ("lat", "lon", "v"), [(i % 180 - 90 + 0.5, i % 360 - 180 + 0.5, i % 7) for i in range(n)]))
        got = client.get(f"/api/datasets/{_app_id(client, f'n{n}.csv')}/app").json()["charts"][0]["data"]
        assert got["mode"] == ("hex" if hexed else "points"), (n, got["mode"])
        assert sum(got["count"]) == n if hexed else len(got["lon"]) == n
    client = make_client(big_csv)
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        url = f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}/datasets/{_app_id(client, 'big.csv')}"
        with _browse(url) as page:
            t = page.evaluate("document.querySelector('.map-layout .js-plotly-plot').data.map(t => [t.type, t.z.reduce((a, b) => a + b, 0), t.hovertemplate + t.text[0]])")
            assert len(t) == 1 and t[0][0] == "choropleth" and t[0][1] == 60_000 and "points" in t[0][2]
            cells = page.locator(".map-layout .choroplethlayer path")
            label = _hover(page, cells.nth(cells.count() // 2))
            assert re.fullmatch(r"[\d,]+ points?", label.strip()), label
            assert page.errors == []
    finally:
        server.should_exit = True
        thread.join(10)


def test_AC_53(arch):
    base, ids = arch
    with _browse(f"{base}/datasets/{ids['places.csv']}") as page:
        seen = []
        page.on("request", lambda r: seen.append(r.url))
        _click_point(page, 3)
        assert _details(page) == {"lat": "-28", "lon": "-84", "country": "Kenya", "pop": "4,000"}
        assert not [u for u in seen if "/api/" in u]
        # top regions: country (fewest distinct values), ranked by sum of pop, desc
        sums = {c: sum(p for k, p in enumerate(PLACES_POP) if COUNTRIES[k % 4] == c) for c in COUNTRIES}
        ranked = sorted(sums.items(), key=lambda kv: -kv[1])
        got = page.evaluate("document.querySelector('.map-panel .js-plotly-plot').data.map(t => [t.y, t.x])")
        assert got == [[[k for k, _ in ranked], [float(v) for _, v in ranked]]] or got == [[[k for k, _ in ranked], [v for _, v in ranked]]]
        # 3D view and back
        flat, three, btn = page.locator("figure[data-kind=map2d]"), page.locator("figure[data-kind=map3d]"), page.get_by_role("button", name="3D view")
        assert three.is_hidden()
        btn.click()
        page.wait_for_selector("figure[data-kind=map3d] .plot canvas")
        assert three.is_visible() and flat.is_hidden()
        assert page.evaluate("document.querySelector('figure[data-kind=map3d] .js-plotly-plot').data[0].type") == "scatter3d"
        btn.click()
        assert flat.is_visible() and three.is_hidden()
        assert page.errors == []
    # more than 10 regions: top 10 then one Other
    # (covered by the same builder as the leaderboard; see AC-48 for the arithmetic)


def _figure_rules(page):
    """No second y-axis, hover on, and every visible figure's table toggle lists the plotted values and switches back."""
    info = page.evaluate("""() => [...document.querySelectorAll('.js-plotly-plot')].filter(g => !g.closest('[hidden]')).map(g => ({
        id: g.closest('figure').id, keys: Object.keys(g._fullLayout).filter(k => /^yaxis\\d+$/.test(k)),
        overlaying: Object.values(g._fullLayout).some(a => a && typeof a === 'object' && a.overlaying),
        hover: g._fullLayout.hovermode, info: g.data.map(t => t.hoverinfo || null),
        n: g.data.reduce((s, t) => s + (t.type === 'heatmap' ? t.x.length * t.y.length : (t.labels || (t.orientation === 'h' ? t.y : t.x) || t.lon || t.locations || []).length), 0)}))""")
    assert info
    for i in info:
        assert i["keys"] in ([], ["yaxis"]) and not i["overlaying"], i
        assert i["hover"] is not False and not set(i["info"]) & {"none", "skip"}, i
        fig = page.locator("#" + i["id"])
        btn = fig.locator(".table-toggle")
        assert btn.count() == 1, i["id"]
        btn.click()
        assert btn.get_attribute("aria-pressed") == "true" and fig.locator(".plot").is_hidden()
        assert fig.locator("table.plot-table tbody tr").count() == i["n"], (i["id"], i["n"])
        btn.click()
        assert fig.locator(".plot").is_visible() and btn.get_attribute("aria-pressed") == "false"
    return len(info)


def test_AC_54(archetypes_dir, data_dir, make_client, tmp_path):
    import shutil
    root = tmp_path / "all"
    shutil.copytree(archetypes_dir, root)
    shutil.copy(data_dir / "sales.csv", root / "sales.csv")
    client = make_client(root)
    ids = {d["path"]: d["id"] for d in client.get("/api/datasets").json()}
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        base = f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
        for path, least in (("shop.csv", 3), ("shop.csv?app=explorer", 1), ("places.csv", 2), ("measures.csv", 1), ("sales.csv?app=explorer", 4)):
            name = path.split("?")[0]
            with _browse(f"{base}/datasets/{ids[name]}{path[len(name):]}") as page:
                assert _figure_rules(page) >= least, path
                assert page.errors == [], path
    finally:
        server.should_exit = True
        thread.join(10)


def test_AC_55(arch):
    base, ids = arch
    bare = re.compile(r"(?<![\d.,-])\d{4,}(?![\d-])")
    ticks = """() => [...document.querySelectorAll('.js-plotly-plot')].filter(g => !g.closest('[hidden]')).flatMap(g =>
        ['x', 'y'].filter(a => g._fullLayout[a + 'axis'] && g._fullLayout[a + 'axis'].type === 'linear')
          .flatMap(a => [...g.querySelectorAll('.' + a + 'tick text')].map(t => t.textContent)))"""
    # Business: cards, value labels, change table, axis ticks, tooltips
    with _browse(f"{base}/datasets/{ids['shop.csv']}") as page:
        # chart text is checked through ticks/labels below (date ticks such as "Jan 2024" are years, not amounts)
        main = re.sub(r"\d{4}-\d{2}-\d{2}", "", page.evaluate("""() => { const p = document.querySelectorAll('.plot'); p.forEach(e => e.style.display = 'none');
            const t = document.querySelector('main').innerText; p.forEach(e => e.style.display = ''); return t; }"""))
        assert not bare.search(main) and "2,024" not in main  # no bare 4+ digit number, and no separator in a year
        assert page.locator("ul.cards .card-value").first.inner_text() == "7,392"
        assert page.locator("[data-leaderboard] .barlayer text.bartext").evaluate_all("e => e.map(x => x.textContent)") == ["15,354", "15,276"]
        t = page.evaluate(ticks)
        assert t and not [x for x in t if bare.fullmatch(x)], t
        c = _bar_centre(page, "shop")
        page.mouse.move(c["x"] - 2, c["y"]); page.mouse.move(c["x"], c["y"])
        page.wait_for_selector(".hoverlayer .hovertext")
        assert "15,354" in page.locator(".hoverlayer .hovertext").first.text_content()
        assert page.errors == []
    # Map: side panel, axis ticks of the regions bar, tooltip on a point, table view
    with _browse(f"{base}/datasets/{ids['places.csv']}") as page:
        _click_point(page, 19)
        assert _details(page)["pop"] == "20,000"
        main = page.evaluate("""() => { const p = document.querySelectorAll('.plot'); p.forEach(e => e.style.display = 'none');
            const t = document.querySelector('main').innerText; p.forEach(e => e.style.display = ''); return t; }""")
        assert not bare.search(main) and "20,000" in main
        t = page.evaluate(ticks)
        assert t and not [x for x in t if bare.fullmatch(x)], t
        assert page.locator(".map-panel .barlayer .bartext").first.text_content() == "60,000"
        point = page.locator("figure[data-kind=map2d] .js-plotly-plot .point").nth(19).bounding_box()
        page.mouse.move(point["x"] + point["width"] / 2 - 1, point["y"] + point["height"] / 2)
        page.mouse.move(point["x"] + point["width"] / 2, point["y"] + point["height"] / 2)
        page.wait_for_selector(".hoverlayer .hovertext")
        assert "20,000" in page.locator(".hoverlayer .hovertext").first.text_content()
        assert page.errors == []


def _xlsx(client, name, query):
    import openpyxl
    r = client.get(f"/datasets/{_app_id(client, name)}/export.xlsx{query}")
    assert r.status_code == 200
    return openpyxl.load_workbook(io.BytesIO(r.content))


def _pptx(client, name, query):
    from pptx import Presentation
    r = client.get(f"/datasets/{_app_id(client, name)}/export.pptx{query}")
    assert r.status_code == 200
    return list(Presentation(io.BytesIO(r.content)).slides)


def test_AC_56(make_client, archetypes_dir):
    from pptx.enum.chart import XL_CHART_TYPE
    client = make_client(archetypes_dir)
    first = lambda slide: [s.text_frame.text for s in slide.shapes if s.has_text_frame][0]
    # Business: Data first, Summary last, KPI table, trend per measure, leaderboard, change table in order
    wb = _xlsx(client, "shop.csv", "?app=business")
    assert wb.sheetnames == ["Data", "chart-1 table", "chart-2 line", "chart-3 line", "chart-4 bar", "chart-5 table", "Summary"]
    assert [len(wb[n]._charts) for n in wb.sheetnames] == [0, 0, 1, 1, 1, 0, 0]
    assert [r[0] for r in wb["Summary"].iter_rows(values_only=True)][:2] == ["Business overview", "Filters: none"]
    assert [c.value for c in wb["chart-1 table"][1]] == ["Measure", "Previous", "Latest", "Change %"]
    assert [c.value for c in wb["chart-1 table"]["A"]][1:] == ["revenue", "units"]
    slides = _pptx(client, "shop.csv", "?app=business")
    assert first(slides[0]) == "Business overview"
    kinds = [("table" if s.has_table else "chart") for sl in slides[1:] for s in sl.shapes if s.has_table or s.has_chart]
    assert kinds == ["table", "chart", "chart", "chart", "table"]
    assert [s.chart.chart_type for sl in slides[1:] for s in sl.shapes if s.has_chart] == [
        XL_CHART_TYPE.LINE, XL_CHART_TYPE.LINE, XL_CHART_TYPE.COLUMN_CLUSTERED]
    # Map: native lon/lat scatter chart, then top regions
    wb = _xlsx(client, "places.csv", "?app=map")
    assert wb.sheetnames == ["Data", "chart-1 scatter", "chart-2 bar", "Summary"]
    assert wb["Summary"]["A1"].value == "Map overview" and all(len(wb[n]._charts) == 1 for n in wb.sheetnames[1:3])
    assert wb["chart-1 scatter"].max_row - 1 == 20
    slides = _pptx(client, "places.csv", "?app=map")
    assert first(slides[0]) == "Map overview"
    assert [s.chart.chart_type for sl in slides[1:] for s in sl.shapes if s.has_chart] == [
        XL_CHART_TYPE.XY_SCATTER, XL_CHART_TYPE.COLUMN_CLUSTERED]
    # Explorer exports are unchanged (round 4): same sheets and no app title
    wb = _xlsx(client, "shop.csv", "?app=explorer")
    assert wb.sheetnames[0] == "Data" and wb.sheetnames[-1] == "Summary" and "chart-1 table" not in wb.sheetnames
    assert wb["Summary"]["A1"].value == "Filters: none"
    assert first(_pptx(client, "shop.csv", "?app=explorer")[0]) == "Data overview"  # Board gate 187: one client-facing title for every Explorer export


def test_AC_57(archetypes_dir, make_client, tmp_path):
    # part-to-whole donut only for 2-5 parts
    for k in (1, 2, 5, 6, 7):
        rows = [(f"2024-01-{1 + i:02d}", f"c{i % k}", 10 + i) for i in range(14)]
        client = make_client(_folder(tmp_path, f"k{k}", ("date", "kind", "amount"), rows))
        kinds = [c["kind"] for c in client.get(f"/api/datasets/{_app_id(client, f'k{k}.csv')}/charts").json()["charts"]]
        assert ("donut" in kinds) == (2 <= k <= 5), (k, kinds)
    # donut slices use the fixed categorical order --c1..; one hue sequential scale on the map; one y-axis; at most 3 colour series
    client = make_client(archetypes_dir)
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        base = f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
        ids = {d["path"]: d["id"] for d in client.get("/api/datasets").json()}
        var = """n => { const p = document.createElement('i'); p.style.color = 'var(--c' + n + ')'; document.body.append(p);
            const c = getComputedStyle(p).color; p.remove(); return c; }"""
        with _browse(f"{base}/datasets/{ids['places.csv']}?app=explorer") as page:
            donut = page.evaluate("""() => { const g = document.querySelector('[data-kind=donut] .js-plotly-plot'); return g && [g.data[0].labels.length, g.data[0].marker.colors, g.data[0].hole]; }""")
            assert donut and 2 <= donut[0] <= 5 and abs(donut[2] - 0.55) < 1e-9
            assert len(donut[1]) >= donut[0]
            assert page.errors == []
        with _browse(f"{base}/datasets/{ids['places.csv']}") as page:
            n = page.evaluate("[...document.querySelectorAll('.js-plotly-plot')].filter(g => !g.closest('[hidden]')).map(g => g.data.length)")
            assert max(n) <= 3
            assert page.evaluate("document.querySelector('.map-layout .js-plotly-plot').data[0].marker.colorscale.length") == 2
            assert _figure_rules(page) >= 2
        with _browse(f"{base}/datasets/{ids['shop.csv']}") as page:
            assert page.evaluate("[...document.querySelectorAll('.js-plotly-plot')].every(g => !g._fullLayout.yaxis2)")
            assert page.evaluate("[...document.querySelectorAll('.js-plotly-plot')].every(g => g.data.length <= 8 + 1)")
    finally:
        server.should_exit = True
        thread.join(10)


def test_AC_58(arch):
    base, ids = arch
    def table(page, kind):
        f = page.locator(f"figure[data-kind={kind}]").first
        f.locator(".table-toggle").click()
        assert f.locator("table.plot-table tbody tr").count() > 0 and f.locator(".plot").is_hidden()
        f.locator(".table-toggle").click()
        assert f.locator(".plot").is_visible()
    with _browse(f"{base}/datasets/{ids['shop.csv']}") as page:
        _click_bar(page, "web")
        _click_bar(page, "North")
        assert _crumbs(page) == ["All", "channel: web", "store: North"]
        page.go_back()
        _settle(page)
        page.click(".view-as >> text=Explorer")
        _settle(page)
        page.click(".view-as >> text=Business")
        _settle(page)
        table(page, "bar")
        assert len(page.local) > 5 and page.external == [] and page.failed == [] and page.errors == []
    with _browse(f"{base}/datasets/{ids['places.csv']}") as page:
        _click_point(page, 3)
        assert _details(page)["pop"] == "4,000"
        btn = page.get_by_role("button", name="3D view")
        btn.click()
        page.wait_for_selector("figure[data-kind=map3d] .plot canvas")
        btn.click()
        page.wait_for_function("document.querySelector('figure[data-kind=map2d] .plot').getBoundingClientRect().width > 100")
        table(page, "map2d")
        assert len(page.local) > 5 and page.external == [] and page.failed == [] and page.errors == []


# ---- Round 6: number format, Monitoring, Survey, grains, exports (AC-59 .. AC-73) ----------------------------------
# Expected values are computed here in plain Python from the fixture files (conftest.monitor_rows / survey_rows), not by app code.

@contextmanager
def _server():
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(10)


def _ids6(base):
    return {(d["path"], d["sheet"]): d["id"] for d in json.load(urllib.request.urlopen(f"{base}/api/datasets"))}


def _csv_rows(folder, name):
    import csv
    with open(Path(folder) / name, newline="") as f:
        return list(csv.DictReader(f))


def _tiles6(page):
    return {t.locator(".card-label").inner_text(): t for t in page.locator("ul.tiles > li.card.tile").all()}


def _mixed_dir(tmp_path, archetypes_dir, round6_dir):
    """One folder with shop/places/measures (round 5), monitor/quiet/survey (round 6) and book.xlsx (sheet Revenue)."""
    import shutil
    from tests.conftest import write_xlsx
    root = tmp_path / "mixed"
    root.mkdir()
    for n in ("shop.csv", "places.csv", "measures.csv"):
        shutil.copy(Path(archetypes_dir) / n, root / n)
    for n in ("monitor.csv", "survey.csv", "quiet.csv"):
        shutil.copy(Path(round6_dir) / n, root / n)
    write_xlsx(root / "book.xlsx", {"Revenue": [("month", "team", "revenue"),
                                                *[(("date", 45292 + 31 * i), "AB"[i % 2], 100 + i) for i in range(6)]]})
    return root


def test_AC_59(make_client, tmp_path):
    root = tmp_path / "fmt"
    root.mkdir()
    (root / "orders.csv").write_text("order_id,year,region,amount\n" + "".join(
        f"{10045 + i},{2023 + i % 2},{('North', 'South')[i % 2]},{12345 + 100 * i}\n" for i in range(12)))
    (root / "places.csv").write_text("lat,lon,place_id,year,season,pop\n" + "".join(
        f"{-40 + 4 * i},{-120 + 12 * i},{10045 + i},{2000 + i},{1950 + i},{12345 + i}\n" for i in range(20)))
    (root / "ids.csv").write_text("lat,lon,place_id\n" + "".join(f"{-40 + 4 * i},{-120 + 12 * i},{10045 + i}\n" for i in range(20)))
    client = make_client(root)
    oid = _app_id(client, "orders.csv")
    for q in ("", "?app=explorer"):
        html = client.get(f"/datasets/{oid}{q}").text
        text = _text(html)
        assert "12,345" in text and "10045" in text and "2023" in text and "2024" in text, q
        for banned in ("2,023", "2,024", "10,045", "10,046"):
            assert banned not in html, (q, banned)
    separated = [f"{v:,}" for i in range(20) for v in (2000 + i, 1950 + i, 10045 + i)]  # year, year-like and id values with a comma
    with _server() as base:
        pid = _ids6(base)[("places.csv", None)]
        with _browse(f"{base}/datasets/{pid}") as page:
            _click_point(page, 3)
            d = _details(page)
            assert d["pop"] == "12,348" and d["year"] == "2003" and d["place_id"] == "10048" and d["season"] == "1953", d
            tip = _hover(page, page.locator("figure[data-kind=map2d] .js-plotly-plot .point").nth(5))
            label = page.evaluate("document.querySelector('figure[data-kind=map2d] .js-plotly-plot').data[0].name")
            page.get_by_role("button", name="View as table").first.click()
            table = page.locator("table.plot-table").first.inner_text()
            assert not any(s in table for s in separated), table[:300]
            assert not any(s in page.inner_text("main") for s in separated)
            assert page.errors == []
            assert not any(s in tip for s in separated), f"tooltip of the {label} colour column: {tip!r}"
        # Board gate 187: an identifier colour column (place_id) reads "10050" in the tooltip, never "10,050"
        with _browse(f"{base}/datasets/{_ids6(base)[('ids.csv', None)]}") as page:
            pts = page.locator("figure[data-kind=map2d] .js-plotly-plot .point")
            tips = []
            for k in range(pts.count()):
                tips.append(_hover(page, pts.nth(k)))
            assert any(t.strip().endswith("10050") or "10050" in t for t in tips), tips
            assert not any(s in t for t in tips for s in separated), tips


def test_AC_60(make_client, tmp_path):
    root = tmp_path / "count"
    root.mkdir()
    # 12 rows; tier a/b (6 each), grp x/y (5 each) and one row z: the filters below leave 1 and 0 rows
    (root / "five.csv").write_text("tier,grp,n,m\n" + "".join(
        f"{'ab'[i % 2]},{'z' if i == 1 else 'xy'[i % 3 % 2]},{i},{12 - i}\n" for i in range(12)))
    (root / "one.csv").write_text("cat,n,m\na,1,5\n")
    client = make_client(root)
    banned = re.compile(r"\b1 (rows|points)\b")
    one = client.get(f"/datasets/{_app_id(client, 'one.csv')}?app=explorer").text
    assert not banned.search(one)
    assert all(s in one for s in ("1 of 1 row", "1 of 1 point", "First 1 row"))
    fid = _app_id(client, "five.csv")
    page12 = client.get(f"/datasets/{fid}?app=explorer").text
    assert "12 of 12 rows" in page12 and "12 of 12 points" in page12
    for query, row, point in (("f.grp=z", "1 of 1 row", "1 of 1 point"), ("f.grp=z&f.tier=a", "0 of 0 rows", "0 of 0 points")):
        html = client.get(f"/datasets/{fid}?app=explorer&{query}").text
        assert row in html and point in html, (query, re.findall(r"\d+ of [\d,]+ (?:rows?|points?)", html))
        assert not banned.search(html), query
    # tooltips: hover the single histogram bar and the single scatter point of the one-row file
    with _server() as base:
        with _browse(f"{base}/datasets/{_ids6(base)[('one.csv', None)]}?app=explorer") as page:
            hovers = []
            for kind in ("histogram", "scatter"):
                fig = page.locator(f"figure[data-kind={kind}]").first
                fig.scroll_into_view_if_needed()
                pt = fig.locator(".barlayer .point, .scatterlayer .point").first.bounding_box()
                page.mouse.move(pt["x"] + pt["width"] / 2 - 3, pt["y"] + pt["height"] / 2)
                page.mouse.move(pt["x"] + pt["width"] / 2, pt["y"] + pt["height"] / 2)
                page.wait_for_selector(".hoverlayer .hovertext")
                hovers.append(page.locator(".hoverlayer .hovertext").first.text_content().replace("\xa0", " "))
            assert not any(banned.search(h) for h in hovers), hovers
            strings = page.evaluate("[...document.querySelectorAll('.js-plotly-plot')].map(g => JSON.stringify(g.data.map(t => [t.hovertemplate, t.text])))")
            assert not any(banned.search(s) for s in strings), strings
            assert page.errors == []


def test_AC_61(arch):
    base, ids = arch
    with _browse(f"{base}/datasets/{ids['shop.csv']}?app=explorer") as page:
        names = page.eval_on_selector_all("form.filters select", "e => e.map(s => s.name)")
        hit = None
        for fid in page.evaluate("[...document.querySelectorAll('[data-kind=\"bar\"]')].map(f => f.id)"):
            label = page.evaluate("id => document.querySelector('#' + id + ' .js-plotly-plot')._fullLayout.xaxis.title.text", fid)
            if "f." + label in names:
                hit = fid
        assert hit, names
        page.locator(f"#{hit} .plot").scroll_into_view_if_needed()
        c = page.evaluate("""id => { const r = document.querySelector('#' + id + ' .barlayer .point').getBoundingClientRect();
            return {x: r.x + r.width / 2, y: r.y + r.height / 2}; }""", hit)
        page.mouse.move(c["x"] - 2, c["y"] - 2)
        page.mouse.move(c["x"], c["y"])
        page.wait_for_timeout(300)
        assert page.evaluate("id => getComputedStyle(document.querySelector('#' + id + ' .nsewdrag')).cursor", hit) == "pointer"
        assert page.errors == []
    # the Business leaderboard shows the same cursor
    with _browse(f"{base}/datasets/{ids['shop.csv']}") as page:
        assert _bar_cursor(page, "web") == "pointer"
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    para = re.search(r"- Cross-filter \(AC-39[^\n]*\n(?:  [^\n]*\n)+", design).group(0)
    assert "AC-61" in para and "Explorer bars" in para and "pointer" in para and "Business leaderboard" in para


def test_AC_62(make_client, tmp_path):
    import csv
    root = tmp_path / "range"
    root.mkdir()
    # Business: 8 months, month sums 14,000 .. 16,000; Explorer: one line over 40 days with values 14,000 .. 16,000
    with open(root / "flat.csv", "w", newline="") as f:
        csv.writer(f).writerows([("date", "store", "amount"), *[
            (f"2024-{m:02d}-{d:02d}", s, 7000 + 1000 * (m - 1) // 7) for m in range(1, 9) for d, s in ((3, "N"), (17, "S"))]])
    with open(root / "ts.csv", "w", newline="") as f:
        csv.writer(f).writerows([("day", "level", "other"), *[(f"2024-02-{i + 1:02d}" if i < 28 else f"2024-03-{i - 27:02d}",
                                                              14000 + 50 * i, 3 + i % 4) for i in range(40)]])
    make_client(root)
    with _server() as base:
        ids = _ids6(base)
        probe = """() => ({lines: [...document.querySelectorAll('.js-plotly-plot')].filter(g => g.data.some(t => t.type === 'scatter' && /lines/.test(t.mode || '')))
              .map(g => [g._fullLayout.yaxis.range[0], g._fullLayout.yaxis.rangemode]),
            bars: [...document.querySelectorAll('[data-kind="bar"] .js-plotly-plot')].map(g => g._fullLayout.xaxis.range[0] + ':' + g._fullLayout.yaxis.range[0])})"""
        for name, query in (("flat.csv", "?app=business&period=all"), ("ts.csv", "?app=explorer")):
            with _browse(f"{base}/datasets/{ids[(name, None)]}{query}") as page:
                got = page.evaluate(probe)
                assert got["lines"] and all(lo > 0 and mode != "tozero" for lo, mode in got["lines"]), (name, got)
                assert all(b.startswith("0:") or b.endswith(":0") for b in got["bars"]), (name, got)
                assert page.errors == []
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    rules = design.split("## Global chart rules", 1)[1].split("\n## ", 1)[0]
    assert "bars only" in rules and "zero baseline" in rules and "automatic y-range" in rules


def test_AC_63(make_client, tmp_path, archetypes_dir, round6_dir):
    from pptx import Presentation
    client = make_client(_mixed_dir(tmp_path, archetypes_dir, round6_dir))
    sheets = {(d["path"], d["sheet"]): d["id"] for d in client.get("/api/datasets").json()}
    cases = [(("shop.csv", None), "?app=business", "Business overview", "shop.csv"),
             (("shop.csv", None), "?app=explorer", None, "shop.csv"),
             (("places.csv", None), "?app=map", "Map overview", "places.csv"),
             (("monitor.csv", None), "?app=monitoring", "Monitoring overview", "monitor.csv"),
             (("survey.csv", None), "?app=survey", "Survey overview", "survey.csv"),
             (("measures.csv", None), "", None, "measures.csv"),
             (("book.xlsx", "Revenue"), "", None, "book.xlsx")]
    for key, query, title, name in cases:
        r = client.get(f"/datasets/{sheets[key]}/export.pptx{query}")
        assert r.status_code == 200, key
        boxes = [s for s in list(Presentation(io.BytesIO(r.content)).slides)[0].shapes if s.has_text_frame]
        size = lambda b: b.text_frame.paragraphs[0].runs[0].font.size.pt
        first, second = boxes[0].text_frame.text, boxes[1].text_frame.text
        assert first and (title is None or first == title), (key, first)
        assert second.startswith(name) and (key[1] is None or key[1] in second), (key, second)
        assert size(boxes[1]) < size(boxes[0]), (key, size(boxes[0]), size(boxes[1]))


def test_AC_64(make_client, round6_dir, archetypes_dir, tmp_path):
    client = make_client(round6_dir)
    app = lambda c, n: c.get(f"/api/datasets/{_app_id(c, n)}/app").json()
    want = {"monitor.csv": ("monitoring", "R4", ["monitoring", "explorer"]), "quiet.csv": ("monitoring", "R4", ["monitoring", "explorer"]),
            "survey.csv": ("survey", "R5", ["survey", "business", "explorer"]), "orders.csv": ("explorer", "R3", ["explorer"])}
    for name, (a, rule, qualifies) in want.items():
        got = app(client, name)
        assert (got["app"], got["rule"], got["qualifies"]) == (a, rule, qualifies), name
    # survey.csv has a date column and an age column, yet opens as Survey (R5 before R2); Business stays in View-as
    html = _html(client, "survey.csv")
    assert "App: Survey (rule R5)" in html and "App: Monitoring (rule R4)" in _html(client, "monitor.csv")
    assert re.findall(r'<nav class="view-as" aria-label="View as">(.*?)</nav>', html, re.S) and ">Business<" in html
    # the round 5 fixtures keep their app: shop.csv opens as Business with View-as
    arch = make_client(archetypes_dir)
    got = {n: (app(arch, n)["app"], app(arch, n)["rule"]) for n in ("shop.csv", "places.csv", "measures.csv", "sparse.csv")}
    assert got == {"shop.csv": ("business", "R2"), "places.csv": ("map", "R1"), "measures.csv": ("explorer", "R3"),
                   "sparse.csv": ("explorer", "R3")}
    assert ">Business<" in _html(arch, "shop.csv") and ">Explorer<" in _html(arch, "shop.csv")
    # amount guard: shop.csv without revenue (units 1..7) is a survey
    root = tmp_path / "guard"
    root.mkdir()
    rows = [("date", "store", "channel", "product", "units")]
    rows += [(f"2024-0{1 + i % 6}-01", ("N", "S")[i % 2], ("web", "shop")[i % 3 % 2], ("p", "q", "r")[i % 3], 1 + i % 7) for i in range(24)]
    (root / "shop.csv").write_text("\n".join(",".join(map(str, r)) for r in rows) + "\n")
    g = make_client(root)
    assert (app(g, "shop.csv")["app"], app(g, "shop.csv")["rule"]) == ("survey", "R5")
    # four categoricals among seven columns (57% < 60%) is not a survey; a date + numbers and no categorical is monitoring
    (root / "shop.csv").unlink()
    (root / "s.csv").write_text("a,b,c,d,x,y,z\n" + "".join(
        f"{('p', 'q')[i % 2]},{('r', 's')[i % 3 % 2]},{('t', 'u')[i % 2]},{('v', 'w', 'k')[i % 3]},{i * 31},{i * 17},{i * 5}\n" for i in range(30)))
    (root / "mon.csv").write_text("t,v\n" + "".join(f"2024-01-{i + 1:02d},{i * 3.5}\n" for i in range(20)))
    g = make_client(root)
    assert app(g, "s.csv")["rule"] == "R3" and (app(g, "mon.csv")["app"], app(g, "mon.csv")["rule"]) == ("monitoring", "R4")


def test_AC_65(make_client, round6_dir, tmp_path):
    import csv
    import shutil
    from datetime import date, timedelta
    from statistics import fmean
    root = tmp_path / "mon"
    root.mkdir()
    shutil.copy(Path(round6_dir) / "monitor.csv", root / "monitor.csv")
    with open(root / "short.csv", "w", newline="") as f:  # 20 days only: no previous 30-day period
        csv.writer(f).writerows([("time", "level"), *[(f"2024-05-{i + 1:02d}", 10 + i) for i in range(20)]])
    with open(root / "wide.csv", "w", newline="") as f:
        csv.writer(f).writerows([("time", *[f"m{k}" for k in range(10)]), *[(f"2024-01-{i + 1:02d}", *[i + k for k in range(10)]) for i in range(30)]])
    make_client(root)
    rows = [(date.fromisoformat(r["time"]), float(r["temperature"]), float(r["humidity"])) for r in _csv_rows(root, "monitor.csv")]
    latest = rows[-1][0]

    def window(days, back):  # the days*back .. days*(back+1) days before the latest timestamp, half-open
        return [r for r in rows if latest - timedelta(days=days * (back + 1)) < r[0] <= latest - timedelta(days=days * back)]
    num = lambda v: f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"
    with _server() as base:
        ids = _ids6(base)
        for period in (7, 30, 90):
            cur, prev = window(period, 0), window(period, 1)
            with _browse(f"{base}/datasets/{ids[('monitor.csv', None)]}?period={period}") as page:
                tiles = _tiles6(page)
                assert list(tiles) == ["temperature", "humidity"]
                for k, name in ((1, "temperature"), (2, "humidity")):
                    t = tiles[name]
                    vals = [r[k] for r in cur]
                    assert t.locator(".card-value").inner_text() == num(vals[-1]), (period, name)
                    assert t.locator(".tile-range").inner_text().split() == ["Min", num(min(vals)), "Max", num(max(vals))], (period, name)
                    pct = round((fmean(vals) / fmean(r[k] for r in prev) - 1) * 100, 1)
                    arrow, word = ("▲", "up") if pct > 0 else ("▼", "down") if pct < 0 else ("▶", "no change")
                    got = " ".join(t.locator(".card-change").inner_text().split())
                    assert got == f"{arrow} {pct:+.1f}% {word}" if pct else got == f"{arrow} 0.0% {word}", (period, name, got)
                    assert t.locator("svg.spark polyline").count() == 1
                assert page.errors == []
        with _browse(f"{base}/datasets/{ids[('monitor.csv', None)]}?period=all") as page:
            for t in _tiles6(page).values():
                assert t.locator(".card-change").inner_text() == "n/a" and not set(t.inner_text()) & set("▲▼▶")
        with _browse(f"{base}/datasets/{ids[('short.csv', None)]}") as page:  # default 30 days, nothing before it
            t = _tiles6(page)["level"]
            assert t.locator(".card-change").inner_text() == "n/a" and not set(t.inner_text()) & set("▲▼▶")
            assert t.locator(".card-value").inner_text() == "29" and t.locator(".tile-range").inner_text().split() == ["Min", "10", "Max", "29"]
        with _browse(f"{base}/datasets/{ids[('wide.csv', None)]}") as page:  # gates 184/186: tiles cap at 8
            assert page.locator("ul.tiles > li.tile").count() == 8 and page.locator(".note").inner_text() == "8 of 10 measures"
            assert page.errors == []


def test_AC_66(make_client, round6_dir):
    from datetime import date, timedelta
    client = make_client(round6_dir)
    rows = [date.fromisoformat(r["time"]) for r in _csv_rows(round6_dir, "monitor.csv")]
    latest = rows[-1]
    mid = _app_id(client, "monitor.csv")
    for p in ("7", "30", "90", "all"):
        got = client.get(f"/api/datasets/{mid}/app?period={p}").json()
        want = [d.isoformat() for d in rows if p == "all" or d > latest - timedelta(days=int(p))]
        assert got["period"] == p and got["charts"][0]["data"]["x"] == want, p
    html = client.get(f"/datasets/{mid}").text
    nav = re.search(r'<nav class="periods" aria-label="Period">.*?</nav>', html, re.S).group(0)
    links = re.findall(r'<a href="([^"]*)"( aria-current="page")?>([^<]*)</a>', nav)
    assert [x[2] for x in links] == ["7 days", "30 days", "90 days", "All"] and [bool(x[1]) for x in links] == [False, True, False, False]
    assert [x[0].split("period=")[1] for x in links] == ["7", "30", "90", "all"]
    with _server() as base:
        url = f"{base}/datasets/{_ids6(base)[('monitor.csv', None)]}"
        with _browse(url) as page:
            page.get_by_role("link", name="90 days").click()
            page.wait_for_url(re.compile("period=90"))
            _settle(page)
            assert _query(page)["period"] == ["90"] and page.locator(".periods a[aria-current=page]").inner_text() == "90 days"
            assert page.evaluate("document.querySelector('.js-plotly-plot').data[0].x.length") == 90
        with _browse(url + "?period=90") as page:  # opening the URL shows the same period
            assert page.locator(".periods a[aria-current=page]").inner_text() == "90 days"
            assert page.evaluate("document.querySelector('.js-plotly-plot').data[0].x.length") == 90


def test_AC_67(make_client, round6_dir):
    from statistics import fmean, pstdev
    make_client(round6_dir)

    def spikes(name):  # |z| > 3 against the 30 points before each point (population stdev)
        y = [float(r["temperature"]) for r in _csv_rows(round6_dir, name)]
        out = [i for i in range(30, len(y)) if pstdev(y[i - 30:i]) and abs(y[i] - fmean(y[i - 30:i])) / pstdev(y[i - 30:i]) > 3]
        return y, out
    y, planted = spikes("monitor.csv")
    assert planted == [100] and spikes("quiet.csv")[1] == []  # hand-checked: only day 100 reads 60.0 among values 20..26
    day = _csv_rows(round6_dir, "monitor.csv")[100]["time"]
    mean7 = [fmean(y[max(0, i - 6):i + 1]) for i in range(len(y))]
    with _server() as base:
        ids = _ids6(base)
        with _browse(f"{base}/datasets/{ids[('monitor.csv', None)]}?period=all") as page:
            d = page.evaluate("""() => { const g = document.querySelector('.js-plotly-plot');
                return {traces: g.data.map(t => ({name: t.name, mode: t.mode, y: t.y, x: t.x, yaxis: t.yaxis || 'y'})),
                  labels: [...g.querySelectorAll('.textpoint text')].map(e => e.textContent), y2: !!g.layout.yaxis2}; }""")
            main, mean, spike = d["traces"]
            assert (main["name"], mean["name"], spike["name"]) == ("temperature", "7-point mean", "spike")
            assert main["y"] == y and all(abs(a - b) < 1e-6 for a, b in zip(mean["y"][6:], mean7[6:]))
            assert {t["yaxis"] for t in d["traces"]} == {"y"} and not d["y2"]
            assert spike["x"] == [day] and "markers" in spike["mode"] and "text" in spike["mode"]
            assert d["labels"] == ["spike"] and page.errors == []
        with _browse(f"{base}/datasets/{ids[('quiet.csv', None)]}?period=all") as page:
            assert page.evaluate("document.querySelector('.js-plotly-plot').data.map(t => t.name)") == ["temperature", "7-point mean"]
            assert page.locator(".textpoint").count() == 0 and "spike" not in page.locator(".js-plotly-plot").first.inner_text()


def test_AC_68(make_client, round6_dir):
    from collections import Counter
    make_client(round6_dir)
    rows = _csv_rows(round6_dir, "survey.csv")
    with _server() as base:
        url = f"{base}/datasets/{_ids6(base)[('survey.csv', None)]}"
        with _browse(url) as page:
            got = page.evaluate("""() => [...document.querySelectorAll('.questions figure[data-kind=bar]')].map(f => {
                const gd = f.querySelector('.js-plotly-plot'), m = {}, order = [];
                for (const t of gd.data) t.y.forEach((l, i) => { m[l] = t.x[i]; order.push(l); });
                return {m, order}; })""")
            assert len(got) == 3  # the three non-Likert questions: gender, region, city
            gender, region, city = sorted(got, key=lambda v: len(v["order"]))
            assert gender["m"] == dict(Counter(r["gender"] for r in rows)) and region["m"] == dict(Counter(r["region"] for r in rows))
            counts = sorted(Counter(r["city"] for r in rows).values(), reverse=True)  # 12 cities: 4,4,4,4,3 x 8
            assert city["order"][-1] == "Other" and len(city["order"]) == 11
            assert [city["m"][l] for l in city["order"][:-1]] == counts[:10]
            assert city["m"]["Other"] == sum(counts[10:]) == 6 and sum(city["m"].values()) == 40
            # layout: two per row at desktop width; Respondents holds the age histogram only
            tops = page.evaluate("[...document.querySelectorAll('.questions figure[data-kind=bar]')].map(f => Math.round(f.getBoundingClientRect().top + scrollY))")
            assert tops[0] == tops[1] and tops[2] > tops[0]
            sec = page.locator("section.block:has(h2:text-is('Respondents'))")
            assert sec.locator("figure[data-kind=histogram]").count() == 1 and "age" in sec.inner_text()
            assert "respondent_id" not in sec.inner_text()
            assert page.evaluate("document.querySelector('section.block figure[data-kind=histogram] .js-plotly-plot').data[0].y.reduce((a, b) => a + b, 0)") == 40
            assert page.errors == []
        with _browse(url, width=375) as page:  # one chart per row at phone width
            tops = page.evaluate("[...document.querySelectorAll('.questions figure.chart')].map(f => Math.round(f.getBoundingClientRect().top + scrollY))")
            assert tops == sorted(set(tops)) and page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.errors == []


def test_AC_69(make_client, round6_dir):
    from collections import Counter
    rows = _csv_rows(round6_dir, "survey.csv")
    scales = {"q_service": ["Very dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very satisfied"],
              "q_easy": ["Strongly disagree", "Disagree", "Neither agree nor disagree", "Agree", "Strongly agree"],
              "q_visits": ["Never", "Rarely", "Sometimes", "Often", "Always"], "q_score": ["1", "2", "3", "4", "5"]}

    def hue(c):
        c = c.strip()
        v = [int(x) for x in re.findall(r"\d+", c)[:3]] if c.startswith("rgb") else [int(c[i:i + 2], 16) for i in (1, 3, 5)]
        r, g, b = (x / 255 for x in v)
        mx, mn = max(r, g, b), min(r, g, b)
        d = mx - mn
        if d < 0.08:
            return None  # grey
        return ((g - b) / d % 6 if mx == r else (b - r) / d + 2 if mx == g else (r - g) / d + 4) * 60
    make_client(round6_dir)
    with _server() as base:
        with _browse(f"{base}/datasets/{_ids6(base)[('survey.csv', None)]}") as page:
            figs = page.evaluate("""() => [...document.querySelectorAll('figure[data-kind=likert]')].map(f => { const gd = f.querySelector('.js-plotly-plot');
                return {barmode: gd.layout.barmode, range: gd._fullLayout.xaxis.range, orient: gd.data[0].orientation,
                  traces: gd.data.map(t => ({name: String(t.name), pct: t.x[0], count: t.customdata[0], colour: t.marker.color}))}; })""")
            assert len(figs) == 4
            for fig, (q, scale) in zip(figs, scales.items()):
                c = Counter(r[q] for r in rows)
                assert fig["barmode"] == "stack" and fig["range"] == [0, 100] and fig["orient"] == "h", q
                assert [t["name"] for t in fig["traces"]] == scale, q  # scale order, all levels
                assert [t["count"] for t in fig["traces"]] == [c.get(l, 0) for l in scale], q
                assert [round(t["pct"], 6) for t in fig["traces"]] == [round(c.get(l, 0) / 40 * 100, 6) for l in scale], q
                assert abs(sum(t["pct"] for t in fig["traces"]) - 100) < 1e-9, q
                cols = [t["colour"] for t in fig["traces"]]
                assert hue(cols[2]) is None, (q, "neutral middle is grey", cols[2])
                h1, h2 = hue(cols[0]), hue(cols[4])
                assert h1 is not None and h2 is not None and min(abs(h1 - h2), 360 - abs(h1 - h2)) > 60, (q, cols)
            assert page.errors == []


def test_AC_70(make_client, round6_dir):
    from collections import Counter
    rows = _csv_rows(round6_dir, "survey.csv")
    questions = ["gender", "region", "city", "q_service", "q_easy", "q_visits", "q_score"]
    make_client(round6_dir)
    with _server() as base:
        url = f"{base}/datasets/{_ids6(base)[('survey.csv', None)]}"
        form = re.search(r'<form class="crosstab".*?</form>', urllib.request.urlopen(url).read().decode(), re.S).group(0)
        selects = re.findall(r'<select[^>]*name="(row|col)"[^>]*>(.*?)</select>', form, re.S)
        assert [n for n, _ in selects] == ["row", "col"]
        for _, body in selects:
            assert re.findall(r'<option value="([^"]*)"', body) == questions
        read = """() => { const gd = document.querySelector('figure[data-kind=crosstab] .js-plotly-plot'), t = gd.data[0];
            return {x: t.x, y: t.y, text: t.text, z: t.z}; }"""

        def check(page, rq, cq):
            d = page.evaluate(read)
            c = Counter((r[rq], r[cq]) for r in rows)
            tot = Counter(r[rq] for r in rows)
            for i, rl in enumerate(d["y"]):
                shares = []
                for j, cl in enumerate(d["x"]):
                    n = c.get((str(rl), str(cl)), 0)
                    assert d["z"][i][j] == n, (rq, cq, rl, cl)
                    assert d["text"][i][j] == f"{n} ({n / tot[str(rl)] * 100:.1f}%)", (rq, cq, rl, cl, d["text"][i][j])
                    shares.append(n / tot[str(rl)] * 100)
                assert abs(sum(shares) - 100) < 1e-9, (rq, cq, rl)
            assert sum(sum(r) for r in d["z"]) == 40
        with _browse(url) as page:  # default: the first two questions
            check(page, "gender", "region")
            page.get_by_label("Column question").select_option("q_easy")
            page.wait_for_url(re.compile("col=q_easy"))
            _settle(page)
            assert _query(page)["row"] == ["gender"] and _query(page)["col"] == ["q_easy"]
            check(page, "gender", "q_easy")
            assert page.errors == []
        with _browse(url + "?row=q_easy&col=gender") as page:
            assert page.get_by_label("Row question").input_value() == "q_easy" and page.get_by_label("Column question").input_value() == "gender"
            check(page, "q_easy", "gender")


def test_AC_71(make_client, tmp_path, archetypes_dir, round6_dir):
    import openpyxl
    from pptx import Presentation
    client = make_client(_mixed_dir(tmp_path, archetypes_dir, round6_dir))
    xl = lambda n, q: openpyxl.load_workbook(io.BytesIO(client.get(f"/datasets/{_app_id(client, n)}/export.xlsx{q}").content))
    pp = lambda n, q: list(Presentation(io.BytesIO(client.get(f"/datasets/{_app_id(client, n)}/export.pptx{q}").content)).slides)
    first = lambda slide: [s.text_frame.text for s in slide.shapes if s.has_text_frame][0]
    wb = xl("monitor.csv", "?app=monitoring")
    assert wb.sheetnames[0] == "Data" and wb.sheetnames[-1] == "Summary" and wb["Summary"]["A1"].value == "Monitoring overview"
    assert sum(len(ws._charts) for ws in wb) == 1 and type(next(c for ws in wb for c in ws._charts)).__name__ == "LineChart"
    slides = pp("monitor.csv", "?app=monitoring")
    assert first(slides[0]) == "Monitoring overview" and sum(s.has_chart for sl in slides for s in sl.shapes) == 1
    wb = xl("survey.csv", "?app=survey")
    assert wb.sheetnames[0] == "Data" and wb.sheetnames[-1] == "Summary" and wb["Summary"]["A1"].value == "Survey overview"
    assert len([c for ws in wb for c in ws._charts if type(c).__name__ == "BarChart"]) >= 7
    slides = pp("survey.csv", "?app=survey")
    assert first(slides[0]) == "Survey overview"
    titled = {first(sl): any(s.has_chart for s in sl.shapes) for sl in slides[1:]}
    for q in ("gender", "region", "city", "q_service", "q_easy", "q_visits", "q_score"):
        assert titled.get(q) is True, (q, list(titled))


def test_AC_72(make_client, tmp_path):
    import csv
    from datetime import date, timedelta
    root = tmp_path / "grain"
    root.mkdir()

    def write(name, rows):
        with open(root / name, "w", newline="") as f:
            csv.writer(f).writerows([("date", "store", "amount"), *rows])
    start = date(2024, 1, 1)  # a Monday
    write("week.csv", [((start + timedelta(days=i)).isoformat(), "ab"[i % 2], 1000 + i) for i in range(100)])
    months = [(y, m) for y in range(2021, 2025) for m in range(1, 13) if (y, m) <= (2024, 3)]  # 1,155 days
    write("year.csv", [(f"{y}-{m:02d}-01", "ab"[m % 2], 10000 * (y - 2020) + 100 * m) for y, m in months])
    spans = (60, 61, 182, 183, 1096, 1097)  # day <= 60 < week <= 182 < month <= 1096 < year
    for span in spans:
        write(f"span{span}.csv", [((start + timedelta(days=i)).isoformat(), "ab"[i % 2], 5000 + i) for i in range(span + 1)])
    client = make_client(root)
    app = lambda n: client.get(f"/api/datasets/{_app_id(client, n)}/app").json()
    # weeks: full ISO weeks only (the partial last week is left out); 100 days = 14 full weeks + 2 days
    data = app("week.csv")
    full = [sum(1000 + i for i in range(7 * k, 7 * k + 7)) for k in range(14)]
    trend = next(c for c in data["charts"] if c["kind"] == "line")["data"]
    assert data["grain"] == "week" and trend["y"] == full
    assert trend["x"][0] == "2024-01-01" and all(date.fromisoformat(x).weekday() == 0 for x in trend["x"])
    card = data["cards"][0]
    assert (card["latest"], card["previous"]) == (full[-1], full[-2]) and f"{full[-1]:,}" in _text(_html(client, "week.csv"))
    # years: full calendar years only (2024 has three months)
    data = app("year.csv")
    sums = [sum(10000 * (y - 2020) + 100 * m for m in range(1, 13)) for y in (2021, 2022, 2023)]
    trend = next(c for c in data["charts"] if c["kind"] == "line")["data"]
    assert data["grain"] == "year" and trend["y"] == sums and trend["x"] == ["2021-01-01", "2022-01-01", "2023-01-01"]
    card = data["cards"][0]
    assert (card["latest"], card["previous"]) == (sums[-1], sums[-2]) and f"{sums[-1]:,}" in _text(_html(client, "year.csv"))
    assert {s: app(f"span{s}.csv")["grain"] for s in spans} == {60: "day", 61: "week", 182: "week", 183: "month", 1096: "month", 1097: "year"}


def test_AC_73(make_client, tmp_path, archetypes_dir, round6_dir):
    import openpyxl
    from pptx import Presentation
    client = make_client(_mixed_dir(tmp_path, archetypes_dir, round6_dir))
    mid = _app_id(client, "measures.csv")
    assert client.get(f"/api/datasets/{mid}/app").json()["qualifies"] == ["explorer"]
    charts = client.get(f"/api/datasets/{mid}/charts").json()["charts"]
    wb = openpyxl.load_workbook(io.BytesIO(client.get(f"/datasets/{mid}/export.xlsx").content))
    assert wb.sheetnames[0] == "Data" and wb.sheetnames[-1] == "Summary" and sum(len(ws._charts) for ws in wb) > 0
    assert "overview" not in str(wb["Summary"]["A1"].value).lower()
    slides = list(Presentation(io.BytesIO(client.get(f"/datasets/{mid}/export.pptx").content)).slides)
    assert len(slides) == 1 + len(charts)
    assert sum(s.has_chart for sl in slides for s in sl.shapes) == len([c for c in charts if c["kind"] not in ("heatmap", "table")]) > 0
    # Board gate 186: the client-facing title slide says "Data overview", not the internal word "Explorer"
    assert [s.text_frame.text for s in slides[0].shapes if s.has_text_frame][0] == "Data overview"


# ---- Round 7: portal, upload, scan, tiles, theme (AC-74 .. AC-87; Board gates 189, 190, 193) ----------------------
# Self-contained copies of the engineers' browser checks. Round 7 pages are opened with _ctx7 (own context options,
# off-host requests aborted and listed in page.external).

@contextmanager
def _ctx7(base, width=1280, height=900, **ctx):
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={"width": width, "height": height}, **ctx).new_page()
        page.external, page.errors = [], []

        def route(r):
            if r.request.url.startswith(base):
                r.continue_()
            else:
                page.external.append(r.request.url)
                r.abort()
        page.route("**/*", route)
        page.on("console", lambda m: m.type == "error" and page.errors.append(m.text))
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        yield page
        b.close()


def _stay_on_scan(page, base):
    page.route(f"{base}/datasets/**", lambda r: r.abort())


def _tile_order(page):
    return page.evaluate("[...document.querySelectorAll('.grid > .ws-tile')].map(t => t.dataset.tile)")


def _listing(client):
    return sorted((d["path"], d["rows"], d["columns"]) for d in client.get("/api/datasets").json())


def _apps(client):
    return {d["path"]: client.get(f"/api/datasets/{d['id']}/app").json()["app"] for d in client.get("/api/datasets").json()}


def test_AC_74(make_client, data_dir, tmp_path):
    html = make_client(data_dir).get("/").text  # started on a folder: the two tables still follow the portal
    at = html.index('class="portal"')
    assert html.count("<h1>DataBoot</h1>") == 1 and html.count('class="portal"') == 1
    for caption in ("Could not be read", "Other files"):
        assert html.index(f"<caption><h2>{caption}</h2></caption>") > at
    assert re.search(r'<input[^>]*type="file"[^>]* multiple>\s*<label[^>]*>Choose files</label>', html)
    assert re.search(r'<input[^>]*type="file"[^>]* webkitdirectory>\s*<label[^>]*>Choose folder</label>', html)
    empty = tmp_path / "empty"
    empty.mkdir()
    (tmp_path / "a.csv").write_text("x,y\n1,2\n3,4\n")
    (tmp_path / "b.csv").write_text("p,q\n5,6\n7,8\n")
    (tmp_path / "picked" / "sub").mkdir(parents=True)
    (tmp_path / "picked" / "sub" / "c.csv").write_text("x,y\n1,2\n3,4\n")
    make_client(empty)
    with _server() as base:
        for width in (1280, 375):
            with _ctx7(base, width) as page:
                page.goto(base + "/")
                box = page.locator(".portal").bounding_box()
                assert abs(box["width"] - box["height"]) < 1, box
                radius = page.evaluate("getComputedStyle(document.querySelector('.portal')).borderTopLeftRadius")
                assert float(radius.rstrip("%px")) * (box["width"] / 100 if radius.endswith("%") else 1) >= box["width"] / 2 - 1, radius
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
                assert page.get_by_text("Choose files").is_visible() and page.get_by_text("Choose folder").is_visible()
                assert page.locator("h1").count() == 1 and page.locator("h1").inner_text() == "DataBoot"
                assert page.external == [] and page.errors == []
        with _ctx7(base) as page:  # Choose files: several at once
            _stay_on_scan(page, base)
            page.goto(base + "/")
            page.set_input_files("#pick-files", [str(tmp_path / "a.csv"), str(tmp_path / "b.csv")])
            page.wait_for_url(base + "/scan")
            log = page.locator(".scan-log").text_content()
            assert "a.csv" in log and "b.csv" in log and page.errors == []
        with _ctx7(base) as page:  # Choose folder
            _stay_on_scan(page, base)
            page.goto(base + "/")
            page.set_input_files("#pick-folder", str(tmp_path / "picked"))
            page.wait_for_url(base + "/scan")
            assert "sub/c.csv" in page.locator(".scan-log").text_content() and page.errors == []
        with _ctx7(base) as page:  # a dropped file
            _stay_on_scan(page, base)
            page.goto(base + "/")
            page.evaluate("""() => { const dt = new DataTransfer(); dt.items.add(new File(['x,y\\n1,2\\n3,4\\n'], 'dropped.csv', {type: 'text/csv'}));
                document.getElementById('portal').dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true})); }""")
            page.wait_for_url(base + "/scan")
            assert "dropped.csv" in page.locator(".scan-log").text_content() and page.errors == []


def test_AC_75(make_client, data_dir, tmp_path):
    from tests.conftest import files_of, upload
    for pick in ("one", "several", "folder"):
        if pick == "folder":
            files, want = files_of(data_dir), data_dir
        else:
            names = ("sales.csv",) if pick == "one" else ("sales.csv", "points.tsv")
            files = {n: (data_dir / n).read_bytes() for n in names}
            want = tmp_path / pick
            want.mkdir()
            for n, b in files.items():
                (want / n).write_bytes(b)
        folder_run = make_client(want)
        expected = (_listing(folder_run), _apps(folder_run))
        c = make_client(tmp_path / f"empty-{pick}")
        assert upload(c, files).status_code == 200, pick
        assert (_listing(c), _apps(c)) == expected, pick
        if pick == "folder":
            assert "sub/records.json" in [p for p, _, _ in _listing(c)]  # the relative path is kept
    # through the home page: a picked folder keeps sub/sales.csv, and the scan lists it like a folder run
    (tmp_path / "picked" / "sub").mkdir(parents=True)
    (tmp_path / "picked" / "sub" / "sales.csv").write_text("region,amount\nN,1\nS,2\nE,3\n")
    make_client(tmp_path / "empty-browser")
    with _server() as base:
        with _ctx7(base) as page:
            _stay_on_scan(page, base)
            page.goto(base + "/")
            page.set_input_files("#pick-folder", str(tmp_path / "picked"))
            page.wait_for_url(base + "/scan")
            line = page.locator(".scan-log li").first.text_content()
            got = json.load(urllib.request.urlopen(base + "/api/datasets"))
            assert [(d["path"], d["rows"], d["columns"]) for d in got] == [("sub/sales.csv", 3, 2)]
            assert line.startswith("sub/sales.csv") and "3 rows" in line, line
            assert page.errors == []
    expect = make_client(tmp_path / "picked")
    assert _listing(expect) == [("sub/sales.csv", 3, 2)]


def test_AC_76(tmp_path, monkeypatch, data_dir):
    import tempfile
    from fastapi.testclient import TestClient
    from tests.conftest import files_of, upload
    from app import config, main, upload as up
    monkeypatch.setenv("DATABOOT_DATA", str(data_dir))
    monkeypatch.setenv("DATABOOT_OUT", str(tmp_path / "out"))
    before = files_of(data_dir)
    with TestClient(main.app) as c:
        assert upload(c, {"a.csv": b"x\n1\n"}).status_code == 200
        first = config.get().data
        assert upload(c, {"b.csv": b"y\n2\n"}).status_code == 200
        folder = config.get().data
        assert folder != first and not first.exists()  # an earlier upload folder is deleted when the next one is done
        assert folder.is_dir() and folder.is_relative_to(tempfile.gettempdir())
        assert not folder.is_relative_to(config.ROOT) and not folder.is_relative_to(data_dir)
    assert not folder.exists() and not up.OWNED  # the app stopped
    assert files_of(data_dir) == before  # the launcher folder is unchanged
    assert not list(Path(tempfile.gettempdir()).glob(f"{folder.name}*"))


def test_AC_77(make_client, tmp_path, monkeypatch):
    import tempfile
    from tests.conftest import upload
    from app import upload as up
    tmp = Path(tempfile.gettempdir())
    # default cap: 2 GB (declared sizes only, nothing big is sent)
    c = make_client(tmp_path)
    before = set(tmp.glob("databoot-upload-*"))
    r = c.post("/upload", json={"files": [{"path": "big.bin", "size": 3 * 1024 ** 3}]})
    assert r.status_code == 413 and "2 GB" in r.json()["detail"] and "-Folder" in r.json()["detail"], r.text
    assert set(tmp.glob("databoot-upload-*")) == before and not up.OWNED and c.get("/api/datasets").json() == []
    # a small cap: declared total over the cap, and real bytes over the declared size; none of it is kept or listed
    monkeypatch.setenv("DATABOOT_UPLOAD_CAP", "10")
    r = c.post("/upload", json={"files": [{"path": "a.csv", "size": 6}, {"path": "b.csv", "size": 6}]})
    assert r.status_code == 413 and "-Folder" in r.json()["detail"] and not up.OWNED
    batch = c.post("/upload", json={"files": [{"path": "a.csv", "size": 4}, {"path": "b.csv", "size": 4}]}).json()["batch"]
    (folder,) = up.OWNED
    assert c.put(f"/upload/{batch}", params={"path": "a.csv"}, content=b"1234").status_code == 200
    assert c.put(f"/upload/{batch}", params={"path": "b.csv"}, content=b"1234567890").status_code == 413
    assert not folder.exists() and not up.OWNED and c.post(f"/upload/{batch}/done").status_code == 404
    assert c.get("/api/datasets").json() == []
    # the page shows the message and sends nothing
    monkeypatch.setenv("DATABOOT_UPLOAD_CAP", "1000")
    for n in ("big", "big2"):
        (tmp_path / f"{n}.csv").write_text("x\n" + "1\n" * 800)
    make_client(tmp_path / "nothing")
    with _server() as base:
        with _ctx7(base) as page:
            page.goto(base + "/")
            sent = []
            page.on("request", lambda q: "/upload" in q.url and sent.append(q.url))
            page.set_input_files("#pick-files", [str(tmp_path / "big.csv"), str(tmp_path / "big2.csv")])
            alert = page.locator("[role=alert]")
            alert.wait_for()
            assert "1,000 bytes" in alert.inner_text() and "-Folder" in alert.inner_text()
            assert sent == [] and page.url == base + "/" and "big.csv" not in page.locator("main").inner_text()
        with _ctx7(base) as page:  # the server refuses when the page's own check is skipped
            page.goto(base + "/")
            page.evaluate("document.getElementById('portal').dataset.cap = '999999'")
            page.set_input_files("#pick-files", str(tmp_path / "big.csv"))
            alert = page.locator("[role=alert]")
            alert.wait_for()
            assert "-Folder" in alert.inner_text() and "big.csv" not in page.locator("main").inner_text()
        assert json.load(urllib.request.urlopen(base + "/api/datasets")) == []


SCAN_LINE = re.compile(r"^(?P<path>.+?)(?: - (?P<sheet>.+?))?  [\d,]+ rows?  T\d+ N\d+ C\d+ G\d+  -> (?P<app>[A-Z]+) \(rule (?P<rule>R\d)\)$")
SCAN_RECORD = """() => { window.__t = {}; new MutationObserver(ms => ms.forEach(m => {
    const li = m.target; if (li.tagName !== 'LI' || li.hidden) return;
    const i = [...li.parentNode.children].indexOf(li); window.__t[i] = window.__t[i] || performance.now(); }))
    .observe(document, {attributes: true, subtree: true, attributeFilter: ['hidden']}); }"""


def test_AC_78(make_client, archetypes_dir):
    import html as htmllib
    from tests.conftest import files_of, upload
    client = make_client(archetypes_dir)
    assert upload(client, {**files_of(archetypes_dir), "broken.xlsx": b"not a zip file"}).status_code == 200
    page_html = client.get("/scan").text
    got = [htmllib.unescape(m) for m in re.findall(r"<li[^>]*>(.*?)</li>", page_html.split("</ol>")[0])]
    datasets = client.get("/api/datasets").json()
    assert len(got) == len(datasets) + 2
    for line, d in zip(got, datasets):
        m = SCAN_LINE.match(line)
        assert m and m["path"] == d["path"], line
        app = client.get(f"/api/datasets/{d['id']}/app").json()
        assert (m["app"], m["rule"]) == (app["app"].upper(), app["rule"])
        assert f"{d['rows']:,} row" in line
    assert any(re.match(r"^shop\.csv  [\d,]+ rows  T1 N\d C\d G0  -> BUSINESS \(rule R2\)$", x) for x in got)
    assert got[-2] == "broken.xlsx  not a valid xlsx" and got[-1] == "0 bytes uploaded to the internet"
    first = datasets[0]["id"]
    assert f'id="open-workspace" href="/datasets/{first}">Open workspace</a>' in page_html
    with _server() as base:
        with _ctx7(base) as page:  # lines appear one after another, all within 2.5 s
            _stay_on_scan(page, base)
            page.add_init_script("(" + SCAN_RECORD + ")()")
            t0 = time.monotonic()
            page.goto(base + "/scan")
            n = page.locator(".scan-log li").count()
            assert n == len(got) and n > 3
            assert page.locator("#open-workspace").is_visible()  # visible from the start
            page.wait_for_function(f"Object.keys(window.__t).length === {n}", timeout=5000)
            assert time.monotonic() - t0 < 2.5 + 1.5
            t = page.evaluate("window.__t")
            step = min(350, 2500 / n)
            assert t["1"] - t["0"] > step * 0.6 and t[str(n - 1)] - t["0"] < 2500 + 300, t
            assert page.external == [] and page.errors == []
        with _ctx7(base) as page:  # the first dataset opens by itself after the last line
            page.goto(base + "/scan")
            page.wait_for_url(f"{base}/datasets/{first}", timeout=6000)
            assert page.errors == []


def test_AC_79(make_client, data_dir, archetypes_dir):
    client = make_client(data_dir)
    ids = _ids(client)
    i = ids[("sales.csv", None)]
    html = client.get(f"/datasets/{i}").text
    header, main = html.split("<main", 1)
    links = re.findall(r'<a href="/datasets/(\w+)"( aria-current="page")?>([^<]*)</a>', header)
    assert len(links) == len(ids) and [k for k, cur, _ in links if cur] == [i]
    assert "sub/book.xlsx - Lookup" in [n for _, _, n in links]
    assert 'class="app-badge">App: Business (rule R2)<' in html
    assert re.search(r'<div class="archetype">APP: BUSINESS · RULE R2 · T1 N1 C1 · [\d,]+ ROWS</div>', html), re.findall(r'class="archetype">[^<]*', html)
    client = make_client(archetypes_dir)
    ids = _ids(client)
    shop = client.get(f"/datasets/{ids[('shop.csv', None)]}").text
    assert '<div class="archetype">APP: BUSINESS · RULE R2 · T1 N2 C3 · ' in shop
    places = client.get(f"/datasets/{ids[('places.csv', None)]}").text
    assert re.search(r'class="archetype">APP: MAP · RULE R\d · T\d N\d C\d G2 · [\d,]+ ROWS</div>', places)
    with _server() as base:
        for width, tracks in ((1280, 12), (375, 1)):
            with _ctx7(base, width) as page:
                page.goto(f"{base}/datasets/{_ids6(base)[('shop.csv', None)]}")
                _settle(page)
                cols = page.evaluate("getComputedStyle(document.querySelector('.grid')).gridTemplateColumns.split(' ').length")
                assert cols == tracks and page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, cols)
                assert page.errors == []


def test_AC_80(make_client, data_dir, archetypes_dir, round6_dir):
    figures = "figure.chart, ul.cards, ul.tiles, dl.kpis, table"
    cases = (("sales.csv", "?app=explorer", data_dir), ("shop.csv", "", archetypes_dir), ("places.csv", "", archetypes_dir),
             ("monitor.csv", "", round6_dir), ("survey.csv", "", round6_dir))
    for name, query, folder in cases:
        make_client(folder)
        with _server() as base:
            with _ctx7(base) as page:
                page.goto(f"{base}/datasets/{_ids6(base)[(name, None)]}{query}")
                page.wait_for_selector(".js-plotly-plot")
                found = page.evaluate("""(sel) => [...document.querySelectorAll(sel)].map(el => {
                    const t = el.closest('section.ws-tile');
                    return t && {label: t.getAttribute('aria-label'), h2s: [...t.querySelectorAll('h2')].map(h => h.textContent.trim()),
                                 move: !!t.querySelector('.ws-move'), expand: !!t.querySelector('.ws-expand')}})""", figures)
                assert len(found) >= 3 and all(found), (name, found)
                for f in found:
                    assert f["label"] in f["h2s"] and f["move"] and f["expand"], (name, f)
                for label in {f["label"] for f in found}:
                    assert page.get_by_role("region", name=label, exact=True).count() == 1, (name, label)
                assert page.errors == [], name
    golden = json.loads((ROOT / "tests/fixtures/round6_api.json").read_text(encoding="utf-8"))
    for fixture, folder in (("data_dir", data_dir), ("archetypes_dir", archetypes_dir), ("round6_dir", round6_dir)):
        client = make_client(folder)
        ids = _ids(client)
        mine = {k: v for k, v in golden.items() if k.startswith(fixture + "/")}
        assert mine and len(ids) == len(mine), fixture
        for key, want in mine.items():
            path, sheet = key.split("/", 1)[1].split("|")
            for part in ("app", "charts"):
                got = client.get(f"/api/datasets/{ids[(path, sheet or None)]}/{part}").json()
                assert {k: v for k, v in got.items() if k != "dataset"} == {k: v for k, v in want[part].items() if k != "dataset"}, (key, part)


def test_AC_81(make_client, round6_dir):
    make_client(round6_dir)
    with _server() as base:
        ids = _ids6(base)
        survey, monitor = (f"{base}/datasets/{ids[(n, None)]}" for n in ("survey.csv", "monitor.csv"))
        with _ctx7(base) as page:
            page.goto(monitor)
            _settle(page)
            monitor_default = _tile_order(page)
        with _ctx7(base) as page:
            page.goto(survey)
            _settle(page)
            first = _tile_order(page)
            assert len(first) >= 3
            src = page.locator(".grid > .ws-tile").nth(2).locator("figcaption .chart-title, .ws-head h2").first
            page.locator(".grid > .ws-tile").nth(0).scroll_into_view_if_needed()
            src.drag_to(page.locator(".grid > .ws-tile").nth(0))  # drag by the header onto the first tile's place
            moved = [first[2], first[0], first[1], *first[3:]]
            assert _tile_order(page) == moved
            page.reload()
            _settle(page)
            assert _tile_order(page) == moved  # after reload the dataset shows the new order
            page.goto(monitor)
            _settle(page)
            assert _tile_order(page) == monitor_default  # another dataset keeps its default order
            page.goto(survey)
            _settle(page)
            handle = page.locator(".grid > .ws-tile").nth(1).locator(".ws-move")  # keyboard: Alt+Arrow on the move handle
            handle.focus()
            page.keyboard.press("Alt+ArrowLeft")
            assert _tile_order(page) == [moved[1], moved[0], *moved[2:]]
            assert "position 1 of" in page.inner_text("#ws-live")
            assert page.evaluate("document.activeElement.classList.contains('ws-move')")
            page.keyboard.press("Alt+ArrowDown")
            assert _tile_order(page) == moved and "position 2 of" in page.inner_text("#ws-live")
            assert page.external == [] and page.errors == []


CHART3 = ".grid > .ws-tile[data-tile=chart-3]"  # the bar chart of the sales Explorer


def test_AC_82(make_client, data_dir):
    make_client(data_dir)
    is_open = lambda page: page.evaluate("document.querySelector('dialog#tile-dialog').open")  # noqa: E731
    with _server() as base:
        url = f"{base}/datasets/{_ids6(base)[('sales.csv', None)]}?app=explorer"
        with _ctx7(base) as page:
            page.goto(url)
            _settle(page)
            tile, btn = page.locator(CHART3), page.locator(f"{CHART3} .ws-expand")
            place = _tile_order(page)
            assert btn.get_attribute("aria-haspopup") == "dialog" and not is_open(page)
            btn.click()
            page.wait_for_selector("dialog[open] .js-plotly-plot svg.main-svg")
            assert is_open(page) and page.evaluate("document.querySelector('dialog[open] .js-plotly-plot').offsetWidth") > 0.8 * 1280
            page.keyboard.press("Escape")  # Esc closes and focus returns to the expand control
            tile.wait_for()
            assert not is_open(page) and _tile_order(page) == place
            assert page.evaluate("document.activeElement.classList.contains('ws-expand') && !!document.activeElement.closest('.grid')")
            btn.click()
            assert is_open(page)
            page.mouse.click(4, 4)  # the backdrop
            tile.wait_for()
            assert not is_open(page) and page.evaluate("document.activeElement.classList.contains('ws-expand')")
            before = (page.locator(".chips").count(), page.locator(".kpis dd").first.inner_text())
            btn.click()
            page.wait_for_selector("dialog[open] .js-plotly-plot svg.main-svg")
            page.wait_for_timeout(300)
            with page.expect_navigation():  # a bar click inside the overlay filters (script-triggered click, gate 193)
                page.evaluate("""() => document.querySelector('dialog[open] [data-kind="bar"] .plot')
                    .emit('plotly_click', {points: [{x: 'South', label: 'South', data: {}}]})""")
            page.wait_for_load_state("networkidle")
            assert _query(page)["f.region"] == ["South"]
            assert (page.locator(".chips").count(), page.locator(".kpis dd").first.inner_text()) == (1, "2") and before == (0, "6")
            page.wait_for_selector("dialog[open] #chart-3")  # the filtered tile is shown expanded again
            assert page.errors == []


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _contrast(a, b):
    lum = lambda rgb: 0.2126 * _lin(rgb[0]) + 0.7152 * _lin(rgb[1]) + 0.0722 * _lin(rgb[2])  # noqa: E731
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _nums(s):
    return [float(x) for x in re.findall(r"[\d.]+", s)]


def test_AC_83(make_client, data_dir):
    client = make_client(data_dir)
    css = client.get("/static/css/databoot.css").text
    js = client.get("/static/js/dashboard.js").text
    assert "@font-face" not in css and "prefers-color-scheme" not in css and "prefers-color-scheme" not in js
    for token in ("#050a12", "#4de1ff", "#ffb454", "color-scheme: dark", "monospace"):
        assert token in css, token
    with _server() as base:
        url = f"{base}/datasets/{_ids6(base)[('sales.csv', None)]}?app=explorer"
        for scheme in ("light", "dark"):
            with _ctx7(base, color_scheme=scheme) as page:
                page.goto(url)
                _settle(page)
                got = page.evaluate("""() => { const root = getComputedStyle(document.documentElement), tile = document.querySelector('.ws-tile');
                    const tint = e => getComputedStyle(e).color;
                    return {bg: getComputedStyle(document.body).backgroundColor, body: tint(document.body), scheme: root.colorScheme,
                      accent: root.getPropertyValue('--accent').trim(), amber: root.getPropertyValue('--amber').trim(),
                      label: tint(document.querySelector('.chart-title, .ws-head h2')),
                      muted: tint(document.querySelector('.muted, .chart-rule, .chart-count') || document.body),
                      mono: getComputedStyle(document.querySelector('.ws-head h2')).fontFamily,
                      tile: getComputedStyle(tile).backgroundImage, font: document.querySelector('.js-plotly-plot')._fullLayout.font.color,
                      fg: root.getPropertyValue('--fg').trim(), bar: document.querySelector('[data-kind=bar] .js-plotly-plot').data[0].marker.color,
                      axes: Object.keys(document.querySelector('[data-kind=bar] .js-plotly-plot')._fullLayout).filter(k => k.startsWith('yaxis')),
                      range: document.querySelector('[data-kind=bar] .js-plotly-plot')._fullLayout.yaxis.range,
                      y: document.querySelector('[data-kind=bar] .js-plotly-plot').data[0].y}; }""")
                assert got["bg"] == "rgb(5, 10, 18)" and got["scheme"] == "dark", (scheme, got["bg"])
                assert got["accent"] == "#4de1ff" and got["amber"] == "#ffb454" and "mono" in got["mono"].lower()
                assert got["font"] == got["fg"] == "#e6f1fa" and got["bar"] == "#4de1ff"
                assert got["axes"] == ["yaxis"] and got["range"][0] == 0 and got["y"] == sorted(got["y"], reverse=True)
                page_bg = _nums(got["bg"])
                stops = [_nums(s) for s in re.findall(r"rgba?\(([^)]*)\)", got["tile"])]
                assert len(stops) >= 2
                for s in stops:  # the tile gradient over the page, and with the cursor glow at its peak
                    alpha = s[3] if len(s) > 3 else 1
                    eff = [t * alpha + u * (1 - alpha) for t, u in zip(s[:3], page_bg)]
                    for e in (eff, [g * 0.12 + v * 0.88 for g, v in zip([77, 225, 255], eff)]):
                        for key in ("body", "label", "muted"):
                            assert _contrast(_nums(got[key])[:3], e) >= 4.5, (scheme, key, got[key], e)
                assert page.errors == []


def test_AC_84(make_client, data_dir):
    make_client(data_dir)
    with _server() as base:
        url = f"{base}/datasets/{_ids6(base)[('sales.csv', None)]}?app=explorer"
        with _ctx7(base) as page:
            page.add_init_script("""addEventListener('DOMContentLoaded', () => { window.__ends = document.getAnimations()
                .filter(a => a.effect.target && a.effect.target.classList.contains('ws-tile')).map(a => a.effect.getComputedTiming().endTime); })""")
            page.goto(url)
            ends = page.evaluate("window.__ends")
            assert len(ends) >= 3 and max(ends) <= 600, ends
            assert len(set(ends)) > 1  # one after another
            page.wait_for_timeout(700)
            assert page.evaluate("document.getAnimations().filter(a => a.effect.target.classList.contains('ws-tile') && a.playState !== 'finished').length") == 0
            _settle(page)
            assert page.evaluate("document.querySelector('.ws-tile').style.getPropertyValue('--mx')") == ""
            page.locator(CHART3).scroll_into_view_if_needed()
            box = page.locator(CHART3).bounding_box()
            page.mouse.move(box["x"] + 40, box["y"] + 30)
            page.mouse.move(box["x"] + 60, box["y"] + 50)
            assert page.evaluate("['--mx', '--my'].map(v => document.querySelector('.grid > .ws-tile[data-tile=chart-3]').style.getPropertyValue(v))") == ["60px", "50px"]
            assert page.evaluate("getComputedStyle(document.querySelector('.ws-tile')).backdropFilter") != "none"
            page.context.new_cdp_session(page).send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-transparency", "value": "reduce"}]})
            page.locator(f"{CHART3} .ws-expand").click()
            assert page.evaluate("[...document.querySelectorAll('*')].filter(e => getComputedStyle(e).backdropFilter !== 'none').length") == 0
            assert page.evaluate("getComputedStyle(document.querySelector('dialog[open]'), '::backdrop').backdropFilter") == "none"
            assert page.errors == []
        with _ctx7(base, reduced_motion="reduce") as page:
            page.goto(url)
            _settle(page)
            page.locator(CHART3).scroll_into_view_if_needed()
            box = page.locator(CHART3).bounding_box()
            page.mouse.move(box["x"] + 40, box["y"] + 30)
            page.mouse.move(box["x"] + 60, box["y"] + 50)
            assert page.evaluate("document.getAnimations().length") == 0
            assert page.evaluate("document.querySelector('.grid > .ws-tile[data-tile=chart-3]').style.getPropertyValue('--mx')") == ""
            assert page.evaluate("getComputedStyle(document.querySelector('.ws-expand')).transitionDuration") == "0s"


def _reach_mark(page, scope):
    """Tab from the top of the page until a chart mark inside `scope` has focus; return its aria-label."""
    page.evaluate("document.activeElement.blur(); window.scrollTo(0, 0)")
    for _ in range(150):
        page.keyboard.press("Tab")
        label = page.evaluate("""s => { const a = document.activeElement;
            return a && a.matches('path[role=button]') && a.closest(s) ? a.getAttribute('aria-label') : null; }""", scope)
        if label:
            return label
    raise AssertionError("Tab never reached a mark in " + scope)


def _press_navigates(page, key):
    with page.expect_navigation():
        page.keyboard.press(key)
    _settle(page)


def _keyboard_mark(page, scope, drills=False):
    """Tab to a mark, see its ring, Enter filters; then Space on the same mark removes the filter (a drilling leaderboard
    shows the next column on the filtered page, so Space adds that column's filter instead)."""
    column, category = _reach_mark(page, scope).split(": ", 1)
    width, style = page.evaluate("(() => { const s = getComputedStyle(document.activeElement); return [parseFloat(s.outlineWidth), s.outlineStyle]; })()")
    assert width == 3 and style == "solid", (scope, width, style)
    _press_navigates(page, "Enter")
    assert _query(page)["f." + column] == [category]
    if drills:
        column2, category2 = _reach_mark(page, scope).split(": ", 1)
        _press_navigates(page, "Space")
        assert _query(page)["f." + column2] == [category2] and column2 != column
        return
    page.evaluate("l => [...document.querySelectorAll('path[role=button]')].find(p => p.getAttribute('aria-label') === l).focus()", f"{column}: {category}")
    _press_navigates(page, "Space")
    assert "f." + column not in _query(page)


def test_AC_85(make_client, data_dir, archetypes_dir, round6_dir):
    make_client(data_dir)
    with _server() as base:
        with _ctx7(base) as page:  # Explorer bars and donut slices
            page.goto(f"{base}/datasets/{_ids6(base)[('sales.csv', None)]}?app=explorer")
            _settle(page)
            page.wait_for_selector('[data-kind="donut"] .slice path[role=button]')
            assert page.locator('[data-kind="bar"] path[role=button]').count() == 3
            _keyboard_mark(page, '[data-kind="bar"]')
            page.wait_for_selector('[data-kind="donut"] .slice path[role=button]')
            _keyboard_mark(page, '[data-kind="donut"]')
            assert page.errors == []
    make_client(archetypes_dir)
    with _server() as base:
        ids = _ids6(base)
        with _ctx7(base) as page:  # Business leaderboard (drills into the next column)
            page.goto(f"{base}/datasets/{ids[('shop.csv', None)]}")
            _settle(page)
            _keyboard_mark(page, "[data-leaderboard]", drills=True)
            assert page.errors == []
        with _ctx7(base) as page:  # Map top-region bars are not clickable today (gate 179, 193): no Tab stop either
            page.goto(f"{base}/datasets/{ids[('places.csv', None)]}")
            _settle(page)
            assert page.locator(".map-panel .barlayer .point path").count() == 4
            assert page.locator(".map-panel path[role=button], .map-panel path[tabindex]").count() == 0
    make_client(round6_dir)
    with _server() as base:
        with _ctx7(base) as page:  # Survey question bars
            page.goto(f"{base}/datasets/{_ids6(base)[('survey.csv', None)]}")
            _settle(page)
            _keyboard_mark(page, '.questions [data-kind="bar"]')
            assert page.errors == []


def test_AC_86(make_client, tmp_path):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "sales.csv").write_text("date,region,channel,amount\n" + "".join(
        f"2024-01-{1 + i % 6:02d},{('North', 'South', 'East')[i % 3]},{('web', 'shop')[i % 2]},{10 + i}\n" for i in range(12)))
    (tmp_path / "in" / "z_other.csv").write_text("x,y\n1,2\n3,4\n")
    make_client(tmp_path / "empty")
    with _server() as base:
        with _ctx7(base) as page:
            seen = []
            page.on("request", lambda r: seen.append(r.url))
            page.on("response", lambda r: r.status >= 400 and page.errors.append(f"{r.status} {r.url}"))
            page.goto(base + "/")
            page.set_input_files("#pick-files", [str(tmp_path / "in" / "sales.csv"), str(tmp_path / "in" / "z_other.csv")])
            page.wait_for_url(base + "/scan")
            page.locator("#open-workspace").click()
            page.wait_for_url("**/datasets/**")
            _settle(page)
            tiles = page.locator(".grid > .ws-tile")  # drag, expand and close a tile
            first = _tile_order(page)
            tiles.nth(0).scroll_into_view_if_needed()
            tiles.nth(2).locator(".ws-move").drag_to(tiles.nth(0))
            assert _tile_order(page) != first
            bar = page.locator(".grid > .ws-tile", has=page.locator("[data-kind=bar]")).first
            bar.locator(".ws-expand").click()
            page.wait_for_selector("dialog[open] [data-kind=bar] svg.main-svg")
            fig = page.locator("dialog[open] [data-kind=bar]")
            page.wait_for_timeout(300)
            fig.locator(".table-toggle").click()  # toggle the table view
            assert fig.locator("table.plot-table tbody tr").count() > 0 and fig.locator(".plot").is_hidden()
            fig.locator(".table-toggle").click()
            with page.expect_navigation():  # filter inside the overlay (script-triggered click, gate 193)
                page.evaluate("""() => { const p = document.querySelector('dialog[open] [data-kind="bar"] .plot'), t = p.data[0];
                    p.emit('plotly_click', {points: [{x: t.x && t.x[0], y: t.y[0], label: t.y[0], data: {orientation: t.orientation}}]}); }""")
            page.wait_for_selector("dialog[open] [data-kind=bar]")
            assert [k for k in _query(page) if k.startswith("f.")]
            page.locator("dialog[open] .ws-expand").click()
            page.wait_for_selector("dialog[open]", state="detached")
            own = urlparse(base).netloc
            assert len(seen) > 10 and [u for u in seen if urlparse(u).netloc != own and not u.startswith(("data:", "blob:"))] == []
            assert page.external == [] and page.errors == []


def test_AC_87():
    doc = (ROOT / "docs/DESIGN.md").read_text(encoding="utf-8")
    heads = [m for m in re.finditer(r"^(#+) (.*)$", doc, re.M) if "round 7" in m.group(2).lower() and "theme" in m.group(2).lower()]
    assert heads, "no DESIGN.md heading for the round 7 theme and tiles"
    found = []
    for m in heads:  # a section runs to the next heading of the same or a higher level
        nxt = re.search(rf"^#{{1,{len(m.group(1))}}} ", doc[m.end():], re.M)
        found.append(doc[m.start(): m.end() + (nxt.start() if nxt else len(doc))].lower())
    text = max(found, key=len)
    terms = ["#050a12", "#4de1ff", "#ffb454", "mono", "header", "drag handle", "expand", "table toggle", "12-column", "0.6 s",
             "reduced motion", "reduced transparency"]
    assert [t for t in terms if t not in text] == []
