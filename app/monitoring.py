"""Monitoring app figures (rule R4): tiles per numerical column, period selector, main line with rolling mean and spikes
(docs/ARCHITECTURE.md "Round 6: Monitoring app").

view(columns, typed, mapping, period, settings) -> {"tiles", "charts", "period", "periods", "latest"} (+ "note" when
more than TILES measures were cut); export(view) -> chart dicts (tiles table, main line).
"""
import math
from datetime import timedelta

from app import apps, score
from app.business import _table
from app.rules import _chart, _clean, _iso, _num, _sample

PERIODS = ["7", "30", "90", "all"]
TILES = 8
SPARK = 60
MEAN, WINDOW, Z = 7, 30, 3


def _points(typed, t, cols):
    """[(time, [value per column or None])] sorted by time: empty times dropped, repeated times averaged."""
    acc = {}
    for r in typed:
        if r[t] is None:
            continue
        a = acc.setdefault(r[t], [[0.0, 0] for _ in cols])
        for s, c in zip(a, cols):
            v = _num(r[c])
            if v is not None:
                s[0] += v
                s[1] += 1
    return [(k, [s / n if n else None for s, n in acc[k]]) for k in sorted(acc)]


def _mean(vs):
    return sum(vs) / len(vs) if vs else None


def _tile(name, plain, cur, prev, all_):
    mean, previous = _mean(cur), None if all_ else _mean(prev)
    pct = round(100 * (mean - previous) / abs(previous), 1) if mean is not None and previous else None
    up = None if pct is None else "up" if mean > previous else "down" if mean < previous else "no change"
    return {"column": name, "latest": cur[-1] if cur else None, "min": min(cur, default=None),
            "max": max(cur, default=None), "mean": _clean(mean), "previous": _clean(previous), "pct": pct, "dir": up,
            "spark": _sample(cur, SPARK), "plain": plain}


def _spikes(y):
    """Positions i >= WINDOW whose |z| > Z against the WINDOW values before i (population stdev), in O(n).

    Running sums of the shifted values; a stdev within float noise of 0 counts as 0.
    """
    if len(y) <= WINDOW:
        return []
    shift = y[0]
    s = s2 = 0.0
    out = []
    for i, v in enumerate(y):
        if i >= WINDOW:
            m = s / WINDOW
            sd = math.sqrt(max(0.0, s2 / WINDOW - m * m))
            # ponytail: noise floor 1e-9 relative; exact windowed sums if a series ever needs less
            if sd > 1e-9 * max(1.0, abs(m)) and abs(v - shift - m) / sd > Z:
                out.append(i)
            u = y[i - WINDOW] - shift
            s -= u
            s2 -= u * u
        w = v - shift
        s += w
        s2 += w * w
    return out


def _line(columns, t, m, pts, col, cut, settings):
    """Main line chart dict: all points feed the rolling mean and spikes, then the window and the stride sample."""
    series = [(k, v[col]) for k, v in pts if v[col] is not None]
    y = [v for _, v in series]
    mean = [sum(y[max(0, i - MEAN + 1):i + 1]) / min(i + 1, MEAN) for i in range(len(y))]
    spikes = set(_spikes(y))
    win = [i for i, (k, _) in enumerate(series) if cut is None or k > cut]
    keep = sorted(set(_sample(win, settings.chart_cap)) | (spikes & set(win)))
    ys = [_clean(y[i]) for i in keep]
    return _chart("monitor", f"{m} by {columns[t]}", columns[t], m,
                  f"temporal {columns[t]} + numerical {m}: line, {MEAN}-point rolling mean, spike |z| > {Z} over "
                  f"{WINDOW} points", len(keep), len(win),
                  {"x": [_iso(series[i][0]) for i in keep], "y": ys, "mean": [_clean(mean[i]) for i in keep],
                   "spike": [j for j, i in enumerate(keep) if i in spikes]},
                  score.spearman(range(len(ys)), ys) if len(ys) > 1 else 0)


def view(columns, typed, mapping, period, settings):
    """Tiles, main line and period for the (filtered) typed rows; the period falls back to 30 days."""
    period = period if period in PERIODS else "30"
    nums = [i for i, c in enumerate(columns) if mapping.get(c) == "numerical"]
    nums = ([i for i in nums if apps.MEASURE.search(columns[i])] + [i for i in nums if not apps.MEASURE.search(columns[i])])
    shown = nums[:TILES]
    t = next((i for i, c in enumerate(columns) if mapping.get(c) == "temporal"), None)
    pts = [] if t is None else _points(typed, t, shown)
    last = pts[-1][0] if pts else None
    days = None if period == "all" or last is None else timedelta(days=int(period))
    plain = apps.plain(columns, mapping, typed)
    tiles = []
    for j, c in enumerate(shown):
        vals = lambda lo, hi: [v[j] for k, v in pts if v[j] is not None and (lo is None or k > lo) and (hi is None or k <= hi)]
        cur = vals(None if days is None else last - days, None)
        prev = [] if days is None else vals(last - 2 * days, last - days)
        tiles.append(_tile(columns[c], c in plain, cur, prev, days is None))
    charts = []
    if shown and pts:
        charts.append({"id": "chart-1", **_line(columns, t, columns[shown[0]], pts, 0, None if days is None else last - days,
                                                 settings)})
    out = {"tiles": tiles, "charts": charts, "period": period, "periods": PERIODS,
           "latest": last.isoformat() if last else None}
    if len(nums) > TILES:
        out["note"] = f"{TILES} of {len(nums)} measures"
    return out


def export(view):
    """Chart dicts of the Monitoring export (ids chart-1..): tiles table, then the main line as a plain line chart."""
    out = [_table("Measures, latest in the period", ["Column", "Latest", "Min", "Max", "Change %"],
                  [[x["column"], x["latest"], x["min"], x["max"], x["pct"]] for x in view["tiles"]])]
    out += [{**c, "kind": "line", "data": {"x": c["data"]["x"], "y": c["data"]["y"]}} for c in view["charts"]]
    return [{**c, "id": f"chart-{i}"} for i, c in enumerate(out, 1)]
