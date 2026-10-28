"""Column classification (PRD "Classification rules"): classify(columns, rows) -> {column: type}."""
import re
from collections import Counter
from datetime import date, datetime

TYPES = ("geospatial", "temporal", "categorical", "numerical", "other")
GEO = {"lat", "lon", "lng", "latitude", "longitude"}
DATE_FORMATS = ("%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%d.%m.%Y")
SAMPLE = 10_000  # classify looks at the first SAMPLE rows only (gate 176)
NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def _parses(s):
    for parse in (datetime.fromisoformat, *(lambda s, f=f: datetime.strptime(s, f) for f in DATE_FORMATS)):
        try:
            parse(s)
            return True
        except ValueError:
            pass
    return False


def _kind(name, values, total):
    """Type of one column from its non-empty values; total is the loaded row count."""
    if name.strip().lower() in GEO:
        return "geospatial"
    if not values:
        return "other"
    strs = Counter(v for v in values if isinstance(v, str))
    if all(isinstance(v, date) for v in values) or (
            strs and sum(n for s, n in strs.items() if _parses(s)) >= 0.9 * len(values)):
        return "temporal"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) or isinstance(v, str) and NUMBER.match(v.strip())
           for v in values):
        return "numerical"
    distinct = len({str(v) for v in values})
    if all(isinstance(v, (str, bool)) for v in values) and distinct <= 50 and distinct <= 0.5 * total:
        return "categorical"
    return "other"


def classify(columns, rows):
    """{column: type} from the first SAMPLE rows; the first matching rule wins (docs/ARCHITECTURE.md "Classification")."""
    rows = rows[:SAMPLE]
    return {c: _kind(c, [r[i] for r in rows if i < len(r) and r[i] not in (None, "")], len(rows))
            for i, c in enumerate(columns)}
