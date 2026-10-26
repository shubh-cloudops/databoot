import zipfile
from datetime import datetime

import pytest

from app import xlsx
from app.readers import ReadError
from tests.conftest import write_xlsx


def test_book(data_dir):
    path = data_dir / "sub" / "book.xlsx"
    assert xlsx.sheet_names(path) == ["Revenue", "Lookup"]
    cols, rows = xlsx.read_sheet(path, "Revenue")
    assert cols == ["month", "team", "revenue"]
    assert rows[0] == [datetime(2024, 1, 1), "A", 100]
    assert rows[1][0] == datetime(2024, 2, 1)
    assert all(isinstance(r[0], datetime) for r in rows) and len(rows) == 6
    assert xlsx.read_sheet(path, "Lookup") == (["code", "label"], [[i, f"item {i}"] for i in range(3)])


def test_broken(data_dir):
    bad = data_dir / "broken.xlsx"
    for call in (lambda: xlsx.sheet_names(bad), lambda: xlsx.read_sheet(bad, "x"), lambda: xlsx.sheet_names(data_dir / "nope.xlsx")):
        with pytest.raises(ReadError, match="not a valid xlsx"):
            call()


def test_unknown_sheet_and_empty_sheet(tmp_path):
    p = tmp_path / "a.xlsx"
    write_xlsx(p, {"E": []})
    with pytest.raises(ReadError, match="not a valid xlsx"):
        xlsx.read_sheet(p, "missing")
    with pytest.raises(ReadError, match="no header row"):
        xlsx.read_sheet(p, "E")


def _rewrite(src, dst, parts):
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
        for n in zi.namelist():
            zo.writestr(n, parts.get(n, zi.read(n)))
        for n in parts.keys() - set(zi.namelist()):
            zo.writestr(n, parts[n])


def test_shared_booleans_formats_and_gaps(tmp_path):
    src, dst = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    write_xlsx(src, {"S": [("x",)]})
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    styles = (f'<styleSheet {ns}><numFmts count="2"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/>'
              '<numFmt numFmtId="165" formatCode="0.00&quot;d&quot;"/></numFmts>'
              '<cellXfs count="4"><xf numFmtId="0"/><xf numFmtId="164"/><xf numFmtId="165"/><xf numFmtId="22"/></cellXfs></styleSheet>')
    sheet = (f'<worksheet {ns}><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>name</t></is></c><c r="C1" t="inlineStr"><is><t>when</t></is></c></row>'
             '<row r="2"><c r="A2" t="inlineStr"><is><r><t>rich </t></r><r><t>text</t></r></is></c><c r="B2" t="b"><v>1</v></c><c r="C2" s="1"><v>45292.5</v></c></row>'
             '<row r="3"><c r="A3"><v>2.5</v></c><c r="B3" t="b"><v>0</v></c><c r="C3" s="2"><v>45292</v></c></row>'
             '<row r="4"/><row r="5"><c r="C5" s="3"><v>45292</v></c></row></sheetData></worksheet>')
    _rewrite(src, dst, {"xl/styles.xml": styles, "xl/worksheets/sheet1.xml": sheet})
    cols, rows = xlsx.read_sheet(dst, "S")
    assert cols == ["name", "column_2", "when"]
    assert rows == [["rich text", "TRUE", datetime(2024, 1, 1, 12)],
                    [2.5, "FALSE", 45292],  # "0.00"d"" has a quoted d: not a date
                    [None, None, datetime(2024, 1, 1)]]


def test_corrupt_xml(tmp_path):
    src, dst = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    write_xlsx(src, {"S": [("x",), (1,)]})
    _rewrite(src, dst, {"xl/worksheets/sheet1.xml": "<worksheet><sheetData><row"})
    with pytest.raises(ReadError, match="not a valid xlsx"):
        xlsx.read_sheet(dst, "S")
