import socket
import threading
import time
import urllib.request

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
