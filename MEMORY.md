# DataBoot: project memory

## What it is
Local web app: point it at a data folder (mounted folder or drive letter, no raw device access) and it profiles each file, picks charts by rules, and exports PPTX/XLSX with native editable charts. Windows 11 launcher (DataBoot.bat + Start-DataBoot.ps1 + venv), Dockerfile optional. Plain neutral style, system sans font, no logo, no theme toggle (OS colour preference only). Branding unchanged since gate 160.
Text allowed on pages: titles, axis labels, "N of M" counts, one-line "rule used" caption. No generated sentences. Thousands separators everywhere (1,234 of 56,789) through the `num` Jinja filter.

## Stack and layout
FastAPI + Jinja, Plotly.js served locally (app/static/vendor/plotly), world outlines from sane-topojson 4.0.0 world_110m.json (MIT) via Plotly `topojsonURL`. No external requests (AC-9).
- app/readers.py (CSV, TSV, JSON, JSONL, GeoJSON), app/xlsx.py (openpyxl read_only reader with per-sheet isolation + xlsxwriter export + Summary sheet), app/parquet.py (pyarrow), app/catalog.py (scan, stable ids, unreadable list with `sheet` field, file inventory), app/profile.py (classify, first 10,000 rows only), app/rules.py (charts, 8-chart cap, stride sampling, `typed()`, `kpis`), app/score.py (interest score), app/filters.py (parse, apply, options, labels), app/export.py (python-pptx), app/main.py (routes, shared cached `_view(d, filters)`, `_base`, `dashboard`, `_download`), app/launch.py.
- Templates: base, home, dataset. JS: app/static/js/dashboard.js. CSS: app/static/css/databoot.css. Favicon: app/static/blank.svg.
- Docs: docs/ARCHITECTURE.md (Modules, Chart contract, Exports, Decisions, notes table, "Round 3: launcher design", "Round 4: filters"), DESIGN.md, PRD.md, acceptance.json (AC-1..AC-42; AC-14..21 were G-1..G-7 plus thousands, AC-22..27 gate 166/167 items, AC-28..31 round 3 launcher and per-sheet isolation, AC-32..42 round 4: score order, filters, KPIs, filtered exports, cross-filter, 1 s filter target, 5 s first load).
- Round 4 features: every chart gets a rounded `score` (charts() sorts by -score after the 8-chart cut; degenerate inputs score 0); server-side filters via query string `f.<column>=v&from=&to=` (one value per column, AND; categorical = <= 50 distinct, else no dropdown/click filter); KPI strip (rows, columns, missing %, sums) follows the filters; chips with remove links plus "Clear filters"; exports follow the filters (XLSX Summary sheet last, "Filters: none"; PPTX title "Rows: N of M, C columns" when filtered, "Rows: M" otherwise); dashboard.js forwards the query string to the charts API and cross-filters on bar/donut click (second click on the active bar removes the filter). Table "First rows" stays below all charts, no score.
- File types: CSV, TSV, Excel (.xlsx/.xlsm, one dataset per sheet), JSON/JSONL, Parquet, GeoJSON. .xls and unknown files go to the inventory table (type, size, date), no charts.
- Chart kinds: map3d (Plotly 3D scatter, not deck.gl; z axis and colorbar titled from `z_label`), line, bar (sum per category, count when no numeric), donut (2-6 distinct values), histogram (labels "a to b", 6 significant digits), scatter, correlation heatmap, country map (sorted by value). Booleans are categorical.
- Pages: table captions are `<caption><h2>` at `--t-md`; column headers keep real case (no CSS uppercase); Plotly modebar always visible and Tab-reachable (top margin for it); map3d camera pulled back and bottom margin 40 so axis titles are not clipped.
- Xlsx isolation: `_load(path, keep=None)` copies the zip in memory and blanks the other worksheet parts before `load_workbook`; `_part()` finds a sheet's part via `ReadOnlyWorksheet._worksheet_path`. catalog.scan already splits per sheet. A corrupt sheet is listed as 'book.xlsx - <sheet>' with 'not a valid xlsx'; a sheet part missing from the zip is out of scope. [gates 171, 172]
- Launcher: one `$Candidates` list (py -3.13, -3.12, -3.11, python), version check on each, one `Fail` function (message, delete partial .venv, Read-Host pause, exit 1) used for no Python, venv creation and both pip installs, each with a `$LASTEXITCODE` check on the next line. Only 3.11-3.13 accepted. Runs under Windows PowerShell 5.1.
- Requirements: requirements.txt holds runtime pins only; requirements-dev.txt = `-r requirements.txt` + pytest, httpx; README names both. Nothing in app/ imports test tools (tests/test_requirements_split.py).

## Run and test
- Run: `python3 -m uvicorn app.main:app`, or `python3 -m app.launch`. Data folder env var DATABOOT_DATA.
- Tests: `python3 -m pytest -q tests/<file>.py` while working; full suite once at the end (about 110 s at 156 tests in round 3; more now, run it in the background). Browser tests (tests/test_browser.py, test_filter_ui.py, test_filter_browser.py, and Playwright in test_AC_22/24/27/39) use Python Playwright with uvicorn on port 0 in a thread; PLAYWRIGHT_BROWSERS_PATH=/opt/playwright. See skills playwright-tests-for-chart-pages, office-export-with-library-and-reopen-tests, windows-launcher-script-text-tests.
- Launcher tests are text checks (tests/test_launcher_files.py): no pwsh or powershell in the image, so the script itself is never run by agents.
- Shared fixtures: tests/conftest.py (data_dir, big_csv, make_client; write_xlsx is hand-written, takes a sheet as bytes written verbatim, and makes openpyxl warn "no default style"). Python is 3.11 (no tarfile filter=).
- Temp scripts, servers and pip installs go in /tmp, never /work. No python, curl, ps, pkill: use python3 and stop servers via the Popen handle.
- openpyxl, python-pptx, xlsxwriter, pyarrow, pytest, httpx are baked into the verify image (gates 165, 172); runtime ones are pinned in requirements.txt, never vendored (test_AC_23).

## Board decisions
- Exports use xlsxwriter and python-pptx; xlsx reading uses openpyxl `read_only=True`; pyarrow reads Parquet. [gates 162-164]
- Notes: 'could not read file', 'invalid JSON' (also broken GeoJSON), 'not a valid parquet file'. Map count excludes rows with empty lat/lon; histogram with min = max is documented. [gates 166, 167]
- Launcher script is Start-DataBoot.ps1. AC-6 reads "Plotly 3D scatter". [gate 165]
- Python 3.11-3.13 only, 3.14 rejected until all pinned deps ship wheels for it. No suitable Python: "DataBoot needs Python 3.12. Install it with: winget install -e --id Python.Python.3.12", pause, exit 1. [gate 171]
- Per-sheet isolation (AC-25 idea) was built in round 3, not just logged; Board gate 171 overrode the PRD. [gates 170, 171]
- Test literals for the captions in tests/test_acceptance.py (L186, 198, 274, 308, 349) were allowed to change to the h2 form; no other edits to that file by build tickets. [gates 167, 168]
- Overlapping 3D tick labels at 375px are acceptable; pixel-ink check on the canvas edge rows is the accepted clipping test. [gate 168]
- Ticket 403 was superseded by 412 and closed. [gate 169]
- Later (not now): Power BI export, shapefile, PDF/Word stats, SQL.

- Round 4 filters/scoring: scoring only reorders; filter columns with > 50 distinct values get no dropdown or click filter; filters on different columns AND. [gate 175]
- A bar chart on a column filtered to one value is still drawn (the toggle needs it); the donut drops out, so a donut filter is removed with its chip or "Clear filters" (bar-only toggle accepted). DESIGN.md "Cross-filter" is the accepted text. [gates 177, 178]
- First load: a 200,000-row CSV reaches the dashboard in <= 5 s cold (AC-42); classify the first 10,000 rows only, charts and KPIs use all rows (measured about 2.4-2.7 s). Filtered charts API under 1 s on the test image (AC-41). [gate 176, tickets 432, 438]
- Trends are off (team setting only). Maps/heatmap at half width were reviewed and left as is. [gates 175, 176, ticket 437]
- QA must time and report, not assume: AC-42 number, plots drawn from filtered data match "N of M", click cross-filter on vertical bar, donut and horizontal bar (labels > 12 chars) with the toggle. [gate 177]

## Open state at end of round 4
- PM fixes the garbled wording of AC-38 and AC-40 in acceptance.json at the start of round 5 (tests follow gates 175/176). [gate 178, ticket 438]
- The Board still plans to test the launcher on Windows (3.12 + 3.14, and with Python hidden) and open exports in real Excel/PowerPoint. No agent action. [gates 172, 173]
- Round 3 QA ticket 424 ended without the handover JSON; write the JSON before long runs. [gate 174]
- `.gitattributes` (`* text=auto`) and the line-ending revert of tests/fixtures/flat.csv and optional.csv were decided in gate 165; check git before assuming they are done.

## Pitfalls
- Chart counts: records.json gives a histogram too; a lone numeric column gives a histogram. When adding a rule, grep tests for exact chart lists and `chart-N` ids. Adding a key to a chart dict needs no change in main.py (/charts returns the dicts as they are).
- Sampler: stride ceil(total/cap), so 60,000 rows show 30,000; read shown/total from the API in tests.
- Browser test rejects any head src/href that is not a served local path (no data: favicon).
- Plotly 3D titles are WebGL pixels: fix clipping with the camera eye, test with canvas edge pixels.
- openpyxl read_only still parses each sheet's XML at load until `<dimension>`; hand-written fixtures without it fail differently from xlsxwriter ones.
- Chart order changed in round 4 (heatmap can come first): hard-coded kinds lists and sheet names in test_export_xlsx, test_rules and friends follow the real output. Page widgets must avoid `<p>` in main and bare 4+ digit numbers (test_AC_17, test_AC_21): use dl/label/ul and `num`.
- Horizontal bars (labels > 12 chars) keep labels in plot y; bars and donuts use only the first categorical column. Clicking Plotly marks needs force=True / a ring point, and expect_navigation (see playwright skill).
- Filter select/date inputs have ids with label for=; form submit disables empty fields (re-enabled on pageshow).
- Dataclass used as lru_cache key needs unsafe_hash=True with list fields compare=False.
- Tests that call run() must monkeypatch.setenv first so the environment is restored.
- Bash heredoc batches and compound python -c/grep calls can be blocked by the deny list: use Write, Grep and Glob, and run python3 on a file.
- Before a ticket that redoes earlier work or tests earlier work, grep templates, CSS, requirements and test literals: it may already be done (403, 412 and 423 needed little or no code).
