"""Parquet reader: every fixture in tests/fixtures was written once with pyarrow; its CSV twin holds the same values."""
import csv
import shutil
from pathlib import Path

import pytest

from app import catalog, parquet
from app.readers import ReadError

FIX = Path(__file__).parent / "fixtures"
SAME = ["plain", "gzip", "snappy", "dict", "int96", "groups"]


def twin(name):
    with open(FIX / name, newline="") as f:
        head, *rows = csv.reader(f)
    return head, rows


def text(rows):
    return [["" if v is None else str(v) for v in r] for r in rows]


@pytest.fixture(params=[True, False], ids=["pyarrow-or-fallback", "stdlib"])
def reader(request, monkeypatch):
    """Run each check on whatever read() picks, and again with pyarrow hidden so the fallback is always covered."""
    if not request.param:
        monkeypatch.setitem(__import__("sys").modules, "pyarrow.parquet", None)
        monkeypatch.setitem(__import__("sys").modules, "pyarrow", None)
    return parquet.read


@pytest.mark.parametrize("name", SAME)
def test_values_equal_csv_twin(reader, name):
    head, rows = twin("flat.csv")
    columns, got = reader(FIX / f"{name}.parquet")
    assert columns == head
    assert len(got) == 40
    assert text(got) == rows


@pytest.mark.parametrize("name", ["optional", "optional_dict_snappy"])
def test_optional_columns(reader, name):
    head, rows = twin("optional.csv")
    columns, got = reader(FIX / f"{name}.parquet")
    assert columns == head
    assert text(got) == rows
    assert got[0][1] is None and got[0][2] is None and got[0][5] is None


def test_value_types(reader):
    _, (row, *_) = reader(FIX / "snappy.parquet")
    assert [type(v).__name__ for v in row] == ["int", "str", "float", "bool", "date", "datetime"]


@pytest.mark.parametrize("name", ["zstd"])
def test_unsupported_codec(reader, name):
    with pytest.raises(ReadError, match="unsupported parquet encoding"):
        reader(FIX / f"{name}.parquet")


def test_not_parquet_and_empty(reader, tmp_path):
    (tmp_path / "a.parquet").write_bytes(b"not a parquet file at all")
    (tmp_path / "b.parquet").write_bytes(b"")
    with pytest.raises(ReadError, match="unsupported parquet encoding"):
        reader(tmp_path / "a.parquet")
    with pytest.raises(ReadError, match="empty file"):
        reader(tmp_path / "b.parquet")


def test_nested_schema_unsupported(reader, tmp_path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    pq.write_table(pa.table({"a": [[1, 2], [3]]}), tmp_path / "n.parquet")
    with pytest.raises(ReadError, match="unsupported parquet encoding"):
        reader(tmp_path / "n.parquet")


def test_snappy_copies():
    # literal "abcd" then a copy of 8 bytes at offset 4 (overlapping), tag kind 2 = 2-byte offset
    blob = bytes([12, 3 << 2]) + b"abcd" + bytes([(8 - 1) << 2 | 2, 4, 0])
    assert parquet._snappy(blob) == b"abcdabcdabcd"


def test_catalog_scan_lists_parquet(tmp_path):
    for name in ("plain.parquet", "zstd.parquet", "optional.parquet"):
        shutil.copy(FIX / name, tmp_path / name)
    cat = catalog.scan(tmp_path)
    catalog.scan.cache_clear()
    assert [(d.path, d.kind, d.rows, len(d.columns)) for d in cat.datasets] == [
        ("optional.parquet", "parquet", 40, 6), ("plain.parquet", "parquet", 40, 6)]
    assert [(u.path, u.reason) for u in cat.unreadable] == [("zstd.parquet", "unsupported parquet encoding")]
