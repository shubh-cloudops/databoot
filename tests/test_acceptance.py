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
    assert t_full == ["Explorer", "sales.csv", "Rows: 6, 3 columns", "Filters: none"]
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
            cells.nth(cells.count() // 2).scroll_into_view_if_needed()
            box = cells.nth(cells.count() // 2).bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_selector(".hoverlayer .hovertext")
            label = page.locator(".hoverlayer .hovertext").text_content()
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
    assert first(_pptx(client, "shop.csv", "?app=explorer")[0]) == "Explorer"


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
