"""Browser intake (docs/ARCHITECTURE.md "Round 7: upload"): begin / write / finish one upload batch into a temp
folder, cap check, path sanitising, and cleanup of every temp folder this process made."""
import os
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import HTTPException

from app import config

OWNED = set()    # every temp folder this process made and may delete (never a launcher folder)
_batches = {}    # token -> {"dir": Path, "files": {path: declared size}, "sizes": {path: bytes written}}
GB = 1024 ** 3


def safe(path):
    """The path with '/' separators, or None when it is empty, absolute, drive-lettered, has NUL or an empty, '.' or '..' part."""
    if not isinstance(path, str) or "\0" in path:
        return None
    path = path.replace("\\", "/")
    if path.startswith("/") or re.match(r"[A-Za-z]:", path) or any(p in ("", ".", "..") for p in path.split("/")):
        return None
    return path


def cap_message(total, cap):
    def size(n):
        return f"{n / GB:.1f}".removesuffix(".0") + " GB" if n >= GB else f"{n:,} bytes"
    return (f"This upload is {size(total)} and the limit is {size(cap)}. "
            "For larger drives, start DataBoot with the launcher's -Folder option.")


def _drop(folder):
    shutil.rmtree(folder, ignore_errors=True)
    OWNED.discard(folder)


def empty():
    """A new empty temp folder, owned (deleted by cleanup)."""
    folder = Path(tempfile.mkdtemp(prefix="databoot-upload-"))
    OWNED.add(folder)
    return folder


def begin(files, cap):
    """Check the declared list {path, size} and make the batch folder; returns the batch token. One upload at a time:
    a batch begun and never finished is deleted here."""
    if not isinstance(files, list) or not files:
        raise HTTPException(400, "no files")
    declared = {}
    for f in files:
        p = safe(f.get("path")) if isinstance(f, dict) else None
        size = f.get("size") if isinstance(f, dict) else None
        if p is None or p in declared or not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise HTTPException(400, f"bad or duplicate path: {f.get('path') if isinstance(f, dict) else f!r}")
        declared[p] = size
    total = sum(declared.values())
    if total > cap:
        raise HTTPException(413, cap_message(total, cap))
    for b in _batches.values():
        _drop(b["dir"])
    _batches.clear()
    folder = empty()
    _batches[folder.name] = {"dir": folder, "files": declared, "sizes": {}}
    return folder.name


async def write(batch, path, chunks, cap):
    """Stream the async iterator `chunks` to batch/path. Over the cap the whole batch is deleted and 413 raised."""
    b = _batches.get(batch)
    if b is None:
        raise HTTPException(404, "unknown upload")
    path = safe(path)
    if path is None or path not in b["files"]:
        raise HTTPException(400, "path not in this upload")
    target = (b["dir"] / path).resolve()
    if not target.is_relative_to(b["dir"].resolve()):
        raise HTTPException(400, "path not in this upload")
    target.parent.mkdir(parents=True, exist_ok=True)
    others = sum(n for p, n in b["sizes"].items() if p != path)
    n = 0
    with open(target, "wb") as f:
        async for chunk in chunks:
            n += len(chunk)
            if others + n > cap:
                f.close()
                _drop(b["dir"])
                _batches.pop(batch, None)
                raise HTTPException(413, cap_message(others + n, cap))
            f.write(chunk)
    b["sizes"][path] = n
    return n


def finish(batch):
    """The batch folder becomes the data folder; the previous upload folder is deleted. Caller clears the route caches."""
    b = _batches.pop(batch, None)
    if b is None:
        raise HTTPException(404, "unknown upload")
    old = config.get().data
    os.environ["DATABOOT_DATA"] = str(b["dir"])
    if old in OWNED and old != b["dir"]:
        _drop(old)


def cleanup():
    """Delete every owned folder (app shutdown)."""
    for folder in list(OWNED):
        _drop(folder)
    _batches.clear()
