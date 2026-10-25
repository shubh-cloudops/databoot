"""PPTX and XLSX downloads with native, editable Office charts built from the chart dicts of app/rules.py."""
import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

from app import xlsx
from app.xlsx import _ANS, _CNS, _HEAD, _RNS, _TYPE, _esc, _rels, _table

_PNS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_P = _TYPE + "presentationml."
_NS = f'xmlns:a="{_ANS}" xmlns:r="{_RNS}" xmlns:p="{_PNS}"'
_W, _H = 12192000, 6858000  # 16:9
_X, _CW = 457200, 11277600  # left margin, content width
_POINTS = {"map3d", "line", "scatter"}  # shown/total count points; the other kinds count rows
_THEME = (
    f'{_HEAD}<a:theme xmlns:a="{_ANS}" name="DataBoot"><a:themeElements><a:clrScheme name="DataBoot">'
    '<a:dk1><a:srgbClr val="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
    '<a:dk2><a:srgbClr val="333333"/></a:dk2><a:lt2><a:srgbClr val="EEEEEE"/></a:lt2>'
    + "".join(f'<a:accent{i}><a:srgbClr val="{c}"/></a:accent{i}>' for i, c in enumerate(
        ("3B4CC0", "B40426", "2E8B57", "E69F00", "56B4E9", "7F7F7F"), 1))
    + '<a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>'
    '<a:fontScheme name="DataBoot"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
    '<a:minorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
    '<a:fmtScheme name="DataBoot">'
    + "<a:fillStyleLst>" + '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>' * 3 + "</a:fillStyleLst>"
    + "<a:lnStyleLst>" + '<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>' * 3 + "</a:lnStyleLst>"
    + "<a:effectStyleLst>" + "<a:effectStyle><a:effectLst/></a:effectStyle>" * 3 + "</a:effectStyleLst>"
    + "<a:bgFillStyleLst>" + '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>' * 3 + "</a:bgFillStyleLst>"
    "</a:fmtScheme></a:themeElements></a:theme>")
_TREE = ('<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>')
_MASTER = (f'{_HEAD}<p:sldMaster {_NS}><p:cSld><p:spTree>{_TREE}</p:spTree></p:cSld>'
           '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
           'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
           '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>')
_LAYOUT = f'{_HEAD}<p:sldLayout {_NS} type="blank"><p:cSld name="Blank"><p:spTree>{_TREE}</p:spTree></p:cSld></p:sldLayout>'


def _box(id, x, y, w, h, paras, sz, bold=False):
    """A text box with one paragraph per string."""
    runs = "".join(f'<a:p><a:r><a:rPr lang="en-US" sz="{sz}" b="{int(bold)}"/><a:t>{_esc(t)}</a:t></a:r></a:p>' for t in paras)
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{id}" name="Text {id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>{runs}</p:txBody></p:sp>')


def _frame(id, h, uri, body):
    return (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{id}" name="Content {id}"/><p:cNvGraphicFramePr/><p:nvPr/>'
            f'</p:nvGraphicFramePr><p:xfrm><a:off x="{_X}" y="1005840"/><a:ext cx="{_CW}" cy="{h}"/></p:xfrm>'
            f'<a:graphic><a:graphicData uri="{uri}">{body}</a:graphicData></a:graphic></p:graphicFrame>')


def _heat(r):
    """Fill colour of a correlation r: blue (-1), white (0), red (1), the same scale as the xlsx matrix."""
    end = (0xB4, 0x04, 0x26) if r > 0 else (0x3B, 0x4C, 0xC0)
    return "".join(f"{round(255 + (e - 255) * abs(r)):02X}" for e in end)


def _table_frame(id, c):
    """The heatmap as a native a:tbl: a header row and column of labels around the coloured r values."""
    labels, z = c["data"]["labels"], c["data"]["z"]
    n = len(labels) + 1
    row_h, sz = min(370840, 4800600 // n), 1200 if n <= 9 else 900

    def cell(text, fill=None):
        pr = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else ""
        return (f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="{sz}"/><a:t>{_esc(text)}</a:t></a:r></a:p>'
                f'</a:txBody><a:tcPr>{pr}</a:tcPr></a:tc>')

    rows = [[cell(c["x_label"]), *[cell(lab) for lab in labels]]]
    for lab, r in zip(labels, z):
        rows.append([cell(lab), *[cell("" if v is None else f"{v:.2f}", None if v is None else _heat(v)) for v in r]])
    body = ('<a:tbl><a:tblPr firstRow="1"/><a:tblGrid>' + f'<a:gridCol w="{_CW // n}"/>' * n + "</a:tblGrid>"
            + "".join(f'<a:tr h="{row_h}">{"".join(r)}</a:tr>' for r in rows) + "</a:tbl>")
    return _frame(id, row_h * n, "http://schemas.openxmlformats.org/drawingml/2006/table", body)


def _slide(shapes):
    return f'{_HEAD}<p:sld {_NS}><p:cSld><p:spTree>{_TREE}{shapes}</p:spTree></p:cSld></p:sld>'


def _caption(c):
    unit = "points" if c["kind"] in _POINTS else "rows"
    return [c["rule"], f"{c['shown']:,} of {c['total']:,} {unit}"]


def pptx(dataset, charts):
    """Presentation bytes: a title slide, then one slide per chart.

    Each chart slide has the title, a native chart part whose embedded workbook comes from xlsx.write (so Edit Data
    works), and a text box with the rule caption and "N of M". A heatmap slide holds a native table instead of a chart.
    """
    name = Path(dataset.path).name + (f" - {dataset.sheet}" if dataset.sheet else "")
    slides = [_slide(_box(2, _X, 2286000, _CW, 1000000, [name], 4000, True)
                     + _box(3, _X, 3429000, _CW, 600000, [f"{dataset.rows:,} rows, {len(dataset.columns):,} columns"], 2000))]
    rels = [[("slideLayout", "../slideLayouts/slideLayout1.xml")]]
    parts = {}  # zip member -> (data, content type or None)
    n_charts = 0
    for c in charts:
        shapes = _box(2, _X, 228600, _CW, 685800, [c["title"]], 2800, True)
        rel = [("slideLayout", "../slideLayouts/slideLayout1.xml")]
        if c["kind"] == "heatmap":
            shapes += _table_frame(3, c)
        else:
            n_charts += 1
            head, cols = _table(c)
            book = xlsx.write(SimpleNamespace(columns=head), list(zip(*cols)), [c])  # sheet "chart-1 <kind>" holds the table again
            xml = xlsx._chart(c, f"chart-1 {c['kind']}", head, cols)
            parts[f"ppt/charts/chart{n_charts}.xml"] = (
                xml.replace("</c:chartSpace>", '<c:externalData r:id="rId1"><c:autoUpdate val="0"/></c:externalData></c:chartSpace>'),
                _TYPE + "drawingml.chart+xml")
            parts[f"ppt/charts/_rels/chart{n_charts}.xml.rels"] = (_rels(("package", f"../embeddings/Microsoft_Excel_Sheet{n_charts}.xlsx")), None)
            parts[f"ppt/embeddings/Microsoft_Excel_Sheet{n_charts}.xlsx"] = (book, _TYPE + "spreadsheetml.sheet")
            rel.append(("chart", f"../charts/chart{n_charts}.xml"))
            shapes += _frame(3, 4800600, _CNS, f'<c:chart xmlns:c="{_CNS}" r:id="rId2"/>')
        shapes += _box(4, _X, 5943600, _CW, 800000, _caption(c), 1400)
        slides.append(_slide(shapes))
        rels.append(rel)
    n = len(slides)
    for i, (xml, rel) in enumerate(zip(slides, rels), 1):
        parts[f"ppt/slides/slide{i}.xml"] = (xml, _P + "slide+xml")
        parts[f"ppt/slides/_rels/slide{i}.xml.rels"] = (_rels(*rel), None)
    parts["ppt/presentation.xml"] = (
        f'{_HEAD}<p:presentation {_NS}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>'
        + "".join(f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, n + 1))
        + f'</p:sldIdLst><p:sldSz cx="{_W}" cy="{_H}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>', _P + "presentation.main+xml")
    parts["ppt/_rels/presentation.xml.rels"] = (
        _rels(("slideMaster", "slideMasters/slideMaster1.xml"), *[("slide", f"slides/slide{i}.xml") for i in range(1, n + 1)],
              ("theme", "theme/theme1.xml")), None)
    parts["ppt/slideMasters/slideMaster1.xml"] = (_MASTER, _P + "slideMaster+xml")
    parts["ppt/slideMasters/_rels/slideMaster1.xml.rels"] = (_rels(("slideLayout", "../slideLayouts/slideLayout1.xml"), ("theme", "../theme/theme1.xml")), None)
    parts["ppt/slideLayouts/slideLayout1.xml"] = (_LAYOUT, _P + "slideLayout+xml")
    parts["ppt/slideLayouts/_rels/slideLayout1.xml.rels"] = (_rels(("slideMaster", "../slideMasters/slideMaster1.xml")), None)
    parts["ppt/theme/theme1.xml"] = (_THEME, _TYPE + "theme+xml")
    parts["_rels/.rels"] = (_rels(("officeDocument", "ppt/presentation.xml")), None)
    types = "".join(f'<Override PartName="/{p}" ContentType="{t}"/>' for p, (_, t) in parts.items() if t)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", f'{_HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   f'<Default Extension="xml" ContentType="application/xml"/>{types}</Types>')
        for p, (data, _) in parts.items():
            z.writestr(p, data)
    return out.getvalue()
