import io
import posixpath
import re
import zipfile
from xml.etree import ElementTree as ET

from app import export, xlsx
from app.catalog import Dataset

C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
CHARTS = ("lineChart", "barChart", "doughnutChart", "scatterChart")


def download(client, path, sheet=None):
    ds = client.get("/api/datasets").json()
    d = next(d for d in ds if d["path"] == path and d["sheet"] == sheet)
    r = client.get(f"/datasets/{d['id']}/export.pptx")
    assert r.status_code == 200
    return r, zipfile.ZipFile(io.BytesIO(r.content))


def parsed(z):
    """{member: Element}: every XML part must parse (the embedded workbooks are zips, not XML)."""
    return {n: ET.fromstring(z.read(n)) for n in z.namelist() if not n.endswith(".xlsx")}


def texts(z, n):
    return [t.text for t in ET.fromstring(z.read(f"ppt/slides/slide{n}.xml")).iter(A + "t")]


def chart_kinds(z):
    root = parsed(z)
    return [e.tag[len(C):] for n in sorted(root) if n.startswith("ppt/charts/chart") for e in root[n].iter() if e.tag[len(C):] in CHARTS]


def check_package(z):
    root = parsed(z)
    listed = {e.get("PartName").lstrip("/") for e in root["[Content_Types].xml"].iter(CT + "Override")}
    for name in z.namelist():
        if name != "[Content_Types].xml" and not name.endswith(".rels"):
            assert name in listed, name
    assert listed <= set(z.namelist())
    for name, rel in root.items():
        if name.endswith(".rels"):
            folder = name.replace("_rels/", "").rsplit(".rels", 1)[0].rpartition("/")[0]
            for e in rel:
                assert posixpath.normpath(posixpath.join(folder, e.get("Target"))) in z.namelist()


def test_sales_download(make_client, data_dir):
    r, z = download(make_client(data_dir), "sales.csv")
    assert r.headers["content-type"] == TYPE
    assert r.headers["content-disposition"] == 'attachment; filename="sales.pptx"'
    check_package(z)
    assert chart_kinds(z) == ["lineChart", "barChart", "doughnutChart", "barChart"]
    slides = [n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
    assert len(slides) == 5
    assert texts(z, 1) == ["sales.csv", "6 rows, 3 columns"]
    assert texts(z, 2) == ["amount by date", "temporal date + numerical amount: line, sum per date", "6 of 6 points"]
    # one embedded workbook per chart, each readable by the xlsx reader, holding the chart table
    books = sorted(n for n in z.namelist() if n.startswith("ppt/embeddings/"))
    assert len(books) == 4
    cols, rows = xlsx.read_sheet(io.BytesIO(z.read(books[0])), "chart-1 line")
    assert cols == ["date", "amount (sum)"] and rows[0] == ["2024-01-01", 10]
    assert xlsx.sheet_names(io.BytesIO(z.read(books[0]))) == ["Data", "chart-1 line"]
    # the chart part points at its workbook and its series at the sheet inside it
    assert b"externalData" in z.read("ppt/charts/chart1.xml") and b"'chart-1 line'!$A$2:$A$7" in z.read("ppt/charts/chart1.xml")
    assert b"Microsoft_Excel_Sheet1.xlsx" in z.read("ppt/charts/_rels/chart1.xml.rels")


def test_map_substitutes_and_404(make_client, data_dir):
    client = make_client(data_dir)
    _, z = download(client, "points.tsv")
    assert chart_kinds(z)[0] == "scatterChart"
    _, z = download(client, "sub/records.json")
    assert chart_kinds(z) == ["barChart", "barChart"]
    assert not any(b"mapChart" in z.read(n) for n in z.namelist())
    _, z = download(client, "sub/book.xlsx", "Revenue")
    check_package(z)
    r, _ = download(client, "sub/book.xlsx", "Revenue")
    assert r.headers["content-disposition"] == 'attachment; filename="book-Revenue.pptx"'
    assert client.get("/datasets/nope/export.pptx").status_code == 404


def test_heatmap_slide_is_a_native_table_and_counts_have_separators():
    d = Dataset("x", "a.csv", None, "csv", 56789, ["a", "b"])
    heat = {"id": "chart-1", "kind": "heatmap", "title": "correlation", "x_label": "column", "y_label": "column",
            "rule": "2 numerical columns: Pearson r", "shown": 1234, "total": 56789,
            "data": {"labels": ["a", "b"], "z": [[1, -0.5], [None, 1]]}}
    z = zipfile.ZipFile(io.BytesIO(export.pptx(d, [heat])))
    check_package(z)
    assert not [n for n in z.namelist() if n.startswith("ppt/charts") or n.startswith("ppt/embeddings")]
    assert texts(z, 1) == ["a.csv", "56,789 rows, 2 columns"]
    slide = ET.fromstring(z.read("ppt/slides/slide2.xml"))
    assert len(list(slide.iter(A + "tr"))) == 3 and len(list(slide.iter(A + "tc"))) == 9
    assert texts(z, 2)[-1] == "1,234 of 56,789 rows"
    assert "-0.50" in texts(z, 2)


def test_no_charts_and_odd_text_stay_valid():
    d = Dataset("x", "a<&>.csv", "s\x00", "csv", 0, [])
    z = zipfile.ZipFile(io.BytesIO(export.pptx(d, [])))
    check_package(z)
    assert texts(z, 1)[1] == "0 rows, 0 columns"
