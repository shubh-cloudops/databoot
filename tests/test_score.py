import pytest

from app import config, profile, rules, score


def run(cols, rows):
    return rules.charts(cols, rows, profile.classify(cols, rows), config.get())


def test_gini_and_skew_hand_values():
    assert score.gini([16, 23, 7]) == pytest.approx(0.2319, abs=1e-4)
    assert score.skew([10, 20, 5, 7, 3, 1]) == pytest.approx(0.3415, abs=1e-4)


def test_spearman_uses_average_ranks():
    assert score.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert score.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == 1.0
    assert score.spearman([1, 2, 3], [1, 1, 1]) == 0
    assert score._ranks([5, 1, 5, 3]) == [3.5, 1, 3.5, 2]


@pytest.mark.parametrize("fn", [score.gini, score.skew])
def test_degenerate_inputs_score_zero(fn):
    assert fn([]) == fn([5]) == fn([3, 3, 3]) == 0


def test_degenerate_pairs_and_negative_totals():
    assert score.pearson([1], [1]) == score.pearson([1, 2, 3], [4, 4, 4]) == 0
    assert score.spearman([1], [1]) == 0
    assert score.gini([5, -1, 3]) == score.gini([0, 0]) == 0
    assert score.gini([1e308, 1e308, 1e308]) == 0  # overflow


def test_scatter_perfect_line_scores_one():
    cs = run(["x", "y"], [[i, 2 * i] for i in range(6)])
    assert next(c for c in cs if c["kind"] == "scatter")["score"] == 1.0


def test_scores_in_range_and_order_stable():
    cs = run(["k"], [["a"], ["b"], ["a"], ["b"]])
    assert [(c["kind"], c["score"]) for c in cs] == [("bar", 0), ("donut", 0)]
    assert [c["id"] for c in cs] == ["chart-1", "chart-2"]


def test_map_scores(make_client, data_dir):
    cs = run(["lat", "lon"], [["1", "2"], ["3", "4"]])
    assert cs[0]["score"] == 0.6
    assert run(["lat", "lon"], [["1", "2"]])[0]["score"] == 0
    assert run(["country"], [["FRA"], ["JPN"]])[0]["score"] == 0.6


def test_sales_scores_and_repeatable(make_client, data_dir):
    client = make_client(data_dir)
    d = next(d for d in client.get("/api/datasets").json() if d["path"] == "sales.csv")
    a = client.get(f"/api/datasets/{d['id']}/charts").json()
    assert a == client.get(f"/api/datasets/{d['id']}/charts").json()
    assert [(c["kind"], c["score"]) for c in a["charts"]] == [
        ("line", 0.89), ("histogram", 0.34), ("bar", 0.23), ("donut", 0.22)]
    p = next(d for d in client.get("/api/datasets").json() if d["path"] == "points.tsv")
    assert client.get(f"/api/datasets/{p['id']}/charts").json()["charts"][0]["score"] == 0.6
