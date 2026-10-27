"""Shared fixtures: a temp data folder with one file per supported type, plus edge cases.

Tests never touch a real drive or /live: point the app at `data_dir` through the env vars in app/config.py.
"""
import csv
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

SALES = [  # date, region, amount: temporal + categorical + numerical -> line, bar, donut, histogram
    ("2024-01-01", "North", 10), ("2024-01-02", "South", 20), ("2024-01-03", "North", 5),
    ("2024-01-04", "East", 7), ("2024-01-05", "South", 3), ("2024-01-06", "North", 1),
]
POINTS = [(51.5, -0.12, 3.0), (48.85, 2.35, 4.5), (40.71, -74.0, 8.0), (35.68, 139.69, 9.5)]


def _xlsx_cell(ref, value):
    if isinstance(value, str):
        return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
    return f'<c r="{ref}"><v>{value}</v></c>'


def write_xlsx(path, sheets):
    """Minimal valid .xlsx (inline strings, no shared strings) from {sheet name: [rows]}.

    A cell given as ("date", serial) is written with built-in date format 14, as Excel stores dates.
    A sheet given as bytes is written as its raw sheet XML, e.g. b"<<not xml" for a corrupt sheet (AC-31).
    """
    names = list(sheets)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                             for i in range(1, len(names) + 1))
                   + "</Types>")
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1))
                   + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                             for i in range(1, len(names) + 1))
                   + f'<Relationship Id="rId{len(names) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                   + "</Relationships>")
        z.writestr("xl/styles.xml",
                   '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
                   '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
                   '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
                   '<cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14" applyNumberFormat="1"/></cellXfs></styleSheet>')
        for i, rows in enumerate(sheets.values(), 1):
            if isinstance(rows, bytes):
                z.writestr(f"xl/worksheets/sheet{i}.xml", rows)
                continue
            out = []
            for r, row in enumerate(rows, 1):
                cells = []
                for c, value in enumerate(row):
                    ref = f"{chr(65 + c)}{r}"
                    if isinstance(value, tuple):
                        cells.append(f'<c r="{ref}" s="1"><v>{value[1]}</v></c>')
                    else:
                        cells.append(_xlsx_cell(ref, value))
                out.append(f'<row r="{r}">{"".join(cells)}</row>')
            z.writestr(f"xl/worksheets/sheet{i}.xml",
                       '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                       f'<sheetData>{"".join(out)}</sheetData></worksheet>')


@pytest.fixture
def data_dir(tmp_path):
    """Folder the app scans. Expected datasets are listed in docs/ARCHITECTURE.md "Test fixtures"."""
    root = tmp_path / "data"
    (root / "sub").mkdir(parents=True)
    with open(root / "sales.csv", "w", newline="") as f:
        csv.writer(f).writerows([("date", "region", "amount"), *SALES])
    with open(root / "points.tsv", "w", newline="") as f:
        csv.writer(f, delimiter="\t").writerows([("Latitude", "LON", "value"), *POINTS])
    (root / "notes.csv").write_text("comment\n" + "".join(f"free text number {i}\n" for i in range(30)))
    (root / "empty.csv").write_bytes(b"")
    (root / "broken.xlsx").write_bytes(b"not a zip file")
    (root / "manual.pdf").write_bytes(b"%PDF-1.4\n")
    (root / ".hidden.csv").write_text("a\n1\n")
    (root / "sub" / "records.json").write_text(json.dumps([{"country": c, "pop": p} for c, p in
                                                           [("France", 68), ("Japan", 125), ("Brazil", 203)]]))
    (root / "sub" / "events.jsonl").write_text("".join(json.dumps({"n": i, "kind": "ab"[i % 2]}) + "\n" for i in range(10)))
    (root / "sub" / "cities.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {"size": v}}
        for lat, lon, v in POINTS]}))
    # Excel serial 45292 = 2024-01-01.
    write_xlsx(root / "sub" / "book.xlsx", {
        "Revenue": [("month", "team", "revenue"), *[(("date", 45292 + 31 * i), "AB"[i % 2], 100 + i) for i in range(6)]],
        "Lookup": [("code", "label"), *[(i, f"item {i}") for i in range(3)]],
    })
    return root


@pytest.fixture
def big_csv(tmp_path):
    """Folder with one CSV of 60,000 points: more than the default map cap of 50,000 (AC-10)."""
    root = tmp_path / "big"
    root.mkdir()
    with open(root / "big.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("lat", "lng", "value"))
        w.writerows((i % 180 - 90 + 0.5, i % 360 - 180 + 0.5, i % 97) for i in range(60_000))
    return root


@pytest.fixture
def make_client(monkeypatch, tmp_path):
    """make_client(folder) -> TestClient for the app scanning `folder`, writing outputs to tmp_path/'out'.

    Feature tickets that add caches (functools.lru_cache) must clear them here so each test scans afresh.
    """
    def make(folder):
        monkeypatch.setenv("DATABOOT_DATA", str(folder))
        monkeypatch.setenv("DATABOOT_OUT", str(tmp_path / "out"))
        from app import catalog
        catalog.scan.cache_clear()
        catalog.load.cache_clear()
        from app.main import app
        return TestClient(app)
    return make
