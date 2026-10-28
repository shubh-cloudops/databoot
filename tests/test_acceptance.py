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
    assert "<figure" not in r.text and "comment" in r.text and "<caption><h2>Columns</h2></caption>" in r.text
    assert "free text number 0" in r.text
    assert "Chart could not be drawn" not in r.text and "Internal Server Error" not in r.text


def test_AC_8(make_client, data_dir):
    client = make_client(data_dir)
    for d in client.get("/api/datasets").json():
        r = client.get(f"/datasets/{d['id']}")
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
    assert client.get(f"/datasets/{i}").text.count("<figure") == len(many)


def test_AC_17(make_client, data_dir):
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
        html = client.get(f"/datasets/{d['id']}").text
        assert re.search(r"<title>[^<]* - DataBoot</title>", html), d["path"]
    assert not re.search(r"DataOS", home + client.get(f"/datasets/{d['id']}").text, re.I)


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
    page = client.get(f"/datasets/{i}").text
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
    page, errors, close = _page(live, "/datasets/" + ids[("points.tsv", None)])
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
    page, errors, close = _page(live, "/datasets/" + ids[("sales.csv", None)])
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
    page, errors, close = _page(live, "/datasets/" + ids[("points.tsv", None)])
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
    return "/datasets/" + next(d["id"] for d in json.load(urllib.request.urlopen(base + "/api/datasets")) if d["path"] == name)


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
        html = client.get(f"/datasets/{i}").text
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
        api = json.load(urllib.request.urlopen(live + path.replace("/datasets/", "/api/datasets/") + "/charts"))["charts"]
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
    html = client.get(f"/datasets/{i}").text
    form = html.split('<form class="filters" method="get">')[1].split("</form>")[0]
    assert re.findall(r'<select id="\w+" name="([^"]+)"', form) == ["f.department", "f.region"]  # one per categorical
    assert 'type="date" id="from"' in form and 'type="date" id="to"' in form
    for name in ("points.tsv", "sub/records.json"):  # no categorical or temporal column: no control
        assert "<form" not in client.get(f"/datasets/{ids[(name, None)]}").text
    s = client.get(f"/datasets/{ids[('sales.csv', None)]}").text.split('<form class="filters"')[1]
    assert s.count("<select") == 1 and 'name="from"' in s
    book = client.get(f"/datasets/{ids[('sub/book.xlsx', 'Revenue')]}").text.split('<form class="filters"')[1]
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
        page = client.get(f"/datasets/{i}{query}").text
        assert f"{want} of {want} rows" in page


def test_AC_38(live):
    path = _path(live, "sales.csv")
    with _open(live, path + "?f.region=North&from=2024-01-02") as (page, external, errors):
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
        assert urlparse(page.url).query == "" and _kpi(page)["Rows"] == "6" and page.locator(".chips a").count() == 0
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
        assert parse_qs(urlparse(page.url).query) == {"f.region": [want]}
        n = {"South": 2, "North": 3, "East": 1}[want]
        assert page.locator("select[name='f.region']").input_value() == want and _kpi(page)["Rows"] == str(n)
        assert page.locator(".chips a").count() == 1
        for fig in page.locator("figure.chart").all():  # every chart is on the filtered rows
            count = fig.locator(".chart-count").inner_text()
            assert count.split(" of ")[0] == count.split(" of ")[1].split(" ")[0]
            if fig.get_attribute("data-kind") in ("bar", "histogram"):
                assert count.startswith(f"{n} of {n} ")
        _click_nav(page, "bar")
        assert urlparse(page.url).query == "" and _kpi(page)["Rows"] == "6"
        assert errors == [] and external == []
    # horizontal bar (labels > 12 chars): same set and toggle, plus a second filter on another column ANDs
    with _open(live, staff) as (page, external, errors):
        orient, labels, _ = _plot_values(page, "bar")
        assert orient == "h" and max(map(len, labels)) > 12
        _click_nav(page, "bar")
        want = labels[0]
        assert parse_qs(urlparse(page.url).query) == {"f.department": [want]}
        n = sum(1 for k in range(40) if STAFF_DEPTS[k % 3] == want)
        assert page.locator("select[name='f.department']").input_value() == want and _kpi(page)["Rows"] == str(n)
        page.select_option("select[name='f.region']", "North")
        page.click("form.filters button")
        _settle(page)
        assert set(parse_qs(urlparse(page.url).query)) == {"f.department", "f.region"} and page.locator(".chips a").count() == 2
        _click_nav(page, "bar")  # the bar of the clicked column is still drawn: clicking it removes only that filter
        assert set(parse_qs(urlparse(page.url).query)) == {"f.region"} and page.locator(".chips a").count() == 1
        assert errors == [] and external == []
    with _open(live, staff + "?f.department=Customer+support") as (page, external, errors):
        orient, labels, _ = _plot_values(page, "bar")
        assert orient == "h" and labels == ["Customer support"]
        _click_nav(page, "bar")  # second click on the active horizontal bar
        assert urlparse(page.url).query == "" and _kpi(page)["Rows"] == "40"
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
        assert parse_qs(urlparse(page.url).query) == {"f.department": [want]}
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
            assert "200,000" in r.text
    # types come from the first 10,000 rows only: later text does not change them
    folder = tmp_path / "late"
    folder.mkdir()
    (folder / "late.csv").write_text("n,k\n" + "".join(f"{i},{i % 3}\n" for i in range(10_000)) + "".join(f"abc,{i % 3}\n" for i in range(2_000)))
    client = make_client(folder)
    i = client.get("/api/datasets").json()[0]["id"]
    assert client.get(f"/api/datasets/{i}/profile").json()["n"] == "numerical"
    assert client.get(f"/api/datasets/{i}/charts").json()["kpis"]["rows"] == 12_000
