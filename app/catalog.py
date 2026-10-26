"""Data access: scan the data folder, give each dataset a stable id, load its rows. See ARCHITECTURE.md "Data access"."""
import hashlib
import os
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from app import config, parquet, readers, xlsx
from app.readers import ReadError

# Extension -> kind, and the reader of each kind (xlsx is read per sheet in _read).
KINDS = {".csv": "csv", ".tsv": "tsv", ".tab": "tsv", ".xlsx": "xlsx", ".xlsm": "xlsx", ".json": "json",
         ".jsonl": "jsonl", ".ndjson": "jsonl", ".geojson": "geojson",
         ".parquet": "parquet"}
READERS = {"csv": readers.read_csv, "tsv": readers.read_tsv, "json": readers.read_json,
           "jsonl": readers.read_jsonl, "geojson": readers.read_geojson,
           "parquet": parquet.read}
FAILED = "could not read file"


@dataclass(unsafe_hash=True)
class Dataset:
    id: str            # sha1(f"{relative path}|{sheet}")[:12]
    path: str          # path relative to the data folder, forward slashes
    sheet: str | None  # Excel sheet name, else None
    kind: str          # csv, tsv, xlsx, json, jsonl, parquet, geojson
    rows: int          # total data rows in the file (not capped)
    columns: list[str] = field(default_factory=list, compare=False)  # list: keeps Dataset hashable for lru_cache


@dataclass
class Unreadable:
    path: str
    reason: str        # short fixed note, e.g. "empty file", "not a valid xlsx"
    sheet: str | None = None  # set when one Excel sheet failed, else None


@dataclass
class OtherFile:       # file inventory: unrecognised extensions
    path: str
    type: str          # lower-case extension without dot, "" if none
    size: int          # bytes
    modified: str      # ISO date of mtime, YYYY-MM-DD


@dataclass
class Catalog:
    datasets: list[Dataset]
    unreadable: list[Unreadable]
    others: list[OtherFile]


def _read(dataset, path):
    """(columns, rows) of one dataset's file."""
    if dataset.kind == "xlsx":
        return xlsx.read_sheet(path, dataset.sheet)
    return READERS[dataset.kind](path)


def _make(rel, sheet, kind, path):
    """Dataset with row and column counts, read once."""
    key = hashlib.sha1(f"{rel}|{sheet or ''}".encode()).hexdigest()[:12]
    d = Dataset(key, rel, sheet, kind, 0)
    d.columns, rows = _read(d, path)
    d.rows = len(rows)
    return d


@lru_cache(maxsize=1)
def scan(folder) -> Catalog:
    cat = Catalog([], [], [])
    found = []
    for top, dirs, files in os.walk(folder):  # followlinks is off: linked folders are listed, never entered
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        found += [Path(top, f) for f in files if not f.startswith(".")]
    root = Path(folder)
    for path in sorted(found, key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            continue
        ext = path.suffix.lower()
        kind = KINDS.get(ext)
        if kind is None:
            st = path.stat()
            cat.others.append(OtherFile(rel, ext[1:], st.st_size, date.fromtimestamp(st.st_mtime).isoformat()))
            continue
        try:
            sheets = xlsx.sheet_names(path) if kind == "xlsx" else [None]
            if not sheets:
                raise ReadError(xlsx.NOT_XLSX)
        except Exception as e:  # any reader failure is a note on this file only (AC-12)
            cat.unreadable.append(Unreadable(rel, str(e) if isinstance(e, ReadError) else FAILED))
            continue
        for sheet in sheets:
            try:
                cat.datasets.append(_make(rel, sheet, kind, path))
            except Exception as e:
                cat.unreadable.append(Unreadable(rel, str(e) if isinstance(e, ReadError) else FAILED, sheet))
    return cat


@lru_cache(maxsize=4)
def load(dataset: Dataset, max_rows: int) -> list[list]:
    """First max_rows data rows, each a list aligned with dataset.columns (header excluded)."""
    # ponytail: reads the whole file then cuts; stream with a row limit if 200,000-row caps get slow.
    return _read(dataset, Path(config.get().data, dataset.path))[1][:max_rows]
