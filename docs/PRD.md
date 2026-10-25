# PRD: Data OS, an offline data-to-dashboard bootstrapper (round 1)

## Problem
Owners of data (a pen drive, a disk or a folder of spreadsheets) cannot see what is in it without an analyst.
They want software that, like an operating system detecting hardware and drawing a desktop, reads the files and
at once shows datasets, graphs and 3D maps that explain the data on their own, with no one narrating it.
It runs on the client's own machine, fully offline, with no AI or language model: fixed rules look at the
column types and pick the visuals (docs/IDEA.md lines 105-143, docs/BRIEF.md "Asked").

## Users
- **Data owner (client)**: non-technical; has a laptop (16 GB RAM, mid-range GPU such as an RTX 3050) and a
  folder or drive of files. Wants to start the app with one click and look, not configure.
- **Operator (the person who sets the app up for clients)**: installs it once on the client's machine.

## How it works (round 1)
1. The app is started with one folder (a mounted pen drive, disk or directory).
2. It scans the folder and its subfolders for CSV and Excel (.xlsx) files; each file (each sheet) becomes a dataset.
3. The profiler classifies every column as `geospatial`, `temporal`, `categorical` or `numerical`
   (or `other` when none fits) and saves the result as a JSON mapping.
4. The routing rules turn the mapping into a list of charts.
5. The browser dashboard draws those charts, all from locally served files.

### Classification rules (fixed, no AI)
- **Geospatial**: header is `lat`, `lon`, `lng`, `latitude` or `longitude` (case-insensitive, trimmed).
- **Temporal**: a datetime column, or a text column whose non-empty values parse as dates for at least 90%.
- **Numerical**: integer or float column that is not geospatial.
- **Categorical**: text column with at most 50 distinct values and distinct values at most 50% of rows.
- **Other**: anything else (free text, ids); shown in the table but not charted.

### Routing rules
- Temporal + numerical: a time-series line chart of each numerical column against the first temporal column.
- Categorical + numerical: a bar chart of each numerical column summed per value of the first categorical column.
- A latitude and a longitude column: a 3D map of the points (Deck.gl).
- No rule matches: only the data table is shown.
- At most 8 charts per dataset, in the order map, time series, bar.

## User stories
### Must
- M1. As a data owner, I start the app on a folder and see a home page listing every CSV and Excel dataset
  found (file name, sheet, row and column count), with no internet connection.
- M2. As a data owner, I open a dataset and see its column types and a table of its first rows.
- M3. As a data owner, I see the charts the rules pick for that dataset: line charts, bar charts and a 3D map.
- M4. As an operator, I can fetch each dataset's column mapping as JSON, and the same JSON is saved to disk.
- M5. As a data owner, the dashboard works with the network unplugged: every script, style and font is
  served by the app itself.
- M6. As a data owner with a large file, the map and charts still load: data sent to the browser is downsampled
  to a fixed cap, and the page shows how many points it is showing out of how many.
- M7. As a data owner, I start everything with one click (one launcher script) which opens the dashboard in my
  default browser.

### Should
- S1. As a data owner, an unreadable or empty file is listed with a short "could not read" note instead of
  breaking the home page.
- S2. As an operator, a Dockerfile and a Windows launcher (`Start-DataOS.ps1`) package the app, mount the client's
  folder and open the browser, as the idea describes.

### Could
- C1. JSON files that hold a list of records are read as datasets.
- C2. Pick a different folder from the home page without restarting.

### Won't (this round)
- See "Out of scope".

## Out of scope
- Any AI or language model, cloud or local; generated insight text or narration.
- Internet access, cloud hosting, SaaS, accounts or logins.
- PowerPoint, Excel report and Power BI exports (only in the superseded AI version of the idea).
- PDF, Word, SQL, shapefile and GeoJSON files.
- Raw or unmounted device access (the drive must be mounted as a folder).
- Chart types beyond the three rules above.

## Constraints
- Fully offline: no request may leave the machine; no CDN links in any page.
- Runs within 16 GB RAM: files are read with a row cap per dataset for profiling, and data sent to the
  browser is capped (map points and chart points) by downsampling; the caps are settings with defaults.
- Python backend on the existing project scaffold (FastAPI + Jinja, `app/main.py`); the idea names Flask and
  Plotly Dash, the stack choice is left to the architecture (see open questions).
- Charts with a locally vendored Plotly.js; 3D map with a locally vendored Deck.gl and no online base-map tiles.
- The data folder is read-only to the app; outputs (the JSON mappings) go to the app's own output folder.
- Tests must run without Docker, a browser GPU or a real drive: they point the app at a temp folder of fixtures.

## Branding
No logo, colours or fonts for the business were found. docs/reference/ holds captures of deck.gl and
unstructured.io, which are third-party libraries named in the idea, not the client's website; they are not used
for branding. The working product name "Data OS" comes from the idea's `Start-DataOS.ps1`.
