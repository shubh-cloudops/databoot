"""Routing rules: charts(columns, rows, mapping, settings) -> list of chart dicts (ARCHITECTURE.md "Chart contract")."""
import math
import re
import statistics
from datetime import date, datetime

from app.profile import DATE_FORMATS, NUMBER

MAX_CHARTS = 8
LAT = {"lat", "latitude"}
LON = {"lon", "lng", "longitude"}
COUNTRY = {"country", "country_name", "nation", "iso3", "iso_a3"}
ISO3 = re.compile(r"[A-Z]{3}")
BINS = 20
HEATMAP_COLS = 12


def _num(v):
    """Finite float of a number or numeric string, else None (bool, text, NaN and inf are None)."""
    if isinstance(v, str) and NUMBER.match(v.strip()):
        v = float(v)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return v


def _clean(v):
    """JSON-safe number: NaN and inf (for example an overflowing sum) become None."""
    return v if v is None or math.isfinite(v) else None


def _time(v):
    """Naive datetime of a date, datetime or date string, else None."""
    if isinstance(v, str):
        for parse in (datetime.fromisoformat, *(lambda s, f=f: datetime.strptime(s, f) for f in DATE_FORMATS)):
            try:
                v = parse(v.strip())
                break
            except ValueError:
                pass
        else:
            return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    return datetime(v.year, v.month, v.day) if isinstance(v, date) else None


def _iso(t):
    return t.date().isoformat() if t == datetime(t.year, t.month, t.day) else t.isoformat()


def _sample(points, cap):
    """Stride sampling: step = ceil(n / cap), so at most cap points are kept."""
    return points[::max(1, math.ceil(len(points) / cap))]


def _first(columns, mapping, kind, n=1):
    """Indexes of the first n columns of this type."""
    return [i for i, c in enumerate(columns) if mapping.get(c) == kind][:n]


def _chart(kind, title, x, y, rule, shown, total, data):
    return {"kind": kind, "title": title, "x_label": x, "y_label": y, "rule": rule,
            "shown": shown, "total": total, "data": data}


def _map3d(columns, rows, mapping, settings):
    geo = [i for i, c in enumerate(columns) if mapping.get(c) == "geospatial"]
    lat = next((i for i in geo if columns[i].strip().lower() in LAT), None)
    lon = next((i for i in geo if columns[i].strip().lower() in LON), None)
    if lat is None or lon is None:
        return []
    z = _first(columns, mapping, "numerical")
    points = []
    for r in rows:
        x, y = _num(r[lon]), _num(r[lat])
        if x is not None and y is not None:
            points.append((x, y, _num(r[z[0]]) if z else 0))
    shown = _sample(points, settings.map_cap)
    lons, lats, zs = zip(*shown) if shown else ([], [], [])
    rule = f"geospatial {columns[lon]} + {columns[lat]}: 3D map" + (f", z = {columns[z[0]]}" if z else "")
    chart = _chart("map3d", f"{columns[z[0]] if z else 'points'} by location", columns[lon], columns[lat], rule,
                   len(shown), len(points), {"lon": list(lons), "lat": list(lats), "z": list(zs)})
    chart["z_label"] = columns[z[0]] if z else None
    return [chart]


def _lines(columns, rows, mapping, settings):
    out = []
    for t in _first(columns, mapping, "temporal"):
        for n in _first(columns, mapping, "numerical", 2):
            sums = {}
            for r in rows:
                when, v = _time(r[t]), _num(r[n])
                if when is not None and v is not None:
                    sums[when] = sums.get(when, 0) + v
            points = _sample(sorted(sums.items()), settings.chart_cap)
            out.append(_chart("line", f"{columns[n]} by {columns[t]}", columns[t], f"{columns[n]} (sum)",
                              f"temporal {columns[t]} + numerical {columns[n]}: line, sum per {columns[t]}",
                              len(points), len(sums),
                              {"x": [_iso(k) for k, _ in points], "y": [_clean(v) for _, v in points]}))
    return out


def _bars(columns, rows, mapping, settings):
    out = []
    for c in _first(columns, mapping, "categorical"):
        for n in _first(columns, mapping, "numerical", 2) or [None]:
            sums, used = {}, 0
            for r in rows:
                v = 1 if n is None else _num(r[n])
                if r[c] not in (None, "") and v is not None:
                    sums[str(r[c])] = sums.get(str(r[c]), 0) + v
                    used += 1
            ranked = sorted(sums.items(), key=lambda kv: (-kv[1], kv[0]))
            what, how = ("rows", "count") if n is None else (columns[n], "sum")
            out.append(_chart("bar", f"{what} by {columns[c]}", columns[c], "count" if n is None else f"{what} (sum)",
                              f"categorical {columns[c]}" + ("" if n is None else f" + numerical {columns[n]}")
                              + f": bar, {how} per {columns[c]}",
                              used, used, {"x": [k for k, _ in ranked], "y": [_clean(v) for _, v in ranked]}))
    return out


def _country_map(columns, rows, mapping, settings):
    # "text column": categorical or other (a column of mostly distinct names is classified other)
    c = next((i for i, h in enumerate(columns)
              if h.strip().lower() in COUNTRY and mapping.get(h) in ("categorical", "other")), None)
    if c is None:
        return []
    n = next(iter(_first(columns, mapping, "numerical")), None)
    sums, used = {}, 0
    for r in rows:
        v = 1 if n is None else _num(r[n])
        if r[c] not in (None, "") and v is not None:
            sums[str(r[c])] = sums.get(str(r[c]), 0) + v
            used += 1
    if not sums:
        return []
    sums = dict(sorted(sums.items(), key=lambda kv: (-kv[1], kv[0])))
    mode = "ISO-3" if all(ISO3.fullmatch(k) for k in sums) else "country names"
    what = "rows" if n is None else columns[n]
    return [_chart("country_map", f"{what} by {columns[c]}", columns[c], "count" if n is None else f"{what} (sum)",
                   f"text {columns[c]}" + ("" if n is None else f" + numerical {columns[n]}")
                   + f": country map, {'count' if n is None else 'sum'} per {columns[c]} ({mode})",
                   used, used, {"locations": list(sums), "values": [_clean(v) for v in sums.values()],
                                "locationmode": mode})]


def _donut(columns, rows, mapping, settings):
    (c,) = _first(columns, mapping, "categorical") or [None]
    if c is None:
        return []
    counts = {}
    for r in rows:
        if r[c] not in (None, ""):
            counts[str(r[c])] = counts.get(str(r[c]), 0) + 1
    if not 2 <= len(counts) <= 6:
        return []
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    used = sum(counts.values())
    return [_chart("donut", f"rows by {columns[c]}", columns[c], "count",
                   f"categorical {columns[c]} ({len(counts)} values): donut, count per {columns[c]}", used, used,
                   {"labels": [k for k, _ in ranked], "values": [v for _, v in ranked]})]


def _histogram(columns, rows, mapping, settings):
    (n,) = _first(columns, mapping, "numerical") or [None]
    if n is None:
        return []
    vals = [v for v in (_num(r[n]) for r in rows) if v is not None]
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    bins = BINS if hi > lo else 1
    counts = [0] * bins
    for v in vals:
        try:
            i = int((v - lo) * bins / (hi - lo)) if hi > lo else 0
        except OverflowError:  # range near the float limit
            i = int((v - lo) / (hi - lo) * bins)
        counts[min(i, bins - 1)] += 1
    edges = [lo + (hi - lo) * i / bins for i in range(bins)] + [hi]
    return [_chart("histogram", f"{columns[n]} distribution", columns[n], "count",
                   f"numerical {columns[n]}: histogram, {bins} equal-width {'bins' if bins > 1 else 'bin'}",
                   len(vals), len(vals), {"edges": [_clean(e) for e in edges], "counts": counts})]


def _scatter(columns, rows, mapping, settings):
    ix = _first(columns, mapping, "numerical", 2)
    if len(ix) < 2:
        return []
    a, b = ix
    points = [(x, y) for x, y in ((_num(r[a]), _num(r[b])) for r in rows) if x is not None and y is not None]
    shown = _sample(points, settings.chart_cap)
    xs, ys = zip(*shown) if shown else ([], [])
    return [_chart("scatter", f"{columns[b]} vs {columns[a]}", columns[a], columns[b],
                   f"numerical {columns[a]} + numerical {columns[b]}: scatter", len(shown), len(points),
                   {"x": list(xs), "y": list(ys)})]


def _heatmap(columns, rows, mapping, settings):
    ix = _first(columns, mapping, "numerical", HEATMAP_COLS)
    if len(ix) < 3:
        return []
    cols = [[_num(r[i]) for r in rows] for i in ix]

    def pearson(a, b):
        pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
        try:
            return max(-1.0, min(1.0, statistics.correlation(*zip(*pairs))))
        except (statistics.StatisticsError, OverflowError, ZeroDivisionError, TypeError):
            return None  # fewer than 2 pairs or a constant column: undefined

    z = [[1 if i == j else pearson(a, b) for j, b in enumerate(cols)] for i, a in enumerate(cols)]
    used = sum(sum(v is not None for v in vs) >= 2 for vs in zip(*cols))
    names = [columns[i] for i in ix]
    return [_chart("heatmap", "correlation of numerical columns", "column", "column",
                   f"numerical {', '.join(names)}: Pearson correlation, pairwise complete rows",
                   used, used, {"labels": names, "z": z})]


def charts(columns, rows, mapping, settings):
    """Chart dicts for one dataset; mapping is profile.classify's {column: type}. [] when no rule matches (AC-7)."""
    rules = (_map3d, _country_map, _lines, _bars, _donut, _histogram, _scatter, _heatmap)
    found = [c for rule in rules for c in rule(columns, rows, mapping, settings)][:MAX_CHARTS]
    return [{"id": f"chart-{i}", **c} for i, c in enumerate(found, 1)]
