"""Business app figures part 1: grain, periods, KPI cards, trend lines (ARCHITECTURE.md "Round 5: Business app")."""
from datetime import date, datetime

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
    charts = got["charts"]
    assert [c["kind"] for c in charts] == ["line", "line"]
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
