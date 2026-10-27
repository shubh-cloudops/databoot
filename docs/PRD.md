# PRD: DataBoot, an offline data-to-dashboard bootstrapper (round 3)

Round 3 fixes the Windows launcher bug the Board found on Windows 11 (docs/IDEA.md, docs/BRIEF.md):
Start-DataBoot.ps1 hardcodes `py -3.11`, so on a machine with Python 3.12 and 3.14 the venv is not created and the
script then crashes on `.venv\Scripts\python.exe`. It also records the AC-25 corrupt-sheet gap from round 2 QA
(gate 170). No page, chart, export or style changes; everything below "Product today" stays as it is.

## Problem
Owners of data (a pen drive, a disk or a folder of spreadsheets) cannot see what is in it without an analyst.
DataBoot reads the files and at once shows datasets, charts and a 3D map, fully offline, with no AI: fixed rules
look at the column types and pick the visuals. Charts can be taken away as editable XLSX and PPTX files.
This round: the one-click start must work on any Windows machine with Python 3.11, 3.12 or 3.13 installed, and
must say clearly what went wrong instead of crashing with a closed window.

## Users
- **Data owner (client)**: non-technical; a Windows 11 laptop and a folder or drive of files. Starts the app with
  one click and looks.
- **Operator**: installs it once on the client's machine; may have several Python versions installed.

## Product today (built in rounds 1 and 2, kept)
1. Started on one folder (mounted folder or drive letter, no raw device access).
2. Scans it and its subfolders: CSV, TSV, Excel (.xlsx/.xlsm, one dataset per sheet), JSON/JSONL, GeoJSON and
   Parquet become datasets; .xls and unknown files go to an "Other files" inventory (type, size, date).
3. Classifies every column as geospatial, temporal, categorical, numerical or other and saves the mapping as JSON.
4. Rules pick at most 8 charts: Plotly 3D scatter map, line, bar, donut, histogram, scatter, correlation heatmap,
   country map. Each chart has a one-line "rule used" caption and an "N of M" count.
5. Exports each dataset as XLSX (xlsxwriter) and PPTX (python-pptx) with native, editable charts.
6. Accessible tables (h2 captions, original-case headers) and an always-visible chart tool bar.
7. Launcher: DataBoot.bat + Start-DataBoot.ps1 (venv, or `-Docker`); Dockerfile optional.

## User stories
### Must (rounds 1 and 2, kept)
- M1. I see every dataset in the folder listed with name, sheet, rows and columns, offline (AC-1, AC-14).
- M2. I open a dataset and see its column types, its first 20 rows and the charts the rules pick
  (AC-2..AC-8, AC-16, AC-27).
- M3. Every asset is served by the app itself (AC-9); large files are downsampled with an "N of M" count (AC-10).
- M4. One launcher command opens the dashboard (AC-11, AC-13).
- M5. I download a dataset as XLSX or PPTX with native, editable charts (AC-18, AC-23).
- M6. Tables and the chart tool bar work with keyboard and screen reader (AC-22, AC-24).

### Must (round 3)
- M7. As an operator on a machine with Python 3.12 and 3.14 (no 3.11), I double-click DataBoot.bat and the
  launcher creates the venv with the newest Python from 3.11 to 3.13 it finds, trying `py -3.13`, `py -3.12`,
  `py -3.11`, then `python` only if its version is 3.11 to 3.13 (AC-28).
- M8. As an operator, when venv creation or a pip install fails (or no suitable Python is found), I see a clear
  message saying what failed, the partial `.venv` is removed so the next run starts clean, the window stays open
  until I press a key, and the script exits with code 1 (AC-29).
- M9. As the team, a test fails if the launcher goes back to a single hardcoded Python version (AC-30).

### Should
- S1. Unreadable, empty or undecodable files are listed with a reason, and the rest still works (AC-12, AC-20,
  AC-25, AC-26).
- S2. Other files are listed in an inventory with type, size and date (AC-15).
- S3. Numbers use thousands separators (AC-21); the product is named DataBoot (AC-19).
- S4. A workbook with one corrupt sheet XML still lists its other sheets; the corrupt one is listed under "Could
  not be read" with its sheet name (AC-31; Board gate 171 chose to build this, not only log it).

### Could
- C1. Pick a different folder from the home page without restarting.
- C2. (Moved to S4 by gate 171.)

## Out of scope
- Python 3.14 or older than 3.11; changes to DataBoot.bat, the Dockerfile, the `-Docker` path or other platforms.
- Any page, chart, export, template, CSS or JS change; new branding, logo or theme toggle.
- Power BI export, shapefile, PDF/Word stats, SQL (Board: later). Any AI, internet access, accounts.

## Constraints
- Python candidates in order: `py -3.13`, `py -3.12`, `py -3.11`, then `python` with a version check
  (`sys.version_info` between 3.11 and 3.13). The first that runs is used to create `.venv`.
- `$LASTEXITCODE` is checked after every native command in the venv path: venv creation and each pip install
  (wheels and online). On failure: `Write-Host` a message naming the step, `Remove-Item -Recurse -Force .venv`
  if it exists, a pause (e.g. `Read-Host "Press Enter to close"`), `exit 1`. No Python found uses the same path.
- Earlier launcher behaviour stays: folder dialog, folder check, `-Docker` branch, wheels offline install,
  `.venv\Scripts\python.exe -m app.launch $Folder`.
- The test image has no PowerShell: launcher tests are text checks on Start-DataBoot.ps1 (order of candidates,
  checks after each native command, cleanup, pause, exit 1). tests/test_launcher_files.py:17 needs the
  `"py -3.11"` needle replaced if the script builds the command from a version list.
- Tests keep running without Docker, Office, a GPU, PowerShell or a real drive.

## Branding
No business website capture and no docs/brand/ folder: docs/reference/ holds captures of deck.gl and
unstructured.io, third-party libraries named in the round 1 idea, not the client's site. The Board chose
(gate 160): name DataBoot, plain neutral style, system sans font, no logo, blank SVG favicon. Unchanged.
