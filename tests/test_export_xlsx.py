import io
import warnings
import zipfile
from xml.etree import ElementTree as ET

import openpyxl

from app import xlsx
from app.catalog import Dataset

C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def download(client, path, sheet=None):
    ds = client.get("/api/datasets").json()
    d = next(d for d in ds if d["path"] == path and d["sheet"] == sheet)
    r = client.get(f"/datasets/{d['id']}/export.xlsx?app=explorer")
    assert r.status_code == 200
    return r, zipfile.ZipFile(io.BytesIO(r.content))


def parsed(z):
    """{member: Element}: every XML part must parse."""
    return {n: ET.fromstring(z.read(n)) for n in z.namelist()}


def chart_kinds(z):
    return [e.tag[len(C):] for n in sorted(z.namelist()) if n.startswith("xl/charts/")
            for e in parsed(z)[n].iter() if e.tag in (C + "lineChart", C + "barChart", C + "doughnutChart", C + "scatterChart")]


def test_sales_download(make_client, data_dir):
    r, z = download(make_client(data_dir), "sales.csv")
    assert r.headers["content-type"] == TYPE
    assert r.headers["content-disposition"] == 'attachment; filename="sales.xlsx"'
    # Data sheet round-trips through the reader; one chart sheet per chart, each with a drawing and a chart part.
    assert xlsx.sheet_names(io.BytesIO(r.content)) == ["Data", "chart-1 line", "chart-2 histogram", "chart-3 bar", "chart-4 donut", "Summary"]
    cols, rows = xlsx.read_sheet(io.BytesIO(r.content), "Data")
    assert cols == ["date", "region", "amount"] and len(rows) == 6 and rows[0][1] == "North"
    assert chart_kinds(z) == ["lineChart", "barChart", "barChart", "doughnutChart"]
    assert len([n for n in z.namelist() if n.startswith("xl/drawings/drawing")]) == 4
    # chart 1 references the table on its own sheet, which holds header + 6 points at A1
    c1 = z.read("xl/charts/chart1.xml").decode()
    assert "'chart-1 line'!$A$2:$A$7" in c1 and "'chart-1 line'!$B$2:$B$7" in c1
    cols, rows = xlsx.read_sheet(io.BytesIO(r.content), "chart-1 line")
    assert cols == ["date", "amount (sum)"] and rows[0] == ["2024-01-01", 10]
    cols, rows = xlsx.read_sheet(io.BytesIO(r.content), "chart-2 histogram")
    assert sum(r[1] for r in rows) == 6 and len(rows) == 20


def test_reopens_in_openpyxl_with_charts_and_no_style_warning(make_client, data_dir):
    client = make_client(data_dir)
    for path, sheet in [("sales.csv", None), ("points.tsv", None), ("sub/records.json", None), ("sub/book.xlsx", "Revenue")]:
        r, _ = download(client, path, sheet)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            wb = openpyxl.load_workbook(io.BytesIO(r.content))
        assert not [w for w in caught if "no default style" in str(w.message)]
        assert wb.sheetnames[0] == "Data"
        assert sum(len(ws._charts) for ws in wb) > 0
        assert all(len(n) <= 31 for n in wb.sheetnames)


def test_cells_stay_text_and_empty_chart_has_none():
    d = Dataset("x", "a.csv", None, "csv", 2, ["a", "b"])
    rows = [["=HYPERLINK(\"http://x\",\"y\")", "12"], ["http://example.com", float("nan")]]
    empty = {"id": "chart-1", "kind": "line", "title": "t", "x_label": "x", "y_label": "y", "rule": "r",
             "shown": 0, "total": 0, "data": {"x": [], "y": []}}
    wb = openpyxl.load_workbook(io.BytesIO(xlsx.write(d, rows, [empty])))
    ws = wb["Data"]
    assert ws["A2"].value.startswith("=HYPERLINK") and ws["A2"].data_type == "s"
    assert ws["B2"].value == "12" and ws["B2"].data_type == "s" and ws["A3"].hyperlink is None
    assert "#NUM!" in ws["B3"].value  # nan_inf_to_errors
    assert wb["chart-1 line"]["A1"].value == "x" and not wb["chart-1 line"]._charts


def test_map3d_and_country_map(make_client, data_dir):
    client = make_client(data_dir)
    r, z = download(client, "points.tsv")
    assert chart_kinds(z)[0] == "scatterChart"
    cols, rows = xlsx.read_sheet(io.BytesIO(r.content), "chart-1 map3d")
    assert cols == ["LON", "Latitude", "z"] and len(rows) == 4
    _, z = download(client, "sub/records.json")
    assert chart_kinds(z) == ["barChart", "barChart"]  # country_map, then the histogram of pop
    assert b"country" in z.read("xl/charts/chart1.xml")
    assert not any(b"mapChart" in z.read(n) or b"cx:" in z.read(n) for n in z.namelist())


def test_heatmap_sheet_has_color_scale_and_no_chart():
    d = Dataset("x", "a.csv", None, "csv", 3, ["a", "b", "c"])
    rows = [[1, 2, 3], [2, 4, 7], [3, 5, 1]]
    heat = {"id": "chart-1", "kind": "heatmap", "title": "t", "x_label": "column", "y_label": "column", "rule": "r",
            "shown": 3, "total": 3, "data": {"labels": ["a", "b", "c"], "z": [[1, 0.5, None], [0.5, 1, -1], [None, -1, 1]]}}
    data = xlsx.write(d, rows, [heat])
    z = zipfile.ZipFile(io.BytesIO(data))
    assert not [n for n in z.namelist() if n.startswith("xl/charts")]
    sheet = ET.fromstring(z.read("xl/worksheets/sheet2.xml"))  # xlsxwriter: sheetN.xml in sheet order
    cf = sheet.find(M + "conditionalFormatting")
    assert cf.get("sqref") == "B2:D4"
    scale = cf.find(f"{M}cfRule/{M}colorScale")
    assert len(scale.findall(M + "cfvo")) == 3 and len(scale.findall(M + "color")) == 3
    assert [e.get("rgb") for e in scale.findall(M + "color")] == ["FF3B4CC0", "FFFFFFFF", "FFB40426"]
    assert xlsx.read_sheet(io.BytesIO(data), "chart-1 heatmap")[0] == ["column", "a", "b", "c"]


def test_odd_values_stay_valid_xml():
    d = Dataset("x", "a.csv", None, "csv", 2, ["a<&>\"", "b"])
    rows = [["x\x00y\x0b", float("nan")], [True, 1e300]]
    data = xlsx.write(d, rows, [])
    parsed(zipfile.ZipFile(io.BytesIO(data)))
    assert xlsx.read_sheet(io.BytesIO(data), "Data")[0] == ['a<&>"', "b"]
    assert xlsx.sheet_names(io.BytesIO(data)) == ["Data", "Summary"]


def test_filename_with_sheet_and_404(make_client, data_dir):
    client = make_client(data_dir)
    r, _ = download(client, "sub/book.xlsx", "Revenue")
    assert r.headers["content-disposition"] == 'attachment; filename="book-Revenue.xlsx"'
    assert client.get("/datasets/nope/export.xlsx").status_code == 404


def test_scatter_and_heatmap_from_numeric_file(make_client, tmp_path):
    folder = tmp_path / "num"
    folder.mkdir()
    (folder / "n.csv").write_text("a,b,c\n" + "".join(f"{i},{i * i % 7},{10 - i}\n" for i in range(8)))
    r, z = download(make_client(folder), "n.csv")
    names = xlsx.sheet_names(io.BytesIO(r.content))
    assert names == ["Data", "chart-1 heatmap", "chart-2 histogram", "chart-3 scatter", "Summary"]
    assert chart_kinds(z) == ["barChart", "scatterChart"]
    parsed(z)
    assert b"colorScale" in z.read("xl/worksheets/sheet2.xml")


def test_filtered_export_has_filtered_rows_and_summary(make_client, data_dir):
    client = make_client(data_dir)
    d = next(d for d in client.get("/api/datasets").json() if d["path"] == "sales.csv")
    r = client.get(f"/datasets/{d['id']}/export.xlsx?app=explorer&f.region=North")
    names = xlsx.sheet_names(io.BytesIO(r.content))
    assert names[0] == "Data" and names[-1] == "Summary"
    assert len(xlsx.read_sheet(io.BytesIO(r.content), "Data")[1]) == 3
    assert xlsx.read_sheet(io.BytesIO(r.content), "Summary")[0] == ["Filters: region = North"]
    bar = next(n for n in names if n.endswith(" bar"))
    assert sum(row[1] for row in xlsx.read_sheet(io.BytesIO(r.content), bar)[1]) == 16
    plain = client.get(f"/datasets/{d['id']}/export.xlsx?app=explorer")
    assert xlsx.read_sheet(io.BytesIO(plain.content), "Summary")[0] == ["Filters: none"]
