"""OOXML spreadsheets with the standard library (zipfile + xml.etree): read .xlsx sheets, write .xlsx with native charts.

Reading: sheet_names(path) -> [name]; read_sheet(path, sheet) -> (columns, rows) in the shape of app/readers.py.
Anything that is not a readable workbook raises ReadError("not a valid xlsx").
"""
import posixpath
import re
import zipfile
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

from app.readers import NO_HEADER, ReadError, _names

NOT_XLSX = "not a valid xlsx"
_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_EPOCH = datetime(1899, 12, 30)
_QUOTED = re.compile(r'"[^"]*"|\\.|\[[^\]]*\]|_.|\*.')  # literals, escapes, [Red]/[$-409], padding
_DATE_FMT = re.compile(r"d|yy|m.*y|y.*m")


def _iter(z, part):
    """Stream the elements of one zip member as they close (iterparse)."""
    with z.open(part) as f:
        for _, el in ET.iterparse(f):
            yield el


def _open(path):
    try:
        return zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise ReadError(NOT_XLSX) from None


def _sheets(z):
    """[(name, zip member)] in workbook order."""
    targets = {}
    for el in _iter(z, "xl/_rels/workbook.xml.rels"):
        if el.tag == _REL + "Relationship":
            t = el.get("Target")
            targets[el.get("Id")] = t.lstrip("/") if t.startswith("/") else posixpath.normpath("xl/" + t)
    return [(el.get("name"), targets[el.get(_R + "id")]) for el in _iter(z, "xl/workbook.xml") if el.tag == _M + "sheet"]


def _shared_strings(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    out = []
    for el in _iter(z, "xl/sharedStrings.xml"):
        if el.tag == _M + "si":  # <t> or rich-text runs <r><t>; phonetic <rPh> text is skipped
            out.append("".join(t.text or "" for r in el if r.tag != _M + "rPh" for t in ([r] if r.tag == _M + "t" else r.iter(_M + "t"))))
            el.clear()
    return out


def _date_styles(z):
    """Set of cellXfs indexes whose number format is a date."""
    if "xl/styles.xml" not in z.namelist():
        return set()
    custom, xfs, in_xfs = {}, [], False
    for ev, el in _events(z, "xl/styles.xml"):
        if ev == "start" and el.tag == _M + "cellXfs":
            in_xfs = True
        elif ev == "end" and el.tag == _M + "cellXfs":
            in_xfs = False
        elif ev == "end" and el.tag == _M + "numFmt":
            custom[el.get("numFmtId")] = el.get("formatCode", "")
        elif ev == "end" and el.tag == _M + "xf" and in_xfs:
            xfs.append(el.get("numFmtId", "0"))
    return {str(i) for i, f in enumerate(xfs) if _is_date(f, custom)}


def _events(z, part):
    with z.open(part) as f:
        yield from ET.iterparse(f, events=("start", "end"))


def _is_date(fmt_id, custom):
    if fmt_id in custom:
        return bool(_DATE_FMT.search(_QUOTED.sub("", custom[fmt_id]).lower()))
    return fmt_id.isdigit() and 14 <= int(fmt_id) <= 22


def _col(ref):
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + ord(ch.upper()) - 64
    return n - 1


def _value(c, strings, dates):
    """Python value of one <c> element (None when empty)."""
    t, v = c.get("t"), c.find(_M + "v")
    if t == "inlineStr":
        s = "".join(x.text or "" for x in c.iter(_M + "t"))
    elif v is None or v.text is None:
        return None
    elif t == "s":
        s = strings[int(v.text)]
    elif t == "b":
        return "TRUE" if v.text.strip() == "1" else "FALSE"
    elif t in ("str", "e"):
        s = v.text
    else:
        f = float(v.text)
        if c.get("s") in dates:
            return _EPOCH + timedelta(days=f)
        return int(f) if f.is_integer() and abs(f) < 1e15 else f
    return s or None


def _rows(z, member, strings, dates):
    """Yield each non-empty row of the sheet as a list indexed by column."""
    for el in _iter(z, member):
        if el.tag != _M + "row":
            continue
        row = []
        for c in el.iter(_M + "c"):
            i = _col(c.get("r", ""))
            row += [None] * (i + 1 - len(row))
            row[i] = _value(c, strings, dates)
        el.clear()
        if any(v is not None for v in row):
            yield row


def sheet_names(path):
    z = _open(path)
    try:
        with z:
            return [name for name, _ in _sheets(z)]
    except (KeyError, ET.ParseError):
        raise ReadError(NOT_XLSX) from None


def read_sheet(path, sheet):
    """(columns, rows): the first non-empty row is the header; rows are padded or cut to its width."""
    z = _open(path)
    try:
        with z:
            member = dict(_sheets(z)).get(sheet)
            if member is None:
                raise ReadError(NOT_XLSX)
            rows = _rows(z, member, _shared_strings(z), _date_styles(z))
            header = next(rows, None)
            if header is None:
                raise ReadError(NO_HEADER)
            columns = _names(["" if h is None else str(h) for h in header])
            n = len(columns)
            return columns, [(r + [None] * n)[:n] for r in rows]
    except (KeyError, ET.ParseError, zipfile.BadZipFile, ValueError, IndexError) as e:
        if isinstance(e, ReadError):
            raise
        raise ReadError(NOT_XLSX) from None
