"""Server-side filters, KPIs and the shared cached view (F1, K1, D1; Board gate 175)."""
import time
from datetime import datetime

from app import filters, rules

COLS = ["date", "region", "amount"]
MAP = {"date": "temporal", "region": "categorical", "amount": "numerical"}
ROWS = [[datetime(2024, 1, d), r, a] for d, r, a in
        [(1, "North", 10.0), (2, "South", 20.0), (3, "North", 5.0), (4, None, 7.0)]] + [[None, "North", 1.0]]


def test_parse_keeps_categorical_last_value_and_valid_dates():
    p = {"f.region": "North", "f.amount": "5", "f.nope": "x", "from": "2024-1-3", "to": "20240105"}
    assert filters.parse(p, COLS, MAP) == (("f.region", "North"), ("to", "2024-01-05"))
    assert filters.parse({"f.region": ""}, COLS, MAP) == ()
    hash(filters.parse({"from": "2024-01-03"}, COLS, MAP))


def test_parse_ignores_dates_without_temporal_column():
    assert filters.parse({"from": "2024-01-03"}, ["a"], {"a": "numerical"}) == ()


def test_apply_and_drop_rows_without_time():
    assert filters.apply((), COLS, MAP, ROWS) is None
    assert filters.apply((("f.region", "North"),), COLS, MAP, ROWS) == [0, 2, 4]
    both = (("f.region", "North"), ("from", "2024-01-02"))
    assert filters.apply(both, COLS, MAP, ROWS) == [2]  # row 4 has no time
    assert filters.apply((("to", "2024-01-02"),), COLS, MAP, ROWS) == [0, 1]
    assert filters.apply((("f.region", "Mars"),), COLS, MAP, ROWS) == []


def test_labels_summary_options():
    f = (("f.region", "North"), ("from", "2024-01-01"), ("to", "2024-01-05"))
    lab = filters.labels(f, COLS, MAP)
    assert lab == ["region = North", "date from 2024-01-01", "date to 2024-01-05"]
    assert filters.summary(lab) == "Filters: region = North; date from 2024-01-01; date to 2024-01-05"
    assert filters.summary([]) == "Filters: none"
    assert filters.options(COLS, ROWS, MAP) == {"region": ["North", "South"]}


def test_options_capped_at_50():
    rows = [[f"v{i:03d}"] for i in range(80)]
    assert filters.options(["c"], rows, {"c": "categorical"})["c"] == [f"v{i:03d}" for i in range(50)]


def test_kpis():
    raw = [[None, "", 1], ["x", "y", 2.5]]
    k = rules.kpis(["a", "b", "n"], raw, raw, {"n": "numerical"})
    assert k == {"rows": 2, "columns": 3, "missing_pct": 33.3, "sums": [{"column": "n", "sum": 3.5}]}
    assert rules.kpis(["a"], [], [], {})["missing_pct"] == 0


def _api(client, data_dir, query=""):
    sales = next(d for d in client.get("/api/datasets").json() if d["path"].endswith("sales.csv"))
    return client.get(f"/api/datasets/{sales['id']}/charts{query}").json()


def test_charts_api_filters(make_client, data_dir):
    client = make_client(data_dir)
    base = _api(client, data_dir)
    assert base["filters"] == []
    assert base["kpis"] == {"rows": 6, "columns": 3, "missing_pct": 0.0,
                            "sums": [{"column": "amount", "sum": 46}]}
    north = _api(client, data_dir, "?f.region=North")
    assert north["filters"] == ["region = North"]
    assert north["kpis"]["rows"] == 3 and north["kpis"]["sums"][0]["sum"] == 16
    assert not [c for c in north["charts"] if c["kind"] == "donut"]
    totals = {c["kind"]: c["total"] for c in base["charts"]}
    assert all(c["total"] < totals[c["kind"]] for c in north["charts"] if c["kind"] in totals)
    assert _api(client, data_dir, "?from=2024-01-03&to=2024-01-05")["kpis"]["rows"] == 3
    assert _api(client, data_dir, "?f.nope=1&f.amount=5")["kpis"]["rows"] == 6


def test_page_accepts_filters(make_client, data_dir):
    client = make_client(data_dir)
    sales = next(d for d in client.get("/api/datasets").json() if d["path"].endswith("sales.csv"))
    assert client.get(f"/datasets/{sales['id']}?f.region=North").status_code == 200


def test_filtered_charts_within_1_s(big_sales_csv, make_client):
    client = make_client(big_sales_csv)
    i = client.get("/api/datasets").json()[0]["id"]
    assert client.get(f"/api/datasets/{i}/charts").status_code == 200  # warm-up
    start = time.perf_counter()
    r = client.get(f"/api/datasets/{i}/charts?f.region=North")
    took = time.perf_counter() - start
    assert r.status_code == 200 and r.json()["kpis"]["rows"] == 50000
    assert took < 1.0
