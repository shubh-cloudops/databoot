"""Parquet reader: read(path) -> (columns, rows), the same shape as the other readers. See ARCHITECTURE.md "Data access".

pyarrow only (a runtime dependency, requirements.txt), so every codec it supports reads. Any pyarrow error on the file is
ReadError('not a valid parquet file'); a nested column (struct, list, map) is ReadError('unsupported parquet encoding').
"""
import os

import pyarrow.parquet as pq

from app.readers import EMPTY, ReadError, _names

UNSUPPORTED = "unsupported parquet encoding"
INVALID = "not a valid parquet file"


def read(path):
    """(columns, rows) of a .parquet file; rows are lists aligned to columns, a null is None."""
    if os.path.getsize(path) == 0:
        raise ReadError(EMPTY)
    try:
        table = pq.read_table(path)
    except Exception:  # pyarrow's own errors (ArrowInvalid, OSError, ...) on a corrupt file
        raise ReadError(INVALID)
    if any(f.type.num_fields for f in table.schema):  # struct, list and map types all have children
        raise ReadError(UNSUPPORTED)
    cols = [c.to_pylist() for c in table.columns]
    return _names(table.column_names), [list(r) for r in zip(*cols)] if cols else []
