"""Survey app figures (rule R5): one bar per question, Likert 100% bars, cross-tab heatmap, Respondents histograms
(docs/ARCHITECTURE.md "Round 6: Survey app").

view(columns, typed, mapping, base_typed, chosen, settings) -> {"charts", "questions", "pick"}; base_typed = the
unfiltered typed rows, so a filter never changes a question's kind or its level order. export(view) -> chart dicts.
"""
from collections import Counter

from app import apps, score
from app.business import TOP, _ranked, _table
from app.rules import _chart, _histogram, _num

# numbers: whole numbers; the first scale that holds every value wins; a tuple lists spellings of one level
SCALES = [("strongly disagree", "disagree", ("neutral", "neither agree nor disagree"), "agree", "strongly agree"),
          ("very dissatisfied", "dissatisfied", ("neutral", "neither satisfied nor dissatisfied"), "satisfied",
           "very satisfied"),
          ("very unlikely", "unlikely", ("neutral", "neither likely nor unlikely"), "likely", "very likely"),
          ("never", "rarely", "sometimes", "often", "always"),
          (1, 2, 3, 4, 5), (1, 2, 3, 4, 5, 6, 7)]


def _key(v):
    """Whole numbers compare as ints, any other value as lower-cased stripped text."""
    n = _num(v)
    return int(n) if n is not None and n == int(n) else str(v).strip().lower()


def _scale(values):
    """(levels, neutral index, {key: level index}) or None."""
    present = [v for v in values if v not in (None, "")]
    if len({_key(v) for v in present}) < 2:
        return None
    for labels in SCALES:
        pos = {k: i for i, lab in enumerate(labels) for k in (lab if isinstance(lab, tuple) else (lab,))}
        if all(_key(v) in pos for v in present):
            own = {}
            if isinstance(labels[0], str):
                for v in present:
                    own.setdefault(pos[_key(v)], str(v).strip())
            levels = [own.get(i, lab[0] if isinstance(lab, tuple) else lab) for i, lab in enumerate(labels)]
            return levels, len(labels) // 2, pos
    return None


def scale(values):
    """(levels, neutral index) of the Likert scale all values lie on, every level kept; None when there is none."""
    s = _scale(values)
    return s and s[:2]


def _answers(columns, mapping, typed):
    """Indexes of whole-number 1..7 columns that count as answers: none when another numerical column has an
    amount-style name (the guard that keeps a sales file with a `units` column out of Survey)."""
    nums = [i for i, c in enumerate(columns) if mapping.get(c) == "numerical"]
    ans = []
    for i in nums:
        vals = [r[i] for r in typed if r[i] not in (None, "")]
        if vals and all(v == int(v) and 1 <= v <= 7 for v in vals):
            ans.append(i)
    # ponytail: name heuristic, same as apps.MEASURE; a survey with a `price_paid` column loses its 1..7 answers
    return [] if any(apps.MEASURE.search(columns[i]) for i in nums if i not in ans) else ans


def questions(columns, mapping, typed):
    """Names of the categorical columns and the 1..5/1..7 answer columns, in column order."""
    keep = set(_answers(columns, mapping, typed))
    return [c for i, c in enumerate(columns) if mapping.get(c) == "categorical" or i in keep]


def pick(qs, row, col):
    """(row question, column question): the two names asked for when both are questions, else the first two."""
    return (row, col) if row in qs and col in qs else tuple(qs[:2])


def _labels(typed, i, sc):
    """Label per row: the scale level for Likert questions, else the text of the value; None for empty cells."""
    return [None if r[i] in (None, "") else sc[0][sc[2][_key(r[i])]] if sc else str(r[i]) for r in typed]


def _bar(name, labels):
    counts = Counter(v for v in labels if v is not None)
    bars = _ranked(counts)
    return {**_chart("bar", name, name, "count", f"categorical {name}: bar, count per value, top {TOP} and Other",
                     sum(counts.values()), sum(counts.values()),
                     {"x": [k for k, _ in bars], "y": [v for _, v in bars]}, score.gini(counts.values())),
            "orientation": "h", "baseline": 0, "other": len(counts) > TOP}


def _likert(name, labels, sc):
    levels, neutral, _ = sc
    counts = Counter(v for v in labels if v is not None)
    n = sum(counts.values())
    c = [counts.get(lv, 0) for lv in levels]
    return _chart("likert", name, name, "%", f"{name}: Likert scale, share of answers per level", n, n,
                  {"levels": levels, "counts": c, "pct": [100 * x / n if n else 0 for x in c], "neutral": neutral}, 0)


def _order(labels, sc):
    """Levels seen: scale order for Likert questions, else count desc then name."""
    seen = Counter(v for v in labels if v is not None)
    return [lv for lv in sc[0] if lv in seen] if sc else sorted(seen, key=lambda k: (-seen[k], k))


def _crosstab(row, col, rl, cl, rsc, csc):
    pairs = Counter((a, b) for a, b in zip(rl, cl) if a is not None and b is not None)
    y = _order([a for a, _ in pairs.elements()], rsc)
    x = _order([b for _, b in pairs.elements()], csc)
    z = [[pairs[a, b] for b in x] for a in y]
    pct = [[100 * v / sum(r) for v in r] for r in z]
    return _chart("crosstab", f"{row} by {col}", col, row, f"{row} x {col}: count and row % per answer pair",
                  sum(pairs.values()), sum(pairs.values()), {"x": x, "y": y, "z": z, "pct": pct}, 0)


def view(columns, typed, mapping, base_typed, chosen, settings):
    """Question figures, cross-tab and Respondents histograms of the (filtered) typed rows."""
    qs = questions(columns, mapping, base_typed)
    row, col = chosen if chosen else pick(qs, None, None)
    ans = _answers(columns, mapping, base_typed)
    charts, labels, scales = [], {}, {}
    for name in qs:
        i = columns.index(name)
        scales[name] = _scale([r[i] for r in base_typed])
        labels[name] = _labels(typed, i, scales[name])
        charts.append(_likert(name, labels[name], scales[name]) if scales[name] else _bar(name, labels[name]))
    if len(qs) >= 2:
        charts.append(_crosstab(row, col, labels[row], labels[col], scales[row], scales[col]))
    plain = apps.plain(columns, mapping, base_typed)
    nums = [i for i, c in enumerate(columns) if mapping.get(c) == "numerical" and i not in ans and i not in plain]
    for i in nums[:2]:
        charts += _histogram(columns, typed, {columns[i]: "numerical"}, settings)
    return {"charts": [{"id": f"chart-{n}", **c} for n, c in enumerate(charts, 1)], "questions": qs,
            "pick": [row, col]}


def export(view):
    """Chart dicts of the Survey export (ids chart-1..): a bar per question, the cross-tab as a table, histograms."""
    out = []
    for c in view["charts"]:
        d = c["data"]
        if c["kind"] == "likert":
            out.append({**c, "kind": "bar", "data": {"x": d["levels"], "y": d["counts"]}})
        elif c["kind"] == "crosstab":
            out.append(_table(c["title"], [c["y_label"], *d["x"]], [[a, *r] for a, r in zip(d["y"], d["z"])]))
        else:
            out.append(c)
    return [{**c, "id": f"chart-{i}"} for i, c in enumerate(out, 1)]
