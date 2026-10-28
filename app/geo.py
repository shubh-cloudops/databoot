"""Map app figures: 2D points or hexbin cells, row details, top regions, the 3D chart for the toggle
(docs/ARCHITECTURE.md "Round 5: Map app").

view(columns, rows, typed, mapping, settings) -> {"charts", "map3d"}: the map2d chart (points, or hex cell centres
above HEX_AT points, drawn as a GeoJSON choropleth: Board gate 180), the top-regions bar (Board gate 179) and the
Explorer 3D chart with z = the primary numeric (Board gate 180).
"""
import math

from app import apps
from app.business import TOP, _ranked
from app.rules import COUNTRY, _chart, _clean, _map3d, _num

HEX_AT = 5000
HEX_ACROSS = 40


def _hex(lons, lats):
    """Pointy-top axial cells of size lon span / 40: ({(q, r): count}, size)."""
    span = max(lons) - min(lons)
    s = span / HEX_ACROSS or 1.0
    cells = {}
    for x, y in zip(lons, lats):
        q, r = (math.sqrt(3) / 3 * x - y / 3) / s, 2 / 3 * y / s
        qi, ri, zi = round(q), round(-q - r), round(r)  # cube x, y, z
        dq, dr, dz = abs(qi - q), abs(ri + q + r), abs(zi - r)
        if dq > dr and dq > dz:
            qi = -ri - zi
        elif dr <= dz:
            zi = -qi - ri
        cells[(qi, zi)] = cells.get((qi, zi), 0) + 1
    return cells, s


def _regions(columns, rows, typed, mapping, prim):
    """Top-regions bar: country column, else the categorical with the fewest distinct values (>= 2); None if none."""
    cats = [i for i, c in enumerate(columns) if mapping.get(c) == "categorical"]
    country = [i for i, c in enumerate(columns) if c.strip().lower() in COUNTRY and mapping.get(c) in ("categorical", "other")]
    distinct = {i: len({r[i] for r in typed if r[i] not in (None, "")}) for i in cats}
    pool = [i for i in cats if distinct[i] >= 2]
    c = country[0] if country else min(pool, key=lambda i: (distinct[i], i), default=None)
    if c is None:
        return None
    sums = {}
    for r in typed:
        v = 1 if prim is None else _num(r[prim])
        if r[c] not in (None, "") and v is not None:
            sums[str(r[c])] = sums.get(str(r[c]), 0) + v
    bars = _ranked(sums)
    what = "rows" if prim is None else columns[prim]
    return {**_chart("bar", f"{what} by {columns[c]}", columns[c], "count" if prim is None else f"{what} (sum)",
                     f"categorical {columns[c]}" + ("" if prim is None else f" + numerical {columns[prim]}")
                     + f": bar, {'count' if prim is None else 'sum'} per {columns[c]}, top 10 and Other",
                     len(sums), len(sums), {"x": [k for k, _ in bars], "y": [_clean(v) for _, v in bars]}, 0),
            "orientation": "h", "baseline": 0, "drill": False, "other": len(sums) > TOP}


def view(columns, rows, typed, mapping, settings):
    """Figures of the Map app on the view rows; no chart without a lat + lon pair."""
    role = apps.roles(columns, mapping, typed)
    if not role["G"]:
        return {"charts": [], "map3d": None}
    lat, lon = role["lat"], role["lon"]
    prim = (apps.measures(columns, mapping) or [None])[0]
    pts = [i for i, r in enumerate(typed)
           if r[lat] is not None and r[lon] is not None and -90 <= r[lat] <= 90 and -180 <= r[lon] <= 180]
    name = columns[prim] if prim is not None else None
    x, y = columns[lon], columns[lat]
    lons, lats = [typed[i][lon] for i in pts], [typed[i][lat] for i in pts]
    extra = {"z_label": name}
    if len(pts) > HEX_AT:
        cells, s = _hex(lons, lats)
        keys = sorted(cells)
        data = {"mode": "hex", "lon": [s * math.sqrt(3) * (q + r / 2) for q, r in keys],
                "lat": [s * 1.5 * r for _, r in keys], "count": [cells[k] for k in keys], "size": s}
        rule = f"geospatial {x} + {y}: hexbin map, count per cell"
    else:
        data = {"mode": "points", "lon": lons, "lat": lats,
                "color": [typed[i][prim] if prim is not None else None for i in pts], "row": pts}
        rule = f"geospatial {x} + {y}: map" + (f", colour = {name}" if name else "")
        extra |= {"columns": list(columns), "rows": [["" if c is None else str(c) for c in rows[i]] for i in pts]}
    chart = _chart("map2d", f"{name} by location" if name else "points", x, y, rule, len(pts), len(typed), data,
                   0.6 if len(pts) >= 2 else 0)
    charts = [{**chart, **extra, "id": "chart-1"}]
    regions = _regions(columns, rows, typed, mapping, prim)
    if regions:
        charts.append({**regions, "id": "chart-2"})
    return {"charts": charts, "map3d": next(iter(_map3d(columns, typed, mapping, settings, prim)), None)}
