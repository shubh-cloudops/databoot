# Architecture: DataBoot (round 4)

DataBoot scans one mounted folder or drive letter, profiles every dataset with fixed rules and draws the
charts those rules pick, fully offline. Sources: docs/PRD.md (round 4), docs/acceptance.json (AC-1..AC-41),
Board gates 160-175 (graphify-out/memory.md). Round 4 keeps everything rounds 1 to 3 built and adds: an interest
score per chart that sets the order, a KPI strip, server-side filters kept in the URL, click cross-filter and
filtered exports. No new dependency, no new page or route path, so no sitemap or NAV change.

No docs/TRENDS.md this round (docs/team.json: trends off, gate 175), so I used no trend advice.

**Gate 175 overrides the PRD on AC-38 and AC-39.** The PRD had C2 (second click removes the filter) as a Could and
no chips; the Board said "build C2 now" and "each active filter shows as a removable chip, plus Clear filters". I
reworded AC-38 (chips) and AC-39 (second click removes) in acceptance.json and moved C2 into PRD M13. Ids unchanged.

## Round 4 changes at a glance
| # | Change | Files | AC |
|---|---|---|---|
| S1 | Interest score per chart, computed on the full filtered rows inside each rule | `app/score.py` (new), `app/rules.py` | AC-32 |
| S2 | Charts sorted by score after the 8-chart cut (stable), ids renumbered in display order | `app/rules.py` `charts` | AC-33 |
| D1 | Data access: per-dataset cache of raw rows, column types, typed rows and dropdown options; per-filter cache of the view | `app/main.py`, `app/rules.py` `typed`, `app/profile.py` (speed only) | AC-41 |
| F1 | Filters: parse query params, apply, labels, canonical query string | `app/filters.py` (new), `app/main.py` | AC-37, AC-38 |
| K1 | KPI figures of the filtered rows | `app/rules.py` `kpis` | AC-36 |
| P1 | Page: KPI strip, filter form, chips, Clear filters, score in caption, first chart full width, filtered export links | `dataset.html`, `databoot.css` (Designer) | AC-34..AC-38 |
| J1 | dashboard.js: fetch with the page's query string, tidy form submit, Plotly click cross-filter with toggle | `app/static/js/dashboard.js` | AC-38, AC-39 |
| E1 | Exports take the same query params; XLSX `Summary` sheet (last), PPTX title slide filter line | `app/main.py`, `app/xlsx.py`, `app/export.py` | AC-40 |
| T1 | `big_sales_csv` fixture (200,000 rows), done by the architect | `tests/conftest.py` | AC-41 |

## Round 4: request flow (one function for page, API and exports)
```python
@lru_cache(maxsize=4)
def _base(d):                     # once per dataset: the slow part (classify is seconds on 200,000 rows)
    rows = catalog.load(d, config.get().max_rows)
    mapping = profile.classify(d.columns, rows)          # types from the UNFILTERED rows
    return rows, mapping, rules.typed(d.columns, rows, mapping), filters.options(d.columns, rows, mapping)

@lru_cache(maxsize=8)
def _view(d, f):                  # f = filters.parse(...) result: a hashable tuple
    rows, mapping, typed, options = _base(d)
    keep = filters.apply(f, d.columns, mapping, typed)   # list of row indexes, or None when f == ()
    rows_f = rows if keep is None else [rows[i] for i in keep]
    typed_f = typed if keep is None else [typed[i] for i in keep]
    return {"rows": rows_f, "mapping": mapping, "options": options, "filters": f,
            "labels": filters.labels(f, d.columns, mapping),
            "charts": rules.charts(d.columns, typed_f, mapping, settings),
            "kpis": rules.kpis(d.columns, rows_f, typed_f, mapping)}
```
- Every route that shows data calls `_view(d, filters.parse(request.query_params, d.columns, mapping))`: the
  dashboard page, `/api/datasets/{id}/charts` and both exports. With no (or only ignored) params `f == ()` and
  every route answers as before, plus the new keys (`score`, `kpis`, `filters`, Summary sheet, filter line).
- Column types come from the unfiltered rows, so a filter never changes a column's type, the dropdowns or which
  rules can run. The rules then run on the filtered rows, so a chart whose rule no longer matches (for example a
  donut on the filtered column, now 1 value) is simply not generated and not shown (gate 175).
- `rules.typed(columns, rows, mapping)`: a copy of the rows with numerical and geospatial cells as `_num(v)` and
  temporal cells as `_time(v)`, others as they are. `_num`/`_time` return typed values unchanged, so the rules
  keep calling them and still work on raw rows (unit tests pass raw rows). Raw rows stay for the First rows
  table, the XLSX Data sheet and % missing, so what the owner sees is what the file holds.
- The page and the API share the `_view` cache, so the dashboard's own fetch is a cache hit. `tests/conftest.py`
  `make_client` must call `main._base.cache_clear()` and `main._view.cache_clear()` (the ticket that adds them).
- `/api/datasets/{id}/profile` keeps calling `classify` and writing the JSON (AC-2); it may use `_base(d)[1]`.

## Round 4: filters (`app/filters.py`)
Query parameters (the same on `/datasets/{id}`, `/api/datasets/{id}/charts`, `export.xlsx`, `export.pptx`):

| Param | Meaning | Ignored when |
|---|---|---|
| `f.<column>=<value>` | rows where `str(cell) == value` in that column (the same `str()` key bars and donuts use) | column is not categorical in the mapping (so >50-distinct columns never filter, gate 175), value empty |
| `from=YYYY-MM-DD` | rows whose first temporal column is on or after that day (`_time(cell).date() >= from`) | no temporal column, not a valid `date.fromisoformat` |
| `to=YYYY-MM-DD` | on or before that day, inclusive | same |

- One value per column (gate 175): a repeated `f.region` keeps the last (`query_params[key]`). Filters on
  different columns and the date range combine with AND. A row with an empty or unparseable time is dropped as
  soon as `from` or `to` is set. A value not among the options is still applied (a stale shared link shows 0 rows
  and its chip, which removes it).
- `parse(params, columns, mapping) -> tuple`: canonical `((name, value), ...)` pairs, categorical params in column
  order, then `from`, then `to`; value strings as given (dates re-printed ISO). Hashable for `_view`'s cache, and
  `urllib.parse.urlencode(f)` is the canonical query string.
- `apply(f, columns, mapping, typed) -> list[int] | None`: `None` for `f == ()`, else the kept row indexes.
- `labels(f, columns, mapping) -> [str]`: `region = North`, `date from 2024-01-01`, `date to 2024-03-31` (the
  temporal column's real name). Used by the chips, the PPTX title slide and the XLSX Summary sheet.
- `summary(labels) -> str`: `"Filters: " + "; ".join(labels)`, or `"Filters: none"` (gate 175 wording).
- `options(columns, rows, mapping) -> {column: [values]}`: every categorical column, `sorted` distinct
  non-empty `str(cell)` of the unfiltered rows (at most 50 each, AC-3).
- Chip remove link: `"?" + urlencode([p for p in f if p != chip])`, or the bare page path when nothing is left.

## Round 4: interest score (`app/score.py`, used inside `app/rules.py`)
Each rule computes its chart's score from the full data it has before stride sampling, and passes it to
`_chart(..., score=...)`. `charts()` rounds every score with `round(s, 2)`, cuts to `MAX_CHARTS` in rule order
(unchanged selection), then `sorted(found, key=lambda c: -c["score"])` (stable: ties keep the rule order 3D map,
country map, line, bar, donut, histogram, scatter, heatmap), then sets `id = chart-1..N` in that display order.
Every score helper returns a float in 0..1 and returns 0 for fewer than 2 usable values, constant values or any
undefined result (`StatisticsError`, `ZeroDivisionError`, overflow).

| kind | Score | Input (full, before sampling) |
|---|---|---|
| line | `abs(spearman(range(n), sums))`: Pearson of average ranks (ties share the mean rank) | the per-time sums sorted by time (`sums` dict in `_lines`), value column = that line's own column |
| bar, donut | Gini: x sorted ascending, `2 * sum(i * x_i) / (n * sum(x)) - (n + 1) / n`, i = 1..n | the category totals drawn; any negative total or `sum(x) == 0` gives 0 |
| scatter | `abs(pearson(xs, ys))` | all point pairs (not the sample) |
| histogram | `min(1, abs(g1) / 3)`, `g1 = m3 / m2 ** 1.5` with population moments (divide by n) | all values |
| heatmap | largest `abs(z[i][j])`, `i != j`, `None` skipped | the matrix the chart draws |
| map3d, country_map | `0.6` | 0 when the chart has fewer than 2 points / countries |

Hand-checked on `data_dir` sales.csv (date, region, amount; script in /tmp, ticket 428): line 0.89 (rho -0.886),
histogram 0.34 (g1 1.024), bar 0.23 (Gini of 16, 23, 7 = 0.2319), donut 0.22 (Gini of 3, 2, 1 = 0.2222).
So sales.csv now shows line, histogram, bar, donut (was line, bar, donut, histogram). `pearson` is
`statistics.correlation` clamped to [-1, 1] (as the heatmap does now); Python 3.11 has no `method="ranked"`, so
`spearman` ranks by hand. Scores add no network request and no dependency (stdlib only).

## Round 4: KPIs (`rules.kpis(columns, rows, typed, mapping)`)
`{"rows": len(rows), "columns": len(columns), "missing_pct": round(100 * empty / (rows * columns), 1) (0 when no
cells), "sums": [{"column": name, "sum": s}, ...]}` for the first 3 numerical columns. `empty` counts raw cells
that are `None` or `""`. A sum is over the typed non-`None` values, printed as an `int` when whole, else
`round(s, 2)`; an all-empty column sums to 0. Page labels: `Rows`, `Columns`, `Missing`, `<column> (sum)`; every
figure through the `num` filter (`Missing` as `0.0%`).

## Round 4: speed (AC-41)
Measured in this image (16 cores, Python 3.11) on a 200,000-row CSV like `big_sales_csv` (/tmp probe, ticket 428):
`catalog.load` 0.41 s; `profile.classify` **20.9 s**; `rules.charts` on raw rows 4.4 s, on typed rows 2.8 s;
casting to typed rows once 1.3 s; a region filter (1 of 4) 0.01 s; charts on those 50,000 typed rows 0.7-1.0 s,
of which the heatmap is 0.41 s because it computes `pearson` for both triangles. Levers, all required:
1. `_base` cache (types and typed rows once per dataset), so a filter request pays only filter + rules + KPIs.
2. Heatmap: compute each pair once (`j > i`) and mirror it; z is symmetric, the result is identical.
3. `profile._kind`: count each distinct string once (`collections.Counter(strs)`, then `_parses` per key times its
   count): same result, and the 20 s first load drops a lot (categorical and number columns repeat values).
The AC-41 test first requests the charts API without filters (warm-up: load, classify, typed rows), then times one
request with `f.region=North` (not cached yet) and asserts `< 1.0` s.

## Round 3 changes at a glance (built, kept)
| # | Change | Files | AC |
|---|---|---|---|
| L1 | Launcher picks the newest Python 3.11-3.13 (`py -3.13`, `-3.12`, `-3.11`, then `python` with a version check) | `Start-DataBoot.ps1` | AC-28, AC-30 |
| L2 | `$LASTEXITCODE` checked after venv creation and both pip installs; one `Fail` path: message, delete `.venv`, pause, `exit 1` | `Start-DataBoot.ps1` | AC-29 |
| X1 | Per-sheet isolation: a corrupt sheet XML no longer fails the whole workbook (gate 171: build it) | `app/xlsx.py` (reader half only) | AC-25, AC-31 |
| D1 | Test-only packages move to `requirements-dev.txt` (gate 171) | `requirements.txt`, `requirements-dev.txt`, `README.md` | W-5 |
| T1 | Launcher text tests and the corrupt-sheet test | `tests/test_launcher_files.py`, `tests/test_acceptance.py` | AC-28..AC-31 |

**Gate 171 overrides the PRD on AC-31.** The PRD (ticket 417) read "log AC-25 per-sheet isolation" as "write the
gap down"; the Board answered "BUILD per-sheet isolation this round". I reworded AC-31 in acceptance.json to the
built behaviour (other sheets list and open; the corrupt one shows as `book.xlsx - <sheet>`, `not a valid xlsx`)
and changed PRD S4/C2 to match. Ids are unchanged.

Done by the architect (ticket 418), so engineers need not redo it:
- `requirements.txt` holds only runtime pins (fastapi, jinja2, uvicorn, pyarrow, openpyxl, python-pptx,
  xlsxwriter); new `requirements-dev.txt` = `-r requirements.txt` + `httpx==0.28.1`, `pytest==9.1.1`. README
  says `pip install -r requirements-dev.txt`. Nothing under `app/` imports httpx or pytest (grep), and the
  Dockerfile, launcher and `wheels\` download keep using `requirements.txt`, so clients no longer get test tools.
  The orchestrator's verify step lives in /opt/prodagents (not in this repo); it must install
  `requirements-dev.txt` (open question for the Board; the image already has both today).
- `tests/conftest.write_xlsx` accepts a sheet given as `bytes` and writes it verbatim as that sheet's XML, so a
  test can build `{"Good": [...], "Bad": b"<<not xml", "Also": [...]}`.

## Round 3: launcher design (L1, L2)
DataBoot.bat runs `powershell` (Windows PowerShell 5.1), not pwsh. The venv branch of `Start-DataBoot.ps1`
becomes the shape below. Folder dialog, folder check, the `-Docker` branch, the `wheels` offline install and the
final `.venv\Scripts\python.exe -m app.launch $Folder` stay as they are.

```powershell
function Fail($Message) {
    Write-Host $Message
    if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
    Read-Host "Press Enter to close" | Out-Null
    exit 1
}

# Newest Python 3.11-3.13 first; 3.14 is rejected until every pinned dependency ships wheels for it (gate 171).
$Candidates = @(@("py", "-3.13"), @("py", "-3.12"), @("py", "-3.11"), @("python"))
$Check = "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)"
```
- **Search** (AC-28): for each candidate, skip it if `Get-Command $c[0]` finds nothing; run
  `$rest = @($c | Select-Object -Skip 1); & $c[0] @rest -c $Check` with output to `$null`; the first with `$LASTEXITCODE -eq 0` is used for
  `-m venv .venv`. The version check runs for the `py` candidates too (one loop, and a broken `py` entry
  is skipped rather than trusted). None found: `Fail "DataBoot needs Python 3.12. Install it with: winget
  install -e --id Python.Python.3.12"` (exact text, gate 171).
- **Checks** (AC-29): after `-m venv .venv`: `if ($LASTEXITCODE -ne 0) { Fail "Could not create the Python
  environment (.venv)." }`; after the wheels pip install: `Fail "Could not install the packages from wheels."`;
  after the online pip install: `Fail "Could not install the packages (pip install -r requirements.txt)."`.
  Each message names its step. `exit 1` inside a function ends the script.
- **PowerShell 5.1 pitfall**: with `$ErrorActionPreference = "Stop"`, redirecting a native command's stderr
  (`2>$null`, `*>$null`) turns its first stderr line into a terminating NativeCommandError in 5.1. `py -3.13`
  prints "No suitable Python runtime found" to stderr when 3.13 is missing, so the probe would throw instead of
  moving on. Run the probe with `$ErrorActionPreference = "Continue"` set locally (inside a small function or a
  `try/finally` that restores it), or wrap the probe in `try { ... } catch { }`. Same for `Get-Command`: use
  `-ErrorAction SilentlyContinue`. There is no PowerShell in the image, so this cannot be run here; the
  engineer writes it carefully and the Board runs it on Windows.
- The venv is created with the same `$c[0] @rest -m venv .venv`. Keep the version list in one place
  (`$Candidates`) so AC-30's test can read it; do not leave a literal `py -3.11 -m venv` line.

## Round 3: per-sheet isolation design (X1)
Root cause, probed in /tmp (ticket 418): openpyxl 3.1.5 `load_workbook(read_only=True)` builds a
`ReadOnlyWorksheet` per sheet, and its `__init__` calls `_get_size()`, which parses the sheet XML until it meets
`<dimension>`. A sheet with no `<dimension>` (every `conftest.write_xlsx` workbook) or a sheet that is not XML is
parsed at load time, so one bad sheet makes `load_workbook` raise and `sheet_names` returns `not a valid xlsx`
for the whole file. (An xlsxwriter workbook truncated after its `<dimension>` already isolates today.)

Fix in `app/xlsx.py` only; `catalog.scan` already catches per sheet and builds `Unreadable(rel, reason, sheet)`
(catalog.py L95-99), so no catalog, template or route change:
- `_load(path, keep=None)`: copy the zip into a `BytesIO`, writing every worksheet part
  (`xl/worksheets/*.xml`, not `_rels`) as an empty sheet
  `<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>`, except
  the part named `keep`; then `load_workbook(copy, read_only=True, data_only=True)`. Styles, shared strings and
  workbook.xml are copied as they are, so dates and sheet order are unchanged. Not a zip / no workbook part /
  any open error: `ReadError("not a valid xlsx")` as today.
- `sheet_names(path)`: `_load(path)` (all blanked), so the list never parses a sheet; returns
  `book.sheetnames`; empty list still raises `not a valid xlsx`.
- `read_sheet(path, sheet)`: find the part of `sheet` (`book[sheet]._worksheet_path` on the all-blanked load,
  e.g. `xl/worksheets/sheet2.xml`), then `_load(path, keep=part)` and read as today. A parse error of that one
  sheet raises `not a valid xlsx`, which scan records with the sheet name.
- `path` may be a path or `BytesIO` (tests pass both); seek a `BytesIO` back to 0 before each copy.
- The /tmp probe gave, for `{"Good": [[a, d], [1, date]], "Bad": <truncated or b"<<x">, "Also": [...]}`:
  names `Good, Bad, Also`; Good and Also rows read (date as `datetime`); Bad raised `ParseError`.
- `_worksheet_path` is a private openpyxl attribute; openpyxl is pinned at 3.1.5 and the tests catch a change.
  Mark it with a `ponytail:` comment, and one for the copy cost: each sheet read rewrites the zip in memory
  (uncompressed `ZIP_STORED` is fine), so a workbook with N sheets is copied N + 1 times at scan.
- Known limit, not in scope: a sheet whose part is missing from the zip is dropped by openpyxl without an error,
  so it is neither listed nor in "Could not be read" (probe: names `Good, Also`).

## Round 2 changes (built, kept)
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
- Python 3.11-3.13 (the image runs 3.11) plus pinned libraries in requirements.txt: fastapi, jinja2, uvicorn (httpx
  and pytest are in requirements-dev.txt since round 3), and for data
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
Round 3 touches only `app/xlsx.py` (reader: `_load(path, keep=None)`, X1) and `Start-DataBoot.ps1` (L1, L2);
the "Round 2" column below is what round 2 changed.

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

Round 4: new `app/filters.py` (`parse`, `apply`, `labels`, `summary`, `options`) and `app/score.py`
(`spearman`, `pearson`, `gini`, `skew`, each giving the 0..1 score); `app/rules.py` gains `typed`, `kpis`, a
`score` per chart and the sort; `app/main.py` replaces `_charts` with `_base` and `_view`; `xlsx.write` and
`export.pptx` gain a `summary` argument; `profile._kind` counts distinct strings once; `dataset.html`,
`databoot.css`, `dashboard.js` as in "Pages". Readers, catalog, launcher and config are unchanged.

## Routes (sitemap: two pages, no nav beyond a "DataBoot" home link; unchanged)
| Method, path | Returns |
|---|---|
| GET `/` | Home: datasets table, "Could not be read" table, "Other files" table |
| GET `/datasets/{id}` | Dashboard page; 404 for unknown id; round 4: filter query params (see "Round 4: filters") |
| GET `/api/datasets` | `[{"id","path","sheet","kind","rows","columns"}]` (columns = count) |
| GET `/api/datasets/{id}/profile` | `{column: type}` (AC-2), also writes `<out>/profiles/{id}.json` |
| GET `/api/datasets/{id}/charts` | chart contract below; fetched once by dashboard.js on load with the page's query string (no polling) |
| GET `/datasets/{id}/export.pptx` | PPTX download (same filter params) |
| GET `/datasets/{id}/export.xlsx` | XLSX download (same filter params) |
| GET `/health` | `{"ok": true}` |
| `/static/...` | StaticFiles mount |

No page or route is added in round 4 (only query params), so no sitemap or NAV change.

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

## Chart contract (`GET /api/datasets/{id}/charts[?f.<column>=v&from=YYYY-MM-DD&to=YYYY-MM-DD]`)
```json
{"dataset": "3f2a9c01b7de",
 "filters": ["region = North"],
 "kpis": {"rows": 3, "columns": 3, "missing_pct": 0.0, "sums": [{"column": "amount", "sum": 16}]},
 "charts": [
  {"id": "chart-1", "kind": "line", "title": "amount by date",
   "x_label": "date", "y_label": "amount (sum)",
   "rule": "temporal date + numerical amount: line, sum per date",
   "shown": 3, "total": 3, "score": 1.0,
   "data": {"x": ["2024-01-01", "..."], "y": [10, "..."]}}]}
```
**Round 4 additions**: `filters` (the labels, `[]` when none), `kpis` (see "Round 4: KPIs"), and `score` (float,
2 decimals) on every chart; `charts` is in score order and `id` follows that order. `rule` is unchanged (the page
appends the score). For `bar` and `donut`, `x_label` is the categorical column's name: dashboard.js uses it as
the cross-filter column. The page reads nothing from `filters`/`kpis` in JS (both are server-rendered); they are
there for tests and for the AC-37 "API matches the page" check.
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
- **Round 4 dashboard order** (top to bottom): crumb, page head (h1, export links), KPI strip, filter form,
  chips + Clear filters, charts grid, Columns table, First rows table (AC-34: the First rows table stays last;
  no score, no caption, gate 175). All of it is server-rendered from `_view`; a filter change is a normal GET
  navigation to the new URL, so every chart, count, KPI, chip and control comes from the server and the browser's
  Back button restores the previous filter state with no `pushState` code (AC-38).
  - **KPI strip**: `<dl class="kpis">` with one `<div><dt>Rows</dt><dd>3</dd></div>` per figure. No `<p>`:
    test_AC_17 rejects any `<p>` in main except the folder path.
  - **Filter form**: `<form class="filters" method="get" action="/datasets/{id}">`; one `<label>` + `<select
    name="f.<column>">` per key of `options` (first option `All`, value `""`; the active value `selected`); when
    a temporal column exists, `<input type="date" name="from">` and `name="to"` labelled `<column> from` /
    `<column> to`, preset from `f`; a submit button `Apply` (works with no JS). Only categorical columns get a
    dropdown (gate 175: >50 distinct values is not categorical).
  - **Chips**: `<ul class="chips">`, one `<li><a href="{remove link}" aria-label="Remove filter region =
    North">region = North</a></li>` per label (the Designer adds the ×), then `<a class="btn" href="/datasets/{id}">
    Clear filters</a>`; the whole list only when a filter is active.
  - **Caption**: `<span class="chart-rule">{{ c.rule }} · score {{ "%.2f"|format(c.score) }}</span>` (AC-35;
    test_AC_17 still finds `c["rule"]` in the figure and one `.chart-rule`).
  - **Grid (AC-34)**: `.charts > .chart:first-child { grid-column: 1 / -1 }`; the round 2 rule that makes
    map3d, country_map and heatmap span both columns is removed, so the others sit two per row from 900px and one
    per row below (the existing breakpoints; phone = the 599px narrow breakpoint, gate 175). The Designer owns
    the look.
  - **Export links** carry the canonical query: `href="/datasets/{id}/export.pptx{{ qs }}"`, `qs` = `"?" +
    urlencode(f)` or `""`.
- **Round 4 dashboard.js** (J1):
  - fetch `"/api/datasets/" + id + "/charts" + location.search` (same params, so the same cached `_view`).
  - Form tidy-up: on `change` of a select or date input, submit the form; on `submit`, set `disabled = true` on
    empty fields first so the URL holds only active filters (disabled fields are not sent).
  - Cross-filter (AC-39, C2): after `newPlot` of a `bar` or `donut`, `plot.on("plotly_click", ...)`: category =
    `pt.label` for donut, `pt.y` for a horizontal bar, else `pt.x`; key = `"f." + c.x_label`;
    `p = new URLSearchParams(location.search)`; if `p.get(key) === category` delete it (second click removes,
    gate 175) else `p.set(key, category)`; `location.assign(location.pathname + (p.toString() ? "?" + p : ""))`.
    `newPlot` replaces handlers on redraw (theme or breakpoint change), so attach after each draw.
- **Text rule (gate 160)**: only titles, axis labels, column names/types, `N of M` counts and the one-line rule
  caption. Fixed table headings and notes are labels.
- Style: plain, neutral, system sans, no logo, blank SVG favicon (gates 160, 165). The Designer owns the rest.

## Exports
Layout is unchanged from round 1 except the round 4 filter additions (AC-40):
- Both routes call `_view(d, f)` with the request's params: the Data sheet gets the filtered raw rows, every
  chart the filtered data, in score order (sheet `chart-1 …` = the top chart, as on the page).
- `xlsx.write(dataset, rows, charts, summary="Filters: none")`: after the chart sheets, a last sheet `Summary`
  with A1 = `summary`. Last, not second, so `Data` stays first (AC-18) and chart sheets keep `sheet2.xml…`.
- `export.pptx(dataset, charts, summary="Filters: none")`: the title slide gets a third text box with `summary`
  (14 pt) under the rows/columns line. The rows/columns line keeps the dataset size.
- main passes `filters.summary(view["labels"])`. Defaults keep direct calls in the unit tests working.

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

## Launcher (AC-11, AC-13; venv branch changed in round 3, AC-28..AC-30)
`python -m app.launch <folder> [--port 8765] [--no-browser]`; `DataBoot.bat` calls `Start-DataBoot.ps1`
(venv by default; `-Docker` checks `docker info`, mounts `${Folder}:/data:ro`, runs the container, opens the
browser). The venv branch picks its Python and checks exit codes as in "Round 3: launcher design" above.
`Start-DataBoot.ps1` runs `pip install -r requirements.txt` (runtime pins only since round 3).
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
| AC-25 | per-sheet try/except in `scan` (round 2) plus X1 | existing `test_AC_25` (header-less `Lookup` sheet) stays; X1 adds the corrupt-XML case under AC-31 |
| AC-26 | `INVALID_JSON` note (round 2) | existing `test_AC_26` |
| AC-27 | `rules.py` country order, map3d `z_label` (round 2) | existing `test_AC_27` |
| AC-28 | L1: `$Candidates` = `py -3.13`, `py -3.12`, `py -3.11`, `python`; each must pass `$Check` (3.11 <= version <= 3.13) | text checks on `Start-DataBoot.ps1` (no PowerShell in the image): `"-3.13"`, `"-3.12"`, `"-3.11"` appear in that order inside the `$Candidates` line, then `"python"`; the script contains `(3, 11) <= sys.version_info[:2] <= (3, 13)`; `-m venv .venv` is called on the chosen candidate, not on a literal version |
| AC-29 | L2: `Fail` function; `$LASTEXITCODE -ne 0` check after venv and after each pip install; no-Python message | text checks: `function Fail` contains `Remove-Item -Recurse -Force .venv`, `Read-Host` and `exit 1`, in that order; the exact gate 171 message `DataBoot needs Python 3.12. Install it with: winget install -e --id Python.Python.3.12`; split the script at `-m venv .venv`, `--find-links wheels` and the online `pip install -r requirements.txt`: each piece after them holds `$LASTEXITCODE` before the next native command; every `Fail` call comes before the final `-m app.launch` line |
| AC-30 | L1 keeps all versions in one list | a test fails if `re.search(r"py -3\.1\d+ -m venv", ps1)` matches, or if `$Candidates` lacks any of 3.13/3.12/3.11 or holds them out of order (same parser as AC-28) |
| AC-31 | X1: `_load(path, keep)` blanks the other worksheet parts in an in-memory copy | `write_xlsx(data_dir / "book3.xlsx", {"Good": [("a","b"),(1,2)], "Bad": b"<<not xml", "Also": [("a","b"),(3,4)]})` and a second file whose `Bad` is a truncated sheet XML (e.g. `b'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>a'`): home "Could not be read" has `book3.xlsx - Bad` with `not a valid xlsx`; Good and Also are in `/api/datasets` and their pages and `/charts` return 200; `book3.xlsx` alone (no sheet) is not in the unreadable table |
| AC-32 | S1: `app/score.py` helpers called inside each rule on the full (filtered) data; `score` on every chart | `data_dir` sales.csv API: line 0.89, histogram 0.34, bar 0.23, donut 0.22 (hand values in "Round 4: interest score"); points.tsv map3d 0.6; unit tests of `score.gini([16, 23, 7])` ≈ 0.2319, `score.skew` of 10, 20, 5, 7, 3, 1 ≈ 0.3415, constant or 1-value inputs give 0, a scatter on y = 2x gives 1.0 |
| AC-33 | S2: round, cut to 8 in rule order, stable sort by `-score`, renumber ids | sales.csv kinds `["line", "histogram", "bar", "donut"]`, ids `chart-1..4`; a tie case keeps rule order (file `k\na\nb\na\nb\n`: bar and donut both score 0, so `["bar", "donut"]`); two requests give equal JSON; page `data-kind` order equals the API order |
| AC-34 | P1 grid CSS (`:first-child` spans `1 / -1`); First rows table after `.charts` in the template | Playwright at 1280 px: first figure width ≈ `.charts` width, figures 2 and 3 share a `top` and are each about half; at 390 px every figure is full width; in the HTML the `data-table` comes after the last `</figure>` |
| AC-35 | P1 caption `rule · score 0.NN` | per figure: `.chart-rule` text ends with `f" · score {c['score']:.2f}"` for the API chart at the same position |
| AC-36 | K1 `rules.kpis`; `<dl class="kpis">` | sales.csv: Rows 6, Columns 3, Missing 0.0%, amount (sum) 46; with `?f.region=North`: 3 and 16; `big_csv`: figures with separators (`60,000`) and test_AC_21 still green |
| AC-37 | F1 `filters.parse/apply/options`; form in the template | sales.csv page has `<select name="f.region">` with North/South/East and `type="date"` inputs `from`/`to`; notes.csv has no select; API with `f.region=North`: every `total` smaller than unfiltered, `kpis.rows == 3`; `from=2024-01-03&to=2024-01-05`: `kpis.rows == 3`; the page with the same params shows the same counts as the API |
| AC-38 | server-rendered filtered page; GET navigation; chips; Clear filters link | `/datasets/{id}?f.region=North`: `<option value="North" selected>`, chip `region = North`, KPI 3 rows; Playwright: pick South in the select, URL gains `f.region=South`, `page.go_back()` returns to the North URL and its KPI 3; click the chip's link, then `Clear filters`: URL has no `f.`, KPI 6 |
| AC-39 | J1 `plotly_click` on bar/donut; toggle | Playwright on sales.csv: `page.evaluate` emits a click via `document.getElementById(barId).querySelector('.plot').emit('plotly_click', {points: [{x: 'South', label: 'South', data: {}}]})` (Plotly's own handler path) or a real mouse click on the bar; URL has `f.region=South`, select shows South, KPI rows 2; same click again: no `f.region`, rows 6 |
| AC-40 | E1 `_view` in both export routes; Summary sheet last; title slide line | XLSX with `?f.region=North`: Data has 3 rows, first sheet `Data`, last `Summary` A1 `Filters: region = North`, bar sheet total 16; without params Summary A1 `Filters: none`; PPTX: slide 1 texts contain `Filters: region = North` / `Filters: none`, a chart's series values sum to the filtered total |
| AC-41 | D1 caches + heatmap pairs once + Counter in classify | `big_sales_csv`: GET charts (warm-up), then `time.perf_counter()` around GET charts `?f.region=North`: 200 and `< 1.0` s; `kpis.rows == 50000` |

## Work items without AC ids: explicit checks
- **W-1 Unreadable.sheet (gate 162)**: a workbook where one sheet fails lists `book.xlsx - <sheet>` in "Could not
  be read" and the other sheets as datasets; `Unreadable("x.csv", "empty file").sheet is None`.
- **W-2 invalid JSON (gate 162)**: `{oops` in .json and a bad line in .jsonl give `invalid JSON`; `{"a": 1}` and
  `[1, 2]` keep `not a list of records`.
- **W-3 chart items (gate 162)**: records.json country map `locations` = `["Brazil", "Japan", "France"]` (203,
  125, 68); points.tsv map3d `z_label` is `"value"` and `null` for a lat/lon-only file.
- **W-4 line endings**: `git diff --stat tests/fixtures` empty; `.gitattributes` is exactly `* text=auto`.
- **W-5 dev requirements (gate 171, done in ticket 418)**: `requirements.txt` has no `pytest` and no `httpx`
  line; `requirements-dev.txt` starts with `-r requirements.txt` and pins `pytest==9.1.1`, `httpx==0.28.1`;
  README's install line names `requirements-dev.txt`. `test_AC_23` still finds the four library pins in
  requirements.txt. QA may add a text test for these lines.

## Tests that must change with the code (name them in the tickets)
Round 4 (put each edit in the ticket that changes the behaviour; sales.csv order becomes line, histogram, bar,
donut; every XLSX gains a last `Summary` sheet):
- S1/S2 ticket: `tests/test_rules.py::test_sales_bar_and_line` L16 kinds order, L17 `line, bar = cs[:2]` (pick
  by kind), L22 the key set gains `"score"`. `test_export_xlsx.py::test_sales_download` L39 sheet list (`chart-2
  histogram`, `chart-3 bar`, `chart-4 donut`), L42 `chart_kinds` order, L49 `chart-4 histogram` -> `chart-2
  histogram`. `test_export_xlsx.py::test_scatter_and_heatmap_from_numeric_file` L130 order and L133 `sheet4.xml`
  if the heatmap moves (re-run, do not guess). `test_rules.py::test_big_map_is_sampled` and
  `test_pages.py::test_big_csv_counts_have_separators` L81 use `charts[0]` as the map3d: big.csv also has a
  histogram of `value` (score = its skew), so select the map by kind if it is no longer first.
- E1 ticket: `test_export_xlsx.py` L39 and L130 sheet lists end with `"Summary"`, L114 `["Data"]` ->
  `["Data", "Summary"]`; `test_export_pptx.py` checks on slide 0 texts, if any, gain `Filters: none`.
- Any test with a hard-coded chart order on the page (grep `data-kind`, `"chart-1"`, `[0]["kind"]`) is re-run.

Round 3:
- `tests/test_launcher_files.py:17` looks for the needle `"py -3.11"`, which L1 removes (the list holds
  `"py", "-3.11"`). Replace that needle with `"-3.11"` (or move the version checks to the AC-28/30 tests); keep
  every other needle (`FolderBrowserDialog`, `--no-index --find-links wheels`, `requirements.txt`,
  `-m app.launch`, docker lines, `exit 1`, `[switch]$Docker`).
- `tests/test_acceptance.py::test_AC_25`: its comment says a truncated sheet XML fails the whole workbook; after X1
  that is false. Update the comment; the corrupt-XML assertions go in the new `test_AC_31`.
- `tests/test_xlsx_read.py::test_broken` and `tests/test_catalog.py::test_failed_sheet_is_listed_with_its_name`
  must still pass unchanged (not-a-zip stays `not a valid xlsx` for the whole file; the monkeypatched
  `read_sheet` still gives `book.xlsx - Bad`).

Round 2 (done):
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

## Test fixtures (tests/conftest.py; round 3: `write_xlsx` takes raw sheet XML as `bytes`)
`data_dir` builds: `sales.csv`, `points.tsv`, `notes.csv`, `empty.csv`, `broken.xlsx`, `manual.pdf`,
`.hidden.csv`, `sub/records.json`, `sub/events.jsonl`, `sub/cities.geojson`, `sub/book.xlsx` (sheets `Revenue`
with Excel date cells, `Lookup`). `write_xlsx` stays hand-written: openpyxl reads it (with the harmless "no
default style" warning, which AC-23 only checks on exports). `big_csv` holds 60,000 lat/lng rows.
`make_client(folder)` sets the env and returns a TestClient. Parquet fixtures in `tests/fixtures/` (written once
by pyarrow) with CSV twins `flat.csv`, `optional.csv`. Playwright fixtures are function-scoped.
Round 4 (added by the architect): `big_sales_csv` -> folder with `sales.csv`, 200,000 rows of `date, region,
product, amount, qty` (region North/South/East/West by `i % 4`, so `f.region=North` keeps 50,000 rows; 12 x 28
dates; product 20 values; amount `i % 997`; qty 1..9), for AC-41. The hand-checked score values use `data_dir`
sales.csv. `make_client` must also clear `main._base` and `main._view` once they exist (D1 ticket).

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
10. (Round 3) Per-sheet isolation by blanking the other worksheet parts in an in-memory copy, not by calling
    openpyxl's `ExcelReader` steps by hand: public `load_workbook` stays the only entry point, so styles, shared
    strings and dates are read the way they are today, and the change stays inside `_load`. Cost: one in-memory
    zip copy per sheet read.
11. (Round 3) The version check runs on every candidate, `py` ones included: one loop, one rule (3.11-3.13), and a
    `py` launcher that maps `-3.13` to something odd is still checked. 3.14 is rejected (gate 171).
12. (Round 3) One `Fail` function for all four failure points (no Python, venv, wheels pip, online pip), so
    the cleanup, pause and exit code cannot drift apart between them.
13. (Round 3) Launcher tests are text checks: the image has no PowerShell (`which pwsh powershell` is empty,
    ticket 417), so the real run is the Board's on Windows.
14. (Round 3) AC-31 reworded rather than adding AC-32: gate 171 replaced the "log the gap" item with "build it",
    and a doc-only AC would describe behaviour that is no longer true.
15. (Round 4) Filter changes are plain GET navigations of a server-rendered page, not `pushState` + client
    re-render: the URL is the state, Back works natively, the page works without JS, and the KPI strip, chips,
    counts and dropdowns have one renderer (Jinja). Cost: a page load per change; the `_view` cache makes the
    dashboard's own API fetch a hit, and Plotly is served from the browser cache.
16. (Round 4) Column types come from the unfiltered rows; rules run on the filtered rows. Types, dropdowns and the
    date column stay put while filtering, and charts that no longer apply drop out (gate 175).
17. (Round 4) Scores are computed inside each rule, where the full pre-sampling data is, not from the chart dict:
    the dict holds a stride sample for line and scatter and bins for the histogram (PRD: full filtered rows).
18. (Round 4) Ids are renumbered after the sort, so `chart-1` is the top chart on the page, in the API, on the
    second PPTX slide and in the first XLSX chart sheet. Tests that named sheets by rule order change (listed).
19. (Round 4) Query params `f.<column>` with a prefix, not bare column names: a column named `from` or `to`
    cannot clash with the date range, and unknown params are ignored safely. Readable in a shared link.
20. (Round 4) The XLSX `Summary` sheet goes last: `Data` stays first (AC-18) and existing `sheetN.xml` positions
    of chart sheets do not move. The summary text is built once (`filters.summary`) and passed to both writers.
21. (Round 4) Speed by caching and two exact-result fixes (heatmap pairs once, distinct strings classified once),
    not by sampling for scores: the PRD fixes scores on the full filtered rows, and the measured budget fits.
    `# ponytail:` mark the `_view` cache (8 entries, memory = filtered row lists) and the typed-rows copy.
