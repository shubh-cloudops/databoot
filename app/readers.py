"""Text readers, one per kind: read_csv, read_tsv, read_json, read_jsonl, read_geojson(path) -> (columns, rows).

Rows are lists aligned to columns; an empty cell is None, csv/tsv cells are str. count_rows(path, kind) -> (columns, n)
reads the same file without keeping rows. Unreadable files raise ReadError(note) with a fixed note (the NOTES below).
.xlsx is in app/xlsx.py and .parquet in app/parquet.py; both raise this ReadError too.
"""
import csv
import json
import os

EMPTY = "empty file"
NO_HEADER = "no header row"
NOT_RECORDS = "not a list of records"
DECODE = "could not decode text"
LON, LAT = "longitude", "latitude"


class ReadError(ValueError):
    """str(error) is the short note shown for an unreadable file."""


def _open(path):
    """Text handle on `path`: utf-8-sig, else cp1252. Decoding is checked up front so streaming cannot fail midway."""
    if os.path.getsize(path) == 0:
        raise ReadError(EMPTY)
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with open(path, encoding=enc) as f:
                while f.read(1 << 16):
                    pass
        except UnicodeDecodeError:
            continue
        return open(path, encoding=enc, newline="")
    raise ReadError(DECODE)


def _names(header):
    """Strip; empty -> column_N (1-based); repeats -> name_2, name_3."""
    seen, out = set(), []
    for i, h in enumerate(header, 1):
        name = h.strip() or f"column_{i}"
        base, n = name, 2
        while name in seen:
            name, n = f"{base}_{n}", n + 1
        seen.add(name)
        out.append(name)
    return out


def _csv(path, delimiter):
    """Yield the column names, then each data row padded or cut to that width."""
    with _open(path) as f:
        rows = csv.reader(f, delimiter=delimiter)
        for header in rows:
            if any(c.strip() for c in header):
                break
        else:
            raise ReadError(NO_HEADER)
        columns = _names(header)
        yield columns
        n = len(columns)
        for r in rows:
            if r:  # csv.reader gives [] for a blank line
                yield [c or None for c in (r + [""] * n)[:n]]


def _cell(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return None if v == "" else v


def _load_json(f):
    try:
        return json.load(f)
    except ValueError:  # includes JSONDecodeError
        raise ReadError(NOT_RECORDS) from None


def _records(items):
    for d in items:
        if not isinstance(d, dict):
            raise ReadError(NOT_RECORDS)
        yield {k: _cell(v) for k, v in d.items()}


def _json(path):
    with _open(path) as f:
        data = _load_json(f)
    if isinstance(data, dict):
        data = next((data[k] for k in ("data", "records") if isinstance(data.get(k), list)), None)
    if not isinstance(data, list):
        raise ReadError(NOT_RECORDS)
    yield from _records(data)


def _jsonl(path):
    with _open(path) as f:
        for line in f:
            if line.strip():
                try:
                    d = json.loads(line)
                except ValueError:
                    raise ReadError(NOT_RECORDS) from None
                yield from _records([d])


def _lonlat(geometry):
    """Point -> its coordinates; any other shape -> mean of its first ring or line; anything else -> (None, None)."""
    try:
        c = geometry["coordinates"]
        while isinstance(c[0], list) and isinstance(c[0][0], list):  # Polygon, Multi*: go down to the first ring / line
            c = c[0]
        if not isinstance(c[0], list):  # Point
            return c[0], c[1]
        return sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c)
    except (TypeError, KeyError, IndexError):
        return None, None


def _geojson(path):
    with _open(path) as f:
        data = _load_json(f)
    if isinstance(data, dict) and data.get("type") == "Feature":
        data = {"features": [data]}
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise ReadError(NOT_RECORDS)
    for feat in data["features"]:
        if not isinstance(feat, dict):
            raise ReadError(NOT_RECORDS)
        d = next(_records([feat.get("properties") or {}]))
        d[LON], d[LAT] = _lonlat(feat.get("geometry"))
        yield d


_DICTS = {"json": _json, "jsonl": _jsonl, "geojson": _geojson}


def _load(path, kind, keep):
    """-> (columns, rows) when keep, else (columns, row count)."""
    if kind in ("csv", "tsv"):
        it = _csv(path, "," if kind == "csv" else "\t")
        columns = next(it)
        return columns, list(it) if keep else sum(1 for _ in it)
    keys, recs, n = {}, [], 0
    for d in _DICTS[kind](path):  # json must be parsed whole; ponytail: jsonl is streamed, a huge .json is not
        keys.update(dict.fromkeys(d))
        n += 1
        if keep:
            recs.append(d)
    if kind == "geojson":
        columns = [k for k in keys if k not in (LON, LAT)] + [LON, LAT]
    elif keys:
        columns = list(keys)
    else:
        raise ReadError(NO_HEADER)
    return columns, [[d.get(c) for c in columns] for d in recs] if keep else n


def read_csv(path):
    return _load(path, "csv", True)


def read_tsv(path):
    return _load(path, "tsv", True)


def read_json(path):
    return _load(path, "json", True)


def read_jsonl(path):
    return _load(path, "jsonl", True)


def read_geojson(path):
    return _load(path, "geojson", True)


def count_rows(path, kind):
    """(columns, data row count) for a text kind, without keeping the rows."""
    return _load(path, kind, False)
