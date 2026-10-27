# DataBoot: project memory

## What it is
Local web app: point it at a data folder (mounted folder or drive letter, no raw device access) and it profiles each file, picks charts by rules, and exports PPTX/XLSX with native editable charts. Windows 11 launcher (.bat + PowerShell + venv), Dockerfile optional. Plain neutral style, system sans font, no logo, no theme toggle (OS colour preference only).
Text allowed on pages: titles, axis labels, "N of M" counts, one-line "rule used" caption. No generated sentences. Thousands separators everywhere (1,234 of 56,789) through the `num` Jinja filter.

## Stack and layout
FastAPI + Jinja, Plotly.js served locally (app/static/vendor/plotly), world outlines from sane-topojson 4.0.0 world_110m.json (MIT) via Plotly `topojsonURL`. No external requests (AC-9).
- app/readers.py (CSV, TSV, JSON, JSONL, GeoJSON), app/xlsx.py (openpyxl read_only reader + xlsxwriter export), app/parquet.py (pyarrow), app/catalog.py (scan, stable ids, unreadable list with `sheet` field, file inventory), app/profile.py (classify), app/rules.py (charts, 8-chart cap, stride sampling), app/export.py (python-pptx), app/main.py (routes, `_charts`, `_download`), app/launch.py.
- Templates: base, home, dataset. JS: app/static/js/dashboard.js. CSS: app/static/css/databoot.css. Favicon: app/static/blank.svg.
- Docs: docs/ARCHITECTURE.md (Modules, Chart contract, Exports, Decisions, notes table), DESIGN.md, PRD.md, acceptance.json (AC-1..AC-27; AC-14..21 were G-1..G-7 plus thousands, AC-22..27 are the gate 166/167 items).
- File types: CSV, TSV, Excel (.xlsx/.xlsm, one dataset per sheet), JSON/JSONL, Parquet, GeoJSON. .xls and unknown files go to the inventory table (type, size, date), no charts.
- Chart kinds: map3d (Plotly 3D scatter, not deck.gl; z axis and colorbar titled from `z_label`), line, bar (sum per category, count when no numeric), donut (2-6 distinct values), histogram (labels "a to b", 6 significant digits), scatter, correlation heatmap, country map (sorted by value). Booleans are categorical.
- Pages: table captions are `<caption><h2>` at `--t-md`; column headers keep real case (no CSS uppercase); Plotly modebar always visible and Tab-reachable (top margin for it); map3d camera pulled back and bottom margin 40 so axis titles are not clipped.

## Run and test
- Run: `python3 -m uvicorn app.main:app`, or `python3 -m app.launch`. Data folder env var DATABOOT_DATA.
- Tests: `python3 -m pytest -q tests/<file>.py` while working; full suite once at the end (about 110 s, 139 passed at end of round 2). Browser tests (tests/test_browser.py, and Playwright in test_AC_22/24/27) use Python Playwright with uvicorn on port 0 in a thread; PLAYWRIGHT_BROWSERS_PATH=/opt/playwright. See skills playwright-tests-for-chart-pages and office-export-with-library-and-reopen-tests.
- Shared fixtures: tests/conftest.py (data_dir, big_csv, make_client; write_xlsx stays hand-written and makes openpyxl warn "no default style"). Python is 3.11 (no tarfile filter=).
- Temp scripts, servers and pip installs go in /tmp, never /work. No python, curl, ps, pkill: use python3 and stop servers via the Popen handle.
- openpyxl, python-pptx, xlsxwriter, pyarrow are baked into the verify image (gate 165); all four are pinned in requirements.txt, never vendored (test_AC_23).

## Board decisions
- Exports use xlsxwriter and python-pptx; xlsx reading uses openpyxl `read_only=True`; pyarrow reads Parquet. ARCHITECTURE.md no longer says "standard library only". [gates 162-164]
- Notes: 'could not read file', 'invalid JSON' (also broken GeoJSON), 'not a valid parquet file'. Map count excludes rows with empty lat/lon; histogram with min = max is documented. [gates 166, 167]
- Launcher script is Start-DataBoot.ps1. AC-6 reads "Plotly 3D scatter". [gate 165]
- Test literals for the captions in tests/test_acceptance.py (L186, 198, 274, 308, 349) were allowed to change to the h2 form; no other edits to that file by build tickets. [gates 167, 168]
- Overlapping 3D tick labels at 375px are acceptable; pixel-ink check on the canvas edge rows is the accepted clipping test. [gate 168]
- Ticket 403 was superseded by 412 and closed. [gate 169]
- Later (not now): Power BI export, shapefile, PDF/Word stats, SQL.

## Open state at end of round 2
- Round 3 candidate: per-sheet isolation for a corrupt sheet XML (today the whole workbook is 'not a valid xlsx'; only an empty or header-less sheet is split out as 'file - sheet'). Board said not needed in round 2. [gate 170]
- Exports have not been opened in real Excel or PowerPoint; the Board will do that on Windows. No agent action.
- `.gitattributes` (`* text=auto`) and the line-ending revert of tests/fixtures/flat.csv and optional.csv were decided in gate 165; check git before assuming they are done.

## Pitfalls
- Chart counts: records.json gives a histogram too; a lone numeric column gives a histogram. When adding a rule, grep tests for exact chart lists and `chart-N` ids. Adding a key to a chart dict needs no change in main.py (/charts returns the dicts as they are).
- Sampler: stride ceil(total/cap), so 60,000 rows show 30,000; read shown/total from the API in tests.
- Browser test rejects any head src/href that is not a served local path (no data: favicon).
- Plotly 3D titles are WebGL pixels: fix clipping with the camera eye, test with canvas edge pixels.
- Dataclass used as lru_cache key needs unsafe_hash=True with list fields compare=False.
- Tests that call run() must monkeypatch.setenv first so the environment is restored.
- Bash heredoc batches and compound python -c/grep calls can be blocked by the deny list: use Write, Grep and Glob, and run python3 on a file.
- Before a ticket that redoes earlier work, grep templates, CSS and test literals: it may already be done (403 and 412 ended with no code change).
