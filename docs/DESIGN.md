# Design: DataBoot (round 2)

Stylesheet: `app/static/css/databoot.css` (all tokens and components below; linked by `app/templates/base.html`).
Sources: docs/PRD.md, docs/ARCHITECTURE.md ("Pages", R5, R6), Board gates 160 and 165: **branding unchanged:
DataBoot, plain neutral style, system sans font, no logo, blank SVG favicon** (`app/static/blank.svg`), text only
as titles, axis labels, `N of M` counts and one rule caption. No docs/TRENDS.md this round (`team: -trends`), so no
trend advice is used. No external fonts, images, icons or CDNs; no raster or SVG logo. The brand is the word
"DataBoot" set in the system font. No docs/brand/ and no site capture exist, so no logo is copied.

**Round 2 delta** (everything not listed here is unchanged from round 1; tokens are unchanged):
1. Table titles are real `h2` elements inside the `<caption>` (AC-22).
2. Column headers keep their case: no upper-casing, no letter spacing (AC-22). `th` is `--t-sm`, not `--t-xs`.
3. The Plotly mode bar is always visible and its buttons are in the Tab order with a visible ring (AC-24).
4. 3D map z axis and colour bar are titled with the z column name (`z_label`), see Charts.
5. Numbers with thousands separators and the new inventory/Parquet/XLSX datasets need no new component.

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
| `--t-lg` | 1.25rem, 650 | h2, brand |
| `--t-md` | 1rem, line-height 1.5 | body, chart title (650), table titles (`caption h2`, 650) |
| `--t-sm` | 0.875rem | tables, `th` (650, `--muted`, original case), captions, notes |
| `--t-xs` | 0.8125rem | badges |
Numbers in tables and counts use `font-variant-numeric: tabular-nums` and right-align (`.num`). Thousands
separators are used everywhere (Board gate 161), through the `num` filter.

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
| `.table-wrap > table` | scrolls sideways inside its own box, page never scrolls sideways. Title is `<caption><h2>Name</h2></caption>`: `caption` pads 12/16/8px, `caption h2` has margin 0 and `--t-md`. `th` shows names exactly as read (`Latitude`, `LON`) | row hover soft fill |
| `.js-plotly-plot .modebar` | Plotly tool bar, drawn by the library, restyled only by the CSS here: opacity 1 always, buttons 28px min, icons `--muted` | focus ring 3px `--accent`, active icon `--accent` |
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
  **Mode bar is always visible: `displayModeBar: true`** (not `"hover"`: hover mode hides the buttons from
  keyboard users and from touch screens). Layout `modebar: {bgcolor: transparent, color: --muted, activecolor:
  --accent}` so the icons follow the theme (`--muted` is 5.4 / 6.6 : 1 on the card). The CSS adds
  `opacity: 1` as a guard. Buttons are `<a>` without `href`, so after every draw (and every redraw on theme or
  breakpoint change) `dashboard.js` sets `tabindex="0"`, `role="button"` and `aria-label` (from `data-title`) on each
  `.modebar-btn` and maps Enter and Space to click (ARCHITECTURE R6). Focus shows the same 3px `--accent` ring.
- Per kind: line = `--c1` 2px, no markers unless `shown <= 40`; bar = `--c1`, gap 0.2, horizontal when the longest
  label has > 12 characters; donut = hole 0.55, legend right (below at 375px), `textinfo: "percent"`; histogram =
  `--c1`, bars touching (gap 0.02); scatter = `--c1` markers size 6, opacity 0.7; heatmap = diverging scale,
  `zmin -1`, `zmax 1`, cell values printed as annotations in black or white, whichever contrasts more (>= 4.5:1) with that cell's colour, `null` cells blank; map3d = scatter3d markers size 3, `--seq` colour by
  z when z is real data, else `--c1`; with a `z_label` the z axis title and the colour bar title are that column
  name, and with `z_label` null (z is the constant 0) the z axis is hidden and there is no colour bar; country_map = choropleth, `--seq` scale, outlines `--line-strong`, coastlines
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
- Tab order: skip link, brand, page actions, chart mode-bar buttons (visible, 28px, ring on focus), table links.
  Landmarks: `header`, `main#main`. Mode-bar buttons have an `aria-label`.
- One `h1` per page, then `h2` per table (inside its `<caption>`), no skipped level; figures keep a figcaption
  title, not a heading. Tables have `caption` and `th scope`. Type badges carry text.
- `lang="en"`; zoom is not blocked; layout reflows at 320px with no horizontal page scroll.

## Page layouts
Both pages share the header (56px) and `main` (max 1200px).

### Home `/`
Desktop (>= 900px): h1 `DataBoot`; below it a `.muted` line with the scanned folder path (`.mono`). Then up to
three `.table-wrap` tables, 32px apart, each titled by `<caption><h2>` (Datasets, Could not be read, Other files):
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
2. Columns table (caption h2 `Columns`): column | type badge.
3. First rows table (caption h2 `First 20 rows`, the number comes from the server): `.data-table` scrolling
   inside its wrap, cells truncated with ellipsis at 28ch, headers in the file's own case.
Charts come first because they are the product; the tables are the evidence behind them.
375px: crumb, h1, buttons full width stacked (44px each), charts one column (plot 280px, wide kinds 340px),
columns table, rows table (scrolls sideways in its box). Chart legends move below the plot. Nothing overflows
the page width.

## Honesty rules (for design review)
- Skeleton shimmer only while a fetch is pending. No fake progress bars, no "live" dots, no sparkline filler.
- Every number on screen comes from the server response; chart counts are `shown`/`total` as given.
- Colour never carries meaning alone: type is a word, category is in the axis or legend, heatmap prints values.

## Changes this round
Ticket 408 (Board gate 167): `caption h2` is `--t-md` (1rem, 650, margin 0), not `--t-lg`; the global `h2` and `.brand`
stay `--t-lg`. Type scale and Components tables updated. (This supersedes item (2) of ticket 405 below.)

Design review (ticket 405), 1280, 800 and 375 px, light and dark, a demo folder with every chart kind, unreadable and
other files: no console errors, all charts drawn. Fixed: (1) the breadcrumb with a long unbroken file name made the
page scroll sideways by 104px at 375px, now `.crumb` has `overflow-wrap: anywhere`; (2) `caption h2` was 1rem, the
spec says `--t-lg`, now 1.25rem; (3) heatmap cell values used Plotly's automatic text colour (#444 on #6ea4ff, about
3.9:1 in dark), now drawn by `dashboard.js` `cellValues` in black or white by computed contrast. No token change.

Round 2 (ticket 394, architecture phase): `databoot.css` now styles `caption h2`, drops the upper-case and letter
spacing from `th` (also `th` size `--t-xs` to `--t-sm`), forces the mode bar to opacity 1, makes its buttons 28px
and gives focused ones the 3px `--accent` ring with a selector long enough to beat Plotly's own 1px black outline.
The engineer still has to change the two templates (`<caption><h2>`) and `dashboard.js` (`displayModeBar: true`,
button tabindex, `modebar` colours, z titles); until then the CSS rules are inert. No token change, no new colour,
no new motion. Mode-bar buttons are 28px (WCAG 2.2 target size minimum is 24px), smaller than the 44px of our own
controls because they belong to the library; the same data is in the tables.

Round 1 files: `app/static/css/databoot.css`; `app/templates/base.html` links it and adds the skip link, header and
`main#main`. Home, dashboard and `dashboard.js` use these classes.

Design review (ticket 386), checked in a real browser at 1280, 800 and 375 px, light and dark, reduced motion:
no sideways page scroll at any width, no console errors, every `.plot` has an aria-label, focus ring is 3px
`--accent`. Fixed: table links and the crumb link were 29px and 16px high, now 44px (`td a`, `.crumb a`);
table cells centre vertically so numbers line up with the link row; Modified dates no longer wrap (`td.nowrap`);
a blank `/static/blank.svg` icon (not a logo) stops the `/favicon.ico` 404 console error (no logo, no new route); 3D map
camera is pulled back at <= 599px so the lat/lon axis titles are not clipped; Plotly mode-bar buttons get the
same focus ring. Table names are `<caption>`s (styled like h2) rather than h2 elements. The mode bar uses
`displayModeBar: "hover"`, so its buttons are not in the tab order until shown; the same data is in the tables.
No token change.
