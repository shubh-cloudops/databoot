# Architecture: DataBoot (round 2)

DataBoot scans one mounted folder or drive letter, profiles every dataset with fixed rules and draws the
charts those rules pick, fully offline. Sources: docs/PRD.md (round 2), docs/acceptance.json (AC-1..AC-24),
Board gates 160-165 (graphify-out/memory.md). Round 2 keeps everything round 1 built. It moves the Office
exports and the xlsx reader to real libraries, moves Parquet to pyarrow only, makes three accessibility fixes
and gives G-1..G-7 their AC ids (AC-14..AC-20, plus AC-21 for thousands separators).

No docs/TRENDS.md this round (gate 160: `team: -trends`), so I used no trend advice.

## Round 2 changes at a glance
| # | Change | Files | AC |
|---|---|---|---|
| R1 | XLSX export on **xlsxwriter** | `app/xlsx.py` (writer half replaced) | AC-18, AC-23 |
| R2 | PPTX export on **python-pptx** | `app/export.py` (rewritten) | AC-18 |
| R3 | xlsx reading on **openpyxl** `read_only=True` | `app/xlsx.py` (reader half replaced) | AC-1, AC-12 |
| R4 | Parquet on **pyarrow only**, no stdlib fallback (gate 162) | `app/parquet.py` | AC-14, AC-20 |
| R5 | Table titles are `<caption><h2>…</h2></caption>`; headers keep their case | `home.html`, `dataset.html`, `databoot.css` | AC-22 |
| R6 | Plotly modebar always shown, buttons in Tab order | `dashboard.js`, `databoot.css` | AC-24 |
| R7 | Fixed notes `invalid JSON`, `not a valid parquet file`; `Unreadable.sheet` | `readers.py`, `parquet.py`, `catalog.py` | AC-12, AC-20 |
| R8 | Gate 162 chart items: country map sorted by value, map3d z title | `rules.py`, `dashboard.js` | AC-16 (W-3) |
| R9 | QA renames `test_G_1..7`, `test_G_thousands` to `test_AC_14..21` | `tests/test_acceptance.py` | all new ids |

Done by the architect (ticket 393): `xlsxwriter==3.3.0` added to requirements.txt; `.gitattributes` holds
`* text=auto` (every file in the index was already LF, `git ls-files --eol`, so nothing else renormalises);
`tests/fixtures/flat.csv` and `optional.csv` checked out to their committed bytes (gate 165); `test_G_7` now uses
a corrupt `.parquet` (gate 165) so the suite passes with pyarrow installed.

## Stack and constraints
- FastAPI + Jinja server-rendered pages; one vanilla JS module `app/static/js/dashboard.js` draws charts with
  Plotly. No framework, no build step.
- Python 3.11 plus pinned libraries in requirements.txt: fastapi, jinja2, uvicorn, httpx, pytest, and for data
  formats **xlsxwriter==3.3.0, python-pptx==1.0.2, openpyxl==3.1.5, pyarrow==26.0.0** (gates 162/164/165). All
  four import in the agent image (`python3 -c "import xlsxwriter, pptx, openpyxl, pyarrow"` gave 3.3.0 / 1.0.2 /
  3.1.5 / 26.0.0). None is vendored: nothing under `app/` or the repo root may contain their sources (AC-23).
  python-pptx itself requires XlsxWriter (it writes the embedded chart workbooks with it), so the pins agree.
- Round 1's "standard library only" rule is gone. No pandas: our readers already give `(columns, rows)` lists.
- Vendored front-end assets (MIT, unchanged): `app/static/vendor/plotly/plotly.min.js` (4.1.2) and
  `app/static/vendor/topojson/world_110m.json`, `world_50m.json` (sane-topojson 4.0.0). These are static
  browser files, not Python libraries; AC-23 is about the four Python libraries.
- Every `Plotly.newPlot` passes config `{topojsonURL: "/static/vendor/topojson/", displaylogo: false,
  responsive: true, displayModeBar: true}` (was `"hover"`, AC-24). No request leaves the machine (AC-9).

## Modules
| File | Owns | Round 2 |
|---|---|---|
| `app/config.py` | `get() -> Settings` from env: `DATABOOT_DATA`, `DATABOOT_OUT`, `DATABOOT_MAX_ROWS` (200,000), `DATABOOT_MAP_CAP` (50,000), `DATABOOT_CHART_CAP` (5,000) | unchanged |
| `app/catalog.py` | `scan(folder) -> Catalog` (datasets, unreadable, others), stable ids, `load(dataset, max_rows)` | `Unreadable` gains `sheet: str \| None = None` |
| `app/readers.py` | csv, tsv, json, jsonl, geojson readers; `ReadError` and the fixed notes | `INVALID_JSON = "invalid JSON"` |
| `app/xlsx.py` | `sheet_names(path)`, `read_sheet(path, sheet)` on openpyxl; `write(dataset, rows, charts) -> bytes` on xlsxwriter | both halves replaced; hand-written OOXML deleted |
| `app/parquet.py` | `read(path) -> (columns, rows)` on pyarrow | stdlib reader, thrift and snappy code deleted |
| `app/profile.py` | `classify(columns, rows) -> {column: type}` | unchanged |
| `app/rules.py` | `charts(columns, rows, mapping, settings) -> [chart]`, sampling | country map order; map3d `z_label` |
| `app/export.py` | `pptx(dataset, charts) -> bytes` on python-pptx | rewritten; no import from `app.xlsx` |
| `app/launch.py`, `DataBoot.bat`, `Start-DataBoot.ps1`, `Dockerfile` | launcher | unchanged |
| `app/main.py` | routes, `num` filter, `_charts`, `_download` | unchanged |
| `app/templates/home.html`, `dataset.html` | pages | h2 inside each caption |
| `app/static/js/dashboard.js`, `app/static/css/databoot.css` | drawing, style | modebar; no uppercase `th` |

## Routes (sitemap: two pages, no nav beyond a "DataBoot" home link; unchanged)
| Method, path | Returns |
|---|---|
| GET `/` | Home: datasets table, "Could not be read" table, "Other files" table |
| GET `/datasets/{id}` | Dashboard page; 404 for unknown id |
| GET `/api/datasets` | `[{"id","path","sheet","kind","rows","columns"}]` (columns = count) |
| GET `/api/datasets/{id}/profile` | `{column: type}` (AC-2), also writes `<out>/profiles/{id}.json` |
| GET `/api/datasets/{id}/charts` | chart contract below; fetched once by dashboard.js on load (no polling) |
| GET `/datasets/{id}/export.pptx` | PPTX download |
| GET `/datasets/{id}/export.xlsx` | XLSX download |
| GET `/health` | `{"ok": true}` |
| `/static/...` | StaticFiles mount |

No page or route is added this round, so no sitemap or NAV change.

## Data access
- `scan(folder)`: `os.walk` (no symlink follow), skip names starting with `.`; sorted by relative path. Missing
  folder: empty catalog. Kind by lower-case extension: `.csv` csv, `.tsv`/`.tab` tsv, `.xlsx`/`.xlsm` xlsx (one
  dataset per sheet, each sheet loaded once at scan, gate 162), `.json` json, `.jsonl`/`.ndjson` jsonl,
  `.parquet` parquet, `.geojson` geojson. Anything else, `.xls` included, goes to `others` (type = extension,
  size in bytes, modified date YYYY-MM-DD).
- Any reader exception is caught per file (per sheet for xlsx) in `scan` and becomes
  `Unreadable(path, reason, sheet=None)`. `sheet` is the sheet name when one sheet of a workbook fails, else
  `None` (gate 162). The home table shows `path` and, when set, ` - sheet` after it. **Fixed reasons** (the
  only texts allowed in the reason cell):

  | Reason | When |
  |---|---|
  | `empty file` | size 0 (any kind) |
  | `no header row` | csv/tsv/xlsx sheet with no non-empty row |
  | `could not decode text` | csv/tsv not utf-8-sig and not cp1252 |
  | `invalid JSON` | `json.JSONDecodeError` in .json, .jsonl (any line) and .geojson |
  | `not a list of records` | valid JSON of the wrong shape (`{"a": 1}`, `[1, 2]`, geojson `[]`) |
  | `not a valid xlsx` | openpyxl cannot open the file or parse a sheet; workbook with no worksheets |
  | `not a valid parquet file` | **new**: any pyarrow error opening or reading the file (bad magic, bad footer, truncated) |
  | `unsupported parquet encoding` | pyarrow read it but a column is nested (struct, list, map: `field.type.num_fields > 0`) |
  | `could not read file` | any other exception (`catalog.FAILED`) |
- Dataset id: `hashlib.sha1(f"{path}|{sheet or ''}".encode()).hexdigest()[:12]`, stable across restarts.
- Rows read on demand by `load(dataset, settings.max_rows)` (`lru_cache(maxsize=4)`); `scan` is
  `lru_cache(maxsize=1)`; `make_client` clears both.
- Readers return cells as Python values: `None` for empty, `str`, `int`, `float`, `datetime`/`date`.
  - csv/tsv/json/jsonl/geojson: unchanged from round 1 (`csv` module, `utf-8-sig` then `cp1252`; JSON records,
    keys in first-seen order, nested values as `json.dumps`; geojson one row per feature plus `longitude`,
    `latitude`).
  - **xlsx (openpyxl)**: `wb = openpyxl.load_workbook(path, read_only=True, data_only=True)`; always
    `wb.close()` in `finally` (read-only keeps the file open). `sheet_names` = titles of `wb.worksheets` that
    have `iter_rows` (chartsheets are skipped). `read_sheet`: `ws.reset_dimensions()` first (some writers store
    a wrong `<dimension>`, which read-only mode trusts), then `ws.iter_rows(values_only=True)`. Cell mapping:
    `bool` -> `"TRUE"`/`"FALSE"` (as round 1, so booleans stay categorical), `datetime`/`date` kept, `time` ->
    `v.isoformat()`, `str` `""` -> `None`, numbers kept (openpyxl gives `int` for whole numbers). Rows with no
    non-`None` cell are dropped; the first kept row is the header; rows are padded or cut to its width.
    `path` may be a path or a `BytesIO` (tests pass `io.BytesIO`). Any exception other than `ReadError` ->
    `ReadError("not a valid xlsx")` (openpyxl raises `BadZipFile`, `InvalidFileException`, `KeyError`,
    `IndexError`, XML parse errors). Formula cells give their cached value (`data_only=True`).
    A probe in /tmp showed openpyxl gives the round 1 values for dd/mm/yyyy and numFmt 22 dates, a `0.00"d"`
    format staying a number, rich text joined, and booleans (as `True`/`False`, hence the mapping).
  - **parquet (pyarrow)**: `size == 0` -> `empty file`; `table = pyarrow.parquet.read_table(path)`, any
    exception -> `not a valid parquet file`; nested field -> `unsupported parquet encoding`; else
    `columns = _names(table.column_names)`, rows = `zip(*[c.to_pylist() for c in table.columns])` as lists.
    Every codec pyarrow supports is read (ZSTD, LZ4, BROTLI too), so `zstd.parquet` becomes a dataset (40x6).
    INT96 and TIMESTAMP give `datetime`, DATE gives `date`, as round 1.
- Header cleanup (`readers._names`): strip; empty header -> `column_N` (1-based); duplicates get `_2`, `_3`.
- Output folder `<out>` (default `./output`, git-ignored). The data folder is never written to.

## Classification (AC-3, unchanged)
Per column, over non-empty values of the loaded rows, first match wins:
1. **geospatial**: header lower-cased and stripped is `lat`, `lon`, `lng`, `latitude` or `longitude`.
2. **temporal**: every value is `date`/`datetime`; or ≥ 90% of `str` values parse with
   `datetime.fromisoformat` or `%d/%m/%Y`, `%m/%d/%Y`, `%Y/%m/%d`, `%d-%m-%Y`, `%d.%m.%Y`. A bare year stays numerical.
3. **numerical**: every value is `int`/`float` (not `bool`), or a numeric-looking `str`.
4. **categorical**: text with distinct count ≤ 50 and ≤ 50% of loaded rows (booleans included).
5. **other**: everything else, including all-empty columns.

## Routing rules (charts)
Built by `rules.charts` in this order, then cut to the first 8 (`MAX_CHARTS`):
| kind | When | Data |
|---|---|---|
| `map3d` | a lat and a lon geospatial column | x lon, y lat, z first numerical (else 0); rows with an empty lat or lon are not counted (`total`); stride-sampled to `map_cap` |
| `country_map` | a categorical/other column named `country`, `country_name`, `nation`, `iso3`, `iso_a3` | sum of first numerical per country (count if none), **sorted by value desc, then name** (gate 162, like bars); `locationmode` `ISO-3` when all values are 3 upper-case letters, else `country names` |
| `line` | temporal + numerical; first 2 numerical | sum per distinct timestamp, sorted, stride-sampled to `chart_cap` |
| `bar` | categorical; first 2 numerical, or 1 count chart | sum (or count) per value, sorted by value desc |
| `donut` | first categorical with 2 to 6 distinct values | row count per value |
| `histogram` | first numerical | 20 equal-width bins over min..max (max in the last bin); **min = max gives 1 bin** with edges `[min, max]` |
| `scatter` | 2+ numerical | first two numerical, rows with both values, stride-sampled to `chart_cap` |
| `heatmap` | 3+ numerical | Pearson r of the first 12 numerical, pairwise complete rows; `null` when undefined |

No rule matches -> `[]` (AC-7). Stride sampling: `step = ceil(n / cap)`, keep `points[::step]`, so shown ≤ cap.
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
donut `{"labels": [], "values": []}`; histogram `{"edges": [n+1 floats], "counts": [n ints]}`;
heatmap `{"labels": [], "z": [[r or null]]}`; map3d `{"lon": [], "lat": [], "z": []}`;
country_map `{"locations": [], "values": [], "locationmode": "ISO-3" | "country names"}`.
**Round 2 addition**: a map3d chart also has `"z_label"`: the z column name, or `null` when z is the constant 0.
dashboard.js uses it as the scene z axis title and the colorbar title (gate 162). It is a new key on map3d only;
no test compares whole chart dicts (QA: grep for dict equality before relying on this).
Dates are ISO strings; `NaN`/`inf` become `null`. `shown`/`total` count points (map3d, line, scatter) or rows
(the other kinds). The same dicts feed the page, the JSON and both exports.

## Pages
- **Home** `/`: h1 `DataBoot`, the folder path, then three tables. Each table:
  `<table><caption><h2>Datasets</h2></caption>…`, likewise `Could not be read`, `Other files`. Empty tables are hidden.
- **Dashboard** `/datasets/{id}`: h1 file name (+ sheet); `<caption><h2>Columns</h2></caption>` table; one
  `<figure class="chart" id="chart-N" data-kind="...">` per chart with `<figcaption>` (title, `.chart-rule`,
  `.chart-count` "N of M points|rows"); `<caption><h2>First 20 rows</h2></caption>` table (the number is
  `rows|length|num`); links to both exports.
- **h2 inside caption (AC-22, gate 165)**: the `<caption>` stays, so the table keeps its accessible name; the h2
  puts it in the heading outline. CSS resets the h2 inside a caption to the caption's current look (font size,
  margin 0); the Designer owns the exact style. Headings: h1 page title, h2 table titles; figures keep their
  figcaption title (not a heading), so the outline is h1 > h2 with no skipped level.
- **Header case (AC-22)**: delete `text-transform: uppercase` (and the letter-spacing that goes with it) from the
  `th` rule in `databoot.css` (L89). Templates already print the names as read.
- **Modebar (AC-24)**: `displayModeBar: true`. Plotly's modebar is `opacity: 0` until hover in its own CSS; add
  `.js-plotly-plot .plotly .modebar { opacity: 1; }` to `databoot.css`. The buttons are `<a class="modebar-btn">`
  elements without `href`, so they are not focusable: after each `Plotly.newPlot(...)` resolves (and after each
  redraw on theme or breakpoint change), set `tabindex="0"` and `role="button"` on every `.modebar-btn` in that
  figure, copy `data-title` into `aria-label`, and on `keydown` Enter or Space call `btn.click()` and
  `preventDefault()`. The existing `.modebar-btn:focus-visible` ring (databoot.css L57) then shows.
- **Text rule (gate 160)**: only titles, axis labels, column names/types, `N of M` counts and the one-line rule
  caption. Fixed table headings and notes are labels.
- Style: plain, neutral, system sans, no logo, blank SVG favicon (gates 160, 165). The Designer owns the rest.

## Exports
Layout is unchanged from round 1 (PRD constraint); only the writers change.

### XLSX: `app/xlsx.write(dataset, rows, charts) -> bytes` on xlsxwriter
- `xlsxwriter.Workbook(buf, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False,
  "strings_to_numbers": False, "nan_inf_to_errors": True, "default_date_format": "yyyy-mm-dd hh:mm:ss"})`.
  `strings_to_formulas: False` stops a cell like `=HYPERLINK(...)` from a data file becoming a live formula
  (CSV injection); `strings_to_urls: False` avoids Excel's hyperlink limit on big sheets.
- Sheet `Data`: header row = `dataset.columns`, then the loaded rows. Write each cell by type: `None` skipped,
  `bool` -> `write_boolean`, `datetime`/`date` -> `write_datetime` (default date format), `int`/`float` ->
  `write_number`, else `write_string` of `str(v)[:32767]` (Excel's cell limit).
- One sheet per chart, named `f"{chart['id']} {chart['kind']}"` (e.g. `chart-1 line`, ≤ 31 chars), with the
  chart's table at A1 (header row + data, the same `_table(c)` columns as round 1), and a native chart inserted
  at the cell right of the table:

  | kind | Table columns | xlsxwriter chart |
  |---|---|---|
  | line | x_label, y_label | `{"type": "line"}` |
  | bar, country_map | x_label, y_label | `{"type": "column"}` |
  | histogram | bin label `"a to b"` (each edge with 6 significant digits), count | `{"type": "column"}`, gap 0 |
  | donut | label, value | `{"type": "doughnut"}` |
  | scatter | x_label, y_label | `{"type": "scatter"}` |
  | map3d | lon label, lat label, `z` | `{"type": "scatter"}` of lon/lat (Office map charts need Bing, online) |
  | heatmap | `column`, then labels; r values | **no chart**; `conditional_format` `3_color_scale` on the r cells: min `#3B4CC0` (num -1), mid `#FFFFFF` (num 0), max `#B40426` (num 1) |
- Series ranges use the list form `[sheet, first_row, col, last_row, col]` so xlsxwriter quotes the sheet name
  (`'chart-1 line'!$A$2:$A$7`). Chart title = `title`; axis titles = `x_label`, `y_label`; value axis number
  format `#,##0` (thousands separators); legend off for single series. A chart with 0 rows gets its sheet and
  table but no chart (xlsxwriter needs at least one point).
- The workbook xlsxwriter writes has a proper `styles.xml`, so openpyxl opens it without the "Workbook contains
  no default style" warning (AC-23; the round 1 hand-written file caused it, seen in the ticket 393 test run).
- Filenames: `<file stem>[-<sheet>].xlsx`, `Content-Disposition: attachment` (unchanged, `main._download`).

### PPTX: `app/export.pptx(dataset, charts) -> bytes` on python-pptx
- `prs = Presentation()`; `prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)` (16:9; the default
  template is 4:3, 9144000 wide). Every slide uses `prs.slide_layouts[6]` ("Blank", checked) and text boxes,
  so slide text is exactly what we put there.
- Slide 1: text boxes with the display name (`path` file name + ` - sheet`) and `f"{rows:,} rows, {cols:,} columns"`.
- One slide per chart: title text box; then `slide.shapes.add_chart(type, x, y, cx, cy, data)`:
  line `XL_CHART_TYPE.LINE`, bar/country_map/histogram `COLUMN_CLUSTERED`, donut `DOUGHNUT` with
  `CategoryChartData` (categories = x or labels, `None` -> `""`; one series named y_label); scatter/map3d
  `XY_SCATTER` with `XyChartData` (points with a `None` coordinate skipped). python-pptx embeds a workbook with
  the chart data, so "Edit Data" works in PowerPoint (native, editable: AC-18). Axis titles = x_label/y_label,
  value axis `number_format = '#,##0'`, `number_format_is_linked = False`.
- Heatmap slide: `slide.shapes.add_table(n + 1, n + 1, …)` (native table), header row/column of labels, r
  cells as `f"{r:.2f}"` (empty for `null`) filled with the same blue-white-red scale (`_heat(r)` stays).
- Last text box on each chart slide: the rule caption, then `f"{shown:,} of {total:,} {points|rows}"`.
- XML-illegal control characters (`\x00-\x08\x0b\x0c\x0e-\x1f`) are removed from every string given to
  python-pptx (lxml raises on them); keep one `_clean_text` helper in export.py.
- Filenames: `<file stem>[-<sheet>].pptx` (unchanged).

## Launcher (AC-11, AC-13; unchanged)
`python -m app.launch <folder> [--port 8765] [--no-browser]`; `DataBoot.bat` calls `Start-DataBoot.ps1`
(venv by default; `-Docker` checks `docker info`, mounts `${Folder}:/data:ro`, runs the container, opens the
browser). `Start-DataBoot.ps1` runs `pip install -r requirements.txt`, which now brings the four libraries.
Dockerfile `python:3.11-slim` installs requirements.txt too. Offline client machines: the `wheels\` folder
(`pip download -r requirements.txt -d wheels` on a connected machine, Windows wheels) is used with `--no-index`.

## How each acceptance item is met
| AC | How | Test (QA, tests/test_acceptance.py) |
|---|---|---|
| AC-1 | `catalog.scan` walks subfolders; xlsx sheets via openpyxl (R3); home datasets table | `data_dir`: paths, `Revenue`/`Lookup` sheets, row and column counts |
| AC-2 | profile route returns `classify()` and writes `<out>/profiles/{id}.json` | JSON equals file content; keys = every column |
| AC-3 | `profile.classify` rules above | fixture: `Latitude`/`LON` geo, `date` temporal, `region` categorical, `comment` other |
| AC-4 | `line` rule; `figure[data-kind=line]`; Plotly draws it | sales.csv and book.xlsx Revenue; Playwright draw check |
| AC-5 | `bar` rule | sales.csv sums North 16, South 23, East 7 |
| AC-6 | `map3d` rule drawn as Plotly `scatter3d`; outlines from `/static/vendor/topojson/`; no off-host requests | points.tsv and cities.geojson have one, sales.csv none; Playwright: WebGL canvas, off-host requests aborted and counted 0 |
| AC-7 | `charts == []`, page 200 | notes.csv: types + table, no `<figure` |
| AC-8 | dashboard template | every dataset: Columns table and ≤ 20 rows |
| AC-9 | vendored Plotly + topojson; `topojsonURL` config | every `src`/`href` is local and 200; Playwright records no off-host request |
| AC-10 | stride sampling to `map_cap` | `big_csv`: `shown` ≤ 50,000, `total` 60,000, page shows `N of 60,000 points` |
| AC-11 | `app.launch.run` | injected `open_browser` gets `http://127.0.0.1:<port>/`, home 200 |
| AC-12 | per-file (per-sheet) try/except in `scan`; fixed reasons table | empty.csv `empty file`, broken.xlsx `not a valid xlsx`; others list and open |
| AC-13 | `Dockerfile`, `Start-DataBoot.ps1` | text checks: `docker info`, `:/data:ro`, `docker run`, `Start-Process`; no `Start-DataOS.ps1` |
| AC-14 | readers + pyarrow `parquet.read` (R4) | tsv/json/jsonl/geojson counts; **9** parquet fixtures (zstd now reads) at 40x6; profile and charts equal flat.csv |
| AC-15 | `others` list, home "Other files" table | manual.pdf `pdf 9 <date>`, old.xls `xls 2`; no `<a ` in that table; `.hidden.csv` absent |
| AC-16 | rules table above, 8-chart cap | donut, histogram, scatter, heatmap, country map values; many.csv ≤ 8 figures |
| AC-17 | figcaption has one `.chart-rule` and one `.chart-count` | per figure regex; no `<p>` in main except the folder path |
| AC-18 | xlsxwriter (R1) and python-pptx (R2) | openpyxl: first sheet `Data`, header = columns, `sum(len(ws._charts)) > 0`; python-pptx: `len(slides) == 1 + len(charts)`, some `shape.has_chart` |
| AC-19 | titles and h1 in templates | home `<title>DataBoot</title>`, dashboards `… - DataBoot`, no `DataOS` |
| AC-20 | pyarrow error -> `not a valid parquet file` (R4, R7) | corrupt `bad.parquet` (magic + zeros + footer length) in the "Could not be read" table with that reason; sales.csv still opens |
| AC-21 | `num` Jinja filter | big.csv `60,000`; `N of 60,000 points`; no unseparated 4+ digit number in main |
| AC-22 | `<caption><h2>` (R5); no `text-transform` on `th` | each of the 5 captions matches `<caption>\s*<h2>NAME</h2>\s*</caption>` (First rows: `First \d+ rows`); `databoot.css` has no `uppercase`; a mixed-case header (`Latitude`, `LON`) appears verbatim in `<th>` |
| AC-23 | requirements.txt pins; library writers | parse requirements.txt for the 4 exact pins; no file named `xlsxwriter`, `pptx`, `openpyxl`, `pyarrow` (dir or `.py`) under the repo outside `.venv`; `warnings.catch_warnings(record=True)` around `load_workbook` of an export: no message contains `no default style` |
| AC-24 | `displayModeBar: true`, modebar CSS opacity 1, focusable buttons (R6) | Playwright, no hover: first `.modebar` computed `opacity` is `1` and visible; pressing Tab from the page top reaches an element with class `modebar-btn` |

## Work items without AC ids: explicit checks
- **W-1 Unreadable.sheet (gate 162)**: a workbook where one sheet fails lists `book.xlsx - <sheet>` in "Could not
  be read" and the other sheets as datasets; `Unreadable("x.csv", "empty file").sheet is None`.
- **W-2 invalid JSON (gate 162)**: `{oops` in .json and a bad line in .jsonl give `invalid JSON`; `{"a": 1}` and
  `[1, 2]` keep `not a list of records`.
- **W-3 chart items (gate 162)**: records.json country map `locations` = `["Brazil", "Japan", "France"]` (203,
  125, 68); points.tsv map3d `z_label` is `"value"` and `null` for a lat/lon-only file.
- **W-4 line endings**: `git diff --stat tests/fixtures` empty; `.gitattributes` is exactly `* text=auto`.

## Tests that must change with the code (name them in the tickets)
- `tests/test_parquet.py`: drop the `stdlib` fixture param and `test_snappy_copies` (fallback deleted, gate
  162); `test_unsupported_codec` (zstd) becomes "zstd reads, values equal flat.csv"; not-parquet bytes expect
  `not a valid parquet file`; nested schema keeps `unsupported parquet encoding`; `test_catalog_scan_lists_parquet`
  expects 3 datasets and no unreadable.
- `tests/test_readers.py` L84-85: `{oops` and the bad jsonl line expect `invalid JSON`.
- `tests/test_xlsx_read.py::test_shared_booleans_formats_and_gaps`: `_rewrite` adds `xl/sharedStrings.xml`
  without a content type or relationship, so openpyxl cannot find it (IndexError in a /tmp probe). Use
  `inlineStr` cells instead (the probe then gave the expected rows with `True`/`False` -> `"TRUE"`/`"FALSE"`).
- `tests/test_export_xlsx.py`: chart kinds, sheet names and ranges should still hold (xlsxwriter writes
  `xl/charts/chartN.xml` with `c:lineChart`, `c:barChart`, `c:doughnutChart`, `c:scatterChart`); the heatmap
  test reads `xl/worksheets/sheet2.xml` `conditionalFormatting` (xlsxwriter writes it there). Re-check, do not assume.
- `tests/test_export_pptx.py`: the embedded workbook is python-pptx's (`Sheet1`, not `Data`/`chart-1 line`) and
  its part names differ. Replace the L64-71 internals with python-pptx reopen checks: chart type per slide,
  `chart.plots[0].categories`, texts per slide. Keep `check_package` (python-pptx output is a valid package).
- `tests/test_acceptance.py`, `tests/test_pages.py`: `<caption>Columns</caption>`-style literals and `_rows_of`
  must accept `<caption><h2>…</h2></caption>`; test_G_1 expects 9 parquet datasets; then the rename (R9).

## Test fixtures (tests/conftest.py, unchanged)
`data_dir` builds: `sales.csv`, `points.tsv`, `notes.csv`, `empty.csv`, `broken.xlsx`, `manual.pdf`,
`.hidden.csv`, `sub/records.json`, `sub/events.jsonl`, `sub/cities.geojson`, `sub/book.xlsx` (sheets `Revenue`
with Excel date cells, `Lookup`). `write_xlsx` stays hand-written: openpyxl reads it (with the harmless "no
default style" warning, which AC-23 only checks on exports). `big_csv` holds 60,000 lat/lng rows.
`make_client(folder)` sets the env and returns a TestClient. Parquet fixtures in `tests/fixtures/` (written once
by pyarrow) with CSV twins `flat.csv`, `optional.csv`. Playwright fixtures are function-scoped.

## Decisions
1. Office files on xlsxwriter (write), python-pptx (write) and openpyxl `read_only=True` (read), Parquet on
   pyarrow; pinned, not vendored (gates 162, 164, 165). This deletes roughly 500 lines of hand-written OOXML,
   thrift and snappy code, and the files open cleanly in Office.
2. No stdlib Parquet fallback (gate 162): pyarrow is a pinned runtime dependency, so a second reader is
   untested weight. Consequence: ZSTD/LZ4/BROTLI files now read (AC-14 counts 9 parquet datasets).
3. A corrupt Parquet file gets the new note `not a valid parquet file`; `unsupported parquet encoding` stays
   only for nested schemas, which the flat row model cannot show.
4. The PPTX no longer embeds our own workbook: python-pptx embeds its own, which is what makes "Edit Data" work.
   One writer per format instead of export.py importing xlsx internals.
5. xlsxwriter with `strings_to_formulas`, `strings_to_urls` and `strings_to_numbers` off: cells from client
   files are data, never formulas or links (CSV injection, hyperlink cap).
6. h2 inside `<caption>` rather than replacing the caption (gate 165): keeps the table name and adds the heading.
7. Modebar buttons made focusable with JS after each draw (Plotly renders `<a>` without `href`); CSS alone cannot
   put them in the Tab order.
8. Rows loaded on demand (LRU 4, 200,000-row cap), charts computed once server-side and shared by page, JSON and
   exports; server-rendered figures and captions (round 1, unchanged).
9. Vendored Plotly 4.1.2 and sane-topojson 4.0.0 stay: they are browser assets, the only way to be offline (AC-9).
