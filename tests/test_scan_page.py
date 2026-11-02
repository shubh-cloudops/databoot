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
    assert "<p" not in main and r.text.count("<script") == 1 and '<script src="/static/js/scan.js" defer></script>' in r.text
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


# ---- scan.js in a real browser (ARCHITECTURE.md "Round 7: scan screen") ----
import json
import time
import urllib.parse
import urllib.request

from tests.test_browser import base, browser  # noqa: F401  (fixtures)

RECORD = """() => { window.__t = {}; new MutationObserver(ms => ms.forEach(m => {
    const li = m.target; if (li.tagName !== 'LI' || li.hidden) return;
    const i = [...li.parentNode.children].indexOf(li); window.__t[i] = window.__t[i] || performance.now(); }))
    .observe(document, {attributes: true, subtree: true, attributeFilter: ['hidden']}); }"""


def seed(base, archetypes_dir):
    files = {**files_of(archetypes_dir), "broken.xlsx": b"not a zip file"}
    req = lambda url, **kw: urllib.request.urlopen(urllib.request.Request(base + url, **kw))
    sent = json.dumps({"files": [{"path": p, "size": len(b)} for p, b in files.items()]}).encode()
    batch = json.load(req("/upload", data=sent, headers={"Content-Type": "application/json"}))["batch"]
    for p, b in files.items():
        req(f"/upload/{batch}?path={urllib.parse.quote(p)}", data=b, method="PUT")
    req(f"/upload/{batch}/done", data=b"", method="POST")
    return json.load(req("/api/datasets"))[0]["id"]


def guarded(browser, base, **ctx):
    page = browser.new_context(viewport={"width": 1280, "height": 900}, **ctx).new_page()
    external, errors = [], []
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else (external.append(r.request.url), r.abort()))
    page.on("pageerror", lambda e: errors.append(str(e)))
    return page, external, errors


def test_reveal_timing(base, browser, archetypes_dir):
    seed(base, archetypes_dir)
    page, external, errors = guarded(browser, base)
    page.route(f"{base}/datasets/**", lambda r: r.abort())  # stay on /scan so the timestamps can be read
    page.add_init_script("(" + RECORD + ")()")
    t0 = time.monotonic()
    page.goto(base + "/scan")
    n = page.locator(".scan-log li").count()
    assert n > 3
    page.wait_for_function(f"Object.keys(window.__t).length === {n}", timeout=5000)
    assert time.monotonic() - t0 < 2.5 + 1.5  # 2.5 s of reveal plus load and tolerance
    t = page.evaluate("window.__t")
    step = min(350, 2500 / n)
    assert t["1"] - t["0"] > step * 0.6 and t[str(n - 1)] - t["0"] < 2500 + 300
    assert external == [] and errors == []


def test_opens_first_dataset_after_the_last_line(base, browser, archetypes_dir):
    first = seed(base, archetypes_dir)
    page, external, errors = guarded(browser, base)
    page.goto(base + "/scan")
    page.wait_for_url(f"{base}/datasets/{first}", timeout=6000)
    assert page.url == f"{base}/datasets/{first}" and errors == []


def test_reduced_motion_lines_in_turn_without_transition(base, browser, archetypes_dir):
    seed(base, archetypes_dir)
    page, external, errors = guarded(browser, base, reduced_motion="reduce")
    page.route(f"{base}/datasets/**", lambda r: r.abort())
    page.add_init_script("(" + RECORD + ")()")
    page.goto(base + "/scan")
    n = page.locator(".scan-log li").count()
    page.wait_for_function(f"Object.keys(window.__t).length === {n}", timeout=5000)
    t = page.evaluate("window.__t")
    assert t["1"] > t["0"] and t[str(n - 1)] > t["1"]
    assert page.evaluate("getComputedStyle(document.querySelector('.scan-log li')).transitionDuration") == "0s"
    assert external == [] and errors == []


def test_without_javascript_every_line_shows(base, browser, archetypes_dir):
    seed(base, archetypes_dir)
    page, _, _ = guarded(browser, base, java_script_enabled=False)
    page.goto(base + "/scan")
    time.sleep(0.5)
    assert page.locator(".scan-log li:visible").count() == page.locator(".scan-log li").count() > 3
    assert page.url == base + "/scan"
