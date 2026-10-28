"""Server-side filters (docs/ARCHITECTURE.md "Round 4: filters"): f.<column>=value, from=, to= (gate 175)."""
from datetime import date

from app.rules import _time

MAX_OPTIONS = 50


def _temporal(columns, mapping):
    return next((i for i, c in enumerate(columns) if mapping.get(c) == "temporal"), None)


def parse(params, columns, mapping):
    """Canonical hashable ((name, value), ...): categorical f.<column> in column order, then from, then to.

    params is any mapping with .get (a repeated key already keeps the last value); anything unusable is ignored.
    """
    out = []
    for c in columns:
        v = params.get(f"f.{c}")
        if v and mapping.get(c) == "categorical" and ("f." + c, v) not in out:
            out.append(("f." + c, v))
    if _temporal(columns, mapping) is not None:
        for key in ("from", "to"):
            try:
                out.append((key, date.fromisoformat(params.get(key, "")).isoformat()))
            except ValueError:
                pass
    return tuple(out)


def apply(f, columns, mapping, typed):
    """Indexes of the typed rows that satisfy every filter (AND); None when f is empty."""
    if not f:
        return None
    want = dict(f)
    cats = [(i, want["f." + c]) for i, c in enumerate(columns) if "f." + c in want]
    ti = _temporal(columns, mapping)
    lo, hi = want.get("from", ""), want.get("to", "")  # ISO strings compare like dates
    keep = []
    for k, r in enumerate(typed):
        if not all(str(r[i]) == v for i, v in cats):
            continue
        if lo or hi:
            t = _time(r[ti])
            if t is None or (lo and t.date().isoformat() < lo) or (hi and t.date().isoformat() > hi):
                continue
        keep.append(k)
    return keep


def labels(f, columns, mapping):
    """Chip texts: 'region = North', 'date from 2024-01-01', 'date to 2024-03-31'."""
    ti = _temporal(columns, mapping)
    return [f"{columns[ti]} {n} {v}" if n in ("from", "to") else f"{n[2:]} = {v}" for n, v in f]


def summary(labels):
    return "Filters: " + ("; ".join(labels) or "none")


def options(columns, rows, mapping):
    """{categorical column: sorted distinct non-empty str values, at most MAX_OPTIONS}."""
    return {c: sorted({str(r[i]) for r in rows if r[i] not in (None, "")})[:MAX_OPTIONS]
            for i, c in enumerate(columns) if mapping.get(c) == "categorical"}
