"""Extra chart rules (donut, histogram, scatter, heatmap, country_map), order and the 8-chart cap; values hand-computed."""
import json

from app import config, rules
from tests.test_rules import charts_of


def run(cols, rows, mapping):
    cs = rules.charts(cols, rows, mapping, config.get())
    json.dumps(cs, allow_nan=False)
    return cs


def only(cs, kind):
    return next(c for c in cs if c["kind"] == kind)


def test_donut_counts_and_limits():
    rows = [["a"], ["b"], ["a"], ["c"], ["a"], [""]]
    d = only(run(["c"], rows, {"c": "categorical"}), "donut")
    assert d["data"] == {"labels": ["a", "b", "c"], "values": [3, 1, 1]} and d["shown"] == d["total"] == 5
    assert not [c for c in run(["c"], [["a"], ["a"]], {"c": "categorical"}) if c["kind"] == "donut"]  # 1 value
    seven = [[v] for v in "abcdefg"]
    assert not [c for c in run(["c"], seven, {"c": "categorical"}) if c["kind"] == "donut"]  # 7 values
    assert only(run(["c"], seven[:5], {"c": "categorical"}), "donut")["data"]["values"] == [1] * 5
    assert not [c for c in run(["c"], seven[:6], {"c": "categorical"}) if c["kind"] == "donut"]  # 6 values


def test_histogram_edges_and_counts():
    # 0..20: width 1, value v lands in bin v, so 20 goes into the last bin with 19
    h = only(run(["x"], [[v] for v in range(21)], {"x": "numerical"}), "histogram")
    assert h["data"]["edges"] == [float(i) for i in range(21)]
    assert h["data"]["counts"] == [1] * 19 + [2]
    assert h["shown"] == h["total"] == 21
    # min = max -> one bin
    one = only(run(["x"], [[4], [4], [4]], {"x": "numerical"}), "histogram")
    assert one["data"] == {"edges": [4, 4], "counts": [3]}


def test_scatter_pairs_and_sampling(monkeypatch):
    cols, rows = ["a", "b"], [[1, 2], [2, None], [3, 6], [4, 8], [5, 10]]
    m = {"a": "numerical", "b": "numerical"}
    s = only(run(cols, rows, m), "scatter")
    assert s["data"] == {"x": [1, 3, 4, 5], "y": [2, 6, 8, 10]} and s["shown"] == s["total"] == 4
    assert (s["x_label"], s["y_label"]) == ("a", "b")
    monkeypatch.setenv("DATABOOT_CHART_CAP", "2")  # step = ceil(4 / 2) = 2
    s = only(run(cols, rows, m), "scatter")
    assert s["data"] == {"x": [1, 4], "y": [2, 8]} and (s["shown"], s["total"]) == (2, 4)


def test_heatmap_pearson_pairwise_and_null():
    cols = ["a", "b", "c", "d"]
    # rows 1-3: a=[1,2,3] b=[1,3,2] c=[3,2,1] -> r(a,b)=1/2, r(a,c)=-1, r(b,c)=-1/2; row 4 has only a and d
    rows = [[1, 1, 3, 5], [2, 3, 2, 5], [3, 2, 1, 5], [9, None, None, 5]]
    h = only(run(cols, rows, dict.fromkeys(cols, "numerical")), "heatmap")
    z = h["data"]["z"]
    assert h["data"]["labels"] == cols and h["shown"] == h["total"] == 4
    expect = [[1, .5, -1, None], [.5, 1, -.5, None], [-1, -.5, 1, None], [None, None, None, 1]]
    for got, want in zip(z, expect):
        assert [g if g is None else round(g, 12) for g in got] == want
    assert [z[i][i] for i in range(4)] == [1] * 4


def test_heatmap_needs_three_columns_and_uses_twelve():
    two = run(["a", "b"], [[1, 2], [2, 1]], dict.fromkeys("ab", "numerical"))
    assert "heatmap" not in [c["kind"] for c in two]
    cols = [f"n{i}" for i in range(14)]
    h = only(run(cols, [list(range(14)), list(range(14, 28))], dict.fromkeys(cols, "numerical")), "heatmap")
    assert h["data"]["labels"] == cols[:12] and len(h["data"]["z"]) == 12


def test_country_map_iso3_and_names(make_client, data_dir):
    iso = only(run(["iso3", "gdp"], [["FRA", 3], ["JPN", 4], ["FRA", 5]], {"iso3": "categorical", "gdp": "numerical"}),
               "country_map")
    assert iso["data"] == {"locations": ["FRA", "JPN"], "values": [8, 4], "locationmode": "ISO-3"}
    tie = only(run(["iso3", "n"], [["JPN", 1], ["FRA", 1], ["BRA", 5]], {"iso3": "categorical", "n": "numerical"}),
               "country_map")
    assert tie["data"]["locations"] == ["BRA", "FRA", "JPN"]  # ties break by name
    make_client(data_dir)  # sub/records.json: country is text with 3 distinct of 3 rows, so classified other
    names = only(charts_of(data_dir, "sub/records.json"), "country_map")
    assert names["data"] == {"locations": ["Brazil", "Japan", "France"], "values": [203, 125, 68],
                             "locationmode": "country names"}
    cnt = only(run(["Country"], [["FRA"], ["Fra"], ["FRA"]], {"Country": "categorical"}), "country_map")
    assert cnt["data"] == {"locations": ["FRA", "Fra"], "values": [2, 1], "locationmode": "country names"}
    assert not [c for c in run(["country", "n"], [["x", 1]], {"country": "numerical", "n": "numerical"})
                if c["kind"] == "country_map"]


def test_order_and_cap():
    cols = ["lat", "lon", "country", "date", "v1", "v2", "v3"]
    rows = [[1, 2, "FRA", "2024-01-01", 1, 3, 2], [3, 4, "JPN", "2024-01-02", 2, 1, 5], [5, 6, "FRA", "2024-01-03", 3, 2, 1]]
    m = {"lat": "geospatial", "lon": "geospatial", "country": "categorical", "date": "temporal",
         "v1": "numerical", "v2": "numerical", "v3": "numerical"}
    cs = run(cols, rows, m)  # 10 candidates: scatter and heatmap are cut
    assert ["map3d", "country_map", "line", "line", "bar", "bar", "donut", "histogram"]
    assert [c["id"] for c in cs] == [f"chart-{i}" for i in range(1, 9)]
    num = run(["v1", "v2", "v3"], [[1, 2, 3], [2, 1, 3], [3, 3, 1]], dict.fromkeys(["v1", "v2", "v3"], "numerical"))
    assert [c["kind"] for c in num] == ["heatmap", "scatter", "histogram"]
