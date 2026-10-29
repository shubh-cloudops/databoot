"""Archetype detection, measures and GET /api/datasets/{id}/app (ARCHITECTURE.md "Round 5")."""
import pytest

from app import apps, catalog, config, main


def _ids(client):
    return {d["path"]: d["id"] for d in client.get("/api/datasets").json()}


def _detect_and_measures(name):
    d = next(d for d in catalog.scan(config.get().data).datasets if d.path == name)
    _, mapping, typed, _ = main._base(d)
    return apps.detect(d.columns, mapping, typed), [d.columns[i] for i in apps.measures(d.columns, mapping)]


@pytest.mark.parametrize("name, app, rule, qualifies, meas", [
    ("shop.csv", "business", "R2", ["business", "explorer"], ["revenue", "units"]),
    ("places.csv", "map", "R1", ["map", "explorer"], ["pop"]),
    ("measures.csv", "explorer", "R3", ["explorer"], ["a", "b", "c"]),
    ("sparse.csv", "explorer", "R3", ["explorer"], ["a", "b", "c"]),
])
def test_detect_and_measures_on_fixtures(make_client, archetypes_dir, name, app, rule, qualifies, meas):
    make_client(archetypes_dir)
    got, cols = _detect_and_measures(name)
    assert got == {"app": app, "rule": rule, "qualifies": qualifies}
    assert cols == meas


def test_measures_name_rule_first_then_column_order(make_client, tmp_path):
    (tmp_path / "m.csv").write_text("a,Total,qty\n" + "".join(f"{i},{i * 3},{i + 7}\n" for i in range(6)))
    make_client(tmp_path)
    assert _detect_and_measures("m.csv")[1] == ["Total", "qty", "a"]


def test_measures_no_match_falls_back_to_first_numerical():
    assert apps.measures(["x", "y"], {"x": "numerical", "y": "numerical"}) == [0, 1]


def test_empty_rows_only_map_with_two_numericals():
    cols, mapping = ["lat", "lon", "a", "b", "c"], {"lat": "geospatial", "lon": "geospatial", "a": "numerical",
                                                    "b": "numerical", "c": "numerical"}
    assert apps.detect(cols, mapping, [])["app"] == "explorer"
    assert apps.detect(cols[:4], mapping, [])["app"] == "map"


def test_app_route_detected_and_stable(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    sid = _ids(client)["shop.csv"]
    plain = client.get(f"/api/datasets/{sid}/app").json()
    assert (plain["app"], plain["rule"], plain["qualifies"], plain["shown"]) == (
        "business", "R2", ["business", "explorer"], "business")
    again = client.get(f"/api/datasets/{sid}/app").json()
    filtered = client.get(f"/api/datasets/{sid}/app?f.store=North").json()
    for other in (again, filtered):
        assert {k: other[k] for k in ("app", "rule", "qualifies")} == {k: plain[k] for k in ("app", "rule", "qualifies")}
    assert filtered["filters"] and plain["filters"] == []


def test_app_param_must_qualify(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    ids = _ids(client)
    assert client.get(f"/api/datasets/{ids['shop.csv']}/app?app=map").json()["shown"] == "business"
    assert client.get(f"/api/datasets/{ids['shop.csv']}/app?app=nope").json()["shown"] == "business"
    assert client.get(f"/api/datasets/{ids['measures.csv']}/app?app=business").json()["shown"] == "explorer"


def test_app_explorer_charts_equal_charts_route(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    mid = _ids(client)["measures.csv"]
    got = client.get(f"/api/datasets/{mid}/app").json()["charts"]
    assert got == client.get(f"/api/datasets/{mid}/charts").json()["charts"]
    assert [c["id"] for c in got] == [f"chart-{i}" for i in range(1, len(got) + 1)] and got


def test_app_unknown_id_is_404(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    assert client.get("/api/datasets/nope/app").status_code == 404


def test_plain_on_orders_csv(make_client, round6_dir):
    client = make_client(round6_dir)
    d = next(d for d in catalog.scan(config.get().data).datasets if d.path == "orders.csv")
    assert {d.columns[i] for i in main._plain(d)} == {"order_id", "year"}  # amount (12345..) is not plain
    sid = _ids(client)["orders.csv"]
    charts = client.get(f"/api/datasets/{sid}/app").json()["charts"]
    hist = next(c for c in charts if c["kind"] == "histogram" and c["x_label"] == "order_id")
    assert hist["plain"] == ["x"]
    assert next(c for c in charts if c["kind"] == "scatter")["plain"] == ["x", "y"]


def test_plain_name_and_value_rules():
    cols = ["id", "zip_code", "Phone ", "fiscal_yr", "age", "n", "empty"]
    mapping = dict.fromkeys(cols, "numerical")
    typed = [[1, 12345.0, 5.0, 7.0, 30.0, 1999.0, None], [2, 54321.0, 6.0, 8.0, 40.0, 2024.0, None]]
    assert apps.plain(cols, mapping, typed) == {0, 1, 2, 3, 5}  # n: all whole numbers in 1900..2100
    assert apps.plain(["ident"], {"ident": "categorical"}, [["x"]]) == frozenset()


def test_plural_and_sep():
    assert [apps.plural(n, "point") for n in (1, 2, 0)] == ["1 point", "2 points", "0 points"]
    assert apps.plural(1200, "row") == "1,200 rows"
    assert [apps.sep(v) for v in ("20000", "-1234567.891", "999", "2024", "abc", "01234", "1,234", None)] == [
        "20,000", "-1,234,567.891", "999", "2,024", "abc", "01234", "1,234", "None"]
