"""GET /scan (docs/ARCHITECTURE.md "Round 7: scan screen"): one server-rendered line per dataset and unreadable file."""
import html
import re

from conftest import files_of
from conftest import upload as send

LINE = re.compile(r"^(?P<path>.+?)(?: - (?P<sheet>.+?))?  [\d,]+ rows?  T\d+ N\d+ C\d+ G\d+  -> (?P<app>[A-Z]+) \(rule (?P<rule>R\d)\)$")


def lines(page):
    return [html.unescape(m) for m in re.findall(r"<li[^>]*>(.*?)</li>", page.split("</ol>")[0])]


def scan(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    files = {**files_of(archetypes_dir), "broken.xlsx": b"not a zip file"}
    assert send(client, files).status_code == 200
    return client, client.get("/scan")


def test_one_line_per_dataset_and_unreadable(make_client, archetypes_dir):
    client, r = scan(make_client, archetypes_dir)
    assert r.status_code == 200
    got = lines(r.text)
    datasets = client.get("/api/datasets").json()
    assert len(got) == len(datasets) + 1 + 1
    for line, d in zip(got, datasets):
        m = LINE.match(line)
        assert m and m["path"] == d["path"]
        app = client.get(f"/api/datasets/{d['id']}/app").json()
        assert (m["app"], m["rule"]) == (app["app"].upper(), app["rule"])
    assert "shop.csv" in got[[d["path"] for d in datasets].index("shop.csv")]
    assert any(re.match(r"^shop\.csv  [\d,]+ rows  T1 N\d C\d G0  -> BUSINESS \(rule R2\)$", x) for x in got)
    assert got[-2] == "broken.xlsx  not a valid xlsx"
    assert got[-1] == "0 bytes uploaded to the internet"


def test_open_workspace_and_plain_markup(make_client, archetypes_dir):
    client, r = scan(make_client, archetypes_dir)
    first = client.get("/api/datasets").json()[0]["id"]
    assert f'<a class="btn btn-primary" id="open-workspace" href="/datasets/{first}">Open workspace</a>' in r.text
    assert '<ol class="scan-log" aria-live="polite">' in r.text and "<h1>DataBoot</h1>" in r.text
    main = r.text.split("<main")[1]
    assert "<p" not in main and "<script" not in r.text
    assert "http://" not in r.text.split("</head>")[0] and "https://" not in r.text.split("</head>")[0]


def test_no_dataset_opens_home(make_client, tmp_path):
    r = make_client(tmp_path).get("/scan")
    assert 'id="open-workspace" href="/">' in r.text
    assert lines(r.text) == ["0 bytes uploaded to the internet"]


def test_summary_and_page_context(make_client, data_dir):
    from app import main
    client = make_client(data_dir)
    d = next(d for d in main.catalog.scan(data_dir).datasets if d.path == "sales.csv")
    assert main._summary(d) == {"app": "business", "rule": "R2", "T": 1, "N": 1, "C": 1, "G": 0}
    assert client.get(f"/datasets/{d.id}").status_code == 200
    assert "G0" in client.get("/scan").text
