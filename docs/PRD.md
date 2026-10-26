# PRD: DataBoot, an offline data-to-dashboard bootstrapper (round 2)

Round 2 applies the Board's suggestions (docs/IDEA.md, gate 164): Office exports and xlsx reading move to real
libraries, three small accessibility fixes, and the acceptance list catches up with what round 1 built.
Nothing new is built; everything below "Product today" stays as it is.

## Problem
Owners of data (a pen drive, a disk or a folder of spreadsheets) cannot see what is in it without an analyst.
DataBoot reads the files and at once shows datasets, charts and a 3D map, fully offline, with no AI: fixed rules
look at the column types and pick the visuals. Charts can be taken away as editable XLSX and PPTX files.

## Users
- **Data owner (client)**: non-technical; a Windows 11 laptop and a folder or drive of files. Starts the app with
  one click and looks.
- **Operator**: installs it once on the client's machine.

## Product today (built in round 1, kept)
1. Started on one folder (mounted folder or drive letter, no raw device access).
2. Scans it and its subfolders: CSV, TSV, Excel (.xlsx/.xlsm, one dataset per sheet), JSON/JSONL, GeoJSON and
   Parquet become datasets; .xls and unknown files go to an "Other files" inventory (type, size, date).
3. Classifies every column as geospatial, temporal, categorical, numerical or other (booleans are categorical)
   and saves the mapping as JSON.
4. Rules pick at most 8 charts: Plotly 3D scatter map, line, bar, donut, histogram, scatter, correlation heatmap,
   country map. Each chart has a one-line "rule used" caption and an "N of M" count.
5. Exports each dataset as XLSX and PPTX with native, editable charts.
6. Launcher: DataBoot.bat + Start-DataBoot.ps1 (venv); Dockerfile optional.

## User stories
### Must (round 1, kept)
- M1. I see every dataset in the folder listed with name, sheet, rows and columns, offline (AC-1, AC-14).
- M2. I open a dataset and see its column types, its first 20 rows and the charts the rules pick
  (AC-2..AC-8, AC-16).
- M3. Every asset is served by the app itself (AC-9); large files are downsampled with an "N of M" count (AC-10).
- M4. One launcher command opens the dashboard (AC-11, AC-13).
- M5. I download a dataset as XLSX or PPTX and the charts in it are native, editable charts (AC-18).

### Must (round 2)
- M6. As an operator, the exports and the xlsx reader are built on xlsxwriter, python-pptx and openpyxl
  (read_only=True), listed pinned in requirements.txt with pyarrow, so the files open cleanly in Office (AC-23).
- M7. As a keyboard or screen-reader user, each table's title is an h2 heading (AC-22) and the chart tool bar is
  visible without hovering, so I can reach its buttons with Tab (AC-24).
- M8. As a data owner, table column headers show the real column names as written in my file, not upper-cased
  (AC-22).

### Should
- S1. Unreadable, empty or undecodable files are listed with a reason, and the rest still works (AC-12, AC-20).
- S2. Other files are listed in an inventory with type, size and date (AC-15).
- S3. Numbers on the pages use thousands separators (AC-21); the product is named DataBoot (AC-19).

### Could
- C1. Pick a different folder from the home page without restarting.

## Out of scope
- New features, pages, chart kinds or export formats; any use of pyarrow beyond reading Parquet.
- Power BI export, shapefile, PDF/Word stats, SQL (Board: later).
- Any AI or language model, generated sentences, internet access, accounts.
- New branding, logo or theme toggle.

## Constraints
- Fully offline: no request leaves the machine.
- requirements.txt pins xlsxwriter==3.3.0, python-pptx==1.0.2, openpyxl==3.1.5, pyarrow==26.0.0; no vendored
  libraries. ARCHITECTURE.md drops "standard library only".
- Exports keep the round 1 layout: XLSX first sheet "Data" with the column names as header plus one sheet per
  chart; PPTX one title slide plus one slide per chart.
- Plotly config `displayModeBar: true` (was "hover"); DESIGN.md is updated to match.
- `.gitattributes` holds `* text=auto`; tests/fixtures/flat.csv and optional.csv go back to their committed bytes.
- Tests keep running without Docker, Office, a GPU or a real drive; QA renames test_G_* to the new AC ids.

## Branding
No business website capture and no docs/brand/ folder: docs/reference/ holds captures of deck.gl and
unstructured.io, third-party libraries named in the round 1 idea, not the client's site. The Board chose
(gate 160): name DataBoot, plain neutral style, system sans font, no logo, blank SVG favicon. Unchanged.
