"""Business app figures part 1: grain, periods, KPI cards, trend lines (ARCHITECTURE.md "Round 5: Business app")."""
from datetime import date, datetime, timedelta

import pytest

from app import business

COLS = ["day", "kind", "amount"]
MAP = {"day": "temporal", "kind": "categorical", "amount": "numerical"}


def _view(rows):
    typed = [[datetime.fromisoformat(d) if d else None, k, a] for d, k, a in rows]
    return business.view(COLS, rows, typed, MAP, (), {})


def _shop(make_client, archetypes_dir, query=""):
    client = make_client(archetypes_dir)
    sid = next(d["id"] for d in client.get("/api/datasets").json() if d["path"] == "shop.csv")
    return client.get(f"/api/datasets/{sid}/app{query}").json()


@pytest.mark.parametrize("span, want", [(0, "day"), (60, "day"), (61, "week"), (182, "week"), (183, "month"),
                                         (1096, "month"), (1097, "year")])
def test_grain_thresholds(span, want):
    assert business.grain(span) == want


def test_period_starts_and_steps():
    d = date(2024, 7, 10)  # a Wednesday
    assert [business.start(d, g) for g in ("day", "week", "month", "year")] == [
        d, date(2024, 7, 8), date(2024, 7, 1), date(2024, 1, 1)]
    assert business.nxt(date(2024, 12, 1), "month") == date(2025, 1, 1)
    assert business.nxt(date(2024, 12, 30), "week") == date(2025, 1, 6)
    assert business.prev(date(2024, 1, 1), "month") == date(2023, 12, 1)


def test_shop_cards_and_charts(make_client, archetypes_dir):
    got = _shop(make_client, archetypes_dir)
    assert (got["grain"], got["latest"], got["previous"]) == ("month", "2024-06-01", "2024-05-01")
    rev, units = got["cards"]
    assert (rev["column"], rev["latest"], rev["previous"], rev["pct"], rev["dir"]) == ("revenue", 7392, 6192, 19.4, "up")
    assert (units["column"], units["latest"], units["previous"], units["pct"], units["dir"]) == ("units", 72, 60, 20.0, "up")
    assert rev["spark"] == [1392, 2592, 3792, 4992, 6192, 7392]  # fewer than 12 periods: from the first one
    charts = got["charts"][:2]  # trends; the leaderboard follows
    assert [c["kind"] for c in got["charts"]] == ["line", "line", "bar"]
    assert charts[0]["data"]["x"] == [f"2024-{m:02d}-01" for m in range(1, 7)]
    assert charts[0]["data"]["y"] == rev["spark"] and charts[1]["data"]["y"] == [12, 24, 36, 48, 60, 72]
    assert (charts[0]["shown"], charts[0]["total"]) == (6, 6)  # July (partial) is left out
    assert not any("yaxis2" in k or "axis" in k.replace("x_label", "") for c in charts for k in c)


def test_filter_applies_to_sums(make_client, archetypes_dir):
    got = _shop(make_client, archetypes_dir, "?f.channel=web")
    rev, units = got["cards"]
    # June web rows: 2 days x 3 stores, base 600 + stores 10 * (0 + 1 + 2) * 2 + sum of i % 12 (30) = 3690
    assert (rev["latest"], rev["previous"], units["latest"]) == (3690, 3090, 36)
    assert got["charts"][0]["data"]["y"][-1] == 3690


def test_day_grain_one_month_previous_sum_zero():
    got = _view([("2024-03-01", "a", 5), ("2024-03-04", "a", 7)])
    assert (got["grain"], got["latest"], got["previous"]) == ("day", "2024-03-04", "2024-03-03")
    card = got["cards"][0]
    assert (card["latest"], card["previous"], card["pct"], card["dir"]) == (7, 0, None, None)
    assert card["spark"] == [5, 0, 0, 7]  # zero-filled days 03-01..03-04
    assert got["charts"][0]["data"]["x"] == ["2024-03-01", "2024-03-02", "2024-03-03", "2024-03-04"]


def test_spark_keeps_last_12_periods():
    rows = [(f"{y}-{m:02d}-01", "a", v) for v, (y, m) in enumerate([(2023, 12)] + [(2024, m) for m in range(1, 13)], 1)]
    rows.append(("2025-01-05", "a", 99))  # partial month, left out
    got = _view(rows)
    card = got["cards"][0]
    assert (got["grain"], got["latest"]) == ("month", "2024-12-01")
    assert card["spark"] == list(range(2, 14)) and (card["latest"], card["previous"], card["pct"]) == (13, 12, 8.3)
    assert got["charts"][0]["data"]["y"] == list(range(1, 14))  # the trend keeps every period


def test_down_and_no_change():
    down = _view([("2024-03-01", "a", 10), ("2024-03-02", "a", 4)])["cards"][0]
    assert (down["latest"], down["previous"], down["pct"], down["dir"]) == (4, 10, -60.0, "down")
    same = _view([("2024-03-01", "a", 4), ("2024-03-02", "a", 4)])["cards"][0]
    assert (same["pct"], same["dir"]) == (0.0, "no change")


def test_single_date_has_no_previous_period():
    got = _view([("2024-03-01", "a", 4)])
    assert (got["grain"], got["latest"], got["previous"]) == ("day", "2024-03-01", None)
    assert got["cards"][0]["latest"] == 4 and got["cards"][0]["previous"] is None and got["cards"][0]["pct"] is None


def test_no_dates_gives_empty_figures():
    for rows in ([], [(None, "a", 1)]):
        got = _view(rows)
        assert (got["grain"], got["charts"], got["latest"]) == (None, [], None)
        assert got["cards"][0]["latest"] is None and got["cards"][0]["pct"] is None


def test_partial_week_uses_week_before():
    # span 74 days: week grain; the last date (Fri 2024-03-15) is not the week's last day, so L = week of 2024-03-04
    got = _view([("2024-01-01", "a", 1), ("2024-03-15", "a", 2)])
    assert (got["grain"], got["latest"], got["previous"]) == ("week", "2024-03-04", "2024-02-26")


def test_shop_unfiltered_leaderboard_and_changes(make_client, archetypes_dir):
    got = _shop(make_client, archetypes_dir)
    assert {"cards", "charts", "changes", "crumbs", "grain", "latest", "previous"} <= set(got)
    assert [c["id"] for c in got["charts"]] == ["chart-1", "chart-2", "chart-3"]
    lb = got["charts"][-1]
    assert (lb["kind"], lb["orientation"], lb["x_label"], lb["drill"], lb["other"]) == ("bar", "h", "channel", True, False)
    assert (lb["data"]["x"], lb["data"]["y"]) == (["shop", "web"], [15354, 15276])
    # June vs May: each channel gains 600 (2 days x 3 stores x 100), so t is 1.0 for both
    assert got["changes"] == [{"category": "shop", "previous": 3102, "latest": 3702, "delta": 600, "t": 1.0},
                              {"category": "web", "previous": 3090, "latest": 3690, "delta": 600, "t": 1.0}]
    assert got["crumbs"] == [["All", None]]


def test_shop_last_level_has_other_and_changes(make_client, archetypes_dir):
    got = _shop(make_client, archetypes_dir, "?f.channel=web&f.store=North")
    lb = got["charts"][-1]
    assert (lb["x_label"], lb["drill"], lb["other"]) == ("product", False, True)
    assert lb["data"]["x"] == ["p0", "p11", "p10", "p9", "p8", "p7", "p6", "p5", "p4", "p3", "Other"]
    assert lb["data"]["y"] == [800, 606, 600, 506, 500, 406, 400, 306, 300, 206, 306]  # Other = p2 200 + p1 106
    ch = {c["category"]: c for c in got["changes"]}
    assert [c["category"] for c in got["changes"]] == lb["data"]["x"]
    assert (ch["p11"]["previous"], ch["p11"]["latest"], ch["p11"]["delta"], ch["p11"]["t"]) == (0, 606, 606, 1.0)
    assert (ch["p9"]["delta"], ch["p9"]["t"], ch["p10"]["t"]) == (-506, -0.83, 0.99)
    assert ch["p0"]["t"] == 0 and ch["Other"]["delta"] == 0


def test_crumbs_keep_range_app_and_earlier_crumbs(make_client, archetypes_dir):
    got = _shop(make_client, archetypes_dir, "?f.channel=web")
    assert [c[0] for c in got["crumbs"]] == ["All", "channel: web"] and got["crumbs"][1][1] is None
    got = _shop(make_client, archetypes_dir, "?app=business&f.channel=web&f.store=North&from=2024-01-01")
    assert got["crumbs"] == [["All", "?from=2024-01-01&app=business"],
                             ["channel: web", "?f.channel=web&from=2024-01-01&app=business"],
                             ["store: North", None]]
    assert got["charts"][-1]["x_label"] == "product"


def test_drill_order_by_distinct_count_then_column():
    opts = {"b": ["1", "2"], "a": ["1", "2"], "c": ["1"]}
    cols = ["a", "b", "c", "n"]
    m = {"a": "categorical", "b": "categorical", "c": "categorical", "n": "numerical"}
    typed = [["x", "y", "z", 5]]
    got = business.view(cols, typed, typed, m, (("f.c", "z"),), opts)
    assert got["charts"][-1]["x_label"] == "a" and got["charts"][-1]["drill"] is True
    got = business.view(cols, typed, typed, m, (("f.c", "z"), ("f.a", "x"), ("f.b", "y")), opts)
    assert got["changes"] is None and got["charts"] == []
    assert [c[0] for c in got["crumbs"]] == ["All", "c: z", "a: x", "b: y"]


def test_changes_none_without_previous_and_zero_deltas():
    got = _view([("2024-03-04", "a", 5)])
    assert got["changes"] is None
    rows = [("2024-03-01", "a", 5), ("2024-03-02", "a", 5), ("2024-03-02", "b", 3), ("2024-03-01", "b", 3)]
    typed = [[datetime.fromisoformat(d), k, a] for d, k, a in rows]
    got = business.view(COLS, rows, typed, MAP, (), {"kind": ["a", "b"]})
    assert [c["t"] for c in got["changes"]] == [0, 0] and got["charts"][-1]["data"]["y"] == [10, 6]


def test_week_grain_100_days_monday_x_and_iso_week_sums():
    # 2024-01-01 is a Monday; day i (0..99) has amount i + 1, so ISO week k (7 days) sums to 49k + 28
    rows = [((date(2024, 1, 1) + timedelta(days=i)).isoformat(), "a", i + 1) for i in range(100)]
    got = _view(rows)  # the last day, Tue 2024-04-09, is in a partial week, which is left out: 14 full weeks
    assert (got["grain"], got["latest"], got["previous"]) == ("week", "2024-04-01", "2024-03-25")
    x, y = got["charts"][0]["data"]["x"], got["charts"][0]["data"]["y"]
    assert len(x) == 14 and all(date.fromisoformat(s).weekday() == 0 for s in x)
    assert x[0] == "2024-01-01" and x[-1] == "2024-04-01"
    assert y == [49 * k + 28 for k in range(14)] and y[:3] == [28, 77, 126] and y[-1] == 665
    card = got["cards"][0]
    assert (card["latest"], card["previous"], card["pct"], card["dir"]) == (665, 616, 8.0, "up")
    assert card["spark"] == y[-12:]


def test_year_grain_monthly_rows_leave_the_partial_year_out():
    # 2021-01 .. 2024-03: 1,155 days; amount = 100 * (year - 2020) + month, so a full year sums to 1200 * (year - 2020) + 78
    months = [(y, m) for y in range(2021, 2025) for m in range(1, 13) if (y, m) <= (2024, 3)]
    got = _view([(f"{y}-{m:02d}-01", "a", 100 * (y - 2020) + m) for y, m in months])
    assert (got["grain"], got["latest"], got["previous"]) == ("year", "2023-01-01", "2022-01-01")
    assert got["charts"][0]["data"]["x"] == ["2021-01-01", "2022-01-01", "2023-01-01"]
    assert got["charts"][0]["data"]["y"] == [1278, 2478, 3678]  # the 2024 months (Jan-Mar) are not a year
    card = got["cards"][0]
    assert (card["latest"], card["previous"], card["pct"], card["dir"]) == (3678, 2478, 48.4, "up")
    assert card["spark"] == [1278, 2478, 3678]
