"""Map app figures part 1: valid points, points mode, hex cells (ARCHITECTURE.md "Round 5: Map app")."""
import math
from types import SimpleNamespace

from app import geo

COLS = ["lat", "lon", "pop"]
MAP = {"lat": "geospatial", "lon": "geospatial", "pop": "numerical"}


def _view(rows):
    """geo.view on (lat, lon, pop) tuples; typed cells are numbers or None, rows stay as the raw strings."""
    typed = [[None if c is None else float(c) for c in r] for r in rows]
    raw = [["" if c is None else str(c) for c in r] for r in rows]
    return geo.view(COLS, raw, typed, MAP, SimpleNamespace())["charts"][0]


def _app(make_client, folder, name):
    client = make_client(folder)
    sid = next(d["id"] for d in client.get("/api/datasets").json() if d["path"] == name)
    return client.get(f"/api/datasets/{sid}/app").json()


def test_points_mode_colour_rows_and_invalid_points():
    rows = [(10, 20, 5), (91, 20, 6), (10, 181, 7), (None, 20, 8), (-90, -180, None), (0, 0, 1)]
    c = _view(rows)
    assert c["kind"] == "map2d" and c["data"]["mode"] == "points"
    assert c["data"]["lat"] == [10, -90, 0] and c["data"]["lon"] == [20, -180, 0]
    assert c["data"]["color"] == [5, None, 1]  # a missing pop stays None
    assert c["data"]["row"] == [0, 4, 5]  # view row indexes
    assert (c["shown"], c["total"]) == (3, 6) and c["z_label"] == "pop"
    assert c["columns"] == COLS and c["rows"] == [["10", "20", "5"], ["-90", "-180", ""], ["0", "0", "1"]]


def test_no_numeric_means_none_colour_and_no_pair_means_no_chart():
    typed = [[1.0, 2.0], [3.0, 4.0]]
    c = geo.view(["lat", "lon"], [["1", "2"], ["3", "4"]], typed, {"lat": "geospatial", "lon": "geospatial"}, None)
    assert c["charts"][0]["data"]["color"] == [None, None] and c["charts"][0]["z_label"] is None
    assert geo.view(["a"], [["1"]], [[1.0]], {"a": "numerical"}, None) == {"charts": [], "map3d": None}


def test_hex_counts_by_hand(monkeypatch):
    monkeypatch.setattr(geo, "HEX_AT", 3)
    # lon span 40 -> size 1; three points round to cell (0, 0), the one at lon 40 to (23, 0)
    c = _view([(0, 0, 1), (0.1, 0, 1), (-0.1, 0, 1), (0.3, 40, 1)])
    d = c["data"]
    assert d["mode"] == "hex" and d["size"] == 1.0 and d["count"] == [3, 1]
    assert d["lon"] == [0, math.sqrt(3) * 23] and d["lat"] == [0, 0]
    assert (c["shown"], c["total"]) == (4, 4) and "rows" not in c


def test_hex_zero_span_has_size_one(monkeypatch):
    monkeypatch.setattr(geo, "HEX_AT", 1)
    d = _view([(5, 7, 1), (5, 7, 2)])["data"]
    assert d["size"] == 1.0 and d["count"] == [2]


def test_more_than_5000_points_make_hex_cells():
    c = _view([(i % 180 - 90, i % 360 - 180, 1) for i in range(5001)])
    assert c["data"]["mode"] == "hex" and sum(c["data"]["count"]) == 5001
    assert len(c["data"]["count"]) < 5001


def test_app_route_places_is_points(make_client, archetypes_dir):
    got = _app(make_client, archetypes_dir, "places.csv")
    c = got["charts"][0]
    assert got["shown"] == "map" and c["kind"] == "map2d" and c["data"]["mode"] == "points"
    assert c["data"]["color"] == [1000 * (i + 1) for i in range(20)] and c["z_label"] == "pop"
    assert (c["shown"], c["total"]) == (20, 20) and len(c["rows"]) == 20 and got["map3d"] is None


def test_app_route_points_tsv(make_client, data_dir):
    c = _app(make_client, data_dir, "points.tsv")["charts"][0]
    assert c["kind"] == "map2d" and c["data"]["mode"] == "points" and c["z_label"] == "value"


def test_app_route_big_csv_is_hex(make_client, big_csv):
    got = _app(make_client, big_csv, "big.csv")
    c = got["charts"][0]
    assert got["shown"] == "map" and c["data"]["mode"] == "hex"
    assert sum(c["data"]["count"]) == 60_000 and len(c["data"]["count"]) < 60_000
    assert (c["shown"], c["total"]) == (60_000, 60_000)
