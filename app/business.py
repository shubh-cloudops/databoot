"""Business app figures: periods, KPI cards, trend, leaderboard with drill-down, change table
(docs/ARCHITECTURE.md "Round 5: Business app").

view(columns, rows, typed, mapping, f, options, app=None) -> {"cards", "charts" (trends, then the leaderboard),
"changes", "crumbs", "grain", "latest", "previous"}; app is the request's `app` param, kept in the crumb links.
"""
from datetime import timedelta
from urllib.parse import urlencode

from app import apps, score
from app.rules import _chart, _clean, _num

SPARK = 12


def grain(span):
    """Period size from the span in days between the first and the last date."""
    return "day" if span <= 60 else "week" if span <= 182 else "month" if span <= 1096 else "year"


def start(d, g):
    """First day of the period of grain g holding date d."""
    return {"day": d, "week": d - timedelta(days=d.weekday()), "month": d.replace(day=1),
            "year": d.replace(month=1, day=1)}[g]


def nxt(p, g):
    """Start of the period after the one starting at p."""
    return {"day": lambda: p + timedelta(days=1), "week": lambda: p + timedelta(days=7),
            "month": lambda: (p.replace(day=28) + timedelta(days=4)).replace(day=1),
            "year": lambda: p.replace(year=p.year + 1)}[g]()


def prev(p, g):
    return start(p - timedelta(days=1), g)


def _trend(columns, typed, mapping):
    """Cards and one trend line per measure for the first temporal column, on the (filtered) typed rows."""
    cols = apps.measures(columns, mapping)
    t = next((i for i, c in enumerate(columns) if mapping.get(c) == "temporal"), None)
    dated = [] if t is None else [(r[t].date(), r) for r in typed if r[t] is not None]
    if not dated:
        return {"cards": [{"column": columns[m], "latest": None, "previous": None, "pct": None, "dir": None, "spark": []}
                          for m in cols], "charts": [], "grain": None, "latest": None, "previous": None}
    first, last = min(d for d, _ in dated), max(d for d, _ in dated)
    g = grain((last - first).days)
    p0 = start(first, g)
    ps = start(last, g)
    big_l = ps if last == nxt(ps, g) - timedelta(days=1) else prev(ps, g)
    big_p = prev(big_l, g)
    periods = []  # p0 .. L; empty when there is no full period
    p = p0
    while p <= big_l:
        periods.append(p)
        p = nxt(p, g)
    sums = {m: {} for m in cols}
    for d, r in dated:
        k = start(d, g)
        for m in cols:
            v = _num(r[m])
            if v is not None:
                sums[m][k] = sums[m].get(k, 0) + v
    cards, charts = [], []
    for m in cols:
        s = sums[m]
        ys = [_clean(s.get(q, 0)) for q in periods]
        latest = s.get(big_l, 0) if periods else None
        previous = s.get(big_p, 0) if big_p >= p0 and periods else None
        pct = round(100 * (latest - previous) / abs(previous), 1) if previous else None
        up = None if pct is None else "up" if latest > previous else "down" if latest < previous else "no change"
        cards.append({"column": columns[m], "latest": latest, "previous": previous, "pct": pct, "dir": up,
                      "spark": ys[-SPARK:]})
        if periods:
            charts.append({"id": f"chart-{len(charts) + 1}", **_chart(
                "line", f"{columns[m]} by {columns[t]}", columns[t], f"{columns[m]} (sum per {g})",
                f"temporal {columns[t]} + numerical {columns[m]}: line, sum per {g}, latest full period last",
                len(periods), len(periods), {"x": [q.isoformat() for q in periods], "y": ys},
                score.spearman(range(len(ys)), ys))})
    return {"cards": cards, "charts": charts, "grain": g, "latest": big_l.isoformat() if periods else None,
            "previous": big_p.isoformat() if periods and big_p >= p0 else None}


TOP = 10


def view(columns, rows, typed, mapping, f, options, app=None):
    """Trend figures plus the leaderboard, change table and crumbs for the filtered typed rows."""
    out = _trend(columns, typed, mapping)
    order = sorted(options, key=lambda c: (len(options[c]), columns.index(c)))  # coarse to fine
    active = dict(f)
    free = [c for c in order if "f." + c not in active]
    out["changes"] = None
    m = apps.measures(columns, mapping)
    if free and m:
        out["charts"].append(_leaderboard(columns, typed, mapping, out, free, m[0]))
        out["changes"] = _changes(columns, typed, mapping, out, free[0], m[0])
    keep = [(k, v) for k, v in f if k in ("from", "to")] + ([("app", app)] if app else [])
    crumbs, shown = [["All", keep]], []
    for c in order:
        if "f." + c in active:
            shown.append(("f." + c, active["f." + c]))
            crumbs.append([f"{c}: {active['f.' + c]}", shown + keep])
    out["crumbs"] = [(label, "?" + urlencode(q) if i < len(crumbs) - 1 else None) for i, (label, q) in enumerate(crumbs)]
    return out


def _sums(columns, typed, c, m, keep=lambda r: True):
    sums = {}
    ci = columns.index(c)
    for r in typed:
        v = _num(r[m])
        if r[ci] not in (None, "") and v is not None and keep(r):
            sums[str(r[ci])] = sums.get(str(r[ci]), 0) + v
    return sums


def _ranked(sums):
    """Top TOP (name, sum) by sum descending then name, then ("Other", rest sum) when there is a rest."""
    ranked = sorted(sums.items(), key=lambda kv: (-kv[1], kv[0]))
    top, rest = ranked[:TOP], ranked[TOP:]
    return top + ([("Other", sum(v for _, v in rest))] if rest else [])


def _leaderboard(columns, typed, mapping, out, free, m):
    c = free[0]
    sums = _sums(columns, typed, c, m)
    bars = _ranked(sums)
    return {"id": f"chart-{len(out['charts']) + 1}", **_chart(
        "bar", f"{columns[m]} by {c}", c, f"{columns[m]} (sum)",
        f"categorical {c} + numerical {columns[m]}: bar, sum per {c}, top {TOP} and Other",
        len(sums), len(sums), {"x": [k for k, _ in bars], "y": [_clean(v) for _, v in bars]}, score.gini(sums.values())),
        "orientation": "h", "baseline": 0, "drill": len(free) > 1, "other": len(sums) > TOP}


def _changes(columns, typed, mapping, out, c, m):
    """Rows (category, previous, latest, delta, t) for the leaderboard's categories, Other included."""
    if out["latest"] is None or out["previous"] is None:
        return None
    t = next(i for i, h in enumerate(columns) if mapping.get(h) == "temporal")
    g = out["grain"]
    period = lambda iso: (lambda r: r[t] is not None and start(r[t].date(), g).isoformat() == iso)
    latest = _sums(columns, typed, c, m, period(out["latest"]))
    previous = _sums(columns, typed, c, m, period(out["previous"]))
    names = [k for k, _ in _ranked(_sums(columns, typed, c, m))]
    top = names[:TOP]
    rest = lambda d: sum(v for k, v in d.items() if k not in top)
    rows = [(k, previous.get(k, 0), latest.get(k, 0)) for k in top]
    if len(names) > TOP:
        rows.append(("Other", rest(previous), rest(latest)))
    big = max((abs(l - p) for _, p, l in rows), default=0)
    return [{"category": k, "previous": p, "latest": l, "delta": l - p, "t": round((l - p) / big, 2) if big else 0}
            for k, p, l in rows]
