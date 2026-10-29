"""Monitoring figures (MO1): points, windows, tiles, rolling mean, spikes, export (ARCHITECTURE.md "Round 6: Monitoring app")."""
import statistics
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app import monitoring
from tests.conftest import monitor_rows

COLS = ["time", "temperature", "humidity"]
MAP = {"time": "temporal", "temperature": "numerical", "humidity": "numerical"}
SET = SimpleNamespace(chart_cap=500)


def _typed(rows):
    return [[datetime.fromisoformat(r[0]) if r[0] else None, *r[1:]] for r in rows]


def _view(rows, period="30", columns=COLS, mapping=MAP, settings=SET):
    return monitoring.view(columns, _typed(rows), mapping, period, settings)


def _tile(v, name):
    return next(t for t in v["tiles"] if t["column"] == name)


def test_monitor_hand_values_period_30():
    rows = monitor_rows()
    v = _view(rows)
    assert (v["period"], v["periods"], v["latest"]) == ("30", ["7", "30", "90", "all"], "2024-04-29T00:00:00")
    cur, prev = rows[90:], rows[60:90]  # 120 days: last 30 and the 30 before
    t = _tile(v, "temperature")
    assert (t["latest"], t["min"], t["max"], t["pct"], t["dir"]) == (20.0, 20.0, 60.0, 5.1, "up")
    assert t["mean"] == pytest.approx(statistics.fmean(r[1] for r in cur))
    assert t["previous"] == pytest.approx(statistics.fmean(r[1] for r in prev))
    assert t["pct"] == round(100 * (t["mean"] - t["previous"]) / t["previous"], 1)
    h = _tile(v, "humidity")
    assert (h["latest"], h["min"], h["max"], h["pct"], h["dir"]) == (54, 50, 54, 0.0, "no change")
    assert len(t["spark"]) == 30 and t["plain"] is False
    assert "note" not in v


def test_quiet_down_all_and_seven():
    q = _view(monitor_rows(spike=False))
    assert (_tile(q, "temperature")["pct"], _tile(q, "temperature")["dir"]) == (-0.4, "down")
    a = _view(monitor_rows(), "all")
    assert [t["pct"] for t in a["tiles"]] == [None, None] and [t["dir"] for t in a["tiles"]] == [None, None]
    assert a["charts"][0]["total"] == 120 and a["period"] == "all"
    s = _view(monitor_rows(), "7")
    assert s["charts"][0]["total"] == 7 and len(_tile(s, "temperature")["spark"]) == 7
    assert _view(monitor_rows(), "bad")["period"] == "30"


def test_windows_are_half_open():
    rows = [(f"2024-01-{d:02d}", float(d), 1) for d in range(1, 21)]  # last = 20th, N = 7
    t = _tile(_view(rows, "7"), "temperature")
    # current t > 13th: 14..20; previous 6 < t <= 13: 7..13 (7 points each, no overlap)
    assert t["min"] == 14 and t["max"] == 20 and t["mean"] == 17 and t["previous"] == 10


def test_empty_time_dropped_repeats_averaged_sorted():
    rows = [("2024-01-02", 4.0, 1), ("", 100.0, 1), ("2024-01-01", 1.0, 1), ("2024-01-02", 6.0, 3)]
    v = _view(rows, "all")
    c = v["charts"][0]
    assert c["data"]["x"] == ["2024-01-01", "2024-01-02"] and c["data"]["y"] == [1.0, 5.0]
    assert _tile(v, "humidity")["latest"] == 2 and _tile(v, "temperature")["max"] == 5.0


def test_previous_zero_or_empty_gives_no_pct():
    rows = [("2024-01-01", 0.0, 1), ("2024-02-15", 5.0, 1), ("2024-03-01", 7.0, 1)]
    assert _tile(_view(rows, "7"), "temperature")["previous"] is None  # empty previous window
    zero = [("2024-01-01", 0.0, 1), ("2024-01-20", 5.0, 1)]
    t = _tile(_view(zero, "7"), "temperature")
    assert t["previous"] is None or t["pct"] is None
    z = [("2024-01-10", 0.0, 1), ("2024-01-20", 5.0, 1)]
    t = _tile(_view(z, "30"), "temperature")
    assert t["pct"] is None and t["dir"] is None


def test_main_line_mean_and_spike_recomputed_by_hand():
    rows = monitor_rows()
    y = [r[1] for r in rows]
    c = _view(rows, "all")["charts"][0]
    assert c["kind"] == "monitor" and c["data"]["y"] == y
    want = [sum(y[max(0, i - 6):i + 1]) / min(i + 1, 7) for i in range(120)]
    assert c["data"]["mean"] == pytest.approx(want)
    spikes = [i for i in range(30, 120)
              if statistics.pstdev(y[i - 30:i]) > 0 and abs(y[i] - statistics.fmean(y[i - 30:i])) / statistics.pstdev(y[i - 30:i]) > 3]
    assert spikes == [100] == c["data"]["spike"]
    assert c["data"]["x"][100] == "2024-04-10" and c["data"]["mean"][100] == pytest.approx(28.4286, abs=1e-4)
    assert c["data"]["mean"][-1] == 23.0
    assert _view(monitor_rows(spike=False), "all")["charts"][0]["data"]["spike"] == []


def test_spike_positions_follow_window_and_survive_sampling():
    v = _view(monitor_rows(), "all", settings=SimpleNamespace(chart_cap=10))
    c = v["charts"][0]
    assert c["shown"] < 20 and c["data"]["x"][c["data"]["spike"][0]] == "2024-04-10"
    p30 = _view(monitor_rows(), "30")["charts"][0]
    assert p30["data"]["x"][0] == "2024-03-31" and p30["data"]["spike"] == [10] and p30["total"] == 30
    assert _view(monitor_rows(), "7")["charts"][0]["data"]["spike"] == []
    p90 = _view(monitor_rows(), "90")["charts"][0]
    assert p90["data"]["spike"] == [p90["data"]["x"].index("2024-04-10")]


def test_tile_cap_note_and_primary_first():
    cols = ["time"] + [f"m{i}" for i in range(10)] + ["revenue"]
    mp = {c: "numerical" for c in cols} | {"time": "temporal"}
    rows = [("2024-01-01", *range(11)), ("2024-01-02", *range(11))]
    v = monitoring.view(cols, _typed(rows), mp, "30", SET)
    assert len(v["tiles"]) == 8 and v["note"] == "8 of 11 measures"
    assert [t["column"] for t in v["tiles"]][:3] == ["revenue", "m0", "m1"]
    assert v["charts"][0]["y_label"] == "revenue"


def test_plain_column_flagged_and_no_time_no_chart():
    cols = ["time", "year", "temperature"]
    mp = {"time": "temporal", "year": "numerical", "temperature": "numerical"}
    rows = [("2024-01-01", 2024, 1.5), ("2024-01-02", 2024, 2.5)]
    v = monitoring.view(cols, _typed(rows), mp, "30", SET)
    assert [t["plain"] for t in v["tiles"]] == [True, False]
    n = monitoring.view(["a"], [[1.0]], {"a": "numerical"}, "30", SET)
    assert n["charts"] == [] and n["latest"] is None and n["tiles"][0]["latest"] is None


def test_export_table_and_line():
    ex = monitoring.export(_view(monitor_rows()))
    assert [c["id"] for c in ex] == ["chart-1", "chart-2"]
    assert ex[0]["kind"] == "table" and ex[0]["data"]["head"] == ["Column", "Latest", "Min", "Max", "Change %"]
    assert ex[0]["data"]["rows"][0] == ["temperature", 20.0, 20.0, 60.0, 5.1]
    assert ex[1]["kind"] == "line" and set(ex[1]["data"]) == {"x", "y"} and len(ex[1]["data"]["y"]) == 30


def test_200000_rows_stay_fast():
    start = datetime(2020, 1, 1)
    typed = [[start + timedelta(minutes=i), 20.0 + i % 7, 1.0] for i in range(200_000)]
    t0 = time.perf_counter()
    v = monitoring.view(COLS, typed, MAP, "all", SimpleNamespace(chart_cap=500))
    assert time.perf_counter() - t0 < 5 and v["charts"][0]["total"] == 200_000
