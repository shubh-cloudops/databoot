"""One reader per file kind: read(path, max_rows) -> (columns, rows, total_rows). Raise ValueError(reason) when unreadable.

Text kinds here (csv, tsv, json, jsonl, geojson); .xlsx is in app/xlsx.py and .parquet in app/parquet.py.
"""
