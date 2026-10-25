"""Data access: scan the data folder, give each dataset a stable id, load its rows. See ARCHITECTURE.md "Data access"."""
from dataclasses import dataclass, field


@dataclass
class Dataset:
    id: str            # sha1(f"{relative path}|{sheet}")[:12]
    path: str          # path relative to the data folder, forward slashes
    sheet: str | None  # Excel sheet name, else None
    kind: str          # csv, tsv, xlsx, json, jsonl, parquet, geojson
    rows: int          # total data rows in the file (not capped)
    columns: list[str] = field(default_factory=list)


@dataclass
class Unreadable:
    path: str
    reason: str        # short fixed note, e.g. "empty file", "not a valid xlsx"


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


def scan(folder) -> Catalog:
    raise NotImplementedError


def load(dataset: Dataset, max_rows: int) -> list[list]:
    """First max_rows data rows, each a list aligned with dataset.columns (header excluded)."""
    raise NotImplementedError
