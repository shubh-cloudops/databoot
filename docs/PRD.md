# PRD: DataBoot, an offline data-to-dashboard bootstrapper (round 6)

Round 6 has two parts (docs/IDEA.md, docs/BRIEF.md). **Part 1** finishes the seven gate 181 fix-ups to round 5
(number format by column role, plurals, Explorer bar cursor, score only in Explorer, line y-range, PPTX title
slide, an ARCHITECTURE.md fix). **Part 2** adds two apps to the ordered rule table: **Monitoring** (R4) and
**Survey** (R5). QA adds a fixture per new archetype, week and year grain tests and an Explorer-only export case.
No AI, offline, no network requests, no new dependencies. Everything under "Product today" stays.

## Problem
Owners of data (a pen drive, a disk or a folder of spreadsheets) cannot see what is in it without an analyst.
DataBoot reads the files and at once shows datasets and charts, fully offline, with no AI: fixed rules look at the
column types and pick the visuals. Charts can be taken away as editable XLSX and PPTX files.
This round: two common kinds of file still fall through to the generic Explorer. Sensor or metric logs (a
timestamp and readings) need "where is it now, what range, did anything spike"; survey exports (many answer
columns) need "how did people answer each question, and how do two questions relate". Round 5 also left small
inconsistencies the Board asked to fix first (a year shown as "2,024", "1 points", scores on pages that are not
ordered by score).

## Users
- **Data owner (client)**: non-technical; a Windows 11 laptop and a folder or drive of files. Starts the app with
  one click and looks; may share a dashboard link with a colleague on the same machine or network.
- **Operator**: installs it once on the client's machine.

## Product today (rounds 1 to 5, kept)
1. Started on one folder; lists CSV, TSV, Excel (per sheet), JSON/JSONL, GeoJSON and Parquet datasets, an "Other
   files" inventory and a "Could not be read" list. Columns classified on the first 10,000 rows.
2. **Explorer** (R3): at most 8 rule-picked charts ordered by score, KPI strip, filters, click-to-filter, chips,
   URL state, filtered XLSX/PPTX exports with native charts.
3. **Business** (R2): KPI cards with sparkline, trend per measure, leaderboard with "Other", drill-down with
   breadcrumb, change table.
4. **Map** (R1): 2D map with sequential colours or hexagon density cells, side panel, top regions, 3D view.
5. Badge "App: <name> (rule <id>)", "View as" switch, `app=` in the URL, exports per app, global chart rules in
   docs/DESIGN.md, table toggle on every chart, launcher, optional Dockerfile.

## Column roles and archetype rules
Roles as in round 5: **G** = a lat/lon pair (counted once); **T** = temporal; **N** = numerical, not counting the
lat/lon pair; **C** = categorical; **I** = other. The ordered table, first match wins (new rows in bold; the
code that walks it does not change):

| Rule | Condition | App |
|------|-----------|-----|
| R1 | G present and (N <= 2 or at least 50% of rows have coordinates) | Map |
| R2 | T >= 1 and C >= 1 and N >= 1 | Business |
| **R4** | **T >= 1 and N >= 1 and C = 0** | **Monitoring** |
| **R5** | **C >= 4 and C >= 60% of all columns and N <= 2** | **Survey** |
| R3 | always | Explorer |

R4 and R5 sit before R3 as the idea says. R2 and R4 cannot both hold (C >= 1 vs C = 0). A file that meets both R2
and R5 (a date, a number and 4 or more categoricals) opens as Business and can be switched to Survey with "View
as" (see open questions). For R5 only, a whole-number column whose values all lie in 1..5 counts as a Likert
question (C), not as N; R1, R2 and R4 still count it as N.

### Number format by column role (fix-up 1)
- Thousands separators only for values of **numeric** columns and for counts/sums the app computes.
- Never for **identifier** columns (role I, or a numerical column whose name is `id` or ends in `id`/`_id`, or
  contains `code`, `zip` or `phone`, any case), **temporal** columns, or **year-like** columns (a whole-number
  column whose name contains `year`, any case, or whose values are all whole numbers from 1900 to 2100).
- Applies in tables, the Map side panel, tooltips and table views. The decision is made from the column's role on
  the server, not by matching the rendered text. "2,024" never appears for a year column.

## User stories
### Must (rounds 1 to 5, kept)
- M1-M28 as in round 5: listing, profiling, Explorer charts and filters, exports, launcher, accessibility, detection,
  badge, View as, Business, Map, global chart rules, no network (AC-1..AC-58, some reworded below).

### Must (round 6, part 1: fix-ups)
- M29. Number format by role. As a data owner, a year reads 2024 and an order id reads 10045, while amounts read
  12,345 (AC-59; AC-55 reworded).
- M30. Plurals. "1 point", "1 row", "1 of 1 row"; "0 points", "2 points" (AC-60; AC-17 reworded).
- M31. Explorer bars show the same pointer cursor as clickable Business bars; DESIGN.md Cross-filter (AC-39) text
  says so (AC-61).
- M32. "score 0.xx" only in Explorer captions; Business, Map, Monitoring and Survey captions show none (AC-35
  reworded).
- M33. Line charts keep the automatic y-range in every app; the zero baseline is for bars only; DESIGN.md says so
  (AC-62). This reverses the round 5 design review's zero start on Business trends.
- M34. PPTX title slide: the app title, then the file name (with sheet for Excel) as a smaller second line (AC-63).
- M35. Architect: docs/ARCHITECTURE.md L147-148 describes hexagon choropleth cells (gate 180). Doc-only, no AC.

### Must (round 6, part 2: new apps)
- M36. Detection. Monitoring and Survey files open in their app, with the badge "App: Monitoring (rule R4)" or
  "App: Survey (rule R5)"; earlier fixtures keep their app (AC-64).
- M37. Monitoring tiles. One sparkline tile per numeric column: latest value, min, max over the selected period, and
  the change against the previous period as an arrow icon + signed % with 1 decimal + "up"/"down"/"no change",
  never colour alone (AC-65).
- M38. Period selector. 7 days, 30 days, 90 days, All; the choice is in the URL and sets the tiles and main line
  (AC-66).
- M39. Main line. The primary numeric (AC-46 name rule) over time with its rolling mean as a second line on the same
  y-axis; spikes flagged with a marker and the text label "spike" (AC-67).
- M40. Survey questions. One horizontal bar chart per question (categorical column), bars sorted by count, top 10
  then "Other", in a small-multiples grid (AC-68).
- M41. Likert questions. A 100% stacked bar per Likert question, segments in scale order on a diverging palette
  with a grey neutral (AC-69).
- M42. Cross-tab. Two dropdowns pick a row question and a column question; a heatmap shows the counts with row %
  (AC-70).
- M43. Both new apps have the "View as" switch (AC-45), a table toggle on every chart, one y-axis and tooltips
  (AC-54), and no request to another host (AC-9).

### Should
- S1. Unreadable files listed with a reason; Other files inventory; DataBoot name; speed (AC-12, AC-15, AC-19..AC-21,
  AC-25, AC-26, AC-31, AC-41).
- S2. Archetype exports (AC-56). New: Monitoring and Survey exports titled "Monitoring overview" and "Survey
  overview" (AC-71).
- S3. QA: Business week and year grain (AC-72); an Explorer-only dataset's exports (AC-73).

### Could
- C1. Pick a different folder from the home page without restarting.
- C2. Rules for Directory and Drive apps (later round).

## Monitoring app definitions (defaults; Board to confirm)
- Time column = the first T column; rows sorted by time; repeated timestamps are averaged into one point.
- Period = the last 7, 30 or 90 days ending at the latest timestamp, or All; default 30 days; URL `period=7|30|90|all`.
- Tile: latest = value at the latest timestamp; min and max over the period; change = mean of the period vs mean
  of the window of the same length right before it, signed % with 1 decimal. "All", an empty previous window or a
  previous mean of 0 give "n/a" and no arrow. Sparkline = the period's values.
- Main line = the primary numeric; rolling mean and spikes use a trailing window of the 30 points before each point;
  a point is a spike when that window is full and |value - mean| / standard deviation > 3 (no spike when the
  deviation is 0). Spikes are computed on all rows, then the selected period is shown.
- The round 4 filter form (date range) stays; there are no categorical filters, since C = 0.

## Survey app definitions (defaults; Board to confirm)
- Question = every C column (including R5's 1..5 Likert columns), in column order. N and I columns are not charted.
- Likert = a question whose non-empty values all lie on one known scale with at least 2 distinct values:
  1..5, or (any case) "strongly disagree, disagree, neither agree nor disagree / neutral, agree, strongly agree".
  Neutral = 3 or the middle label, drawn grey; disagree side and agree side in the two hues of the diverging scale.
- Non-Likert question: horizontal bars of row counts per value, sorted descending, top 10 then "Other".
- Grid: two charts per row at desktop width, one at phone width (DESIGN.md gives the details).
- Cross-tab: the two dropdowns list every question and default to the first two; cell text = count and row % with
  1 decimal; row % of each row sums to 100. The pick is in the URL.
- The round 4 category filters and click-to-filter on non-Likert bars stay.

## Out of scope
- Directory and Drive apps; any app beyond Monitoring and Survey.
- Any AI or learned recommender, any new dependency, any network request, map tiles or online geocoding.
- Changes to earlier apps beyond the seven fix-ups. Trends research is off (Board, gate 179 and IDEA "trends off").
- Launcher, Dockerfile, readers, Power BI, shapefile, PDF/Word, SQL, measure picker. New branding, logo or theme
  toggle.

## Constraints
- Deterministic: same file, same roles, same app, same figures, in the API, page and exports.
- With no `app` parameter a dataset opens in its detected app; `app=explorer` gives the Explorer page. The new rules
  must not change the app of any round 1-5 fixture; a test that would change passes `app=` explicitly.
- Speed: a 200,000-row CSV that opens as Monitoring or Survey answers within AC-42's 5 seconds cold.
- Text allowed on pages stays as before (titles, axis labels, counts, rule caption, badge, KPI and tile labels,
  breadcrumb, button labels, the "spike" label). No generated sentences (AC-17).
- Style follows docs/DESIGN.md: plain neutral, system sans font, OS colour preference only. The designer adds the
  Monitoring and Survey layouts and the fix-up 3 and 5 wording.
- Team (IDEA): designer, frontend and backend; trends off.

## Branding
No business website capture and no docs/brand/ folder: docs/reference/ holds captures of deck.gl and
unstructured.io, third-party libraries named in the round 1 idea, not the client's site, plus an empty folder
"0.xx" (the capture step read "score 0.xx" in the idea as a host name; nothing was captured). The Board chose
(gate 160): name DataBoot, plain neutral style, system sans font, no logo, blank SVG favicon. Unchanged.
