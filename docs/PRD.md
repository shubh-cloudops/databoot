# PRD: DataBoot, an offline data-to-dashboard bootstrapper (round 5)

Round 5 makes DataBoot pick a whole app layout per dataset by fixed rules (docs/IDEA.md, docs/BRIEF.md): an
ordered rule table reads the column roles and chooses a **Map app**, a **Business app** or the round 4
**Explorer**. The page shows which app and rule were used, and a "View as" switch offers the other apps the dataset
qualifies for. Global chart rules go into docs/DESIGN.md and apply to every app, Explorer included. Exports follow
the chosen app. No AI, offline, no network requests, no new dependencies. Everything under "Product today" stays.

## Problem
Owners of data (a pen drive, a disk or a folder of spreadsheets) cannot see what is in it without an analyst.
DataBoot reads the files and at once shows datasets and charts, fully offline, with no AI: fixed rules look at the
column types and pick the visuals. Charts can be taken away as editable XLSX and PPTX files.
This round: every dataset gets the same chart grid, whatever it holds. Sales data should open as a business
overview (headline numbers against last period, trend, top categories, what changed), and a file of locations
should open as a map. The charts must follow one set of honest chart rules everywhere.

## Users
- **Data owner (client)**: non-technical; a Windows 11 laptop and a folder or drive of files. Starts the app with
  one click and looks; may share a dashboard link with a colleague on the same machine or network.
- **Operator**: installs it once on the client's machine.

## Product today (rounds 1 to 4, kept)
1. Started on one folder (mounted folder or drive letter, no raw device access); lists CSV, TSV, Excel (per-sheet),
   JSON/JSONL, GeoJSON and Parquet datasets, an "Other files" inventory and a "Could not be read" list.
2. Classifies every column as geospatial, temporal, categorical, numerical or other (first 10,000 rows).
3. Rules pick at most 8 charts (3D scatter map, country map, line, bar, donut, histogram, scatter, heatmap), each
   with a rule caption ending in "· score 0.NN" and an "N of M" count, ordered by score, first one full width.
4. KPI strip, category dropdowns, a date range, click-to-filter on bars, chips and "Clear filters", all kept in
   the URL and applied by the server (`f.<column>`, `from`, `to`).
5. XLSX (Data first, Summary last) and PPTX exports with native, editable charts, following the filters.
6. Accessible tables, always-visible chart tool bar, Windows launcher, optional Dockerfile.
This whole page is the **Explorer** app from now on.

## Column roles and archetype rules
Roles come from the existing column types: **G** = a latitude column plus a longitude column (one pair, counted
once); **T** = temporal; **N** = numerical, not counting the lat/lon pair; **C** = categorical; **I** = other
(identifiers and free text). A row "has coordinates" when both lat and lon are numbers in range
(lat -90..90, lon -180..180).

The detector is an ordered table of (rule id, app, condition); the first rule whose condition holds wins:

| Rule | Condition | App |
|------|-----------|-----|
| R1 | G present and (N <= 2 or at least 50% of rows have coordinates) | Map |
| R2 | T >= 1 and C >= 1 and N >= 1 | Business |
| R3 | always | Explorer |

R4-R7 (Survey, Directory, Monitoring, Drive) are reserved for round 6 and are added as rows of the same table,
before R3, with no change to the code that walks it. A dataset **qualifies** for every app whose rule condition
holds (so Explorer always qualifies). Detection is computed on the full loaded rows and gives the same answer on
every run.

## User stories
### Must (rounds 1 to 4, kept)
- M1. Every dataset is listed with name, sheet, rows and columns, offline (AC-1, AC-14).
- M2. A dataset opens with its column types, first 20 rows and the rule-picked charts (AC-2..AC-8, AC-16, AC-27).
- M3. Every asset is local (AC-9); large files are downsampled with an "N of M" count (AC-10).
- M4. One launcher command opens the dashboard (AC-11, AC-13, AC-28..AC-30).
- M5. XLSX and PPTX exports with native, editable charts (AC-18, AC-23).
- M6. Tables and the chart tool bar work with keyboard and screen reader (AC-22, AC-24).
- M7-M15. Round 4 score, order, layout, KPI strip, filters, URL state, cross-filter (bar-only toggle, gate 178),
  filtered exports, no network (AC-32..AC-42).

### Must (round 5)
- M16. Archetype detection. As a data owner, each dataset opens in the app the rule table picks, and the same
  file always gets the same app (AC-43).
- M17. Badge. The page shows "App: <name> (rule <id>)", for example "App: Business (rule R2)" (AC-44).
- M18. View as. A "View as" switch lists only the apps this dataset qualifies for; picking one shows that app and
  puts `app=<map|business|explorer>` in the URL, so a copied link opens the same app. With only Explorer
  qualifying the switch is not shown (AC-45).
- M19. Business KPI cards. One card per measure (up to 3 N columns: the numeric columns whose name contains
  amount, revenue, sales, total, price, value, cost, qty or quantity first, then the rest, each in column order; the
  first is the **primary amount**): the sum for the latest full period, the change against the previous period as an arrow icon
  (▲ / ▼ / ▶ for zero) + signed % with 1 decimal + a text label ("up", "down", "no change"), never colour alone,
  and a sparkline of the last 12 periods (AC-46).
- M20. Business trend. The primary amount summed per period at an automatic grain, one y-axis; with several
  measures, one small chart per measure, never a second y-axis (AC-47).
- M21. Leaderboard. Horizontal bars of the primary amount per category, top 10 sorted descending with the rest
  summed into one "Other" bar at the end, each bar labelled with its value (AC-48).
- M22. Drill-down. Clicking a leaderboard bar regroups the leaderboard by the next categorical column, inside the
  clicked category (coarse to fine: categorical columns by distinct count, fewest first); a breadcrumb ("All › region: North") goes back a level; the drill path is in the URL (AC-49).
- M23. Change table. For the leaderboard's categories: category, previous period, latest period, delta; the delta
  cell is coloured on a diverging scale with grey at zero and carries its sign, so colour is never the only cue
  (AC-50).
- M24. Map app. A 2D map about 70% of the viewport height on the bundled offline world outline; points coloured by
  the primary numeric (name rule) on a one-hue light-to-dark scale, or one colour when there is no N
  (AC-51).
- M25. Density above 5,000 points. With more than 5,000 rows with coordinates, the map draws hexagonal cells
  coloured by point count instead of the points (AC-52).
- M26. Side panel. Clicking a point shows its column values in a side panel (a cell shows its point count); the
  panel also holds a top-regions bar chart; a "3D view" toggle swaps the map for the existing Plotly 3D scatter and
  back (AC-53).
- M27. Global chart rules in every app. No figure has a second y-axis; every chart has a hover tooltip and a
  "view as table" toggle that shows the chart's plotted values as a table (AC-54); thousands separators
  everywhere, in page text, tooltips, axis ticks and value labels (AC-55); donut only for 2 to 5 parts (AC-16).
  The full rule list lives in docs/DESIGN.md (AC-57).
- M28. No network. No app, toggle or drill makes a request to another host (AC-58).

### Should
- S1. Unreadable files listed with a reason; Other files inventory; DataBoot name; speed (AC-12, AC-15, AC-19..AC-21,
  AC-25, AC-26, AC-31, AC-41).
- S2. Archetype exports. XLSX and PPTX follow the shown app: Business = title "Business overview", then KPIs,
  trend, leaderboard, change table; Map = title "Map overview", then map (native XY scatter of lon/lat) and top
  regions. Explorer exports stay as today. Data stays the first sheet and Summary the last (AC-56).

### Could
- C1. Pick a different folder from the home page without restarting.
- C2. Rules R4-R7 (round 6).

## Business app definitions (defaults; Board to confirm)
- Time column = the first T column; measures = up to 3 N columns, name-rule matches first (the first is the primary amount), summed.
- Grain from the span between the first and last date: <= 60 days = day; <= 182 days = ISO week (Monday start);
  <= 3 years (1,096 days) = month; else year.
- Latest full period = the period holding the last date when that date is the period's last day, else the period
  before it (day grain: always the last day). Previous period = the one right before; a period with no rows is 0.
  Fewer than 2 periods, or a previous value of 0, show "n/a" with no arrow.
- Leaderboard and change table use the categorical column with the fewest distinct values with no active filter; their figures are over all rows of
  the current view (leaderboard) and the latest and previous full periods (change table).
- Drill-down reuses the round 4 filters: clicking a bar sets `f.<column>=<value>` and the leaderboard moves to the
  next C column in drill order (distinct count ascending, ties by column order); at the last C column bars are not clickable; "Other" is never clickable. The
  breadcrumb lists the drilled columns; "All" clears them.
- The round 4 filter form and chips stay on every app; the Business KPI cards replace the round 4 KPI strip in
  the Business app.

## Map app definitions (defaults; Board to confirm)
- Map = Plotly 2D geo (`scattergeo`) on the bundled world_110m outline, fitted to the points.
- Hexbin cells are computed by the server: about 40 cells across the points' longitude span; colour = point count
  on the same one-hue scale; the tooltip shows the count.
- Top regions = the country column if present, else the C column with the fewest distinct values (>= 2); ranked by the
  sum of the primary numeric, else by row count; top 10 descending plus "Other"; with no such column the panel shows
  no bar chart.
- The 3D view toggle colours the points by the primary numeric (name rule); the Explorer 3D map is unchanged.

## Out of scope
- Rules R4-R7 and their apps (round 6); only the table's room for them.
- Any AI or learned recommender, any new dependency, any network request, map tiles or online geocoding.
- Changes to the Explorer beyond the global chart rules (table toggle, tooltips, donut 2-5, separators).
- Launcher, Dockerfile, readers, Power BI, shapefile, PDF/Word, SQL. New branding, logo or theme toggle.

## Constraints
- Deterministic: same file, same roles, same app, same figures, in the API, page and exports.
- With no `app` parameter a dataset opens in its detected app; `app=explorer` gives the round 4 page exactly, so
  the round 1 to 4 page tests that rely on the Explorer layout pass `app=explorer` (old default on). The charts API
  answers as before; the app choice is a separate field or route.
- An `app` value the dataset does not qualify for shows the detected app.
- Speed: a 200,000-row CSV that opens as Business or Map still answers within AC-42's 5 seconds cold and AC-41's
  1 second filtered.
- Text allowed on pages stays as before: titles, axis labels, counts, the rule caption, the badge, KPI labels,
  breadcrumb and button labels. No generated sentences (AC-17).
- Style follows docs/DESIGN.md: plain neutral, system sans font, OS colour preference only.

## Branding
No business website capture and no docs/brand/ folder: docs/reference/ holds captures of deck.gl and
unstructured.io, third-party libraries named in the round 1 idea, not the client's site. The Board chose
(gate 160): name DataBoot, plain neutral style, system sans font, no logo, blank SVG favicon. Unchanged.
