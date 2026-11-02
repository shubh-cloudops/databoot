"""Upload backend (docs/ARCHITECTURE.md "Round 7: upload"): AC-75 same data as a folder run, AC-76 lifecycle, AC-77 cap."""
import os
import tempfile
from pathlib import Path

import pytest
from conftest import files_of
from conftest import upload as send
from fastapi.testclient import TestClient

from app import config, main, upload

BAD = ["../x", "/x", "C:x", "a//b", "a\0b", "a/../b", "./a", "a/", ""]


def listing(client):
    return sorted((d["path"], d["rows"], d["columns"]) for d in client.get("/api/datasets").json())


def apps_of(client):
    return {d["path"]: client.get(f"/api/datasets/{d['id']}/app").json()["app"] for d in client.get("/api/datasets").json()}


def test_safe():
    assert [upload.safe(p) for p in BAD] == [None] * len(BAD)
    assert upload.safe("a\\b\\c.csv") == "a/b/c.csv"
    assert upload.safe("sub/sales.csv") == "sub/sales.csv"


def test_begin_validation(make_client, tmp_path):
    c = make_client(tmp_path)
    before = set(Path(tempfile.gettempdir()).glob("databoot-upload-*"))
    assert c.post("/upload", json={"files": []}).status_code == 400
    assert c.post("/upload", json={"files": [{"path": "a.csv", "size": 1}, {"path": "a.csv", "size": 1}]}).status_code == 400
    for p in BAD:
        assert c.post("/upload", json={"files": [{"path": p, "size": 1}]}).status_code == 400, p
    assert c.post("/upload", content=b"nope").status_code == 400
    assert set(Path(tempfile.gettempdir()).glob("databoot-upload-*")) == before and not upload.OWNED
    r = c.post("/upload", json=[{"path": "a\\b.csv", "size": 1}])  # a bare list works too; backslash becomes /
    assert r.status_code == 200
    r = c.put(f"/upload/{r.json()['batch']}", params={"path": "a/b.csv"}, content=b"x")
    assert r.json() == {"path": "a/b.csv", "bytes": 1}


def test_put_rules(make_client, tmp_path):
    c = make_client(tmp_path)
    batch = c.post("/upload", json={"files": [{"path": "sub/a.csv", "size": 3}]}).json()["batch"]
    assert c.put("/upload/nope", params={"path": "sub/a.csv"}, content=b"abc").status_code == 404
    assert c.put(f"/upload/{batch}", params={"path": "other.csv"}, content=b"abc").status_code == 400
    assert c.put(f"/upload/{batch}", params={"path": "../a.csv"}, content=b"abc").status_code == 400
    assert c.put(f"/upload/{batch}", params={"path": "sub/a.csv"}, content=b"abc").status_code == 200
    (folder,) = upload.OWNED
    assert folder.name == batch and folder.name.startswith("databoot-upload-")
    assert folder.parent == Path(tempfile.gettempdir())
    assert (folder / "sub" / "a.csv").read_bytes() == b"abc"
    assert c.post("/upload/nope/done").status_code == 404


def test_done_switches_folder_and_deletes_previous(make_client, tmp_path):
    c = make_client(tmp_path)
    assert send(c, {"a.csv": b"x\n1\n"}).json() == {"next": "/scan"}
    first = config.get().data
    assert first in upload.OWNED and (first / "a.csv").exists()
    assert send(c, {"b.csv": b"y\n2\n"}).status_code == 200
    second = config.get().data
    assert second != first and not first.exists() and first not in upload.OWNED
    assert [p for p, *_ in listing(c)] == ["b.csv"]


def test_launcher_folder_is_never_deleted(make_client, data_dir):
    c = make_client(data_dir)
    before = files_of(data_dir)
    assert send(c, {"a.csv": b"x\n1\n"}).status_code == 200
    assert send(c, {"b.csv": b"y\n2\n"}).status_code == 200
    assert files_of(data_dir) == before


@pytest.mark.parametrize("pick", ["one", "several", "folder"])
def test_same_listing_as_folder_run(make_client, data_dir, tmp_path, pick):
    if pick == "one":
        files = {"sales.csv": (data_dir / "sales.csv").read_bytes()}
        want = tmp_path / "one"
        want.mkdir()
        (want / "sales.csv").write_bytes(files["sales.csv"])
    elif pick == "several":
        files = {n: (data_dir / n).read_bytes() for n in ("sales.csv", "points.tsv")}
        want = tmp_path / "several"
        want.mkdir()
        for n, b in files.items():
            (want / n).write_bytes(b)
    else:
        files, want = files_of(data_dir), data_dir
    expect = make_client(want)
    expected = (listing(expect), apps_of(expect))
    c = make_client(tmp_path / "empty")
    assert send(c, files).status_code == 200
    assert (listing(c), apps_of(c)) == expected
    if pick == "folder":
        assert "sub/records.json" in dict((p, r) for p, r, _ in listing(c))


def test_second_upload_replaces_rows_of_same_name(make_client, tmp_path):
    c = make_client(tmp_path)
    send(c, {"sales.csv": b"region,amount\nN,1\nS,2\nE,3\n"})
    assert listing(c) == [("sales.csv", 3, 2)]
    d = c.get("/api/datasets").json()[0]["id"]
    c.get(f"/datasets/{d}")  # fill the view caches
    send(c, {"sales.csv": b"region,amount\nN,10\n"})
    assert listing(c) == [("sales.csv", 1, 2)]
    assert c.get(f"/datasets/{d}").status_code == 200


def test_cap_message():
    assert upload.cap_message(int(2.4 * 1024 ** 3), 2 * 1024 ** 3) == (
        "This upload is 2.4 GB and the limit is 2 GB. For larger drives, start DataBoot with the launcher's -Folder option.")
    assert "1,000 bytes" in upload.cap_message(1000, 5)
    assert "2 GB" in upload.cap_message(5, config.get().upload_cap)


def test_cap_declared_total(make_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABOOT_UPLOAD_CAP", "10")
    c = make_client(tmp_path)
    r = c.post("/upload", json={"files": [{"path": "a.csv", "size": 6}, {"path": "b.csv", "size": 6}]})
    assert r.status_code == 413 and r.json()["detail"] == upload.cap_message(12, 10) and not upload.OWNED


def test_cap_real_bytes_delete_batch(make_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABOOT_UPLOAD_CAP", "10")
    c = make_client(tmp_path)
    assert send(c, {"a.csv": b"x,y\n1,2\n"}).status_code == 200  # fits; becomes the current data
    kept = set(upload.OWNED)
    batch = c.post("/upload", json={"files": [{"path": "a.csv", "size": 4}, {"path": "b.csv", "size": 4}]}).json()["batch"]
    (folder,) = upload.OWNED - kept
    assert c.put(f"/upload/{batch}", params={"path": "a.csv"}, content=b"1234").status_code == 200
    r = c.put(f"/upload/{batch}", params={"path": "b.csv"}, content=b"1234567890")  # lied about the size
    assert r.status_code == 413 and r.json()["detail"] == upload.cap_message(14, 10)
    assert not folder.exists() and upload.OWNED == kept
    assert c.post(f"/upload/{batch}/done").status_code == 404
    assert listing(c) == [("a.csv", 1, 2)]  # the earlier finished upload is untouched by the failed one


def test_cleanup_with_lifespan(tmp_path, monkeypatch, data_dir):
    monkeypatch.setenv("DATABOOT_DATA", str(data_dir))
    monkeypatch.setenv("DATABOOT_OUT", str(tmp_path / "out"))
    before = files_of(data_dir)
    with TestClient(main.app) as c:
        assert send(c, {"a.csv": b"x\n1\n"}).status_code == 200
        folder = config.get().data
        assert folder.is_dir() and folder.is_relative_to(tempfile.gettempdir())
        assert not folder.is_relative_to(config.ROOT) and not folder.is_relative_to(data_dir)
    assert not folder.exists() and not upload.OWNED
    assert files_of(data_dir) == before


def test_begin_deletes_unfinished_batch(make_client, tmp_path):
    c = make_client(tmp_path)
    first = c.post("/upload", json={"files": [{"path": "a.csv", "size": 1}]}).json()["batch"]
    folder = next(iter(upload.OWNED))
    second = c.post("/upload", json={"files": [{"path": "b.csv", "size": 1}]}).json()["batch"]
    assert not folder.exists() and len(upload.OWNED) == 1
    assert c.put(f"/upload/{first}", params={"path": "a.csv"}, content=b"x").status_code == 404
    assert c.put(f"/upload/{second}", params={"path": "b.csv"}, content=b"x").status_code == 200


def test_empty_is_owned():
    folder = upload.empty()
    assert folder.is_dir() and folder in upload.OWNED and folder.name.startswith("databoot-upload-")
    upload.cleanup()
    assert not folder.exists()
