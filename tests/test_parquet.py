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


def reader(path):
    return parquet.read(path)


@pytest.mark.parametrize("name", SAME)
def test_values_equal_csv_twin(name):
    head, rows = twin("flat.csv")
    columns, got = reader(FIX / f"{name}.parquet")
    assert columns == head
    assert len(got) == 40
    assert text(got) == rows


@pytest.mark.parametrize("name", ["optional", "optional_dict_snappy"])
def test_optional_columns(name):
    head, rows = twin("optional.csv")
    columns, got = reader(FIX / f"{name}.parquet")
    assert columns == head
    assert text(got) == rows
    assert got[0][1] is None and got[0][2] is None and got[0][5] is None


def test_value_types():
    _, (row, *_) = reader(FIX / "snappy.parquet")
    assert [type(v).__name__ for v in row] == ["int", "str", "float", "bool", "date", "datetime"]


def test_zstd_reads_and_equals_flat_csv():
    head, rows = twin("flat.csv")
    columns, got = reader(FIX / "zstd.parquet")
    assert columns == head and len(got) == 40 and text(got) == rows


def test_not_parquet_and_empty(tmp_path):
    (tmp_path / "a.parquet").write_bytes(b"not a parquet file at all")
    (tmp_path / "b.parquet").write_bytes(b"")
    (tmp_path / "c.parquet").write_bytes(b"PAR1" + bytes(20) + (99).to_bytes(4, "little") + b"PAR1")
    with pytest.raises(ReadError, match="not a valid parquet file"):
        reader(tmp_path / "a.parquet")
    with pytest.raises(ReadError, match="empty file"):
        reader(tmp_path / "b.parquet")
    with pytest.raises(ReadError, match="not a valid parquet file"):
        reader(tmp_path / "c.parquet")


def test_nested_schema_unsupported(tmp_path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    pq.write_table(pa.table({"a": [[1, 2], [3]]}), tmp_path / "n.parquet")
    with pytest.raises(ReadError, match="unsupported parquet encoding"):
        reader(tmp_path / "n.parquet")


def test_catalog_scan_lists_parquet(tmp_path):
    for name in ("plain.parquet", "zstd.parquet", "optional.parquet"):
        shutil.copy(FIX / name, tmp_path / name)
    cat = catalog.scan(tmp_path)
    catalog.scan.cache_clear()
    assert [(d.path, d.kind, d.rows, len(d.columns)) for d in cat.datasets] == [
        ("optional.parquet", "parquet", 40, 6), ("plain.parquet", "parquet", 40, 6), ("zstd.parquet", "parquet", 40, 6)]
    assert cat.unreadable == []
