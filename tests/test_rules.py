import json

from app import catalog, config, profile, rules


def charts_of(folder, path, sheet=None):
    d = next(d for d in catalog.scan(folder).datasets if d.path == path and d.sheet == sheet)
    rows = catalog.load(d, 200_000)
    return rules.charts(d.columns, rows, profile.classify(d.columns, rows), config.get())


def test_sales_bar_and_line(make_client, data_dir):
    make_client(data_dir)
    cs = charts_of(data_dir, "sales.csv")
    assert [c["id"] for c in cs] == ["chart-1", "chart-2", "chart-3", "chart-4"]
    assert [c["kind"] for c in cs] == ["line", "histogram", "bar", "donut"]
    line, bar = (next(c for c in cs if c["kind"] == k) for k in ("line", "bar"))
    assert line["kind"] == "line" and line["data"]["x"][0] == "2024-01-01" and line["data"]["y"] == [10, 20, 5, 7, 3, 1]
    assert bar["kind"] == "bar" and dict(zip(bar["data"]["x"], bar["data"]["y"])) == {"North": 16, "South": 23, "East": 7}
    assert bar["data"]["x"] == ["South", "North", "East"]
    assert bar["shown"] == bar["total"] == 6
    assert set(bar) == {"id", "kind", "title", "x_label", "y_label", "rule", "shown", "total", "data", "score", "baseline"}


def test_bars_sorted_descending_with_zero_baseline():
    cols = ["g", "v"]
    rows = [["b", "-5"], ["a", "3"], ["c", "3"], ["d", "0"], ["e", "-1"], ["a", "0"]]
    bars = [c for c in rules.charts(cols, rows, {"g": "categorical", "v": "numerical"}, config.get()) if c["kind"] == "bar"]
    assert bars
    for b in bars:
        y = b["data"]["y"]
        assert y == sorted(y, reverse=True) and b["baseline"] == 0
    assert bars[0]["data"]["x"] == ["a", "c", "d", "e", "b"] and bars[0]["data"]["y"] == [3, 3, 0, -1, -5]


def test_xlsx_revenue_line(make_client, data_dir):
    make_client(data_dir)
    line = charts_of(data_dir, "sub/book.xlsx", "Revenue")[0]
    assert line["kind"] == "line" and line["x_label"] == "month" and line["data"]["x"][0] == "2024-01-01"
    assert line["data"]["y"] == [100, 101, 102, 103, 104, 105]


def test_no_charts_for_free_text(make_client, data_dir):
    make_client(data_dir)
    assert charts_of(data_dir, "notes.csv") == []


def test_map_axes_and_z(make_client, data_dir):
    make_client(data_dir)
    m = charts_of(data_dir, "points.tsv")[0]
    assert m["kind"] == "map3d" and (m["x_label"], m["y_label"]) == ("LON", "Latitude")
    assert m["z_label"] == "value"
    assert m["data"] == {"lon": [-0.12, 2.35, -74.0, 139.69], "lat": [51.5, 48.85, 40.71, 35.68], "z": [3.0, 4.5, 8.0, 9.5]}


def test_map_without_numerical_z_is_zero():
    cols, rows = ["lat", "lon"], [["1", "2"], ["3", "4"]]
    m = rules.charts(cols, rows, profile.classify(cols, rows), config.get())[0]
    assert m["data"]["z"] == [0, 0] and m["z_label"] is None


def test_no_map_with_only_one_geo_column():
    cols, rows = ["lat", "n"], [["1", "2"]]
    cs = rules.charts(cols, rows, profile.classify(cols, rows), config.get())
    assert [c["kind"] for c in cs] == ["histogram"]


def test_big_map_is_sampled(make_client, big_csv):
    client = make_client(big_csv)
    (d,) = client.get("/api/datasets").json()
    m = client.get(f"/api/datasets/{d['id']}/charts").json()["charts"]
    m = next(c for c in m if c["kind"] == "map3d")
    assert m["kind"] == "map3d" and m["total"] == 60_000 and 0 < m["shown"] <= 50_000
    assert len(m["data"]["lon"]) == m["shown"]


def test_line_sampling_cap(monkeypatch):
    monkeypatch.setenv("DATABOOT_CHART_CAP", "10")
    cols, rows = ["d", "v"], [[f"2024-01-{i % 28 + 1:02d}", i] for i in range(28)]
    line = rules.charts(cols, rows, {"d": "temporal", "v": "numerical"}, config.get())[0]
    assert line["total"] == 28 and line["shown"] == 10 == len(line["data"]["x"])


def test_nan_inf_become_null_and_json_is_valid():
    cols, rows = ["c", "v"], [["a", float("nan")], ["a", 2.0], ["b", 1e308], ["b", 1e308]]
    bar = rules.charts(cols, rows, {"c": "categorical", "v": "numerical"}, config.get())[0]
    assert bar["data"] == {"x": ["b", "a"], "y": [None, 2.0]}  # NaN cell skipped, overflowing sum -> null
    json.dumps(bar, allow_nan=False)


def test_count_bar_without_numerical():
    cols, rows = ["c"], [["a"], ["b"], ["a"], [None]]
    bar = rules.charts(cols, rows, {"c": "categorical"}, config.get())[0]
    assert bar["data"] == {"x": ["a", "b"], "y": [2, 1]} and bar["y_label"] == "count"


def test_charts_route(make_client, data_dir):
    client = make_client(data_dir)
    d = next(d for d in client.get("/api/datasets").json() if d["path"] == "sales.csv")
    r = client.get(f"/api/datasets/{d['id']}/charts")
    assert r.status_code == 200
    body = r.json()
    assert body["dataset"] == d["id"] and [c["kind"] for c in body["charts"]] == ["line", "histogram", "bar", "donut"]
    assert client.get("/api/datasets/nope/charts").status_code == 404
