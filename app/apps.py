"""Archetype detection: the ordered rule table R1 Map, R5 Survey, R2 Business, R4 Monitoring, R3 Explorer (docs/ARCHITECTURE.md "Round 6: detection")."""
import re

from app.rules import LAT, LON, _num

MEASURE = re.compile(r"amount|revenue|sales|total|price|value|cost|qty|quantity", re.I)
NAMES = {"map": "Map", "business": "Business", "monitoring": "Monitoring", "survey": "Survey", "explorer": "Explorer"}


def roles(columns, mapping, typed):
    """Column roles from the profiler's types: lat/lon index, G (pair found), T/N/C index lists, I (rest), coords, rows."""
    geo = [i for i, c in enumerate(columns) if mapping.get(c) == "geospatial"]
    lat = next((i for i in geo if columns[i].strip().lower() in LAT), None)
    lon = next((i for i in geo if columns[i].strip().lower() in LON), None)
    by = {t: [i for i, c in enumerate(columns) if mapping.get(c) == t] for t in ("temporal", "numerical", "categorical")}
    coords = 0
    if lat is not None and lon is not None:
        for r in typed:
            y, x = _num(r[lat]), _num(r[lon])
            coords += y is not None and x is not None and -90 <= y <= 90 and -180 <= x <= 180
    used = set(by["temporal"] + by["numerical"] + by["categorical"])
    return {"lat": lat, "lon": lon, "G": lat is not None and lon is not None, "T": by["temporal"], "N": by["numerical"],
            "C": by["categorical"], "L": answers(columns, mapping, typed), "I": [i for i in range(len(columns)) if i not in used],
            "coords": coords, "rows": len(typed), "cols": len(columns)}


def answers(columns, mapping, typed):
    """L: indexes of numerical columns whose non-empty values are all whole numbers in 1..7; none when another
    numerical column has an amount-style name (the guard that keeps a sales file with a `units` column out of Survey)."""
    nums = [i for i, c in enumerate(columns) if mapping.get(c) == "numerical"]
    ans = []
    for i in nums:
        vals = [r[i] for r in typed if r[i] not in (None, "")]
        if vals and all(v == int(v) and 1 <= v <= 7 for v in vals):
            ans.append(i)
    # ponytail: name heuristic; a survey with a `price_paid` column loses its 1..7 answers
    return [] if any(MEASURE.search(columns[i]) for i in nums if i not in ans) else ans


# Gate 183 order: Survey before Business so a survey with a timestamp opens as Survey; Monitoring after Business.
RULES = [("R1", "map", lambda r: r["G"] and (len(r["N"]) <= 2 or (r["rows"] > 0 and r["coords"] >= 0.5 * r["rows"]))),
         ("R5", "survey", lambda r: (c := len(r["C"]) + len(r["L"])) >= 4 and c >= 0.6 * r["cols"] and len(r["N"]) - len(r["L"]) <= 2),
         ("R2", "business", lambda r: bool(r["T"] and r["C"] and r["N"])),
         ("R4", "monitoring", lambda r: bool(r["T"] and r["N"] and not r["C"])),
         ("R3", "explorer", lambda r: True)]


def detect(columns, mapping, typed):
    """{"app", "rule", "qualifies"}: the first true rule wins, qualifies lists every true rule's app in RULES order."""
    r = roles(columns, mapping, typed)
    hits = [(rule, app) for rule, app, cond in RULES if cond(r)]
    return {"app": hits[0][1], "rule": hits[0][0], "qualifies": [app for _, app in hits]}


def measures(columns, mapping):
    """Up to 3 numerical column indexes, name-rule matches first; [0] is the primary amount."""
    n = [i for i, c in enumerate(columns) if mapping.get(c) == "numerical"]
    return ([i for i in n if MEASURE.search(columns[i])] + [i for i in n if not MEASURE.search(columns[i])])[:3]


def plain(columns, mapping, typed):
    """Numerical column indexes that never get separators: identifiers, codes, years (name rule or values 1900..2100)."""
    out = set()
    for i, c in enumerate(columns):
        if mapping.get(c) != "numerical":
            continue
        n = c.strip().lower()
        vals = [r[i] for r in typed if r[i] not in (None, "")]
        if (n.endswith("id") or any(w in n for w in ("code", "zip", "phone", "year", "yr"))
                or (vals and all(v == int(v) and 1900 <= v <= 2100 for v in vals))):
            out.add(i)
    return frozenset(out)


def sep(v):
    """Thousands separators on the integer part of a number text; any other text stays as it is."""
    t = str(v)
    whole, dot, frac = t.partition(".")
    return f"{int(whole):,}{dot}{frac}" if re.fullmatch(r"-?[1-9]\d{3,}(\.\d+)?", t) else t


def plural(n, word):
    """'1 point', '2 points', '1,200 rows'."""
    return f"{n:,} {word}" + ("" if n == 1 else "s")
