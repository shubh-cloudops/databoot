"""Map app figures: 2D points or hexbin cells, row details, top regions, the 3D chart for the toggle
(docs/ARCHITECTURE.md "Round 5: Map app").

view(columns, rows, typed, mapping, settings) -> {"charts", "map3d"}. This part: the map2d chart (points, or hex cell
centres above HEX_AT points, drawn as a GeoJSON choropleth: Board gate 180); regions and map3d come next.
"""
import math

from app import apps
from app.rules import _chart

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
    return {"charts": [{**chart, **extra, "id": "chart-1"}], "map3d": None}
