import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

from app import launch


def test_missing_folder_exits_2_with_one_line(tmp_path, capsys):
    assert launch.main([str(tmp_path / "nope")]) == 2
    assert len(capsys.readouterr().err.splitlines()) == 1


def test_free_port_skips_busy_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        busy = s.getsockname()[1]
        assert launch.free_port(busy) != busy


def test_run_opens_url_and_serves_home(data_dir, monkeypatch):
    monkeypatch.setenv("DATABOOT_DATA", "")  # run() overwrites it; monkeypatch restores the old value
    urls = []
    got = threading.Event()

    def fake_open(url):
        urls.append(url)
        got.set()

    t = threading.Thread(target=launch.run, args=(data_dir, 8765, fake_open))
    t.start()
    try:
        assert got.wait(10)
        assert urls[0].startswith("http://127.0.0.1:") and urls[0].endswith("/")
        with urllib.request.urlopen(urls[0]) as r:
            assert r.status == 200
    finally:
        deadline = time.time() + 5
        while launch.SERVER is None and time.time() < deadline:
            time.sleep(0.05)
        launch.SERVER.should_exit = True
        t.join(10)
    assert not t.is_alive()
    assert len(urls) == 1


def _serve(monkeypatch, target, *args):
    """Run target(*args) in a thread and wait until the server has started."""
    monkeypatch.setenv("DATABOOT_DATA", "")
    launch.SERVER = None
    t = threading.Thread(target=target, args=args)
    t.start()
    deadline = time.time() + 10
    while (launch.SERVER is None or not launch.SERVER.started) and time.time() < deadline:
        time.sleep(0.05)
    assert launch.SERVER is not None and launch.SERVER.started
    return t, f"http://127.0.0.1:{launch.SERVER.config.port}/"


def _stop(t):
    launch.SERVER.should_exit = True
    t.join(10)
    assert not t.is_alive()


def _tree(folder):
    return sorted((str(p.relative_to(folder)), p.stat().st_size, p.stat().st_mtime_ns) for p in folder.rglob("*"))


def test_no_folder_runs_on_owned_empty_folder_and_deletes_it(monkeypatch):
    t, url = _serve(monkeypatch, launch.main, ["--no-browser"])
    folder = Path(os.environ["DATABOOT_DATA"])
    try:
        assert folder.is_dir() and not list(folder.iterdir())
        with urllib.request.urlopen(url) as r:
            assert r.status == 200 and "<caption>" not in r.read().decode()
    finally:
        _stop(t)
    assert not folder.exists()


def test_launcher_folder_is_never_written_or_deleted(data_dir, monkeypatch):
    before = _tree(data_dir)
    t, url = _serve(monkeypatch, launch.run, data_dir, 8765, None)
    try:
        with urllib.request.urlopen(url) as r:
            assert r.status == 200
    finally:
        _stop(t)
    assert data_dir.is_dir() and _tree(data_dir) == before
