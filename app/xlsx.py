"""OOXML spreadsheets with the standard library (zipfile + xml.etree): read .xlsx sheets, write .xlsx with native charts.

Reading: sheet_names(path) -> [name]; read_sheet(path, sheet) -> (columns, rows) in the shape of app/readers.py.
Anything that is not a readable workbook raises ReadError("not a valid xlsx").
Writing: write(dataset, rows, charts) -> bytes, see the second half of this file.
"""
import io
import math
import posixpath
import re
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

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


# ---- writing -------------------------------------------------------------------------------------------------
_RNS = _R[1:-1]
_CNS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_ANS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_XNS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
_MNS = _M[1:-1]
_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")  # not allowed in XML 1.0
_TYPE = "application/vnd.openxmlformats-officedocument."
_REL_TYPE = _RNS + "/"
_RELNS = _REL[1:-1]
_COLORS = '<color rgb="FF3B4CC0"/><color rgb="FFFFFFFF"/><color rgb="FFB40426"/>'  # blue - white - red, r = -1..1
_AXES = {"line", "bar", "histogram", "country_map"}  # category axis; scatter and map3d use two value axes
_STYLES = (f'{_HEAD}<styleSheet xmlns="{_MNS}"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
           '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
           '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
           '<cellXfs count="3"><xf numFmtId="0"/><xf numFmtId="22" applyNumberFormat="1"/><xf numFmtId="14" applyNumberFormat="1"/></cellXfs>'
           '</styleSheet>')


def _esc(v):
    return escape(_BAD.sub("", str(v)), {'"': "&quot;"})


def _letter(i):
    """Column letters of 0-based column i."""
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref, v):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ""
    if isinstance(v, bool):
        return f'<c r="{ref}" t="b"><v>{int(v)}</v></c>'
    if isinstance(v, (int, float)):
        return f'<c r="{ref}"><v>{v!r}</v></c>'
    if isinstance(v, datetime):
        return f'<c r="{ref}" s="1"><v>{(v.replace(tzinfo=None) - _EPOCH).total_seconds() / 86400!r}</v></c>'
    if isinstance(v, date):
        return f'<c r="{ref}" s="2"><v>{(v - _EPOCH.date()).days}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_esc(v)}</t></is></c>'


def _sheet(table, tail=""):
    rows = "".join(f'<row r="{r}">' + "".join(_cell(f"{_letter(c)}{r}", v) for c, v in enumerate(row)) + "</row>"
                   for r, row in enumerate(table, 1))
    return f'{_HEAD}<worksheet xmlns="{_MNS}" xmlns:r="{_RNS}"><sheetData>{rows}</sheetData>{tail}</worksheet>'


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


def _rng(sheet, col, n):
    L = _letter(col)
    return f"'{sheet}'!${L}$2:${L}${max(n, 1) + 1}"


def _ref(kind, f, vals):
    """c:strRef or c:numRef with its cache; None values are left out of the cache."""
    pts = "".join(f'<c:pt idx="{i}"><c:v>{_esc(v)}</c:v></c:pt>' for i, v in enumerate(vals)
                  if v is not None and not (isinstance(v, float) and not math.isfinite(v)))
    fmt = "<c:formatCode>General</c:formatCode>" if kind == "num" else ""
    return f'<c:{kind}Ref><c:f>{_esc(f)}</c:f><c:{kind}Cache>{fmt}<c:ptCount val="{len(vals)}"/>{pts}</c:{kind}Cache></c:{kind}Ref>'


def _title(s):
    return f'<c:title><c:tx><c:rich><a:bodyPr/><a:p><a:r><a:t>{_esc(s)}</a:t></a:r></a:p></c:rich></c:tx><c:overlay val="0"/></c:title>'


def _axis(tag, id, cross, pos, title, extra):
    grid = "<c:majorGridlines/>" if pos == "l" else ""
    return (f'<c:{tag}><c:axId val="{id}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/>'
            f'<c:axPos val="{pos}"/>{grid}{_title(title)}<c:numFmt formatCode="General" sourceLinked="1"/>'
            '<c:majorTickMark val="out"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
            f'<c:crossAx val="{cross}"/><c:crosses val="autoZero"/>{extra}</c:{tag}>')


def _chart(c, sheet, head, cols):
    """chart part XML whose series point at the table written to `sheet` (x in column A, y in column B)."""
    k, n = c["kind"], len(cols[0])
    scatter = k in ("scatter", "map3d")
    mid = ""
    if scatter:
        mid = '<c:spPr><a:ln w="19050"><a:noFill/></a:ln></c:spPr><c:marker><c:symbol val="circle"/><c:size val="5"/></c:marker>'
    elif k != "line" and k != "donut":
        mid = '<c:invertIfNegative val="0"/>'
    y = _ref("num", _rng(sheet, 1, n), cols[1])
    if scatter:
        pts = f'<c:xVal>{_ref("num", _rng(sheet, 0, n), cols[0])}</c:xVal><c:yVal>{y}</c:yVal>'
    else:
        cats = [None if v is None else str(v) for v in cols[0]]
        pts = f'<c:cat>{_ref("str", _rng(sheet, 0, n), cats)}</c:cat><c:val>{y}</c:val>'
    ser = (f'<c:ser><c:idx val="0"/><c:order val="0"/><c:tx>{_ref("str", f"{chr(39)}{sheet}{chr(39)}!$B$1", [head[1]])}</c:tx>'
           f'{mid}{pts}</c:ser>')
    ids = '<c:axId val="1"/><c:axId val="2"/>'
    if k == "line":
        plot = f'<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>{ser}<c:marker val="1"/>{ids}</c:lineChart>'
    elif k == "donut":
        plot = f'<c:doughnutChart><c:varyColors val="1"/>{ser}<c:firstSliceAng val="0"/><c:holeSize val="50"/></c:doughnutChart>'
    elif scatter:
        plot = f'<c:scatterChart><c:scatterStyle val="lineMarker"/><c:varyColors val="0"/>{ser}{ids}</c:scatterChart>'
    else:
        gap = 10 if k == "histogram" else 150
        plot = (f'<c:barChart><c:barDir val="col"/><c:grouping val="clustered"/><c:varyColors val="0"/>{ser}'
                f'<c:gapWidth val="{gap}"/>{ids}</c:barChart>')
    if k == "donut":
        axes, legend = "", '<c:legend><c:legendPos val="r"/><c:overlay val="0"/></c:legend>'
    else:
        legend = ""
        if scatter:
            axes = (_axis("valAx", 1, 2, "b", c["x_label"], '<c:crossBetween val="midCat"/>')
                    + _axis("valAx", 2, 1, "l", c["y_label"], '<c:crossBetween val="midCat"/>'))
        else:
            axes = (_axis("catAx", 1, 2, "b", c["x_label"], '<c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/>')
                    + _axis("valAx", 2, 1, "l", c["y_label"], '<c:crossBetween val="between"/>'))
    return (f'{_HEAD}<c:chartSpace xmlns:c="{_CNS}" xmlns:a="{_ANS}" xmlns:r="{_RNS}"><c:chart>{_title(c["title"])}'
            f'<c:autoTitleDeleted val="0"/><c:plotArea><c:layout/>{plot}{axes}</c:plotArea>{legend}'
            '<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart></c:chartSpace>')


def _drawing(col):
    """One chart anchored from column `col`, row 2, 10 columns by 20 rows."""
    pos = lambda c, r: f"<xdr:col>{c}</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{r}</xdr:row><xdr:rowOff>0</xdr:rowOff>"
    return (f'{_HEAD}<xdr:wsDr xmlns:xdr="{_XNS}" xmlns:a="{_ANS}" xmlns:r="{_RNS}" xmlns:c="{_CNS}"><xdr:twoCellAnchor>'
            f'<xdr:from>{pos(col, 1)}</xdr:from><xdr:to>{pos(col + 10, 21)}</xdr:to><xdr:graphicFrame macro="">'
            '<xdr:nvGraphicFramePr><xdr:cNvPr id="2" name="Chart 1"/><xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr>'
            '<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm><a:graphic>'
            f'<a:graphicData uri="{_CNS}"><c:chart r:id="rId1"/></a:graphicData></a:graphic></xdr:graphicFrame>'
            '<xdr:clientData/></xdr:twoCellAnchor></xdr:wsDr>')


def _rels(*targets):
    """Relationships part: targets are (type suffix, target) and get ids rId1, rId2, ..."""
    return (f'{_HEAD}<Relationships xmlns="{_RELNS}">'
            + "".join(f'<Relationship Id="rId{i}" Type="{_REL_TYPE}{t}" Target="{x}"/>' for i, (t, x) in enumerate(targets, 1))
            + "</Relationships>")


def write(dataset, rows, charts):
    """Workbook bytes: sheet Data, then one sheet per chart (its table at A1 plus a native chart that references it).

    A heatmap gets its matrix with a 3-colour scale and no chart part; Office has no heatmap chart type.
    """
    sheets = [("Data", _sheet([dataset.columns, *rows]))]
    parts = {}  # zip member -> (xml, content type)
    n_charts = 0
    for i, c in enumerate(charts, 1):
        name = f"chart-{i} {c['kind']}"
        sn = len(sheets) + 1
        if c["kind"] == "heatmap":
            labels, z = c["data"]["labels"], c["data"]["z"]
            cell = f"{_letter(len(labels))}{len(labels) + 1}"
            scale = (f'<conditionalFormatting sqref="B2:{cell}"><cfRule type="colorScale" priority="1"><colorScale>'
                     f'<cfvo type="num" val="-1"/><cfvo type="num" val="0"/><cfvo type="num" val="1"/>{_COLORS}'
                     "</colorScale></cfRule></conditionalFormatting>")
            sheets.append((name, _sheet([[c["x_label"], *labels], *([lab, *r] for lab, r in zip(labels, z))], scale)))
            continue
        n_charts += 1
        head, cols = _table(c)
        sheets.append((name, _sheet([head, *zip(*cols)], '<drawing r:id="rId1"/>')))
        parts[f"xl/worksheets/_rels/sheet{sn}.xml.rels"] = (_rels(("drawing", f"../drawings/drawing{n_charts}.xml")), None)
        parts[f"xl/drawings/drawing{n_charts}.xml"] = (_drawing(len(head) + 1), _TYPE + "drawing+xml")
        parts[f"xl/drawings/_rels/drawing{n_charts}.xml.rels"] = (_rels(("chart", f"../charts/chart{n_charts}.xml")), None)
        parts[f"xl/charts/chart{n_charts}.xml"] = (_chart(c, name, head, cols), _TYPE + "drawingml.chart+xml")
    for i, (_, xml) in enumerate(sheets, 1):
        parts[f"xl/worksheets/sheet{i}.xml"] = (xml, _TYPE + "spreadsheetml.worksheet+xml")
    parts["xl/styles.xml"] = (_STYLES, _TYPE + "spreadsheetml.styles+xml")
    parts["xl/workbook.xml"] = (
        f'{_HEAD}<workbook xmlns="{_MNS}" xmlns:r="{_RNS}"><sheets>'
        + "".join(f'<sheet name="{_esc(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _) in enumerate(sheets, 1))
        + "</sheets></workbook>", _TYPE + "spreadsheetml.sheet.main+xml")
    parts["xl/_rels/workbook.xml.rels"] = (
        _rels(*[("worksheet", f"worksheets/sheet{i}.xml") for i in range(1, len(sheets) + 1)], ("styles", "styles.xml")), None)
    parts["_rels/.rels"] = (_rels(("officeDocument", "xl/workbook.xml")), None)
    types = "".join(f'<Override PartName="/{p}" ContentType="{t}"/>' for p, (_, t) in parts.items() if t)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", f'{_HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   f'<Default Extension="xml" ContentType="application/xml"/>{types}</Types>')
        for p, (xml, _) in parts.items():
            z.writestr(p, xml)
    return out.getvalue()
