"""Spreadsheets: read .xlsx sheets with openpyxl (read_only), write .xlsx with native charts (xlsxwriter).

Reading: sheet_names(path) -> [name]; read_sheet(path, sheet) -> (columns, rows) in the shape of app/readers.py.
Anything that is not a readable workbook raises ReadError("not a valid xlsx").
Writing: write(dataset, rows, charts) -> bytes, see the end of this file.
"""
import io
import zipfile
from datetime import date, datetime

from openpyxl import load_workbook
from xlsxwriter import Workbook

from app.readers import NO_HEADER, ReadError, _names

NOT_XLSX = "not a valid xlsx"


def _value(v):
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return int(v)
    return v or None if isinstance(v, str) else v


_EMPTY = b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>'


def _load(path, keep=None):
    """Open the workbook with every worksheet part blanked except `keep` (a part name such as xl/worksheets/sheet2.xml).

    openpyxl parses each sheet's XML while loading, so one corrupt sheet would fail the whole workbook.
    """
    # ponytail: N+1 zip copies per workbook (one in sheet_names, one per read_sheet); cache the blanked bytes if big books get slow.
    try:
        if hasattr(path, "seek"):
            path.seek(0)
        out = io.BytesIO()
        with zipfile.ZipFile(path) as zi, zipfile.ZipFile(out, "w") as zo:
            for info in zi.infolist():
                n = info.filename
                blank = n.startswith("xl/worksheets/") and n.endswith(".xml") and "/_rels/" not in n and n != keep
                zo.writestr(info, _EMPTY if blank else zi.read(n))
        return load_workbook(out, read_only=True, data_only=True)
    except Exception:  # not a zip, missing file, no workbook part: all "not a valid xlsx"
        raise ReadError(NOT_XLSX) from None


def sheet_names(path):
    book = _load(path)
    try:
        if not book.sheetnames:
            raise ReadError(NOT_XLSX)
        return book.sheetnames
    finally:
        book.close()


def _part(path, sheet):
    book = _load(path)
    try:
        if sheet not in book.sheetnames:
            raise ReadError(NOT_XLSX)
        # ponytail: _worksheet_path is private to openpyxl (ReadOnlyWorksheet), checked against the 3.1.5 pin in requirements.txt.
        return book[sheet]._worksheet_path.lstrip("/")
    finally:
        book.close()


def read_sheet(path, sheet):
    """(columns, rows): the first non-empty row is the header; rows are padded or cut to its width."""
    book = _load(path, _part(path, sheet))
    try:
        ws = book[sheet]
        ws.reset_dimensions()
        rows = ([_value(v) for v in r] for r in ws.iter_rows(values_only=True))
        rows = (r for r in rows if any(v is not None for v in r))
        header = next(rows, None)
        if header is None:
            raise ReadError(NO_HEADER)
        columns = _names(["" if h is None else str(h) for h in header])
        n = len(columns)
        return columns, [(r + [None] * n)[:n] for r in rows]
    except ReadError:
        raise
    except Exception:  # corrupt sheet XML
        raise ReadError(NOT_XLSX) from None
    finally:
        book.close()


# ---- writing -------------------------------------------------------------------------------------------------
_OPTIONS = {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False, "strings_to_numbers": False,
            "nan_inf_to_errors": True, "default_date_format": "yyyy-mm-dd hh:mm:ss"}
_CHART = {"line": "line", "bar": "column", "country_map": "column", "histogram": "column", "donut": "doughnut",
          "scatter": "scatter", "map3d": "scatter"}  # Office map charts need Bing (online), so map3d is lon/lat points


def _cell(ws, r, c, v):
    if v is None:
        return
    if isinstance(v, bool):
        ws.write_boolean(r, c, v)
    elif isinstance(v, (datetime, date)):
        ws.write_datetime(r, c, v.replace(tzinfo=None) if isinstance(v, datetime) else v)
    elif isinstance(v, (int, float)):
        ws.write_number(r, c, v)
    else:
        ws.write_string(r, c, str(v)[:32767])  # Excel's cell limit


def _table(c):
    """(header, columns) of a chart's data table; columns are equal-length lists."""
    d, k = c["data"], c["kind"]
    head = [c["x_label"], c["y_label"]]
    if k == "histogram":
        e = d["edges"]
        return head, [[f"{e[i]:.6g} to {e[i + 1]:.6g}" if None not in e[i:i + 2] else None for i in range(len(d["counts"]))], d["counts"]]
    if k == "map3d":
        return head + ["z"], [d["lon"], d["lat"], d["z"]]
    keys = {"donut": ("labels", "values"), "country_map": ("locations", "values")}.get(k, ("x", "y"))
    return head, [d[keys[0]], d[keys[1]]]


def _grid(ws, head, rows):
    for r, row in enumerate([head, *rows]):
        for c, v in enumerate(row):
            _cell(ws, r, c, v)


def _chart(book, c, name, head, cols):
    k, n = c["kind"], len(cols[0])
    ch = book.add_chart({"type": _CHART[k]})
    series = {"name": [name, 0, 1], "categories": [name, 1, 0, n, 0], "values": [name, 1, 1, n, 1]}
    if k == "histogram":
        series["gap"] = 0
    ch.add_series(series)
    ch.set_title({"name": c["title"]})
    if k == "donut":
        return ch
    ch.set_x_axis({"name": c["x_label"]})
    ch.set_y_axis({"name": c["y_label"], "num_format": "#,##0"})
    ch.set_legend({"none": True})
    return ch


def write(dataset, rows, charts, summary="Filters: none"):
    """Workbook bytes: sheet Data, then one sheet per chart (its table at A1 plus a native chart that references it), then Summary (A1 = summary).

    A heatmap gets its matrix with a 3-colour scale and no chart; Office has no heatmap chart type.
    A chart with no rows keeps its sheet and table but gets no chart.
    """
    out = io.BytesIO()
    book = Workbook(out, _OPTIONS)
    _grid(book.add_worksheet("Data"), dataset.columns, rows)
    for c in charts:
        name = f"{c['id']} {c['kind']}"[:31]
        ws = book.add_worksheet(name)
        if c["kind"] == "heatmap":
            labels = c["data"]["labels"]
            _grid(ws, [c["x_label"], *labels], ([lab, *r] for lab, r in zip(labels, c["data"]["z"])))
            ws.conditional_format(1, 1, len(labels), len(labels), {
                "type": "3_color_scale", "min_type": "num", "min_value": -1, "mid_type": "num", "mid_value": 0,
                "max_type": "num", "max_value": 1, "min_color": "#3B4CC0", "mid_color": "#FFFFFF", "max_color": "#B40426"})
            continue
        head, cols = _table(c)
        _grid(ws, head, zip(*cols))
        if cols[0]:
            ws.insert_chart(1, len(head) + 1, _chart(book, c, name, head, cols))
    book.add_worksheet("Summary").write_string(0, 0, summary)
    book.close()
    return out.getvalue()
