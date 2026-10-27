# PRD: DataBoot, an offline data-to-dashboard bootstrapper (round 4)

Round 4 makes the dashboard assemble itself (docs/IDEA.md, docs/BRIEF.md): every chart gets a fixed-rule interest
score, the scores set the order and layout, a KPI strip sits at the top, and filters (dropdowns, a date range and
click-to-filter on bars and donut slices) work server-side, are kept in the URL and carry into the exports.
No AI, offline, no new dependencies. Everything listed under "Product today" stays as it is.

## Problem
Owners of data (a pen drive, a disk or a folder of spreadsheets) cannot see what is in it without an analyst.
DataBoot reads the files and at once shows datasets, charts and a 3D map, fully offline, with no AI: fixed rules
look at the column types and pick the visuals. Charts can be taken away as editable XLSX and PPTX files.
This round: today the charts come in a fixed order whatever the data says, and the owner cannot narrow the data
down. The most telling chart should come first and largest, the headline numbers should be on top, and the owner
should be able to slice by category or date and take that slice away as XLSX/PPTX.

## Users
- **Data owner (client)**: non-technical; a Windows 11 laptop and a folder or drive of files. Starts the app with
  one click and looks; may share a filtered dashboard link with a colleague on the same machine or network.
- **Operator**: installs it once on the client's machine.

## Product today (built in rounds 1 to 3, kept)
1. Started on one folder (mounted folder or drive letter, no raw device access).
2. Scans it and its subfolders: CSV, TSV, Excel (.xlsx/.xlsm, one dataset per sheet, per-sheet isolation), JSON/JSONL,
   GeoJSON and Parquet become datasets; .xls and unknown files go to an "Other files" inventory (type, size, date).
3. Classifies every column as geospatial, temporal, categorical, numerical or other and saves the mapping as JSON.
4. Rules pick at most 8 charts in a fixed order: Plotly 3D scatter map, country map, line, bar, donut, histogram,
   scatter, correlation heatmap (app/rules.py `charts`). Each chart has a one-line "rule used" caption and an
   "N of M" count. The page then shows the Columns table and the First rows table.
5. Exports each dataset as XLSX (xlsxwriter, first sheet "Data") and PPTX (python-pptx, title slide + one slide per
   chart) with native, editable charts.
6. Accessible tables (h2 captions, original-case headers) and an always-visible chart tool bar.
7. Launcher: DataBoot.bat + Start-DataBoot.ps1 (venv picks Python 3.13/3.12/3.11, clean failure), Dockerfile optional.

## User stories
### Must (rounds 1 to 3, kept)
- M1. I see every dataset in the folder listed with name, sheet, rows and columns, offline (AC-1, AC-14).
- M2. I open a dataset and see its column types, its first 20 rows and the charts the rules pick
  (AC-2..AC-8, AC-16, AC-27).
- M3. Every asset is served by the app itself (AC-9); large files are downsampled with an "N of M" count (AC-10).
- M4. One launcher command opens the dashboard (AC-11, AC-13, AC-28..AC-30).
- M5. I download a dataset as XLSX or PPTX with native, editable charts (AC-18, AC-23).
- M6. Tables and the chart tool bar work with keyboard and screen reader (AC-22, AC-24).

### Must (round 4)
- M7. Interest score. As a data owner, every chart carries a score from 0 to 1 computed by a fixed rule, so the
  same data always gives the same scores (AC-32):
  line = |Spearman rho| of the plotted value against time; bar and donut = Gini coefficient of the category totals
  the chart draws; scatter = |Pearson r| of its two columns; histogram = min(1, |skew| / 3); heatmap = largest
  off-diagonal |r|; 3D map and country map = 0.6. Fewer than 2 usable values, or constant values, give 0.
- M8. Order and layout. Charts are shown from highest score to lowest; ties keep the fixed chart order above. The
  first chart spans the full width; the rest sit in a 2-column grid, 1 column on phones. The First rows table stays
  below every chart (AC-33, AC-34).
- M9. Score in the caption. Each rule caption ends with the score, for example
  "Rule: temporal date + numerical sales: line, sum per date · score 0.82" (AC-35).
- M10. KPI strip. At the top of the dashboard I see rows, columns, % missing, then the sum of each of the first 3
  numerical columns, with thousands separators; it reflects the active filters (AC-36).
- M11. Filters. I get one dropdown per categorical column (at most 50 distinct values, which AC-3 already ensures)
  and a from/to date range when the dataset has a temporal column. Filtering is done by the server through the
  charts route's query parameters; every chart, count and KPI changes (AC-37).
- M12. Filter state in the URL. The page URL holds the filters: opening a copied URL shows the same filtered view,
  the browser Back button returns to the previous filter state, and "Clear filters" returns to the unfiltered
  view (AC-38).
- M13. Cross-filter. Clicking a bar or a donut slice sets that category as the filter on its column and redraws
  every chart and the KPI strip; clicking the active bar or slice again removes that filter (AC-39, gate 175).
  Each active filter shows as a removable chip next to "Clear filters" (AC-38, gate 175).
- M14. Filtered exports. XLSX and PPTX downloads hold only the filtered rows; the PPTX title slide and a "Summary"
  sheet in the XLSX list the active filters, or say "Filters: none" (AC-40).
- M15. No network. Filters, scores and layout add no request to another host (AC-9 stays valid).

### Should
- S1. Unreadable, empty or undecodable files are listed with a reason, and the rest still works (AC-12, AC-20,
  AC-25, AC-26, AC-31).
- S2. Other files are listed in an inventory with type, size and date (AC-15).
- S3. Numbers use thousands separators (AC-21); the product is named DataBoot (AC-19).
- S4. Speed. Applying a filter to a 200,000-row dataset returns the filtered charts within 1 second (AC-41).

### Could
- C1. Pick a different folder from the home page without restarting.
- C2. Moved to M13 by gate 175 (build now).

## Out of scope
- Any AI or learned recommender, any new dependency (scores use the standard library or the installed pyarrow /
  Plotly only), any network request.
- New chart kinds, user-adjustable scores or weights, more than one value per dropdown, filter types other than
  category dropdowns and one date range, numeric range filters.
- Changing the 8-chart cap or which charts the rules pick: scoring only reorders the charts already chosen.
- Launcher, Dockerfile, readers, Power BI, shapefile, PDF/Word, SQL. New branding, logo or theme toggle.

## Constraints
- Deterministic: scores are rounded to 2 decimals before sorting; the sort is stable on the existing rule order, so
  the same file gives the same order on every run and in the API, page and exports.
- Scores are computed on the full filtered rows read (up to DATABOOT_MAX_ROWS, default 200,000), not on the sample
  sent to the browser.
- The charts API (`GET /api/datasets/<id>/charts`) gains the filter query parameters and a numeric `score` per
  chart, plus the KPI values; the dashboard page and both export routes accept the same query parameters. With no
  parameters every route answers exactly as before, so the round 1 to 3 tests stay valid (lesson: old default on).
- The "N of M" counts and existing rule caption text stay; only " · score 0.NN" is appended (AC-17 stays valid: one
  caption, one count, no other sentences; KPI labels and filter labels are labels, not sentences).
- The XLSX keeps "Data" as its first sheet (AC-18); the filter list goes to an extra "Summary" sheet.
- Phone layout follows the existing CSS breakpoint for narrow screens; the 1 s target is measured server-side in the
  test image.
- Style follows docs/DESIGN.md: plain neutral, system sans font, OS colour preference only.

## Branding
No business website capture and no docs/brand/ folder: docs/reference/ holds captures of deck.gl and
unstructured.io, third-party libraries named in the round 1 idea, not the client's site. The Board chose
(gate 160): name DataBoot, plain neutral style, system sans font, no logo, blank SVG favicon. Unchanged.
