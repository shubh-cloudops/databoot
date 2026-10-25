import csv
import json
from datetime import date

from app import profile
from app.readers import read_csv

FIXTURE = "tests/fixtures/flat.csv"


def kinds(name, values, total=None):
    rows = [[v] for v in values]
    return profile.classify([name], rows)[name]


def test_geospatial_by_header_any_case():
    assert all(kinds(n, [1.0]) == "geospatial" for n in ("lat", "LON", "Lng", " Latitude ", "LONGITUDE"))
    assert kinds("latency", [1.0]) == "numerical"


def test_temporal():
    assert kinds("d", [date(2024, 1, 1), date(2024, 1, 2)]) == "temporal"
    assert kinds("d", ["2024-01-01", "2024-01-02 10:00:00"]) == "temporal"
    for v in ("31/12/2024", "12/31/2024", "2024/12/31", "31-12-2024", "31.12.2024"):
        assert kinds("d", [v]) == "temporal"
    assert kinds("d", ["2024-01-01"] * 9 + ["oops"]) == "temporal"
    assert kinds("d", ["2024-01-01"] * 8 + ["oops"] * 2) != "temporal"
    assert kinds("year", [2020, 2021]) == "numerical"
    assert kinds("year", ["2020", "2021"]) == "numerical"


def test_numerical_and_bool():
    assert kinds("n", [1, 2.5, None, ""]) == "numerical"
    assert kinds("n", ["1", "-2.5", "1e3", ".5"]) == "numerical"
    assert kinds("n", [1, "a"]) == "other"
    assert kinds("b", [True, False] * 3) == "categorical"  # bool is not numerical


def test_categorical_limits():
    assert kinds("c", ["a", "b"] * 5) == "categorical"
    assert kinds("c", [f"v{i % 50}" for i in range(100)]) == "categorical"   # 50 distinct, 50% of rows
    assert kinds("c", [f"v{i % 51}" for i in range(200)]) == "other"         # 51 distinct
    assert kinds("c", ["a", "b", "c"]) == "other"                            # 100% distinct


def test_other_and_empty():
    assert kinds("c", [None, "", None]) == "other"
    assert profile.classify(["c"], []) == {"c": "other"}
    assert kinds("c", [{"x": 1}]) == "other"


def test_fixture_file():
    cols, rows = read_csv(FIXTURE)
    got = profile.classify(cols, rows)
    assert got["region"] == "categorical" and got["price"] == "numerical" and got["day"] == "temporal"
    assert got["ts"] == "temporal" and got["id"] == "numerical"


def test_data_dir(data_dir, make_client):
    c = make_client(data_dir)
    by_path = {d["path"]: d for d in c.get("/api/datasets").json()}
    assert by_path["points.tsv"]["columns"] == 3 and by_path["points.tsv"]["rows"] == 4
    assert set(by_path["sales.csv"]) == {"id", "path", "sheet", "kind", "rows", "columns"}
    assert c.get(f"/api/datasets/{by_path['points.tsv']['id']}/profile").json() == {
        "Latitude": "geospatial", "LON": "geospatial", "value": "numerical"}
    assert c.get(f"/api/datasets/{by_path['sales.csv']['id']}/profile").json() == {
        "date": "temporal", "region": "categorical", "amount": "numerical"}
    assert c.get(f"/api/datasets/{by_path['notes.csv']['id']}/profile").json() == {"comment": "other"}


def test_route_matches_saved_file(data_dir, make_client, tmp_path):
    c = make_client(data_dir)
    d = next(d for d in c.get("/api/datasets").json() if d["path"] == "sales.csv")
    body = c.get(f"/api/datasets/{d['id']}/profile").json()
    assert json.loads((tmp_path / "out" / "profiles" / f"{d['id']}.json").read_text()) == body
    assert set(body) == {"date", "region", "amount"}


def test_unknown_id(data_dir, make_client):
    assert make_client(data_dir).get("/api/datasets/nope/profile").status_code == 404
