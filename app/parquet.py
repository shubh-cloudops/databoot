"""Parquet reader: read(path) -> (columns, rows), the same shape as the other readers. See ARCHITECTURE.md "Data access".

Uses pyarrow when it can be imported (a runtime dependency, requirements.txt); otherwise a standard-library reader for flat
schemas: thrift compact footer, data page v1, PLAIN and dictionary encodings, definition levels, UNCOMPRESSED / GZIP /
SNAPPY. ZSTD, LZ4, BROTLI, LZO, nested schemas and other encodings raise ReadError('unsupported parquet encoding') on
both paths, so a file lists the same way whichever reader ran.
"""
import gzip
import os
import struct
from datetime import date, datetime, timedelta

from app.readers import EMPTY, ReadError, _names

UNSUPPORTED = "unsupported parquet encoding"
MAGIC = b"PAR1"
CODECS = {0: "UNCOMPRESSED", 1: "SNAPPY", 2: "GZIP", 3: "LZO", 4: "BROTLI", 5: "LZ4", 6: "ZSTD", 7: "LZ4_RAW"}
OK_CODECS = {"UNCOMPRESSED", "SNAPPY", "GZIP"}
EPOCH = datetime(1970, 1, 1)
# physical type -> struct format of one PLAIN value
FIXED = {1: "<i", 2: "<q", 4: "<f", 5: "<d"}
BOOLEAN, INT32, INT64, INT96, FLOAT, DOUBLE, BYTE_ARRAY = range(7)
DECIMAL, DATE = 5, 6


def read(path):
    """(columns, rows) of a .parquet file; rows are lists aligned to columns, a null is None."""
    if os.path.getsize(path) == 0:
        raise ReadError(EMPTY)
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return _read_plain(path)
    try:
        return _read_arrow(pq, path)
    except ReadError:
        raise
    except Exception:  # pyarrow's own errors (ArrowInvalid, OSError, ...) on a corrupt or odd file
        raise ReadError(UNSUPPORTED)


# ---- pyarrow ----

def _read_arrow(pq, path):
    meta = pq.ParquetFile(path).metadata
    for g in range(meta.num_row_groups):
        for c in range(meta.num_columns):
            if meta.row_group(g).column(c).compression not in OK_CODECS:
                raise ReadError(UNSUPPORTED)
    table = pq.read_table(path)
    if any(f.type.num_fields for f in table.schema):  # struct, list and map types all have children
        raise ReadError(UNSUPPORTED)
    cols = [c.to_pylist() for c in table.columns]
    return _names(table.column_names), [list(r) for r in zip(*cols)] if cols else []


# ---- standard-library reader ----

def _varint(b, i):
    n = shift = 0
    while True:
        x = b[i]
        i += 1
        n |= (x & 0x7F) << shift
        shift += 7
        if x < 0x80:
            return n, i


def _zigzag(n):
    return (n >> 1) ^ -(n & 1)


def _thrift(b, i, ftype):
    """Value of compact-protocol type `ftype` at b[i:] -> (value, next index). Structs are {field id: value}."""
    if ftype in (1, 2):  # bool inside a list: one byte
        return b[i] == 1, i + 1
    if ftype == 3:
        return b[i], i + 1
    if ftype in (4, 5, 6):
        n, i = _varint(b, i)
        return _zigzag(n), i
    if ftype == 7:
        return struct.unpack_from("<d", b, i)[0], i + 8
    if ftype == 8:
        n, i = _varint(b, i)
        return bytes(b[i:i + n]), i + n
    if ftype in (9, 10):
        head = b[i]
        i += 1
        size, et = head >> 4, head & 15
        if size == 15:
            size, i = _varint(b, i)
        out = []
        for _ in range(size):
            v, i = _thrift(b, i, et)
            out.append(v)
        return out, i
    if ftype == 12:
        return _struct(b, i)
    raise ReadError(UNSUPPORTED)  # maps are not used by the parts we read


def _struct(b, i):
    out, last = {}, 0
    while True:
        head = b[i]
        i += 1
        if head == 0:
            return out, i
        ftype = head & 15
        if head >> 4:
            last += head >> 4
        else:
            n, i = _varint(b, i)
            last = _zigzag(n)
        if ftype in (1, 2):  # bool value lives in the field header
            out[last] = ftype == 1
        else:
            out[last], i = _thrift(b, i, ftype)


def _snappy(b):
    n, i = _varint(b, 0)
    out = bytearray()
    while i < len(b):
        tag = b[i]
        i += 1
        kind = tag & 3
        if kind == 0:
            size = tag >> 2
            if size >= 60:
                extra = size - 59
                size = int.from_bytes(b[i:i + extra], "little")
                i += extra
            out += b[i:i + size + 1]
            i += size + 1
            continue
        if kind == 1:
            size, off = 4 + ((tag >> 2) & 7), ((tag >> 5) << 8) | b[i]
            i += 1
        else:
            width = 2 if kind == 2 else 4
            size, off = 1 + (tag >> 2), int.from_bytes(b[i:i + width], "little")
            i += width
        if not 0 < off <= len(out):
            raise ReadError(UNSUPPORTED)
        for _ in range(size):  # byte by byte: a copy may overlap its own output
            out.append(out[-off])
    if len(out) != n:
        raise ReadError(UNSUPPORTED)
    return bytes(out)


def _hybrid(b, i, width, count):
    """`count` values of the RLE / bit-packed hybrid starting at b[i]."""
    out = []
    while len(out) < count:
        h, i = _varint(b, i)
        if h & 1:  # bit-packed: (h >> 1) groups of 8 values
            n = (h >> 1) * 8
            bits = int.from_bytes(b[i:i + (h >> 1) * width], "little")
            i += (h >> 1) * width
            out += [(bits >> (k * width)) & ((1 << width) - 1) for k in range(n)]
        else:  # run: value stored in ceil(width / 8) bytes
            w = (width + 7) // 8
            out += [int.from_bytes(b[i:i + w], "little")] * (h >> 1)
            i += w
    return out[:count], i


def _plain(b, ptype, count):
    if ptype == BOOLEAN:
        return [bool(b[k >> 3] >> (k & 7) & 1) for k in range(count)]
    if ptype in FIXED:
        return list(struct.unpack_from(f"<{count}{FIXED[ptype][1]}", b))
    if ptype == INT96:  # nanoseconds in the day, then the Julian day number
        out = []
        for k in range(count):
            nanos, jd = struct.unpack_from("<qi", b, 12 * k)
            out.append(EPOCH + timedelta(days=jd - 2440588, microseconds=nanos // 1000))
        return out
    out, i = [], 0
    for _ in range(count):
        n = struct.unpack_from("<i", b, i)[0]
        out.append(bytes(b[i + 4:i + 4 + n]).decode("utf-8", "replace"))
        i += 4 + n
    return out


def _pages(buf, meta, ptype, max_def):
    """All values of one column chunk, None for nulls."""
    codec = CODECS.get(meta.get(4))
    if codec not in OK_CODECS:
        raise ReadError(UNSUPPORTED)
    i = meta.get(11) or meta[9]
    total, dictionary, values = meta[5], None, []
    while len(values) < total:
        head, i = _struct(buf, i)
        data = buf[i:i + head[3]]
        i += head[3]
        if codec == "GZIP":
            data = gzip.decompress(data)
        elif codec == "SNAPPY":
            data = _snappy(data)
        if head[1] == 2:  # dictionary page
            dictionary = _plain(data, ptype, head[7][1])
            continue
        if head[1] != 0:  # data page v2 and index pages are not read
            raise ReadError(UNSUPPORTED)
        count, enc = head[5][1], head[5][2]
        pos, levels = 0, [1] * count
        if max_def:
            size = struct.unpack_from("<i", data, 0)[0]
            levels, _ = _hybrid(data, 4, 1, count)
            pos = 4 + size
        present = sum(levels)
        if enc == 0:
            got = _plain(data[pos:], ptype, present)
        elif enc in (2, 8) and dictionary is not None:
            got, _ = _hybrid(data, pos + 1, data[pos], present)
            got = [dictionary[k] for k in got]
        else:
            raise ReadError(UNSUPPORTED)
        it = iter(got)
        values += [next(it) if lv else None for lv in levels]
    return values


def _converter(el):
    """Function turning a decoded value into date / datetime for the column's logical type, else None."""
    conv, logical = el.get(6), el.get(10, {})
    if conv == DECIMAL or 5 in logical:
        raise ReadError(UNSUPPORTED)
    if conv == DATE or 6 in logical:
        return lambda v: date(1970, 1, 1) + timedelta(days=v)
    per_sec = {9: 1000, 10: 1_000_000}.get(conv)
    if 8 in logical:
        per_sec = {1: 1000, 2: 1_000_000, 3: 1_000_000_000}[next(iter(logical[8][2]))]
    if per_sec:
        return lambda v: EPOCH + timedelta(microseconds=v * 1_000_000 // per_sec)
    return None


def _read_plain(path):
    with open(path, "rb") as f:
        buf = f.read()
    if buf[:4] != MAGIC or buf[-4:] != MAGIC:
        raise ReadError(UNSUPPORTED)
    foot = struct.unpack_from("<i", buf, len(buf) - 8)[0]
    meta, _ = _struct(buf, len(buf) - 8 - foot)
    schema = meta[2][1:]  # first element is the root
    if meta[2][0].get(5) != len(schema) or any(e.get(5) or e.get(3) == 2 for e in schema):
        raise ReadError(UNSUPPORTED)  # nested or repeated fields
    columns = [e[4].decode() for e in schema]
    convs = [_converter(e) for e in schema]
    data = [[] for _ in schema]
    for group in meta.get(4, []):
        for k, chunk in enumerate(group[1]):
            vals = _pages(buf, chunk[3], schema[k][1], 1 if schema[k].get(3) == 1 else 0)
            data[k] += [None if v is None else convs[k](v) for v in vals] if convs[k] else vals
    return _names(columns), [list(r) for r in zip(*data)]
