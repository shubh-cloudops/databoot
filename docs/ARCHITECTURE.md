# Architecture: DataBoot (round 1)

DataBoot scans one mounted folder or drive letter, profiles every dataset with fixed rules and draws the
charts those rules pick, fully offline. Sources: docs/PRD.md, docs/acceptance.json, Board gate 160
(graphify-out/memory.md L4-17). **Gate 160 is later than the PRD and wins where they differ**: name DataBoot,
Plotly 3D scatter instead of Deck.gl, more file types, five extra chart kinds, PPTX + XLSX exports, Windows
venv launcher (Docker optional). The PRD text was not rewritten after the gate; the overrides are written next
to each AC row below and as work items G-1..G-7, which have no AC ids yet.

No docs/TRENDS.md this round (gate 160: `team: -trends`), so no trend advice is used.

## Stack and constraints
- FastAPI + Jinja server-rendered pages (gate 160 "scaffold is fine"); one vanilla JS module
  `app/static/js/dashboard.js` draws charts with Plotly. No framework, no build step.
- Python 3.11 standard library only, plus the installed fastapi/jinja2/uvicorn/httpx. **No pandas, openpyxl,
  pyarrow or python-pptx** (not installed, checked with `python3 -c "import pandas"` etc.). That means xlsx,
  parquet, pptx are read/written by our own small OOXML/Parquet code (zipfile, xml.etree, struct, gzip).
- Vendored, MIT licensed, already in the repo:
  - `app/static/vendor/plotly/plotly.min.js` (plotly.js-dist-min 4.1.2) + LICENSE
  - `app/static/vendor/topojson/world_110m.json`, `world_50m.json` (sane-topojson 4.0.0) + LICENSE
- Plotly fetches outlines from `https://cdn.plot.ly/un/` by default. Every `Plotly.newPlot` call **must** pass
  config `{topojsonURL: "/static/vendor/topojson/", displaylogo: false}`. A probe (choropleth with
  `locationmode: "country names"` + scatter3d, every non-127.0.0.1 request aborted) drew 3 country paths and a
  WebGL canvas, with 0 external requests and 0 console errors.
- plotly.min.js holds URL strings (maplibre, carto) for trace types we never use. AC-9 tests check page HTML
  and real browser requests, not the text of vendored files.

## Modules
| File | Owns | Status |
|---|---|---|
| `app/config.py` | `get() -> Settings` from env: `DATABOOT_DATA`, `DATABOOT_OUT`, `DATABOOT_MAX_ROWS` (200,000), `DATABOOT_MAP_CAP` (50,000), `DATABOOT_CHART_CAP` (5,000). Read on every call. | done |
| `app/catalog.py` | `scan(folder) -> Catalog` (datasets, unreadable, others), stable ids, `load(dataset, max_rows)`. Dataclasses in place. | stubs |
| `app/readers.py` | csv, tsv, json, jsonl, geojson readers | empty |
| `app/xlsx.py` | read .xlsx sheets; write .xlsx with native charts (used by export and by the PPTX embedded workbook) | empty |
| `app/parquet.py` | flat-schema Parquet reader | empty |
| `app/profile.py` | `classify(columns, rows) -> {column: type}` | empty |
| `app/rules.py` | `charts(columns, rows, mapping, settings) -> [chart]`, downsampling | empty |
| `app/export.py` | `pptx(dataset, charts) -> bytes`, `xlsx(dataset, rows, charts) -> bytes` | empty |
| `app/launch.py` | one-click launcher | empty |
| `app/main.py` | routes; `/static` mount added | partial |
| `app/templates/home.html`, `dataset.html` | pages (Designer/front end style them) | home placeholder |
| `app/static/js/dashboard.js` | fetch chart JSON, draw with Plotly | empty |
| `DataBoot.bat`, `Start-DataBoot.ps1`, `Dockerfile` | Windows launcher, optional container | to build |

## Routes (sitemap: two pages, no nav beyond a "DataBoot" home link)
| Method, path | Returns |
|---|---|
| GET `/` | Home: datasets table, "could not be read" table, file inventory table |
| GET `/datasets/{id}` | Dashboard page; 404 for unknown id |
| GET `/api/datasets` | `[{"id","path","sheet","kind","rows","columns"}]` (columns = count) |
| GET `/api/datasets/{id}/profile` | `{column: type}` (AC-2), also writes `<out>/profiles/{id}.json` |
| GET `/api/datasets/{id}/charts` | chart contract below; fetched once by dashboard.js on load (no polling) |
| GET `/datasets/{id}/export.pptx` | PPTX download (G-5) |
| GET `/datasets/{id}/export.xlsx` | XLSX download (G-5) |
| GET `/health` | `{"ok": true}` (unchanged) |
| `/static/...` | StaticFiles mount (done) |

Flag for tests and AC text: these two pages are the whole sitemap. Adding a page means updating this table.

## Data access
- `scan(folder)`: `os.walk` (no symlink follow), skip names starting with `.`; sorted by relative path.
  Missing folder: empty catalog, home shows the folder path and empty tables.
- Kind by lower-case extension: `.csv` csv, `.tsv`/`.tab` tsv, `.xlsx`/`.xlsm` xlsx (one dataset per sheet),
  `.json` json, `.jsonl`/`.ndjson` jsonl, `.parquet` parquet, `.geojson` geojson. Anything else goes to
  `others` (file inventory: type = extension, size in bytes, modified date YYYY-MM-DD). Old `.xls` is in the
  inventory, not "could not read" (see open questions).
- A recognised file that fails becomes `Unreadable(path, reason)`; reasons are fixed short notes:
  `empty file`, `no header row`, `not a valid xlsx`, `not a list of records`, `unsupported parquet encoding`,
  `could not decode text`. Any reader exception is caught per file in `scan`, so one bad file never breaks the
  home page (AC-12).
- Dataset id: `hashlib.sha1(f"{path}|{sheet or ''}".encode()).hexdigest()[:12]`, stable across restarts.
- Home needs row and column counts, so `scan` streams each file once for counts and header only. Rows are read
  on demand by `load(dataset, settings.max_rows)`; wrap the loader with `functools.lru_cache(maxsize=4)`.
  `scan` is cached too (`lru_cache(maxsize=1)` keyed by folder); the `make_client` fixture must clear both.
  `# ponytail: rescan only on restart; add a rescan button with C2.`
- Readers return cells as Python values: `None` for empty, `str`, `int`, `float`, `datetime`/`date`.
  - csv/tsv: `csv` module, encoding `utf-8-sig`, fallback `cp1252`; all cells are `str`; empty string -> `None`.
  - xlsx: `zipfile` + `xml.etree`; shared strings, inline strings, numbers, booleans (as str `TRUE`/`FALSE`);
    a numeric cell whose style uses numFmtId 14-22 or a custom format with `d`, `m`+`y` or `yy` is a date
    (serial from 1899-12-30). First non-empty row is the header. Stream sheet XML with `iterparse`.
  - json: top-level list of objects (or `{"data": [...]}`/`{"records": [...]}`); columns = keys in first-seen
    order across rows; nested values become their `json.dumps` string.
  - jsonl: one object per line, blank lines skipped, same column rule.
  - geojson: one row per feature; columns = property keys, then `longitude`, `latitude`. Point uses its
    coordinates; other geometries use the mean of their first ring/line coordinates; null geometry -> `None`.
  - parquet: footer via thrift compact protocol, flat (non-nested) columns, PLAIN, PLAIN_DICTIONARY /
    RLE_DICTIONARY, definition levels for optional columns; codecs UNCOMPRESSED, GZIP and SNAPPY (small
    pure-Python snappy decompressor). ZSTD/LZ4/BROTLI or nested schemas -> `unsupported parquet encoding`.
    INT96 and TIMESTAMP/DATE logical types -> `datetime`/`date`.
- Header cleanup: strip; empty header -> `column_N` (1-based); duplicates get `_2`, `_3`.
- Output folder `<out>` (default `./output`, git-ignored). The data folder is never written to.

## Classification (AC-3, thresholds confirmed by gate 160)
Per column, over non-empty values of the loaded rows, first match wins:
1. **geospatial**: header lower-cased and stripped is `lat`, `lon`, `lng`, `latitude` or `longitude`.
2. **temporal**: every value is `date`/`datetime`; or ≥ 90% of values are `str` that parse with
   `datetime.fromisoformat` or one of `%d/%m/%Y`, `%m/%d/%Y`, `%Y/%m/%d`, `%d-%m-%Y`, `%d.%m.%Y`.
   A bare year like `2020` does not parse (stays numerical).
3. **numerical**: every value is `int`/`float` (not `bool`), or a `str` matching
   `^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$`.
4. **categorical**: text with distinct count ≤ 50 and ≤ 50% of loaded rows.
5. **other**: everything else, including all-empty columns.

## Routing rules (charts)
Built by `rules.charts`, in this order, then cut to the first 8 (`MAX_CHARTS`):
| kind | When | Data |
|---|---|---|
| `map3d` | a lat and a lon geospatial column (lat = `lat`/`latitude`; lon = `lon`/`lng`/`longitude`) | x lon, y lat, z first numerical (else 0); stride-sampled to `map_cap` |
| `country_map` | a text column whose header is `country`, `country_name`, `nation`, `iso3` or `iso_a3` | sum of first numerical per country, count if none; `locationmode` `ISO-3` when every value is 3 upper-case letters, else `country names` |
| `line` | temporal + numerical; first 2 numerical columns | sum per distinct timestamp of the first temporal column, sorted, stride-sampled to `chart_cap` |
| `bar` | categorical; first 2 numerical columns, or 1 count chart when there is no numerical column | sum (or count) per value of the first categorical column, sorted by value desc |
| `donut` | first categorical column with 2 to 6 distinct values | row count per value |
| `histogram` | first numerical column | 20 equal-width bins over min..max (max in last bin; 1 bin when min = max) |
| `scatter` | 2+ numerical columns | first two numerical, rows with both values, stride-sampled to `chart_cap` |
| `heatmap` | 3+ numerical columns | Pearson correlation of the first 12 numerical, pairwise complete rows; `null` when undefined |

No rule matches -> `[]`: the page shows types and table only (AC-7).
Stride sampling: `step = ceil(n / cap)`, keep `points[::step]`, so shown ≤ cap.
`# ponytail: stride can miss peaks; use LTTB if owners ask.`

## Chart contract (`GET /api/datasets/{id}/charts`)
```json
{"dataset": "3f2a9c01b7de",
 "charts": [
  {"id": "chart-1", "kind": "line", "title": "amount by date",
   "x_label": "date", "y_label": "amount (sum)",
   "rule": "temporal date + numerical amount: line, sum per date",
   "shown": 6, "total": 6,
   "data": {"x": ["2024-01-01", "..."], "y": [10, "..."]}}]}
```
`data` per kind: line/scatter `{"x": [], "y": []}`; bar `{"x": [categories], "y": [values]}`;
donut `{"labels": [], "values": []}`; histogram `{"edges": [21 floats], "counts": [20 ints]}`;
heatmap `{"labels": [], "z": [[r or null]]}`; map3d `{"lon": [], "lat": [], "z": []}`;
country_map `{"locations": [], "values": [], "locationmode": "ISO-3" | "country names"}`.
Dates are ISO strings; `NaN`/`inf` become `null`. `shown`/`total` count points (map, line, scatter) or rows
used (bar, donut, histogram, country_map, heatmap). The same dicts feed the page and the exports.

## Pages
- **Home** `/`: h1 `DataBoot`, the folder path, then three tables: datasets (file path, sheet, rows, columns,
  link to `/datasets/{id}`), "Could not be read" (file, reason), "Other files" (file, type, size, modified).
  Empty tables are hidden.
- **Dashboard** `/datasets/{id}`: h1 file name (+ sheet); column types table (column, type); one
  `<figure class="chart" id="chart-N" data-kind="...">` per chart, rendered by the server with
  `<figcaption>` holding the title, the rule caption and `N of M points` (`N of M rows` for aggregates);
  table of the first 20 rows; links to the two exports. dashboard.js fills each figure with Plotly from the
  JSON. Server-rendered figures make AC-4..AC-8 and AC-10 checkable with TestClient alone.
- **Text rule (gate 160)**: only titles, axis labels, column names/types, `N of M` counts and the one-line rule
  caption. No generated sentences. Fixed table headings and notes like `could not be read` are labels.
- Style: plain, neutral, system sans font, no logo (gate 160); the Designer owns the rest.

## Exports (G-5): native editable charts, standard library only
- `xlsx`: sheet `Data` (header + loaded rows), then one sheet per chart with its data table at A1 and a
  drawing with a native chart (`c:lineChart`, `c:barChart`, `c:doughnutChart`, `c:scatterChart`; histogram as
  a column `c:barChart` of bin counts) that references that range. Heatmap: the matrix with a 3-colour
  `colorScale` conditional format. map3d -> `c:scatterChart` of lon/lat. country_map -> bar chart per country.
- `pptx`: slide 1 title (file name, `N rows, M columns`); one slide per chart with title, native chart part
  (`ppt/charts/chartN.xml` + embedded workbook from the same xlsx writer, so "Edit Data" works in PowerPoint),
  and a text box with the rule caption and `N of M`. Heatmap slide uses a native `a:tbl`.
- Office map charts need Bing (online), so no Office map chart; that is why maps become scatter/bar.
- Filenames: `<file stem>[-<sheet>].pptx|xlsx`, `Content-Disposition: attachment`.

## Launcher (AC-11, AC-13, gate 160: Windows 11, .bat + PowerShell + venv, Docker optional)
- `python -m app.launch <folder> [--port 8765] [--no-browser]`: checks the folder exists (else one stderr line,
  exit 2, no argparse usage text), sets `DATABOOT_DATA`, uses the first free port from 8765 up (20 tries), runs
  `uvicorn.Server` on 127.0.0.1 and, once `server.started`, calls `open_browser(url)` (default
  `webbrowser.open`). Expose `run(folder, port, open_browser)` and the running server as `launch.SERVER` so a
  test can fetch the URL from a fake `open_browser` and then set `SERVER.should_exit = True`.
- `DataBoot.bat`: `powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-DataBoot.ps1" %*`.
- `Start-DataBoot.ps1 [-Folder <path or E:\>] [-Docker]`: no folder -> FolderBrowserDialog. Default path:
  create `.venv` with `py -3.11` (fallback `python`) if missing, `pip install -r requirements.txt`
  (`--no-index --find-links wheels` when a `wheels\` folder exists, for offline client machines), then
  `.venv\Scripts\python.exe -m app.launch $Folder`. `-Docker`: `docker info` must succeed (else a message and
  exit 1), `docker build -t databoot .` if the image is missing, `docker run --rm -d -p 8765:8765 -v
  "${Folder}:/data:ro" databoot`, then `Start-Process http://localhost:8765/`.
- `Dockerfile`: `python:3.11-slim`, install requirements, copy `app/`, `ENV DATABOOT_DATA=/data`,
  `CMD uvicorn app.main:app --host 0.0.0.0 --port 8765`.

## How each acceptance item is met
| AC | Gate 160 override | How | Test |
|---|---|---|---|
| AC-1 | also TSV, JSON/JSONL, Parquet, GeoJSON (G-1) | `catalog.scan` walks subfolders; home datasets table | `data_dir`: 8 datasets with paths, `Revenue`/`Lookup` sheets, row and column counts |
| AC-2 | – | profile route returns `classify()` and writes `<out>/profiles/{id}.json` | JSON equals file content; keys = every column |
| AC-3 | thresholds OK | `profile.classify` rules above | unit tests on lists; fixture: `Latitude`/`LON` geo, `date` temporal, `region` categorical, `comment` other |
| AC-4 | – | `line` rule; `figure[data-kind=line]` | sales.csv and book.xlsx Revenue |
| AC-5 | count when no numeric | `bar` rule | sales.csv sums: North 16, South 23, East 7 |
| AC-6 | Plotly scatter3d, not Deck.gl | `map3d` rule, drawn as `scatter3d` | points.tsv and cities.geojson have one; sales.csv has none |
| AC-7 | – | `charts == []`, page still 200 | notes.csv: types + table, no `figure.chart` |
| AC-8 | – | dashboard template | every fixture dataset: types table and ≤ 20 table rows |
| AC-9 | Plotly + topojson vendored | no CDN links; `topojsonURL` config | parse `src`/`href` on `/` and each dashboard: all relative and 200; Playwright run with non-local requests aborted records none |
| AC-10 | – | stride sampling to `map_cap` | `big_csv`: map `shown` ≤ 50,000, `total` 60,000, page text `50000 of 60000` (format numbers without separators or say which) |
| AC-11 | Windows venv launcher calls `app.launch` | `app/launch.py` | fake `open_browser` gets `http://127.0.0.1:<port>/`, home returns 200 |
| AC-12 | – | per-file try/except in `scan` | empty.csv `empty file`, broken.xlsx `not a valid xlsx`; others still list and open |
| AC-13 | script is `Start-DataBoot.ps1` (gate name DataBoot), Docker path behind `-Docker`, plus `DataBoot.bat` | files above | text checks: `docker info`, `:/data:ro`, `docker run`, `Start-Process`, venv lines; Dockerfile `FROM python:3.11` |

## Work items without AC ids (gate 160): explicit checks
- **G-1 file types**: TSV, JSON, JSONL, GeoJSON fixtures list on home with correct counts (points.tsv 4x3,
  records.json 3x2, events.jsonl 10x2, cities.geojson 4x3). Parquet: a feature ticket adds small fixture files
  (uncompressed, gzip, snappy, one dictionary-encoded, one optional column) under `tests/fixtures/` and checks
  values equal the CSV twin.
- **G-2 file inventory**: manual.pdf is in "Other files" with type `pdf`, size 9, today's date; it has no
  dashboard link; `.hidden.csv` is not listed anywhere.
- **G-3 extra charts**: one unit test per kind on inline rows: donut (events.jsonl `kind`), histogram (bin
  edges and counts by hand), scatter and heatmap (3 numerical columns, r = 1 for a column with itself),
  country_map (records.json, `locationmode` `country names`; ISO-3 case on `FRA`/`JPN`). Order and the 8 cap.
- **G-4 caption and text**: each figure has one rule caption and one `N of M`; page `<main>` has no `<p>`
  outside figcaptions and the folder path.
- **G-5 exports**: both routes 200 with the right content type; the zip opens; every XML part parses with
  `xml.etree`; `[Content_Types].xml` lists every part; xlsx has one chart part per chart; pptx has one
  `ppt/charts/chartN.xml` per chart slide with the expected `c:*Chart` element and an embedded workbook.
- **G-6 name**: page titles and h1 say DataBoot.
- **G-7 Parquet errors**: a zstd-coded file is listed as `unsupported parquet encoding`.

## Test fixtures (tests/conftest.py, done)
`data_dir` builds: `sales.csv`, `points.tsv`, `notes.csv`, `empty.csv`, `broken.xlsx`, `manual.pdf`,
`.hidden.csv`, `sub/records.json`, `sub/events.jsonl`, `sub/cities.geojson`, `sub/book.xlsx` (sheets
`Revenue` with Excel date cells, `Lookup`). `write_xlsx` was checked by loading its output with openpyxl in
/tmp (dates come back as datetimes). `big_csv` holds 60,000 lat/lng rows. `make_client(folder)` sets the env
and returns a TestClient. Use function scope for Playwright fixtures, never session scope.
`tests/test_static.py` checks the vendored files are served.

## Decisions
1. Standard-library readers and OOXML writers: the ticket allows only installed libraries and none of pandas,
   openpyxl, pyarrow, python-pptx are installed.
2. Rows loaded on demand with an LRU of 4 and a 200,000 row cap, not all at scan: keeps a big drive inside
   16 GB; home needs only counts.
3. Charts computed server-side once and shared by page, JSON and exports, so all three show the same numbers.
4. Server-rendered figures and captions, JS only draws: tests run without a browser for most ACs.
5. Country map by header name, like the geospatial rule: a fixed rule, no guessing from values.
6. Line charts sum per timestamp: raw transaction rows would draw a zig-zag; same "sum" rule as bars.
7. At most 2 line and 2 bar charts so the extra kinds still fit in the 8-chart cap.
8. `-Docker` switch keeps AC-13's Docker steps while the default follows gate 160's venv launcher.
9. Vendored Plotly 4.1.2 and sane-topojson 4.0.0 (latest on npm, 2026-10-25) now, so AC-9 tests have real
   assets; `world_50m.json` kept for `resolution: 50`.
