"""One test per item in docs/acceptance.json, named after its id. They drive the app through its HTTP routes;
Playwright is used where only a browser can show the result (drawn charts).

AC-13 names Start-DataOS.ps1; Board gate 161 renamed it Start-DataBoot.ps1, and AC-13 / AC-6 ("Deck.gl") wording is
stale in acceptance.json. These tests follow the gate.
"""
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
