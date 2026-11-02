"""Home portal and intake.js (ARCHITECTURE.md "Round 7: upload", H7; AC-74, AC-75, AC-77; Board gate 190)."""
import re

import pytest

from conftest import files_of  # noqa: F401
from tests.test_browser import base, browser  # noqa: F401  (fixtures)


def test_portal_markup(make_client, tmp_path):
    html = make_client(tmp_path).get("/").text
    assert html.count("<h1>") == 1 and "<h1>DataBoot</h1>" in html
    assert html.count('class="portal"') == 1 and "Give me your data" in html
    assert re.search(r'<input[^>]*type="file"[^>]* multiple>\s*<label[^>]*>Choose files</label>', html)
    assert re.search(r'<input[^>]*type="file"[^>]* webkitdirectory>\s*<label[^>]*>Choose folder</label>', html)
    assert "sample" not in html.lower() and "dev only" not in html.lower()
    head = html.split("</head>")[0]
    assert "http://" not in head and "https://" not in head


def page_for(browser, base, width=1280, **ctx):
    page = browser.new_context(viewport={"width": width, "height": 900}, **ctx).new_page()
    seen, errors = [], []
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else (seen.append(r.request.url), r.abort()))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.goto(base + "/")
    return page, seen, errors


@pytest.mark.parametrize("width", [1280, 375])
def test_portal_is_a_circle(base, browser, width):
    page, seen, errors = page_for(browser, base, width)
    box = page.locator(".portal").bounding_box()
    assert abs(box["width"] - box["height"]) < 1
    radius = page.evaluate("getComputedStyle(document.querySelector('.portal')).borderTopLeftRadius")
    assert float(radius.rstrip("%px")) * (box["width"] / 100 if radius.endswith("%") else 1) >= box["width"] / 2 - 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("h1").count() == 1 and seen == [] and errors == []


def listed(page):
    return page.locator("main").inner_text()


def test_choose_files_lists_both(base, browser, tmp_path):
    (tmp_path / "a.csv").write_text("x,y\n1,2\n3,4\n")
    (tmp_path / "b.csv").write_text("p,q\n5,6\n7,8\n")
    page, seen, errors = page_for(browser, base)
    page.route(f"{base}/datasets/**", lambda r: r.abort())  # stay on /scan
    page.set_input_files("#pick-files", [str(tmp_path / "a.csv"), str(tmp_path / "b.csv")])
    page.wait_for_url(base + "/scan")
    text = page.locator(".scan-log").text_content()
    assert "a.csv" in text and "b.csv" in text and errors == [] and seen == []


def test_choose_folder_keeps_relative_path(base, browser, tmp_path):
    (tmp_path / "picked" / "sub").mkdir(parents=True)
    (tmp_path / "picked" / "sub" / "sales.csv").write_text("x,y\n1,2\n3,4\n")
    page, _, errors = page_for(browser, base)
    page.route(f"{base}/datasets/**", lambda r: r.abort())
    page.set_input_files("#pick-folder", str(tmp_path / "picked"))
    page.wait_for_url(base + "/scan")
    assert "sub/sales.csv" in page.locator(".scan-log").text_content() and errors == []


def test_drop_event_uploads(base, browser):
    page, _, errors = page_for(browser, base)
    page.route(f"{base}/datasets/**", lambda r: r.abort())
    page.evaluate("""() => {
        const dt = new DataTransfer(); dt.items.add(new File(['x,y\\n1,2\\n3,4\\n'], 'dropped.csv', {type: 'text/csv'}));
        document.getElementById('portal').dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true})); }""")
    page.wait_for_url(base + "/scan")
    assert "dropped.csv" in page.locator(".scan-log").text_content() and errors == []


def test_state_is_over_during_a_drag(base, browser):
    page, _, _ = page_for(browser, base)
    assert page.get_attribute("#portal", "data-state") == "idle"
    page.evaluate("""() => { const dt = new DataTransfer(); dt.items.add(new File(['a'], 'a.csv'));
        document.getElementById('portal').dispatchEvent(new DragEvent('dragover', {dataTransfer: dt, bubbles: true, cancelable: true})); }""")
    assert page.get_attribute("#portal", "data-state") == "over"


def test_over_the_cap_shows_message_and_sends_nothing(base, browser, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABOOT_UPLOAD_CAP", "1000")
    (tmp_path / "big.csv").write_text("x\n" + "1\n" * 800)
    (tmp_path / "big2.csv").write_text("x\n" + "1\n" * 800)
    page, _, errors = page_for(browser, base)
    page.reload()
    sent = []
    page.on("request", lambda r: "/upload" in r.url and sent.append(r.url))
    page.set_input_files("#pick-files", [str(tmp_path / "big.csv"), str(tmp_path / "big2.csv")])
    alert = page.locator("[role=alert]")
    alert.wait_for()
    assert "1,000 bytes" in alert.inner_text() and "-Folder" in alert.inner_text()
    assert sent == [] and page.url == base + "/" and "big.csv" not in page.locator("main table").all_inner_texts().__str__()
    assert page.get_attribute("#portal", "data-state") == "idle" and errors == []


def test_server_413_shows_same_detail(base, browser, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABOOT_UPLOAD_CAP", "1000")
    (tmp_path / "a.csv").write_text("x\n" + "1\n" * 600)
    page, _, errors = page_for(browser, base)
    page.evaluate("document.getElementById('portal').dataset.cap = '999999'")  # skip the client check
    page.set_input_files("#pick-files", str(tmp_path / "a.csv"))
    alert = page.locator("[role=alert]")
    alert.wait_for()
    assert "1,000 bytes" in alert.inner_text() and "-Folder" in alert.inner_text()
    assert "a.csv" not in listed(page)


def test_rings_turn_at_rest_and_stop_under_reduced_motion(base, browser):
    css = "getComputedStyle(document.querySelector('.portal-rings i')).animationName"
    page, _, _ = page_for(browser, base)
    assert page.get_attribute("#portal", "data-state") == "idle"
    assert page.evaluate(css) == "ring-turn"
    assert page.evaluate("getComputedStyle(document.querySelector('.portal-rings i')).animationPlayState") == "running"
    page, _, _ = page_for(browser, base, reduced_motion="reduce")
    assert page.evaluate(css) == "none"


def test_home_with_folder_keeps_tables_after_portal(make_client, data_dir):
    html = make_client(data_dir).get("/").text
    at = html.index('class="portal"')
    for caption in ("Could not be read", "Other files"):
        assert html.index(f"<caption><h2>{caption}</h2></caption>") > at


def test_dropped_folder_is_walked_and_first_segment_stripped(base, browser):
    page, _, errors = page_for(browser, base)
    page.route(f"{base}/datasets/**", lambda r: r.abort())
    page.evaluate("""() => {
        const file = (name, path) => ({isFile: true, fullPath: path, file: ok => ok(new File(['x,y\\n1,2\\n3,4\\n'], name))});
        const dir = (path, kids) => { let done = false; return {isFile: false, fullPath: path,
            createReader: () => ({readEntries: ok => { const r = done ? [] : kids; done = true; ok(r); }})}; };
        const root = dir('/picked', [dir('/picked/sub', [file('sales.csv', '/picked/sub/sales.csv')])]);
        const dt = new DataTransfer(); dt.items.add(new File(['x'], 'ignored.csv'));
        Object.defineProperty(dt, 'items', {value: [{kind: 'file', webkitGetAsEntry: () => root, getAsFile: () => null}]});
        document.getElementById('portal').dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true})); }""")
    page.wait_for_url(base + "/scan")
    assert "sub/sales.csv" in page.locator(".scan-log").text_content() and errors == []
