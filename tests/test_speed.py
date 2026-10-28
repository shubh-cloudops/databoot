"""First-load speed levers (AC-42, gate 176): sampled classify, heatmap pairs once, typed rows, cold requests."""
import statistics
import time
from datetime import datetime
from pathlib import Path

from app import catalog, profile, rules
from app.readers import read_csv


def _cold(make_client, folder, url):
    client = make_client(folder)  # clears the caches; the file is already on disk
    dataset = client.get("/api/datasets").json()[0]
    start = time.perf_counter()
    r = client.get(url.format(id=dataset["id"]))
    took = time.perf_counter() - start
    assert r.status_code == 200
    return took


def test_cold_dashboard_page_within_5_s(big_sales_csv, make_client):
    assert _cold(make_client, big_sales_csv, "/datasets/{id}") <= 5.0


def test_cold_charts_api_within_5_s(big_sales_csv, make_client):
    assert _cold(make_client, big_sales_csv, "/api/datasets/{id}/charts") <= 5.0


def test_classify_uses_first_10000_rows_only():
    rows = [[str(i)] for i in range(10_000)] + [["text"]]
    assert profile.classify(["n"], rows) == {"n": "numerical"}
    assert profile.classify(["n"], rows[1:]) == {"n": "other"}  # the text row is inside the first 10,000


def test_categorical_rule_uses_sample_size():
    rows = [["a" if i % 2 else "b"] for i in range(10_000)] + [[f"x{i}"] for i in range(30_000)]
    assert profile.classify(["c"], rows) == {"c": "categorical"}


def test_sampled_classify_equals_full_on_fixtures(data_dir, make_client, monkeypatch):
    make_client(data_dir)
    sets = [(d.columns, catalog.load(d, 200_000)) for d in catalog.scan(str(data_dir)).datasets]
    sets += [read_csv(p) for p in sorted(Path("tests/fixtures").glob("*.csv"))]
    sampled = [profile.classify(c, r) for c, r in sets]
    monkeypatch.setattr(profile, "SAMPLE", 10**9)
    assert sampled == [profile.classify(c, r) for c, r in sets]
    assert len(sampled) >= 9


def test_heatmap_matches_brute_force_matrix():
    cols = ["a", "b", "c", "d"]
    rows = [[i, (i * 7) % 11, 100 - i * i, 5 if i % 2 else 5.5] for i in range(30)]
    rows[3][1] = None  # pairwise complete rows
    mapping = {c: "numerical" for c in cols}

    class S:
        map_cap = chart_cap = 1000

    (chart,) = [c for c in rules.charts(cols, rows, mapping, S) if c["kind"] == "heatmap"]
    def corr(i, j):
        pairs = [(r[i], r[j]) for r in rows if r[i] is not None and r[j] is not None]
        return statistics.correlation(*zip(*pairs))

    want = [[1 if i == j else corr(i, j) for j in range(4)] for i in range(4)]
    assert chart["data"]["z"] == want


def test_typed_casts_and_is_idempotent():
    cols = ["when", "n", "lat", "label"]
    mapping = {"when": "temporal", "n": "numerical", "lat": "geospatial", "label": "categorical"}
    rows = [["2024-01-02", "5", "1.5", "x"], ["oops", "nan", "", "y"]]
    t = rules.typed(cols, rows, mapping)
    assert t == [[datetime(2024, 1, 2), 5.0, 1.5, "x"], [None, None, None, "y"]]
    assert rows[0][1] == "5"  # the input is a copy
    assert rules.typed(cols, t, mapping) == t
    assert rules._num(2.5) == 2.5 and rules._time(t[0][0]) is t[0][0]
    assert rules.charts(cols, rows, mapping, type("S", (), {"map_cap": 100, "chart_cap": 100})) == \
        rules.charts(cols, t, mapping, type("S", (), {"map_cap": 100, "chart_cap": 100}))
