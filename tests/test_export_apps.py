"""App exports (E2): title, "table" charts, Business and Map chart lists, Explorer output unchanged (ARCHITECTURE.md "Exports")."""
import io

from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE

from app import business, export, geo, xlsx
from app.catalog import Dataset


def _id(client, name):
    return next(d["id"] for d in client.get("/api/datasets").json() if d["path"] == name)


def _get(make_client, folder, name, kind, query=""):
    client = make_client(folder)
    r = client.get(f"/datasets/{_id(client, name)}/export.{kind}{query}")
    assert r.status_code == 200
    return io.BytesIO(r.content)


def _texts(slide):
    return [s.text_frame.text for s in slide.shapes if s.has_text_frame]


def test_explorer_output_is_round_4(make_client, data_dir):
    got = _get(make_client, data_dir, "sales.csv", "xlsx", "?app=explorer")
    assert xlsx.sheet_names(got) == ["Data", "chart-1 line", "chart-2 histogram", "chart-3 bar", "chart-4 donut", "Summary"]
    assert xlsx.read_sheet(got, "Summary")[0] == ["Filters: none"]
    slides = list(Presentation(_get(make_client, data_dir, "sales.csv", "pptx", "?app=explorer")).slides)
    assert _texts(slides[0])[:2] == ["Data overview", "sales.csv"]


def test_business_xlsx(make_client, archetypes_dir):
    got = _get(make_client, archetypes_dir, "shop.csv", "xlsx", "?app=business")
    assert xlsx.sheet_names(got) == ["Data", "chart-1 table", "chart-2 line", "chart-3 line", "chart-4 bar", "chart-5 table", "Summary"]
    head, rows = xlsx.read_sheet(got, "chart-1 table")
    assert head == ["Measure", "Previous", "Latest", "Change %"] and [r[0] for r in rows] == ["revenue", "units"]
    assert rows[1][1:3] == [5 * 12, 6 * 12]  # units = month number; 12 rows (2 days x 6 store/channel pairs) per month
    head, rows = xlsx.read_sheet(got, "chart-5 table")
    assert head[1:] == ["Previous", "Latest", "Change"] and rows
    assert xlsx.read_sheet(got, "Summary") == (["Business overview"], [["Filters: none"]])


def test_business_pptx(make_client, archetypes_dir):
    slides = list(Presentation(_get(make_client, archetypes_dir, "shop.csv", "pptx", "?app=business")).slides)
    assert _texts(slides[0])[0] == "Business overview" and "Rows: 78, 6 columns" in _texts(slides[0])[2]
    assert [s.has_chart for sl in slides[1:] for s in sl.shapes if s.has_chart or s.has_table] == [False, True, True, True, False]
    charts = [s.chart.chart_type for sl in slides[1:] for s in sl.shapes if s.has_chart]
    assert charts == [XL_CHART_TYPE.LINE, XL_CHART_TYPE.LINE, XL_CHART_TYPE.COLUMN_CLUSTERED]
    table = next(s.table for s in slides[1].shapes if s.has_table)
    assert [c.text for c in table.rows[0].cells] == ["Measure", "Previous", "Latest", "Change %"]


def test_map_exports(make_client, archetypes_dir):
    got = _get(make_client, archetypes_dir, "places.csv", "xlsx", "?app=map")
    assert xlsx.sheet_names(got) == ["Data", "chart-1 scatter", "chart-2 bar", "Summary"]
    assert xlsx.read_sheet(got, "Summary") == (["Map overview"], [["Filters: none"]])
    assert len(xlsx.read_sheet(got, "chart-1 scatter")[1]) == 20
    slides = list(Presentation(_get(make_client, archetypes_dir, "places.csv", "pptx", "?app=map")).slides)
    assert _texts(slides[0])[0] == "Map overview"
    assert [s.chart.chart_type for sl in slides[1:] for s in sl.shapes if s.has_chart] == [
        XL_CHART_TYPE.XY_SCATTER, XL_CHART_TYPE.COLUMN_CLUSTERED]


def test_filters_still_work_in_app_exports(make_client, archetypes_dir):
    full = xlsx.read_sheet(_get(make_client, archetypes_dir, "shop.csv", "xlsx", "?app=business"), "Data")[1]
    got = _get(make_client, archetypes_dir, "shop.csv", "xlsx", "?app=business&f.channel=web")
    assert 0 < len(xlsx.read_sheet(got, "Data")[1]) < len(full)
    assert xlsx.read_sheet(got, "Summary") == (["Business overview"], [["Filters: channel = web"]])
    slide = list(Presentation(_get(make_client, archetypes_dir, "shop.csv", "pptx", "?app=business&f.channel=web")).slides)[0]
    n = len(xlsx.read_sheet(got, "Data")[1])
    assert _texts(slide)[2:] == [f"Rows: {n} of 78, 6 columns", "Filters: channel = web"]


def test_default_app_is_the_detected_one(make_client, archetypes_dir):
    assert xlsx.sheet_names(_get(make_client, archetypes_dir, "shop.csv", "xlsx"))[1] == "chart-1 table"


def test_direct_title_and_table_chart():
    d = Dataset("x", "a.csv", None, "csv", 1, ["a"])
    t = {"id": "chart-1", "kind": "table", "title": "T", "x_label": "a", "y_label": "b", "rule": "r", "shown": 1, "total": 1,
         "data": {"head": ["a", "b"], "rows": [["x", 1.5], ["y", None]]}}
    got = io.BytesIO(xlsx.write(d, [["v"]], [t], "Filters: none", "My title"))
    assert xlsx.sheet_names(got) == ["Data", "chart-1 table", "Summary"]
    assert xlsx.read_sheet(got, "chart-1 table")[1] == [["x", 1.5], ["y", None]]
    assert xlsx.read_sheet(got, "Summary") == (["My title"], [["Filters: none"]])
    slides = list(Presentation(io.BytesIO(export.pptx(d, [t], title="My title"))).slides)
    assert _texts(slides[0])[0] == "My title" and _texts(slides[1])[0] == "T"
    cells = [[c.text for c in r.cells] for r in next(s.table for s in slides[1].shapes if s.has_table).rows]
    assert cells == [["a", "b"], ["x", "1.50"], ["y", ""]]


def test_geo_export_samples_scatter_to_chart_cap():
    class S:
        chart_cap = 3
    typed = [[float(i), float(i)] for i in range(10)]
    got = geo.export({"charts": []}, ["lat", "lon"], typed, {"lat": "geospatial", "lon": "geospatial"}, S())
    assert [c["id"] for c in got] == ["chart-1"] and (got[0]["shown"], got[0]["total"]) == (3, 10)
    assert business.export({"cards": [], "charts": [], "changes": None})[0]["data"]["rows"] == []


def _id_sheet(client, name, sheet):
    return next(d["id"] for d in client.get("/api/datasets").json() if d["path"] == name and d["sheet"] == sheet)


def _first_runs(slide):
    return [s.text_frame.paragraphs[0].runs[0].font for s in slide.shapes if s.has_text_frame]


def test_title_slide_second_line_is_file_name_in_smaller_size(make_client, data_dir, archetypes_dir):
    prs = Presentation(_get(make_client, data_dir, "sales.csv", "pptx", "?app=explorer"))
    assert _texts(prs.slides[0]) == ["Data overview", "sales.csv", "Rows: 6, 3 columns", "Filters: none"]
    fonts = _first_runs(prs.slides[0])
    assert (fonts[0].size.pt, fonts[0].bold, fonts[1].size.pt) == (40, True, 24)
    shapes = list(prs.slides[0].shapes)
    assert all(a.top + a.height <= b.top for a, b in zip(shapes, shapes[1:]))  # no overlap
    assert shapes[-1].top + shapes[-1].height <= prs.slide_height
    slides = list(Presentation(_get(make_client, archetypes_dir, "shop.csv", "pptx", "?app=business")).slides)
    assert _texts(slides[0])[:2] == ["Business overview", "shop.csv"]
    client = make_client(data_dir)
    r = client.get(f"/datasets/{_id_sheet(client, 'sub/book.xlsx', 'Revenue')}/export.pptx")
    slide = Presentation(io.BytesIO(r.content)).slides[0]
    assert _texts(slide)[:2] == ["Business overview", "book.xlsx - Revenue"]
    assert _first_runs(slide)[1].size < _first_runs(slide)[0].size


def test_explorer_only_dataset_exports_have_no_overview(make_client, archetypes_dir):
    client = make_client(archetypes_dir)
    i = _id(client, "measures.csv")
    assert client.get(f"/api/datasets/{i}/app").json()["shown"] == "explorer"
    book = io.BytesIO(client.get(f"/datasets/{i}/export.xlsx").content)
    names = xlsx.sheet_names(book)
    assert names[0] == "Data" and names[-1] == "Summary" and len(names) > 2
    assert xlsx.read_sheet(book, "Summary") == (["Filters: none"], [])
    from openpyxl import load_workbook
    assert sum(len(ws._charts) for ws in load_workbook(book).worksheets) > 0
    n = len(client.get(f"/api/datasets/{i}/charts").json()["charts"])
    slides = list(Presentation(io.BytesIO(client.get(f"/datasets/{i}/export.pptx").content)).slides)
    assert len(slides) == 1 + n and n > 0
    assert all(any(s.has_chart or s.has_table for s in sl.shapes) for sl in slides[1:])
    assert _texts(slides[0])[0] == "Data overview"  # Board gate 186: client-facing title, not "Explorer"
