"""Shared fixtures: a temp data folder with one file per supported type, plus edge cases.

Tests never touch a real drive or /live: point the app at `data_dir` through the env vars in app/config.py.
"""
import csv
import json
import zipfile
from datetime import date, timedelta

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
def big_sales_csv(tmp_path):
    """Folder with sales.csv of 200,000 rows (the DATABOOT_MAX_ROWS default) for the 1 s filter target (AC-41).

    Columns date, region, product, amount, qty: temporal, categorical (4 and 20 values), numerical. region "North" is
    every 4th row (50,000 rows).
    """
    root = tmp_path / "bigsales"
    root.mkdir()
    with open(root / "sales.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("date", "region", "product", "amount", "qty"))
        w.writerows((f"2024-{i % 12 + 1:02d}-{i % 28 + 1:02d}", ("North", "South", "East", "West")[i % 4],
                     f"p{i % 20}", i % 997, i % 9 + 1) for i in range(200_000))
    return root


SHOP_STORES = ("North", "South", "East")
SHOP_CHANNELS = ("web", "shop")


def shop_rows():
    """shop.csv rows: date, store, channel, product, units, revenue (Business, rule R2; ARCHITECTURE.md "Round 5").

    Days 5 and 20 of Jan..Jun 2024 plus 2024-07-10, one row per store x channel: 78 rows, 187 days (month grain).
    The last date is not a month end, so the latest full period is June and the previous one May. units comes
    first but revenue is the primary amount (name rule, gate 179). Drill order: channel (2), store (3), product (12).
    """
    days = [f"2024-{m:02d}-{d:02d}" for m in range(1, 7) for d in (5, 20)] + ["2024-07-10"]
    rows, i = [], 0
    for day in days:
        for s, store in enumerate(SHOP_STORES):
            for c, channel in enumerate(SHOP_CHANNELS):
                rows.append((day, store, channel, f"p{i // 6 % 12}", int(day[5:7]), 100 * int(day[5:7]) + 10 * s + c + i % 12))
                i += 1
    return rows


@pytest.fixture
def archetypes_dir(tmp_path):
    """One file per archetype case of AC-43: shop.csv -> business/R2, places.csv -> map/R1 (lat, lon, country and
    1 numerical), measures.csv -> explorer/R3 (numerical only), sparse.csv -> not map (lat/lon + 3 numerical,
    coordinates in 4 of 10 rows). big_csv (60,000 points) is the hexbin case (AC-52)."""
    root = tmp_path / "arch"
    root.mkdir()
    with open(root / "shop.csv", "w", newline="") as f:
        csv.writer(f).writerows([("date", "store", "channel", "product", "units", "revenue"), *shop_rows()])
    countries = ("France", "Japan", "Brazil", "Kenya")
    with open(root / "places.csv", "w", newline="") as f:
        csv.writer(f).writerows([("lat", "lon", "country", "pop"),
                                 *[(-40 + 4 * i, -120 + 12 * i, countries[i % 4], 1000 * (i + 1)) for i in range(20)]])
    (root / "measures.csv").write_text("a,b,c\n" + "".join(f"{i},{(i * 7) % 11},{2 * i + 1}\n" for i in range(12)))
    (root / "sparse.csv").write_text("lat,lon,a,b,c\n" + "".join(
        (f"{10 + i},{20 + i}" if i < 4 else ",") + f",{i},{i * 2},{i % 3}\n" for i in range(10)))
    return root


def monitor_rows(spike=True):
    """monitor.csv rows: time, temperature, humidity (Monitoring, rule R4; ARCHITECTURE.md "Round 6").

    One reading a day from 2024-01-01 for 120 days; temperature 20 + i % 7, humidity 50 + i % 5. With spike, day 100
    (2024-04-10) reads 60.0: the only point with |z| > 3 against the 30 readings before it.
    """
    return [((date(2024, 1, 1) + timedelta(days=i)).isoformat(), 60.0 if spike and i == 100 else 20.0 + i % 7,
             50 + i % 5) for i in range(120)]


SURVEY_LEVELS = {"q_service": ("Very dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very satisfied"),
                 "q_easy": ("Strongly disagree", "Disagree", "Neither agree nor disagree", "Agree", "Strongly agree"),
                 "q_visits": ("Never", "Rarely", "Sometimes", "Often", "Always")}
SURVEY_CITIES = tuple(f"city{k:02d}" for k in range(12))


def survey_rows():
    """survey.csv rows (Survey, rule R5): submitted (date), respondent_id, age, gender, region, city, q_service,
    q_easy, q_visits (word Likert scales), q_score (1..5, Likert, counts as C for R5 only). 40 respondents.

    C = gender, region, city + 3 word scales (6; q_score makes 7 for R5) of 10 columns; N = respondent_id, age.
    The date makes R2 true too, so it also proves R5 is walked before R2 (gate 183). city has 12 values: top 10 + Other.
    """
    return [(f"2024-03-{i % 28 + 1:02d}", 1001 + i, 18 + (i * 7) % 50, ("female", "male", "other")[i % 3],
             ("North", "South", "East", "West")[i % 4], SURVEY_CITIES[i % 12],
             SURVEY_LEVELS["q_service"][(i * 3) % 5 if i % 4 else 3], SURVEY_LEVELS["q_easy"][i % 5],
             SURVEY_LEVELS["q_visits"][min(4, i // 9)], (1, 2, 3, 4, 5, 4, 4, 5)[i % 8]) for i in range(40)]


@pytest.fixture
def round6_dir(tmp_path):
    """Round 6 archetypes: monitor.csv -> monitoring/R4 (one planted spike), quiet.csv -> monitoring/R4 (no spike),
    survey.csv -> survey/R5, orders.csv -> explorer/R3 with an identifier (order_id) and a year column (AC-59)."""
    root = tmp_path / "r6"
    root.mkdir()
    head = ("time", "temperature", "humidity")
    with open(root / "monitor.csv", "w", newline="") as f:
        csv.writer(f).writerows([head, *monitor_rows()])
    with open(root / "quiet.csv", "w", newline="") as f:
        csv.writer(f).writerows([head, *monitor_rows(spike=False)])
    with open(root / "survey.csv", "w", newline="") as f:
        csv.writer(f).writerows([("submitted", "respondent_id", "age", "gender", "region", "city", *SURVEY_LEVELS,
                                  "q_score"), *survey_rows()])
    with open(root / "orders.csv", "w", newline="") as f:
        csv.writer(f).writerows([("order_id", "year", "region", "amount"),
                                 *[(10045 + i, 2023 + i % 2, ("North", "South")[i % 2], 12345 + 100 * i) for i in range(12)]])
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
        from app import main
        main._base.cache_clear()
        for cache in ("_view", "_detected", "_appview", "_plain"):  # round 5 adds the last two (ARCHITECTURE.md "Round 5")
            if hasattr(main, cache):
                getattr(main, cache).cache_clear()
        app = main.app
        return TestClient(app)
    return make
