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
    return geo.view(COLS, raw, typed, MAP, SimpleNamespace(map_cap=50_000))["charts"][0]


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
    c = geo.view(["lat", "lon"], [["1", "2"], ["3", "4"]], typed, {"lat": "geospatial", "lon": "geospatial"}, SimpleNamespace(map_cap=100))
    assert c["charts"][0]["data"]["color"] == [None, None] and c["charts"][0]["z_label"] is None
    assert geo.view(["a"], [["1"]], [[1.0]], {"a": "numerical"}, None) == {"charts": [], "map3d": None}
    assert geo.view(["lat", "lon"], [["1", "2"]], [[1.0, 2.0]], {"lat": "geospatial", "lon": "geospatial"},
                    SimpleNamespace(map_cap=100))["map3d"]["z_label"] is None


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
    assert (c["shown"], c["total"]) == (20, 20) and len(c["rows"]) == 20 
    assert [x["kind"] for x in got["charts"]] == ["map2d", "bar"] and got["map3d"]["z_label"] == "pop"
    r = got["charts"][1]  # 5 places per country, pop = 1000 * (i + 1), i % 4 picks France, Japan, Brazil, Kenya
    sums = {n: sum(1000 * (i + 1) for i in range(20) if i % 4 == k) for k, n in enumerate(("France", "Japan", "Brazil", "Kenya"))}
    assert r["x_label"] == "country" and r["data"]["x"] == sorted(sums, key=lambda n: -sums[n])
    assert r["data"]["y"] == sorted(sums.values(), reverse=True) and (r["orientation"], r["drill"], r["other"]) == ("h", False, False)
    assert r["id"] == "chart-2" and r["baseline"] == 0


def test_app_route_points_tsv(make_client, data_dir):
    c = _app(make_client, data_dir, "points.tsv")["charts"][0]
    assert c["kind"] == "map2d" and c["data"]["mode"] == "points" and c["z_label"] == "value"


def test_app_route_big_csv_is_hex(make_client, big_csv):
    got = _app(make_client, big_csv, "big.csv")
    c = got["charts"][0]
    assert got["shown"] == "map" and c["data"]["mode"] == "hex"
    assert sum(c["data"]["count"]) == 60_000 and len(c["data"]["count"]) < 60_000
    assert (c["shown"], c["total"]) == (60_000, 60_000)


def _typed(columns, rows, mapping):
    from app import rules
    return rules.typed(columns, rows, mapping)


def test_map3d_z_is_primary_numeric_but_explorer_stays_first_numerical():
    cols, mp = ["lat", "lon", "a", "revenue"], {"lat": "geospatial", "lon": "geospatial", "a": "numerical", "revenue": "numerical"}
    rows = [["1", "2", "3", "40"], ["4", "5", "6", "50"]]
    typed = _typed(cols, rows, mp)
    m3 = geo.view(cols, rows, typed, mp, SimpleNamespace(map_cap=100))["map3d"]
    assert m3["z_label"] == "revenue" and m3["data"]["z"] == [40, 50] and m3["kind"] == "map3d"
    from app import rules
    explorer = next(c for c in rules.charts(cols, typed, mp, SimpleNamespace(map_cap=100, chart_cap=100)) if c["kind"] == "map3d")
    assert explorer["z_label"] == "a"


def test_regions_fewest_distinct_categorical_top_10_and_other():
    cols = ["lat", "lon", "kind", "town", "n"]
    mp = {"lat": "geospatial", "lon": "geospatial", "kind": "categorical", "town": "categorical", "n": "numerical"}
    # kind has 1 distinct value (skipped, < 2); town has 12 -> top 10 + Other
    rows = [[str(i), str(i), "x", f"t{i % 12}", str(i + 1)] for i in range(24)]
    r = geo.view(cols, rows, _typed(cols, rows, mp), mp, SimpleNamespace(map_cap=100))["charts"][1]
    assert r["x_label"] == "town" and len(r["data"]["x"]) == 11 and r["data"]["x"][-1] == "Other" and r["other"] is True
    assert sum(r["data"]["y"]) == sum(range(1, 25)) and r["data"]["y"][:10] == sorted(r["data"]["y"][:10], reverse=True)


def test_regions_row_count_without_numeric_and_none_without_categorical():
    mp = {"lat": "geospatial", "lon": "geospatial", "c": "categorical"}
    rows = [["1", "1", "a"], ["2", "2", "b"], ["3", "3", "b"]]
    r = geo.view(["lat", "lon", "c"], rows, _typed(["lat", "lon", "c"], rows, mp), mp, SimpleNamespace(map_cap=9))["charts"][1]
    assert r["data"] == {"x": ["b", "a"], "y": [2, 1]} and r["y_label"] == "count"
    mp2 = {"lat": "geospatial", "lon": "geospatial"}
    got = geo.view(["lat", "lon"], rows, _typed(["lat", "lon"], rows, mp2), mp2, SimpleNamespace(map_cap=9))
    assert len(got["charts"]) == 1


def test_app_route_without_categorical_has_only_the_map(make_client, tmp_path):
    (tmp_path / "p.csv").write_text("lat,lon,v\n" + "".join(f"{i},{i},{i}\n" for i in range(10)))
    got = _app(make_client, tmp_path, "p.csv")
    assert [c["kind"] for c in got["charts"]] == ["map2d"] and got["map3d"]["z_label"] == "v"


def test_panel_rows_format_numerical_non_plain_columns_only():
    cols, mapping = ["lat", "lon", "pop", "year", "order_id", "name"], {"lat": "geospatial", "lon": "geospatial", "pop": "numerical",
                                                                       "year": "numerical", "order_id": "numerical", "name": "categorical"}
    raw = [["10", "20", "20000", "2024", "10045", "12345"], ["11", "21", "5", "2023", "10046", "x"]]
    typed = [[10.0, 20.0, 20000.0, 2024.0, 10045.0, None], [11.0, 21.0, 5.0, 2023.0, 10046.0, None]]
    c = geo.view(cols, raw, typed, mapping, SimpleNamespace(map_cap=50_000))["charts"][0]
    assert c["rows"][0] == ["10", "20", "20,000", "2024", "10045", "12345"]  # text column untouched
