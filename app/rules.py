"""Routing rules: charts(columns, rows, mapping, settings) -> list of chart dicts (ARCHITECTURE.md "Chart contract")."""
import math
from datetime import date, datetime

from app.profile import DATE_FORMATS, NUMBER

MAX_CHARTS = 8
LAT = {"lat", "latitude"}
LON = {"lon", "lng", "longitude"}


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
    return [_chart("map3d", f"{columns[z[0]] if z else 'points'} by location", columns[lon], columns[lat], rule,
                   len(shown), len(points), {"lon": list(lons), "lat": list(lats), "z": list(zs)})]


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


def charts(columns, rows, mapping, settings):
    """Chart dicts for one dataset; mapping is profile.classify's {column: type}. [] when no rule matches (AC-7)."""
    found = [c for rule in (_map3d, _lines, _bars) for c in rule(columns, rows, mapping, settings)][:MAX_CHARTS]
    return [{"id": f"chart-{i}", **c} for i, c in enumerate(found, 1)]
