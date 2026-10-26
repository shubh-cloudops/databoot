import json

import pytest

from app import readers
from app.readers import ReadError


def test_fixture_files(data_dir):
    sub = data_dir / "sub"
    cols, rows = readers.read_tsv(data_dir / "points.tsv")
    assert (cols, len(rows)) == (["Latitude", "LON", "value"], 4)
    assert rows[0] == ["51.5", "-0.12", "3.0"]
    assert readers.read_csv(data_dir / "sales.csv")[1][0] == ["2024-01-01", "North", "10"]
    cols, rows = readers.read_json(sub / "records.json")
    assert (cols, rows[1]) == (["country", "pop"], ["Japan", 125])
    cols, rows = readers.read_jsonl(sub / "events.jsonl")
    assert (cols, len(rows), rows[3]) == (["n", "kind"], 10, [3, "b"])
    cols, rows = readers.read_geojson(sub / "cities.geojson")
    assert (cols, len(rows), rows[2]) == (["size", "longitude", "latitude"], 4, [8.0, -74.0, 40.71])


def test_count_rows_matches_read(data_dir):
    for name, kind in [("points.tsv", "tsv"), ("sub/records.json", "json"),
                       ("sub/events.jsonl", "jsonl"), ("sub/cities.geojson", "geojson")]:
        cols, rows = getattr(readers, f"read_{kind}")(data_dir / name)
        assert readers.count_rows(data_dir / name, kind) == (cols, len(rows))


def test_csv_headers_and_cells(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text(" a ,,a,a,b\n1,,x\n\n,2,3,4,5,6\n")
    cols, rows = readers.read_csv(p)
    assert cols == ["a", "column_2", "a_2", "a_3", "b"]
    assert rows == [["1", None, "x", None, None], [None, "2", "3", "4", "5"]]


def test_csv_encodings(tmp_path):
    (tmp_path / "bom.csv").write_bytes("﻿name\nÉlan\n".encode("utf-8"))
    assert readers.read_csv(tmp_path / "bom.csv") == (["name"], [["Élan"]])
    (tmp_path / "latin.csv").write_bytes("name\ncafé\n".encode("cp1252"))
    assert readers.read_csv(tmp_path / "latin.csv")[1] == [["café"]]
    (tmp_path / "bad.csv").write_bytes(b"name\n\x81\xff\n")  # 0x81 is undefined in cp1252
    with pytest.raises(ReadError, match="could not decode text"):
        readers.read_csv(tmp_path / "bad.csv")


def test_json_shapes(tmp_path):
    p = tmp_path / "a.json"
    for text in ('{"data": [{"a": 1}, {"b": ""}]}', '{"x": 1, "records": [{"a": 1}, {"b": ""}]}'):
        p.write_text(text)
        assert readers.read_json(p) == (["a", "b"], [[1, None], [None, None]])
    p.write_text('[{"a": {"k": [1]}, "b": null}]')
    assert readers.read_json(p) == (["a", "b"], [['{"k": [1]}', None]])


def test_jsonl_skips_blank_lines(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_text('{"a": 1}\n\n  \n{"b": 2}\n')
    assert readers.read_jsonl(p) == (["a", "b"], [[1, None], [None, 2]])


def test_geojson_geometries(tmp_path):
    def feat(geometry, **props):
        return {"type": "Feature", "geometry": geometry, "properties": props}
    p = tmp_path / "a.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": [
        feat({"type": "Polygon", "coordinates": [[[0, 0], [4, 0], [4, 2], [0, 2]], [[9, 9]]]}, a=1),
        feat({"type": "LineString", "coordinates": [[0, 0], [2, 4]]}, b=2),
        feat(None, a=3),
    ]}))
    assert readers.read_geojson(p) == (["a", "b", "longitude", "latitude"], [
        [1, None, 2.0, 1.0], [None, 2, 1.0, 2.0], [3, None, None, None]])


@pytest.mark.parametrize("kind, text, note", [
    ("csv", "", "empty file"),
    ("jsonl", "", "empty file"),
    ("csv", "\n \n", "no header row"),
    ("json", "[]", "no header row"),
    ("jsonl", "\n\n", "no header row"),
    ("json", '{"a": 1}', "not a list of records"),
    ("json", "[1, 2]", "not a list of records"),
    ("json", "{oops", "invalid JSON"),
    ("jsonl", '{"a": 1}\nnope\n', "invalid JSON"),
    ("geojson", "[]", "not a list of records"),
])
def test_failures(tmp_path, kind, text, note):
    p = tmp_path / f"f.{kind}"
    p.write_text(text)
    with pytest.raises(ReadError, match=note):
        readers.count_rows(p, kind)
    with pytest.raises(ValueError, match=note):  # ReadError is a ValueError
        getattr(readers, f"read_{kind}")(p)
