# DataBoot: project memory

## What it is
Local web app: point it at a data folder (mounted folder or drive letter, no raw device access) and it profiles each file, picks charts by rules, and exports PPTX/XLSX with native editable charts. Windows 11 launcher (DataBoot.bat + Start-DataBoot.ps1 + venv), Dockerfile optional. Plain neutral style, system sans font, no logo, no theme toggle (OS colour preference only). Branding unchanged since gate 160. Trends are off (team setting only, gate 179).
Text allowed on pages: titles, axis labels, "N of M" counts, one-line "rule used" caption. No generated sentences. Thousands separators on counts and amounts (1,234 of 56,789) through the `num` Jinja filter, but never on identifier, temporal or year-like columns (no "2,024"): by column role, not regex (gate 181).

## Stack and layout
FastAPI + Jinja, Plotly.js served locally (app/static/vendor/plotly), world outlines from sane-topojson 4.0.0 world_110m.json (MIT) via Plotly `topojsonURL`. No external requests (AC-9, AC-58).
- app/readers.py (CSV, TSV, JSON, JSONL, GeoJSON), app/xlsx.py (openpyxl read_only reader with per-sheet isolation + xlsxwriter export + Summary sheet), app/parquet.py (pyarrow), app/catalog.py (scan, stable ids, unreadable list with `sheet` field, file inventory), app/profile.py (classify, first 10,000 rows only), app/rules.py (Explorer charts, 8-chart cap, stride sampling, `typed()`, `kpis`), app/score.py, app/filters.py, app/export.py (python-pptx), app/main.py (routes, cached `_view`, `_detected`, `_appview`, `dashboard`, `_download`, `sep`), app/launch.py.
- Round 5 apps: app/apps.py (roles, `detect`, `measures`, primary amount by name rule), app/business.py (periods, KPI cards, trends, leaderboard with Other, drill order, change table; filters `fmt`/`signed`), app/geo.py (valid coordinates, points and hexbin modes, row details, top regions, Map 3D).
- Templates: base, home, dataset, _filters, _figure (figure macro), _tables (Columns, First rows), app_explorer, app_business, app_map, app_monitoring, app_survey, _cards (spark macro). JS: app/static/js/dashboard.js (reads /app, `globalRules`, `render`, `tableToggle`/`tableOf`, `map2d`, `mapPanel`, `barCursor`). CSS: app/static/css/databoot.css. Favicon: app/static/blank.svg.
- Docs: docs/ARCHITECTURE.md (Modules, Chart contract, Exports, Round 3 launcher, Round 4 filters, Round 5 apps), DESIGN.md, PRD.md, acceptance.json (AC-1..AC-73: AC-43..58 round 5 archetypes, Business, Map, exports, global rules, offline; AC-59..73 round 6 number format, plurals, Monitoring, Survey, rule order, grain, Explorer exports).
- File types: CSV, TSV, Excel (.xlsx/.xlsm, one dataset per sheet), JSON/JSONL, Parquet, GeoJSON. .xls and unknown files go to the inventory table, no charts.
- Xlsx isolation: `_load(path, keep=None)` blanks the other worksheet parts before `load_workbook`; a corrupt sheet is listed as 'book.xlsx - <sheet>' with 'not a valid xlsx'. [gates 171, 172]
- Launcher: one `$Candidates` list (py -3.13, -3.12, -3.11, python), one `Fail` function (message, delete partial .venv, pause, exit 1), `$LASTEXITCODE` check after each pip install. Python 3.11-3.13 only. Windows PowerShell 5.1.
- Requirements: requirements.txt runtime pins only; requirements-dev.txt = `-r requirements.txt` + pytest, httpx. Nothing in app/ imports test tools.

## Three apps on one dataset page (round 5)
- `?app=explorer|business|map` picks the body; View-as links appear only when more than one app qualifies (hidden when only Explorer qualifies). Explorer output is unchanged (exports too: title and layout). Explorer charts are computed only when shown. Exports follow the shown app. [gates 179, 180]
- Primary amount = first numeric column whose name contains amount|revenue|sales|total|price|value|cost|qty|quantity (case-insensitive), else the first numeric. KPI cards = up to 3 numerics in that order. Measure picker deferred to round 6.
- Periods: grain by span (day <= 60 days, week <= 182, month <= 1096, year above). Latest full period = the one holding the last date only if that date is its last day, else the one before; previous = the one before that.
- Drill order: remaining categorical columns by distinct count ascending, ties by column order; bars at the last level are not clickable. Leaderboard = top 10 + "Other" (own trace in neutral muted grey, no pointer, clicks do nothing). A real category named "Other" is not special-cased.
- Map: valid lat/lon only; hexbin of ~40 cells across the longitude span drawn as clockwise hexagon choropleth polygons coloured by count; click a point or cell fills the side panel from the payload (no request); top regions = country column, else the categorical with fewest distinct values (>= 2), ranked by primary sum else row count, top 10 + Other; 3D view button sits in a `.map-head` row above the figure and colours by the primary numeric (Explorer map3d unchanged).
- Global chart rules: donut only for 2-5 values; bars sorted descending with a zero baseline (bars only); one y-axis; table toggle on every figure; tooltips with separators; Explorer line charts keep auto y-range (Business trends too since gate 181). Sparkline scales min..max.
- Scores ("score 0.xx" captions) show only in Explorer; Explorer bars get the same bar-click class as Business bars. [gate 181]

## Run and test
- Run: `python3 -m uvicorn app.main:app`, or `python3 -m app.launch`. Data folder env var DATABOOT_DATA.
- Tests: `python3 -m pytest -q tests/<file>.py` while working; full suite once at the end (about 550 s with 407 tests: run it once, alone, in the background and poll for a DONE marker). Browser tests (test_browser, test_filter_*, test_business_page, test_map_page, test_table_toggle, test_offline_apps, Playwright parts of test_acceptance) use Python Playwright with uvicorn on port 0 in a thread; PLAYWRIGHT_BROWSERS_PATH=/opt/playwright. See skills playwright-tests-for-chart-pages, add-page-mode-keep-old-tests-green, acceptance-tests-per-item, office-export-with-library-and-reopen-tests, windows-launcher-script-text-tests.
- Launcher tests are text checks (tests/test_launcher_files.py): no pwsh in the image.
- Shared fixtures: tests/conftest.py (data_dir, big_csv, make_client, shop and places fixtures, archetypes_dir; write_xlsx is hand-written and takes a sheet as bytes). Two fixtures that each call make_client in one test break each other. Python is 3.11.
- Temp scripts, servers and pip installs go in /tmp, never /work. No python, curl, ps, pkill: use python3 and stop servers via the Popen handle.
- openpyxl, python-pptx, xlsxwriter, pyarrow, pytest, httpx are baked into the verify image (gates 165, 172).
- AC-42: 200,000-row CSV reaches the dashboard in <= 5 s cold (Business page measured about 1.7 s); filtered charts API under 1 s (AC-41).

## Board decisions
- Exports use xlsxwriter and python-pptx; xlsx reading uses openpyxl `read_only=True`; pyarrow reads Parquet. [gates 162-164]
- Notes: 'could not read file', 'invalid JSON', 'not a valid parquet file'. Map count excludes rows with empty lat/lon. [gates 166, 167]
- Python 3.11-3.13 only. No suitable Python: "DataBoot needs Python 3.12. Install it with: winget install -e --id Python.Python.3.12", pause, exit 1. [gate 171]
- Filters/scoring: scoring only reorders; filter columns with > 50 distinct values get no dropdown or click filter; filters on different columns AND. [gate 175]
- A bar on a column filtered to one value is still drawn (toggle needs it); the donut drops out, so a donut filter is removed with its chip or "Clear filters". [gates 177, 178]
- Mechanical edits to test_acceptance.py beyond a ticket's list are accepted; sparkline min..max accepted; 3D button above the figure accepted. [gate 181]
- QA must time and report, not assume; click cross-filter on vertical bar, donut and horizontal bar with the toggle. [gate 177]
- Later (not now): Power BI export, shapefile, PDF/Word stats, SQL, measure picker.

## Round 6 apps (Survey, Monitoring) and rule order
- Evaluation order: R1 Map, R5 Survey, R2 Business, R4 Monitoring, R3 Explorer; View-as lists every app the file qualifies for (shop.csv opens as Business; a survey file with a timestamp opens as Survey). [gate 183]
- Survey (app/survey.py): whole-number 1..5/1..7 columns count as answers only when no other numeric column has an amount-style name; Likert scales agree/satisfied/likely/frequency/1-5/1-7 with full scale incl. zero counts, neutral middle grey, share printed in segments >= 8%; up to 2 numerics (age) as histograms under "Respondents"; cross-tab of the first two questions, row % to 1 decimal. [gates 183, 184]
- Monitoring (app/monitoring.py): default period 30 days, half-open windows, change = mean of period vs same-length window before ("All" = n/a); 7-point trailing mean including current point; spike z = population stdev of the previous 30 points; tiles capped at 8 with note "8 of N measures" (primary numeric first); tile Min/Max print whole when whole (`fmt`); spike label is text, not colour alone. Page figure has data-kind=monitor (line is only the export kind).
- Number format is by column role on the server (apps.plain, apps.sep, apps.plural): no separators on identifier, temporal or year-like columns in tables, side panel, tooltips, hex hover; "1 point", "1 row". Explorer line charts keep auto y-range (bars only get a zero baseline); scores only in Explorer; Explorer bars get bar-click. [gate 181, tickets 466, 471, 472]
- Exports: PPTX title slide first line is "Data overview" for EVERY Explorer export, including ?app=explorer (app/main.py:227, app/export.py:114); XLSX Summary has no app title line for Explorer. [gates 184, 187, 188, ticket 480]
- Roles: PM rewords garbled ACs (59, 62, 64-71, 73 reworded after gate 187). Docs: acceptance.json AC-1..AC-73.

## Open state at start of round 7
- Board verifies on Windows: Explorer PPTX title "Data overview"; any miss is the first round 7 ticket. [gate 188]
- Open design question: DESIGN.md tile example shows "Min 20.0 Max 60.0" but the page prints whole numbers; Board accepted whole numbers, the designer corrects the DESIGN.md example (check it is done). [gate 186]
- Suite takes about 550 s (407 tests); Board accepted this. Run the qa check once, in the background. [gate 187]
- Still not tested by agents: AC-25 corrupt-sheet isolation beyond truncated XML (gate 170 candidate), Board's own Windows launcher tests (3.12 + 3.14, Python hidden) and real Excel/PowerPoint opens. No agent action.
- Handover JSON was missing on tickets 464, 470, 474: end every reply with it.

## Pitfalls
- Chart counts: records.json gives a histogram too; a lone numeric column gives a histogram. When adding a rule, grep tests for exact chart lists and `chart-N` ids.
- Sampler: stride ceil(total/cap), so 60,000 rows show 30,000; read shown/total from the API in tests.
- Browser test rejects any head src/href that is not a served local path.
- Plotly 3D titles are WebGL pixels: fix clipping with the camera eye, test with canvas edge pixels.
- Plotly bars stay `crosshair` here: cursor is driven by classes `bar-click`/`no-pointer` from hover events. Hex rings must be clockwise and inside ±180/±90. Phone map colour bar is horizontal. Plotly date ticks ("Jan 2024") look like bare years: read page text with plots hidden.
- openpyxl read_only parses each sheet's XML at load until `<dimension>`; hand-written fixtures fail differently from xlsxwriter ones.
- Page widgets must avoid `<p>` in main (regex `<p[\s>]`, since `<polyline>` matches `<p`) and bare 4+ digit numbers (test_AC_17, test_AC_21, AC-55): use dl/label/ul and `num`. `sep` filter adds separators to numeric First rows cells.
- Typed sums are floats (7392.0): use `fmt`/`signed` in Business templates, not `num`.
- Horizontal bars (labels > 12 chars) keep labels in plot y; Explorer bars and donuts use only the first categorical column. Clicking Plotly marks needs force=True / a ring point, and expect_navigation.
- Filter inputs have ids with label for=; form submit disables empty fields (re-enabled on pageshow); a hidden `app` input keeps the mode on Apply.
- Dataclass used as lru_cache key needs unsafe_hash=True with list fields compare=False.
- Tests that call run() must monkeypatch.setenv first. Bash heredocs and compound python -c calls can be blocked: use Write/Edit/Grep and run python3 on a file.
- Board rulings on a shared string: grep all tests (test_acceptance siblings, test_export*.py) for the old value; see skill change-shared-label-after-board-ruling.
- Before a ticket that redoes or tests earlier work, grep templates, CSS and test literals: it may already be done.
