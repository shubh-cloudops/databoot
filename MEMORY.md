# DataBoot: project memory

## What it is
Local web app: point it at a data folder (mounted folder or drive letter, no raw device access) and it profiles each file, picks charts by rules, and exports PPTX/XLSX with native editable charts. Windows 11 launcher (.bat + PowerShell + venv), Dockerfile optional. Plain neutral style, system sans font, no logo, no theme toggle (OS colour preference only).
Text allowed on pages: titles, axis labels, "N of M" counts, one-line "rule used" caption. No generated sentences. Thousands separators everywhere (1,234 of 56,789) through the `num` Jinja filter.

## Stack and layout
FastAPI + Jinja, Plotly.js served locally (app/static/vendor/plotly), world outlines from sane-topojson 4.0.0 world_110m.json (MIT) via Plotly `topojsonURL`. No external requests (AC-9).
- app/readers.py (CSV, TSV, JSON, JSONL, GeoJSON), app/xlsx.py (xlsx read and export writer), app/parquet.py, app/catalog.py (scan, stable ids, unreadable list, file inventory), app/profile.py (classify), app/rules.py (charts, 8-chart cap, stride sampling), app/export.py (pptx), app/main.py (routes, `_charts`, `_download`), app/launch.py.
- Templates: base, home, dataset. JS: app/static/js/dashboard.js. CSS: app/static/css/databoot.css. Favicon: app/static/blank.svg.
- Docs: docs/ARCHITECTURE.md (Modules, Chart contract, Exports, Decisions), DESIGN.md, PRD.md, acceptance.json (AC-1..AC-13, G-1..G-7 have no ids yet).
- File types: CSV, TSV, Excel (.xlsx/.xlsm, one dataset per sheet), JSON/JSONL, Parquet, GeoJSON. .xls and unknown files go to the inventory table (type, size, date), no charts.
- Chart kinds: map3d (Plotly 3D scatter, not deck.gl), line, bar (sum per category, count when no numeric), donut (2-6 distinct values), histogram, scatter, correlation heatmap, country map. Booleans are categorical.

## Run and test
- Run: `python3 -m uvicorn app.main:app`, or `python3 -m app.launch`. Data folder env var DATABOOT_DATA.
- Tests: `python3 -m pytest -q tests/<file>.py` while working; full suite once at the end (about 65 s, 134 passed, 2 skipped). Browser tests (tests/test_browser.py) use Python Playwright with uvicorn on port 0 in a thread; PLAYWRIGHT_BROWSERS_PATH=/opt/playwright. See skills playwright-tests-for-chart-pages and office-export-with-library-and-reopen-tests.
- Shared fixtures: tests/conftest.py (data_dir, big_csv, make_client). Python is 3.11 (no tarfile filter=).
- Temp scripts, servers and pip installs go in /tmp, never /work (pip from /work leaves wheels in the repo).

## Board decisions (gates 160-164)
- Exports must use xlsxwriter (XLSX) and python-pptx (PPTX); xlsx reading uses openpyxl `read_only=True`; pyarrow is a runtime dependency. All pinned in requirements.txt, never vendored. ARCHITECTURE.md must drop "standard library only".
- Charts: country map sorted by value like bars; map3d z axis and colorbar titled with the column name; map count excludes rows with empty lat/lon; histogram with min = max is documented.
- Accessibility: table captions are h2; Plotly modebar always visible and keyboard reachable; column headers show real names (remove CSS uppercase).
- Launcher script is Start-DataBoot.ps1 (not Start-DataOS.ps1). AC-6 reads "Plotly 3D scatter".
- Notes in ARCHITECTURE.md: 'could not read file', 'invalid JSON', 'not a valid parquet file'; unreadable entries carry a sheet field.
- Add `.gitattributes` with `* text=auto` and revert line-ending changes in tests/fixtures/flat.csv and optional.csv.
- Later (not now): Power BI export, shapefile, PDF/Word stats, SQL.

## Open state at end of round 1 (parked)
- Ticket 389: tests/test_acceptance.py::test_G_5 fails with ModuleNotFoundError (openpyxl, python-pptx not installed in the verify environment; check.py never installs requirements.txt). The app code passes with PYTHONPATH pointing at a /tmp install. Needs the orchestrator or Board to provide the libraries.
- Not yet done from gates 162-164: exports still use the hand-written OOXML in app/xlsx.py and app/export.py; xlsx reader is zipfile-based; captions h2, modebar always visible, header casing, .gitattributes.
- PM still owes: AC ids for G-1..G-7, reword AC-13 and AC-6; QA then renames test_G_* to match.
- Exports were never opened in Excel or PowerPoint (not installed).

## Pitfalls
- Chart counts: records.json gives a histogram too; a lone numeric column gives a histogram. When adding a rule, grep tests for exact chart lists and `chart-N` ids.
- Sampler: stride ceil(total/cap), so 60,000 rows show 30,000; read shown/total from the API in tests.
- Browser test rejects any head src/href that is not a served local path (no data: favicon).
- Dataclass used as lru_cache key needs unsafe_hash=True with list fields compare=False.
- Tests that call run() must monkeypatch.setenv first so the environment is restored.
- Bash heredoc batches get blocked by the deny list: use Write and run python3 on the file.
