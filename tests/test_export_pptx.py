import io
import posixpath
import zipfile
from xml.etree import ElementTree as ET

from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE

from app import export
from app.catalog import Dataset

CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def download(client, path, sheet=None):
    ds = client.get("/api/datasets").json()
    d = next(d for d in ds if d["path"] == path and d["sheet"] == sheet)
    r = client.get(f"/datasets/{d['id']}/export.pptx")
    assert r.status_code == 200
    return r, r.content


def parsed(z):
    """{member: Element}: every XML part must parse (embedded workbooks and the template's printer settings are binary)."""
    return {n: ET.fromstring(z.read(n)) for n in z.namelist() if n.endswith((".xml", ".rels"))}


def check_package(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    root = parsed(z)
    listed = {e.get("PartName").lstrip("/") for e in root["[Content_Types].xml"].iter(CT + "Override")}
    defaults = {e.get("Extension") for e in root["[Content_Types].xml"].iter(CT + "Default")}
    for name in z.namelist():
        if name != "[Content_Types].xml":
            assert name in listed or name.rsplit(".", 1)[-1] in defaults, name
    assert listed <= set(z.namelist())
    for name, rel in root.items():
        if name.endswith(".rels"):
            folder = name.replace("_rels/", "").rsplit(".rels", 1)[0].rpartition("/")[0]
            for e in rel:
                if e.get("TargetMode") != "External":
                    assert posixpath.normpath(posixpath.join(folder, e.get("Target"))) in z.namelist()


def texts(slide):
    return [s.text_frame.text for s in slide.shapes if s.has_text_frame]


def chart_of(slide):
    return next(s.chart for s in slide.shapes if s.has_chart)


def test_sales_download(make_client, data_dir):
    r, data = download(make_client(data_dir), "sales.csv")
    assert r.headers["content-type"] == TYPE
    assert r.headers["content-disposition"] == 'attachment; filename="sales.pptx"'
    check_package(data)
    prs = Presentation(io.BytesIO(data))
    assert (prs.slide_width, prs.slide_height) == (12192000, 6858000)
    slides = list(prs.slides)
    assert len(slides) == 5
    assert all(s.slide_layout.name == "Blank" for s in slides)
    assert texts(slides[0]) == ["sales.csv", "6 rows, 3 columns"]
    assert texts(slides[1])[0] == "amount by date"
    assert texts(slides[1])[-2:] == ["temporal date + numerical amount: line, sum per date", "6 of 6 points"]
    kinds = [chart_of(s).chart_type for s in slides[1:]]
    assert kinds[:3] == [XL_CHART_TYPE.LINE, XL_CHART_TYPE.COLUMN_CLUSTERED, XL_CHART_TYPE.COLUMN_CLUSTERED]
    line = chart_of(slides[1])
    assert len(line.plots[0].categories) == 6 and line.plots[0].categories[0] == "2024-01-01"
    assert line.category_axis.axis_title.text_frame.text == "date"
    assert line.value_axis.axis_title.text_frame.text == "amount (sum)"
    assert line.value_axis.tick_labels.number_format == "#,##0"
    assert list(line.plots[0].series[0].values)[0] == 10


def test_map_substitutes_and_404(make_client, data_dir):
    client = make_client(data_dir)
    _, data = download(client, "points.tsv")
    assert chart_of(list(Presentation(io.BytesIO(data)).slides)[1]).chart_type == XL_CHART_TYPE.XY_SCATTER
    _, data = download(client, "sub/records.json")
    slides = list(Presentation(io.BytesIO(data)).slides)
    assert [chart_of(s).chart_type for s in slides[1:]] == [XL_CHART_TYPE.COLUMN_CLUSTERED] * 2
    r, data = download(client, "sub/book.xlsx", "Revenue")
    check_package(data)
    assert r.headers["content-disposition"] == 'attachment; filename="book-Revenue.pptx"'
    assert client.get("/datasets/nope/export.pptx").status_code == 404


def test_heatmap_slide_is_a_native_table_and_counts_have_separators():
    d = Dataset("x", "a.csv", None, "csv", 56789, ["a", "b"])
    heat = {"id": "chart-1", "kind": "heatmap", "title": "correlation", "x_label": "column", "y_label": "column",
            "rule": "2 numerical columns: Pearson r", "shown": 1234, "total": 56789,
            "data": {"labels": ["a", "b"], "z": [[1, -0.5], [None, 1]]}}
    data = export.pptx(d, [heat])
    check_package(data)
    assert not [n for n in zipfile.ZipFile(io.BytesIO(data)).namelist() if n.startswith("ppt/charts")]
    prs = Presentation(io.BytesIO(data))
    assert texts(list(prs.slides)[0]) == ["a.csv", "56,789 rows, 2 columns"]
    slide = list(prs.slides)[1]
    table = next(s.table for s in slide.shapes if s.has_table)
    assert (len(table.rows), len(table.columns)) == (3, 3)
    assert [[c.text for c in r.cells] for r in table.rows] == [["column", "a", "b"], ["a", "1.00", "-0.50"], ["b", "", "1.00"]]
    assert str(table.cell(1, 2).fill.fore_color.rgb) == export._heat(-0.5) == "9DA6E0"
    assert texts(slide)[-1] == "1,234 of 56,789 rows"


def test_chart_kinds_and_axis_titles():
    d = Dataset("x", "a.csv", None, "csv", 3, ["a"])

    def chart(kind, data, **kw):
        return {"id": "chart-1", "kind": kind, "title": "t", "x_label": "xl", "y_label": "yl", "rule": "r", "shown": 3,
                "total": 3, "data": data, **kw}

    charts = [chart("donut", {"labels": ["a", None], "values": [1, 2]}),
              chart("histogram", {"edges": [0, 1.5, 3], "counts": [4, 5]}),
              chart("country_map", {"locations": ["DEU"], "values": [1234567]}),
              chart("map3d", {"lon": [1, None, 3], "lat": [4, 5, 6], "z": [0, 0, 0]}, z_label=None),
              chart("scatter", {"x": [1, 2], "y": [3, 4]})]
    check_package(export.pptx(d, charts))
    slides = list(Presentation(io.BytesIO(export.pptx(d, charts))).slides)
    got = [chart_of(s) for s in slides[1:]]
    assert [c.chart_type for c in got] == [XL_CHART_TYPE.DOUGHNUT, XL_CHART_TYPE.COLUMN_CLUSTERED,
                                          XL_CHART_TYPE.COLUMN_CLUSTERED, XL_CHART_TYPE.XY_SCATTER, XL_CHART_TYPE.XY_SCATTER]
    assert len(got[0].plots[0].categories) == 2 and got[0].plots[0].categories[0] == "a"
    assert list(got[1].plots[0].categories) == ["0 to 1.5", "1.5 to 3"]
    assert list(got[3].plots[0].series[0].values) == [4, 6]  # the point with a missing lon is skipped
    assert got[2].category_axis.axis_title.text_frame.text == "xl"
    assert texts(slides[1])[-1] == "3 of 3 rows" and texts(slides[4])[-1] == "3 of 3 points"


def test_no_charts_and_illegal_characters_stay_valid():
    d = Dataset("x", "a<&>\x01.csv", "s\x00", "csv", 0, [])
    data = export.pptx(d, [])
    check_package(data)
    slides = list(Presentation(io.BytesIO(data)).slides)
    assert len(slides) == 1 and texts(slides[0]) == ["a<&>.csv - s", "0 rows, 0 columns"]
    c = {"id": "chart-1", "kind": "bar", "title": "t\x00", "x_label": "x\x0b", "y_label": "y", "rule": "r\x1f", "shown": 1,
         "total": 1, "data": {"x": ["a\x00b"], "y": [1]}}
    slides = list(Presentation(io.BytesIO(export.pptx(d, [c]))).slides)
    assert list(chart_of(slides[1]).plots[0].categories) == ["ab"] and texts(slides[1])[0] == "t"
