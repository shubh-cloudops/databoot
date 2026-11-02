"""One-click launcher: python -m app.launch [folder] [--port N] [--no-browser]. Starts uvicorn on 127.0.0.1, opens the browser.
Without a folder it runs on an owned empty temp folder (deleted on exit)."""
import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from app import upload

HOST = "127.0.0.1"
TRIES = 20
SERVER = None  # the running uvicorn.Server; a test sets SERVER.should_exit = True to stop it


def free_port(start):
    """First port from start up that can be bound on HOST (TRIES attempts)."""
    for port in range(start, start + TRIES):
        with socket.socket() as s:
            try:
                s.bind((HOST, port))
            except OSError:
                continue
            return port
    raise OSError(f"no free port from {start} to {start + TRIES - 1}")


def run(folder, port=8765, open_browser=webbrowser.open):
    """Serve folder on the first free port from port; call open_browser(url) once the server has started."""
    global SERVER
    os.environ["DATABOOT_DATA"] = str(folder)
    port = free_port(port)
    from app.main import app  # after DATABOOT_DATA is set
    SERVER = server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="warning"))
    url = f"http://{HOST}:{port}/"

    def opener():
        while not server.started and not server.should_exit:
            time.sleep(0.05)
        if server.started and open_browser:
            open_browser(url)

    threading.Thread(target=opener, daemon=True).start()
    server.run()


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m app.launch")
    p.add_argument("folder", nargs="?")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args(argv)
    if a.folder and not Path(a.folder).is_dir():
        print(f"folder not found: {a.folder}", file=sys.stderr)
        return 2
    if not 0 < a.port < 65536:
        print(f"invalid port: {a.port}", file=sys.stderr)
        return 2
    try:
        run(a.folder or upload.empty(), a.port, None if a.no_browser else webbrowser.open)
    except OSError as e:
        print(str(e), file=sys.stderr)
        return 2
    finally:
        upload.cleanup()  # the app's shutdown does this too; this covers a start that failed
    return 0


if __name__ == "__main__":
    sys.exit(main())
