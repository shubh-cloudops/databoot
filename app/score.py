"""Interest scores for charts (ARCHITECTURE.md "Round 4: interest score"): each returns a float in 0..1, 0 when undefined."""
import math
import statistics

_UNDEFINED = (statistics.StatisticsError, ZeroDivisionError, OverflowError, ValueError)


def _unit(f):
    """f clamped to 0..1; NaN and inf give 0."""
    return min(1.0, max(0.0, f)) if math.isfinite(f) else 0.0


def _ranks(xs):
    """Average ranks (1-based; ties share the mean rank)."""
    order = sorted(range(len(xs)), key=xs.__getitem__)
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def pearson(xs, ys):
    """|r| of two equal-length sequences."""
    try:
        return _unit(abs(statistics.correlation(xs, ys)))
    except _UNDEFINED:
        return 0.0


def spearman(xs, ys):
    """|rho|: Pearson of the average ranks."""
    return pearson(_ranks(list(xs)), _ranks(list(ys)))


def gini(values):
    """Gini coefficient of non-negative totals; 0 for a negative total, sum 0 or fewer than 2 values."""
    x = sorted(values)
    n = len(x)
    try:
        if n < 2 or x[0] < 0 or sum(x) == 0:
            return 0.0
        return _unit(2 * sum(i * v for i, v in enumerate(x, 1)) / (n * sum(x)) - (n + 1) / n)
    except _UNDEFINED:
        return 0.0


def skew(values):
    """min(1, |g1| / 3) with the population g1 = m3 / m2 ** 1.5."""
    x = list(values)
    try:
        n = len(x)
        if n < 2 or min(x) == max(x):
            return 0.0
        mean = sum(x) / n
        m2 = sum((v - mean) ** 2 for v in x) / n
        m3 = sum((v - mean) ** 3 for v in x) / n
        return _unit(abs(m3 / m2 ** 1.5) / 3)
    except _UNDEFINED:
        return 0.0
