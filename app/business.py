"""Business app figures: periods, KPI cards, trend, leaderboard with drill-down, change table
(docs/ARCHITECTURE.md "Round 5: Business app").

view(columns, rows, typed, mapping, f, options) -> {"cards", "charts", "grain", "latest", "previous"}; the leaderboard,
change table and crumbs are added by a later ticket (B1b).
"""
from datetime import timedelta

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


def view(columns, rows, typed, mapping, f, options):
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
