# Design: DataBoot (round 1)

Stylesheet: `app/static/css/databoot.css` (all tokens and components below; linked by `app/templates/base.html`).
Sources: docs/PRD.md, docs/ARCHITECTURE.md ("Pages", "Chart contract"), Board gate 160 (graphify-out/memory.md
L4-17): **plain neutral style, no logo, system sans font**, text only as titles, axis labels, `N of M` counts and
one rule caption. No docs/TRENDS.md this round (`team: -trends`), so no trend advice is used. No external
fonts, images, icons or CDNs; no raster or SVG logo. The brand is the word "DataBoot" set in the system font.

## Visual direction
A quiet instrument panel: flat surfaces, hairline borders, one blue accent, and the charts carry the colour.
Light and dark follow `prefers-color-scheme` (no toggle this round; `color-scheme: light dark` is set so native
controls match). Nothing decorative: no gradients, shadows, icons or animation except the one real loading state.

## Colour tokens
Contrast measured with the WCAG formula (`/tmp/contrast.py`, not kept). Text pairs need 4.5:1; graphics and
control borders need 3:1.

| Token | Light | Dark | Use | Contrast (light / dark) |
|---|---|---|---|---|
| `--bg` | #f7f7f5 | #17191c | page, table header | |
| `--surface` | #ffffff | #202328 | header, cards, tables | |
| `--fg` | #1d2329 | #e8e8e4 | text | 15.9 / 12.8 on surface |
| `--muted` | #5d6670 | #a0a8b0 | captions, th, notes | 5.4 / 6.6 on bg or surface (min) |
| `--line` | #dcdcd6 | #33373c | hairlines (decorative only) | n/a |
| `--line-strong` | #868b92 | #80868e | button, badge, empty-state borders | 3.2 / 4.3 on bg (min) |
| `--accent` | #1f5fbf | #8ab4ff | links, focus ring, primary button | 5.7 / 7.5 |
| `--on-accent` | #ffffff | #0b0d10 | text on a primary button | 6.1 / 9.3 |
| `--accent-soft` | #e6eefa | #26334a | row hover, button hover | fg on it > 12 |
| `--danger` | #b3261e | #ff8a80 | unreadable-file note, chart error | 6.1 / 6.9 |
| `--ok` / `--warn` | #1b6e3c / #8a5300 | #6fcf97 / #e0a84a | reserved; always with a text label | >= 5.8 |

Chart palette (categorical, in this order, each >= 4.5:1 on `--surface`; colour is never the only carrier, the
legend or axis names the category):
`--c1..--c8` light `#1f5fbf #b85c00 #00796b #7b4fb3 #c0392b #6b7a00 #8a5a44 #b0306f`, dark `#6ea4ff #f0963c
#3fc1ad #b79bf0 #ff8a7a #b5c93a #d1a086 #f08ab8`. A chart with one series uses `--c1`. Donut uses `--c1..--c6`
in value order (the rule allows 2 to 6 slices). Bars of one series are all `--c1`: bar height already encodes the
value, so no rainbow bars.
Sequential scale (country map, 3D map z): `--seq-lo` to `--seq-hi`. Diverging scale (correlation heatmap, -1 to
+1, fixed range, 0 at the middle): `--div-neg` (orange) via `--div-mid` to `--div-pos` (blue). Orange/blue is safe
for red-green colour blindness; each heatmap cell also prints its value to two decimals, so the number is read,
not guessed from the hue.

## Type scale
System stack `--font`: `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
(Segoe UI on the Windows 11 target). Code, file paths and cell values may use `--mono`.
| Token | Size | Use |
|---|---|---|
| `--t-xl` | 1.75rem (1.5rem at <= 599px), weight 650 | h1 |
| `--t-lg` | 1.25rem, 650 | h2, brand, table caption |
| `--t-md` | 1rem, line-height 1.5 | body, chart title (650) |
| `--t-sm` | 0.875rem | tables, captions, notes |
| `--t-xs` | 0.8125rem | table headings (upper case, 0.04em), badges |
Numbers in tables and counts use `font-variant-numeric: tabular-nums` and right-align (`.num`). Thousands
separators are not required by the spec; use them if the engineer adds them (open question in ARCHITECTURE.md).

## Spacing, shape, layout
4px grid: `--s1..--s7` = 4, 8, 12, 16, 24, 32, 48. Radius 6px. Max content width 1200px, centred. Page padding
16px (24px from 900px). Tap targets (buttons, brand link, table links) are at least 44px high (`--tap`).
Breakpoints: `<= 599px` phone, `600-899px` single column, `>= 900px` two-column chart grid.

## Components
| Class | What | States |
|---|---|---|
| `.site-header .brand` | white bar, "DataBoot" text link to `/` | hover accent colour, focus ring |
| `.skip` | "Skip to content", first focusable element | visible only on focus |
| `.page-head` | h1 left, `.actions` right; wraps | |
| `.btn`, `.btn-primary` | download links (`Export PPTX`, `Export XLSX`) | hover (soft fill, accent border), focus ring, active 1px press |
| `.table-wrap > table` | scrolls sideways inside its own box, page never scrolls sideways | row hover soft fill |
| `.badge` | column type label (`numerical`, `categorical`, `temporal`, `geospatial`, `other`) in a pill, text always shown | |
| `.note`, `.note-error` | left-bar message, used for fixed labels like `could not be read` | |
| `.empty` | dashed box: "No charts for this dataset" style fixed label, only when `charts == []` | |
| `figure.chart` | card: figcaption on top (`.chart-title`, `.chart-rule`, `.chart-count`), `.plot` below | loading, drawn, error |
| `.plot.is-loading` | skeleton while `/charts` is pending | removed on success or error |
| `.plot-error` | fixed text `Chart could not be drawn` in `--danger` | |

### States
- **Loading**: only `.plot.is-loading`, set from the first paint until the fetch settles. It is a real pending
  request, so the shimmer is honest; it ends in a drawn chart or `.plot-error`. With reduced motion it is a flat
  `--line` block.
- **Empty**: Home with no datasets shows the folder path and hides empty tables (ARCHITECTURE "Pages"). A dataset
  with no matching rule shows the types table, the first-20-rows table and one `.empty` box in place of charts.
- **Error**: unreadable files are listed in their own table with the fixed reason in a `.note-error` cell; a failed
  fetch puts `.plot-error` in that figure only; the other charts still draw.
- **Hover/focus**: described per component. Plotly hover tooltips use `--surface` background, `--fg` text.

## Charts (Plotly, `app/static/js/dashboard.js`)
The engineer reads the tokens at draw time with `getComputedStyle(document.documentElement)` so the CSS stays
the one source of truth, and passes a shared layout:
- `paper_bgcolor`/`plot_bgcolor` transparent; `font: {family: --font, size: 13, color: --fg}`; grid `--line`;
  axis line and ticks `--muted`; `margin` `{l:56, r:16, t:8, b:48}` (smaller `l:44` at 375px); `autosize` with
  `responsive: true`; **no Plotly title** (the figcaption is the title); axis titles from `x_label` / `y_label`.
- `Plotly.newPlot(el, data, layout, {topojsonURL: "/static/vendor/topojson/", displaylogo: false, responsive: true})`.
  Mode bar stays (zoom, pan, reset are useful for 3D), but `displayModeBar: "hover"`.
- Per kind: line = `--c1` 2px, no markers unless `shown <= 40`; bar = `--c1`, gap 0.2, horizontal when the longest
  label has > 12 characters; donut = hole 0.55, legend right (below at 375px), `textinfo: "percent"`; histogram =
  `--c1`, bars touching (gap 0.02); scatter = `--c1` markers size 6, opacity 0.7; heatmap = diverging scale,
  `zmin -1`, `zmax 1`, cell values printed, `null` cells blank; map3d = scatter3d markers size 3, `--seq` colour by
  z when z is real data, else `--c1`; country_map = choropleth, `--seq` scale, outlines `--line-strong`, coastlines
  on, `showframe` off, no base tiles.
- Honest data: the point count shown in `.chart-count` is the server's `shown`/`total` (`N of M points` or `N of
  M rows`). When `shown < total` the caption says so and nothing else; no smoothing, no fake trend line. Plotly
  default transitions are off (`transition: {duration: 0}`), so no chart animates on load.
- Keyboard and screen reader: each `figure` has `aria-label` = chart title; each `.plot` has `role="img"` with
  `aria-label` = `<title>: <rule caption>`; the data is also in the first-20-rows table above/below.

## Motion rules
1. Only two moving things exist: the loading shimmer (real pending fetch) and the 160ms colour transition on
   buttons. Nothing animates because data is "live"; the app does not poll.
2. No scroll reveals, no count-up numbers, no entrance animation of charts.
3. `prefers-reduced-motion: reduce` removes all transitions and animations (blanket rule at the end of the CSS).
   Plotly 3D rotation is user driven only (drag); never auto-rotate.

## Accessibility
- Contrast as in the token tables. Focus: 3px `--accent` outline, 2px offset, on every link and button
  (`:focus-visible`); contrast with the surface >= 3:1 in both themes.
- Tab order: skip link, brand, page actions, table links, chart mode-bar buttons. Landmarks: `header`, `main#main`.
- One `h1` per page, then `h2` per section; tables have `caption` and `th scope`. Type badges carry text.
- `lang="en"`; zoom is not blocked; layout reflows at 320px with no horizontal page scroll.

## Page layouts
Both pages share the header (56px) and `main` (max 1200px).

### Home `/`
Desktop (>= 900px): h1 `DataBoot`; below it a `.muted` line with the scanned folder path (`.mono`). Then up to
three `.table-wrap` tables, 32px apart, each with a `caption`:
1. Datasets: File path | Sheet | Rows (`.num`) | Columns (`.num`) | the file path is the link to `/datasets/{id}`.
2. Could not be read: File | Reason (`.note-error` text colour `--danger`).
3. Other files (file inventory): File | Type | Size (`.num`, bytes) | Modified (YYYY-MM-DD).
Empty tables are not rendered. If everything is empty, one `.empty` box shows the folder path.
375px: same order, one column. Tables keep all columns and scroll sideways inside their `.table-wrap`; File
column has `min-width: 12ch` and wraps long paths (`overflow-wrap: anywhere`). The link row is >= 44px tall.

### Dashboard `/datasets/{id}`
Desktop: `.crumb` link `DataBoot` / file; `.page-head` with h1 (file name, sheet in `.muted`) and `.actions`
with `Export PPTX` (`.btn-primary`) and `Export XLSX` (`.btn`). Then, in order:
1. `.charts` grid, two columns; `map3d`, `country_map` and `heatmap` span both columns; the rest are 320px tall
   cards in the rule order of ARCHITECTURE "Routing rules" (max 8). Each card: title, rule caption, `N of M`,
   plot.
2. `h2` Columns: small table column | type badge.
3. `h2` First 20 rows: `.data-table` scrolling inside its wrap, cells truncated with ellipsis at 28ch.
Charts come first because they are the product; the tables are the evidence behind them.
375px: crumb, h1, buttons full width stacked (44px each), charts one column (plot 280px, wide kinds 340px),
columns table, rows table (scrolls sideways in its box). Chart legends move below the plot. Nothing overflows
the page width.

## Honesty rules (for design review)
- Skeleton shimmer only while a fetch is pending. No fake progress bars, no "live" dots, no sparkline filler.
- Every number on screen comes from the server response; chart counts are `shown`/`total` as given.
- Colour never carries meaning alone: type is a word, category is in the axis or legend, heatmap prints values.

## Changes this round
New: `app/static/css/databoot.css`; `app/templates/base.html` now links it and adds the skip link, header and
`main#main`. Not done here (front-end ticket): `home.html`, `dataset.html`, `dashboard.js` markup using these
classes. Stylesheet cannot be checked in a browser until those pages exist; the design review in the build
phase does that.
