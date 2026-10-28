"""PPTX download: native, editable charts (python-pptx) built from the chart dicts of app/rules.py."""
import io
import re
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Emu, Pt

_W, _H = 12192000, 6858000  # 16:9
_X, _CW = 457200, 11277600  # left margin, content width
_POINTS = {"map3d", "line", "scatter"}  # shown/total count points; the other kinds count rows
_TYPES = {"line": XL_CHART_TYPE.LINE, "bar": XL_CHART_TYPE.COLUMN_CLUSTERED, "country_map": XL_CHART_TYPE.COLUMN_CLUSTERED,
          "histogram": XL_CHART_TYPE.COLUMN_CLUSTERED, "donut": XL_CHART_TYPE.DOUGHNUT,
          "scatter": XL_CHART_TYPE.XY_SCATTER, "map3d": XL_CHART_TYPE.XY_SCATTER}
_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")  # not allowed in XML 1.0


def _clean_text(v):
    """Strings lose XML-illegal characters (lxml raises on them); other values pass through."""
    return _BAD.sub("", v) if isinstance(v, str) else v


def _box(slide, y, h, text, size, bold=False):
    """A text box with one paragraph."""
    tf = slide.shapes.add_textbox(Emu(_X), Emu(y), Emu(_CW), Emu(h)).text_frame
    tf.word_wrap = True
    run = tf.paragraphs[0].add_run()
    run.text = _clean_text(text)
    run.font.size, run.font.bold = Pt(size), bold


def _heat(r):
    """Fill colour of a correlation r: blue (-1), white (0), red (1), the same scale as the xlsx matrix."""
    end = (0xB4, 0x04, 0x26) if r > 0 else (0x3B, 0x4C, 0xC0)
    return "".join(f"{round(255 + (e - 255) * abs(r)):02X}" for e in end)


def _table(slide, c):
    """The heatmap as a native table: a header row and column of labels around the coloured r values."""
    labels, z = c["data"]["labels"], c["data"]["z"]
    n = len(labels) + 1
    row_h, size = min(370840, 4800600 // n), Pt(12 if n <= 9 else 9)
    table = slide.shapes.add_table(n, n, Emu(_X), Emu(1005840), Emu(_CW), Emu(row_h * n)).table
    rows = [[c["x_label"], *labels]] + [[lab, *r] for lab, r in zip(labels, z)]
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = table.cell(i, j)
            cell.text_frame.text = _clean_text(v) if isinstance(v, str) else "" if v is None else f"{v:.2f}"
            for run in cell.text_frame.paragraphs[0].runs:
                run.font.size = size
            if i and j and v is not None:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor.from_string(_heat(v))


def _data(c):
    """python-pptx chart data of a chart dict."""
    d, k = c["data"], c["kind"]
    if k in ("scatter", "map3d"):
        xs, ys = (d["lon"], d["lat"]) if k == "map3d" else (d["x"], d["y"])
        data = XyChartData()
        s = data.add_series(_clean_text(c["y_label"]))
        for x, y in zip(xs, ys):
            if x is not None and y is not None:
                s.add_data_point(x, y)
        return data
    if k == "histogram":
        e = d["edges"]
        cats = [f"{e[i]:.6g} to {e[i + 1]:.6g}" if None not in e[i:i + 2] else None for i in range(len(d["counts"]))]
        vals = d["counts"]
    else:
        ck, vk = {"donut": ("labels", "values"), "country_map": ("locations", "values")}.get(k, ("x", "y"))
        cats, vals = d[ck], d[vk]
    data = CategoryChartData()
    data.categories = ["" if v is None else _clean_text(v) for v in cats]
    data.add_series(_clean_text(c["y_label"]), vals)
    return data


def _chart(slide, c):
    chart = slide.shapes.add_chart(_TYPES[c["kind"]], Emu(_X), Emu(1005840), Emu(_CW), Emu(4800600), _data(c)).chart
    chart.has_title = False
    chart.has_legend = c["kind"] == "donut"
    if c["kind"] != "donut":
        for axis, label in ((chart.category_axis, c["x_label"]), (chart.value_axis, c["y_label"])):
            axis.has_title = True
            axis.axis_title.text_frame.text = _clean_text(label)
        chart.value_axis.tick_labels.number_format = "#,##0"
        chart.value_axis.tick_labels.number_format_is_linked = False


def pptx(dataset, charts, summary="Filters: none", rows_shown=None):
    """Presentation bytes: a title slide (name, "Rows: M" or "Rows: N of M" when filtered, filter summary), then one slide per chart.

    Each chart slide has the title, a native chart (python-pptx embeds the workbook, so Edit Data works) and two last
    text boxes: the rule caption and "N of M". A heatmap slide holds a native table instead of a chart.
    """
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(_W), Emu(_H)
    blank = prs.slide_layouts[6]
    name = Path(dataset.path).name + (f" - {dataset.sheet}" if dataset.sheet else "")
    slide = prs.slides.add_slide(blank)
    _box(slide, 2286000, 1000000, name, 40, True)
    of = "" if rows_shown is None else f"{rows_shown:,} of "
    _box(slide, 3429000, 600000, f"Rows: {of}{dataset.rows:,}, {len(dataset.columns):,} columns", 20)
    _box(slide, 4100000, 600000, summary, 20)
    for c in charts:
        slide = prs.slides.add_slide(blank)
        _box(slide, 228600, 685800, c["title"], 28, True)
        (_table if c["kind"] == "heatmap" else _chart)(slide, c)
        _box(slide, 5943600, 400000, c["rule"], 14)
        _box(slide, 6343600, 400000, f"{c['shown']:,} of {c['total']:,} {'points' if c['kind'] in _POINTS else 'rows'}", 14)
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()
