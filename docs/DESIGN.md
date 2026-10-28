# Design: DataBoot (round 5)

Stylesheet: `app/static/css/databoot.css` (all tokens and components below; linked by `app/templates/base.html`).
Sources: docs/PRD.md, docs/ARCHITECTURE.md ("Pages", "Round 5"), Board gates 160, 165 and 179: **branding unchanged:
DataBoot, plain neutral style, system sans font, no logo, blank SVG favicon** (`app/static/blank.svg`), text only
as titles, axis labels, `N of M` counts and one rule caption. No docs/TRENDS.md this round (`team: -trends`), so no
trend advice is used. No external fonts, images, icons or CDNs; no raster or SVG logo. The brand is the word
"DataBoot" set in the system font. No docs/brand/ and no site capture exist, so no logo is copied.

**Round 5 delta** (Board gate 179: **branding unchanged**, "Trends off" is a team setting, so no docs/TRENDS.md and no
trend advice is used; no logo, no new font, no image). Three apps share one shell, so there are new components but the
look is the same quiet panel:
1. Badge `App: Business (rule R2)` and the `View as` switch under the title (Components).
2. Business app: KPI cards with change arrow and sparkline, trend charts, leaderboard, drill breadcrumb, change table.
3. Map app: a 70vh map with a side panel (point details and top regions) and a `3D view` toggle.
4. Global chart rules for every chart in every app, including Explorer (section "Global chart rules", AC-57), and a
   `View as table` button on every Plotly figure.
5. Donut is drawn for 2 to 5 parts only (gate 179, AC-16): `--c1..--c5`.
6. Tokens: two new (`--seq-pt-lo`, `--delta-max`); every other colour, size, space and motion value is unchanged.
Explorer keeps its round 4 layout; only the chart rules and the table button apply to it.

**Round 4 delta** (Board gate 175; branding unchanged from gate 160; `team: -trends`, so no docs/TRENDS.md and no trend
advice is used; **no token change**: no new colour, size, space or motion value):
1. KPI strip under the page head (`dl.kpis`, Rows, Columns, Missing, up to three `<column> (sum)`).
2. Filter form (`form.filters`: one `.field` select per categorical column, two date inputs when a temporal column
   exists, `Apply`), then removable chips and `Clear filters` (`.chips-row`) only while a filter is active.
3. Grid: the first chart (highest score) spans the full width, all others sit two per row from 900px, one per row
   below. The round 2 rule that made map3d, country map and heatmap span both columns is gone (AC-34).
4. The rule caption ends in ` · score 0.NN`: same `.chart-rule` span and style, no new component. The score is
   text only: no meter, badge or colour scale, because the order of the grid already shows rank and a second
   encoding would repeat it.
5. Clicking a bar or donut slice filters (AC-39); the keyboard equivalent is the dropdowns, which do the same thing.
Everything below not mentioned here is as in round 2.

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
| `--delta-max` | 35% | 35% | most tint a change-table delta cell takes (the share of `--div-pos` or `--div-neg` mixed into `--div-mid`) | `--fg` on the full tint: 7.2 to 9.1 light, 5.8 to 5.9 dark (measured, `/tmp/contrast.py`) |
| `--seq-pt-lo` | #5f8ad3 | #5a7fc4 | low end of map point and hexagon colours | see below |
| `--ok` / `--warn` | #1b6e3c / #8a5300 | #6fcf97 / #e0a84a | reserved; always with a text label | >= 5.8 |

Chart palette (categorical, in this order, each >= 4.5:1 on `--surface`; colour is never the only carrier, the
legend or axis names the category):
`--c1..--c8` light `#1f5fbf #b85c00 #00796b #7b4fb3 #c0392b #6b7a00 #8a5a44 #b0306f`, dark `#6ea4ff #f0963c
#3fc1ad #b79bf0 #ff8a7a #b5c93a #d1a086 #f08ab8`. A chart with one series uses `--c1`. Donut uses `--c1..--c5`
in value order (the rule allows 2 to 5 slices, gate 179). Bars of one series are all `--c1`: bar height already encodes the
value, so no rainbow bars.
Sequential scale (country map, 3D map z): `--seq-lo` to `--seq-hi`. Map points and hexagon cells start at
`--seq-pt-lo` (light #5f8ad3, dark #5a7fc4: 3.2 / 4.4 on the land colour `--bg`, 3.5 / 4.0 on the sea `--surface`) because
the palest `--seq-lo` would vanish on the land; the colour bar uses the same two ends, so what is drawn is what is read. Diverging scale (correlation heatmap, -1 to
+1, fixed range, 0 at the middle): `--div-neg` (orange) via `--div-mid` to `--div-pos` (blue). Orange/blue is safe
for red-green colour blindness; each heatmap cell also prints its value to two decimals, so the number is read,
not guessed from the hue.

## Type scale
System stack `--font`: `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
(Segoe UI on the Windows 11 target). Code, file paths and cell values may use `--mono`.
| Token | Size | Use |
|---|---|---|
| `--t-xl` | 1.75rem (1.5rem at <= 599px), weight 650 | h1, Business card figure |
| `--t-lg` | 1.25rem, 650 | h2, brand |
| `--t-md` | 1rem, line-height 1.5 | body, chart title (650), table titles (`caption h2`, 650), side-panel heading |
| `--t-sm` | 0.875rem | tables, `th` (650, `--muted`, original case), captions, notes |
| `--t-xs` | 0.8125rem | badges |
Numbers in tables and counts use `font-variant-numeric: tabular-nums` and right-align (`.num`). Thousands
separators are used everywhere (Board gate 161), through the `num` filter.

## Spacing, shape, layout
4px grid: `--s1..--s7` = 4, 8, 12, 16, 24, 32, 48. Radius 6px. Max content width 1200px, centred. Page padding
16px (24px from 900px). Tap targets (buttons, brand link, table links) are at least 44px high (`--tap`).
Breakpoints: `<= 599px` phone (gate 175: "phone width" is this one), `600-899px` single column, `>= 900px` two-column chart grid.

## Components
| Class | What | States |
|---|---|---|
| `.site-header .brand` | white bar, "DataBoot" text link to `/` | hover accent colour, focus ring |
| `.skip` | "Skip to content", first focusable element | visible only on focus |
| `.page-head` | h1 left, `.actions` right; wraps | |
| `.btn`, `.btn-primary` | download links (`Export PPTX`, `Export XLSX`) | hover (soft fill, accent border), focus ring, active 1px press |
| `.table-wrap > table` | scrolls sideways inside its own box, page never scrolls sideways. Title is `<caption><h2>Name</h2></caption>`: `caption` pads 12/16/8px, `caption h2` has margin 0 and `--t-md`. `th` shows names exactly as read (`Latitude`, `LON`) | row hover soft fill |
| `.js-plotly-plot .modebar` | Plotly tool bar, drawn by the library, restyled only by the CSS here: opacity 1 always, buttons 28px min, icons `--muted` | focus ring 3px `--accent`, active icon `--accent` |
| `dl.kpis > div` | KPI tile: `dt` label (`--t-sm`, `--muted`), `dd` figure (`--t-lg`, 650, tabular numbers, thousands separators). Surface card, hairline border. Not interactive | none |
| `form.filters`, `.field` | `<label>` above a native `<select>` or `<input type="date">`, 44px high, `--line-strong` border, `--surface` fill, `--fg` text (the controls take `color-scheme`). `.field` is `div.field > label + select` (id on the control, `for` on the label). Fields are 160-260px wide and wrap; `Apply` is a `.btn` in the same row | hover accent border, focus ring |
| `.chips-row > ul.chips > li > a` | active filter, a pill with the label text (`region = North`) and a CSS `×`; the link removes that filter and has `aria-label="Remove filter region = North"`. After the list comes `a.btn` `Clear filters`. The row is not rendered with no filters | hover surface fill, focus ring |
| `.page-title > h1 + .app-badge` | the badge sits under the h1 (a `span`, never `<p>`): `App: Business (rule R2)`, pill, `--surface` fill, `--line-strong` border, `--t-sm` 600. Text only: it states the detected app and rule, nothing else | none (not interactive) |
| `nav.view-as > .view-as-label + ul > li > a` | `View as` label and a joined row of links, one per app the dataset qualifies for (44px high, `--line-strong` border, radius on the ends). The shown app is `aria-current="page"`: `--accent-soft` fill, `--accent` 2px border and the link text; hover soft fill. The whole nav is not rendered when only Explorer qualifies | hover, focus ring, current |
| `ul.cards > li.card` | Business KPI card: `.card-label` (measure name, `--muted`), `.card-value` (`--t-xl`, tabular, separators; `n/a` when there is no full period), `.card-change` (`<span aria-hidden>▲</span>`, `+19.4%`, `up`; ▼ with `down`; ▶ with `no change`; always three parts, **neutral `--fg`, never green or red**, because up is not always good), `.card-period` (`month 2024-06 vs 2024-05`, `--muted`), `svg.spark` below. With no previous value `.card-change` is absent | none |
| `svg.spark` | sparkline: `viewBox="0 0 100 36" preserveAspectRatio="none"`, one `<polyline>` of the last 12 periods (2px `--c1`, non-scaling stroke), `role="img"`, `aria-label` and `<title>` such as `revenue, last 12 months`. Drawn only with 2 or more periods. No axis, no fill, no end dot (the stretch would turn it into an ellipse) | none |
| `nav.crumbs > ol > li` | drill path `All › region: North`; every crumb but the last is a 44px link, the last is `<span aria-current="page">` in 650 weight. `›` is CSS (`content` with empty alt) | hover underline, focus ring |
| `td.delta` + `.pos`, `.neg` or `.zero` | change-table delta cell, with `style="--t: 0.42"` (the payload's `t`, signed or not: CSS takes its absolute value). Text is the signed number (`+1,200`, `-35`, `0`) in `--fg`, right-aligned, 650 weight. Fill: `zero` is `--div-mid` (grey); `pos` mixes `--div-pos` (blue) into `--div-mid` and `neg` mixes `--div-neg` (orange) by `|t| * --delta-max`. Two hues and a grey midpoint, and the sign is in the text, so colour is never the only carrier | none |
| `.btn[aria-pressed="true"]` | any toggle button (`View as table`, `3D view`): `--accent-soft` fill and a 2px `--accent` edge (inset, no layout shift). The label never changes; the pressed state says which view is on | hover, focus ring |
| `button.btn.table-toggle` | `View as table`, last child of every Plotly `figcaption`, right-aligned at >= 600px, under the count at <= 599px (44px high). Pressed: `.plot` gets `hidden` and a `div.plot-table-wrap[tabindex="0"][role="region"][aria-label="<title> data"] > table.plot-table` takes its place, scrolling inside its own box (max 320px high, 420px for maps and heatmap), sticky header, numbers right-aligned with separators. Pressed again: the table is removed and the plot shown. No animation | hover, focus ring, pressed |
| `.map-layout > figure.chart + aside.map-panel` | Map page body: map left, panel right (340px) from 900px, stacked below. Panel = `.panel-box` with `h2` `Selected point` and its `dl` (or `.panel-empty` text `Click a point to see its row.` / `Click a cell to see its count.`), then a `.panel-box` holding the top-regions figure. `aria-live="polite"` on the details box | none |
| `.badge` | column type label (`numerical`, `categorical`, `temporal`, `geospatial`, `other`) in a pill, text always shown | |
| `.note`, `.note-error` | left-bar message, used for fixed labels like `could not be read` | |
| `.empty` | dashed box: "No charts for this dataset" style fixed label, only when `charts == []` | |
| `figure.chart` | card: figcaption on top (`.chart-title`, `.chart-rule`, `.chart-count`), `.plot` below | loading, drawn, error |
| `.plot.is-loading` | skeleton while `/charts` is pending | removed on success or error |
| `.plot-error` | fixed text `Chart could not be drawn` in `--danger` | |

### States
- **Filtered**: a filter is a normal page load (GET), so there is no spinner of ours; the browser shows its own.
  The page after it shows the chips, the matching selects and dates, and the KPI and chart counts of the filtered
  rows. A chart whose rule no longer matches is simply absent (gate 175), with no placeholder. If no chart is left,
  the one `.empty` box shows; if no row is left the KPIs read 0 and `Missing` reads `0.0%`.
- **Loading**: only `.plot.is-loading`, set from the first paint until the fetch settles. It is a real pending
  request, so the shimmer is honest; it ends in a drawn chart or `.plot-error`. With reduced motion it is a flat
  `--line` block.
- **Empty**: Home with no datasets shows the folder path and hides empty tables (ARCHITECTURE "Pages"). A dataset
  with no matching rule shows the types table, the first-20-rows table and one `.empty` box in place of charts.
- **Error**: unreadable files are listed in their own table with the fixed reason in a `.note-error` cell; a failed
  fetch puts `.plot-error` in that figure only; the other charts still draw.
- **Hover/focus**: described per component. Plotly hover tooltips use `--surface` background, `--line-strong` border, `--fg` text (`hoverlabel`).
- **Table view**: `View as table` swaps the plot for the table of the plotted values in the same box; no spinner, no
  motion. A figure that failed to draw has no toggle.
- **Business with too little history**: no full period gives `n/a` cards, no sparkline and no change table; one
  period gives a card with `n/a` change and no arrow. Nothing is filled in to look busy.
- **Drill at the last level**: leaderboard bars are not clickable (`data-drill="false"`, default cursor) and the
  breadcrumb's last crumb is the current page.
- **Map with no coordinates left** (a filter removed them): the figure keeps its 70vh box with Plotly's empty map and
  the count reads `0 of M rows`; the panel shows its empty text.

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
- Round 5 kinds (the global rules above apply; every builder also sets `hoverlabel`, `separators: ".,"`, `hoverformat`/
  `tickformat: ","`):
  - **Trend** (Business) = the line above, `--c1` 2px, one y-axis titled with the measure, y from 0, plot 260px
    (240px at 375). Markers when `shown <= 40`. One chart per measure, never a second axis.
  - **Leaderboard** (`orientation: "h"`) = bars `--c1`, `yaxis.autorange: "reversed"` so the biggest is on top,
    `xaxis.rangemode: "tozero"`, `texttemplate: "%{x:,}"`, `textposition: "outside"`, `cliponaxis: false`, `automargin`
    on y so long labels fit, a 72px right margin for the value text, plot 420px. The `Other` bar is its own trace in
    `--muted` (neutral grey, not a palette colour, so it is the only grey bar), on the same category axis and order
    (`barmode: "overlay"`). Figure carries `data-leaderboard`, and `data-drill="false"` at the last level. Plotly shows
    no pointer over bars itself, so `dashboard.js` toggles a class on the figure from `plotly_hover` / `plotly_unhover`:
    `bar-click` (CSS `cursor: pointer`) over a bar that drills, `no-pointer` (CSS `cursor: default`) over `Other` and
    over every bar at the last level. Clicking `Other`, or any bar at the last level, does nothing.
  - **map2d** (`scattergeo`) = `geo`: `projection natural earth`, `fitbounds: "locations"`, `showland` with `landcolor`
    `--bg`, `bgcolor` `--surface`, `countrycolor` and `coastlinecolor` `--line-strong`, `showframe` off, no tiles. Plot
    height is 70vh (AC-51: 65 to 75% at desktop and phone). Points = markers size 6, opacity 0.8, 0.5px `--muted`
    outline so the palest still reads on the land, colour on the `--seq-pt-lo` to `--seq-hi` scale, colour bar titled
    with the primary numeric's column name (at <= 599px the colour bar is horizontal under the map, 72px bottom margin, because a
    vertical one took half of the 375px and shrank the map to a patch); rows with no value form a second trace in `--muted` and the legend shows.
    Hovering a point shows its place and value with separators; click fills the panel.
  - **Hexbin** (more than 5,000 points) = cells at **true geographic size**, so neighbours touch at every zoom. Draw
    them as one `choropleth` of an inline GeoJSON of hexagons built in `dashboard.js` from the server's centres and
    `size` (vertex = centre + size x (cos, sin) of 30, 90, 150, 210, 270 and 330 degrees), `z` = count, same sequential
    scale, colour bar titled `Points per cell`, 0.5px `--bg` cell edges, tooltip `1,234 points`. Fixed-pixel markers are
    not allowed: they would overlap or leave gaps and so show a density that is not in the data. A click shows
    `Points in cell: N` in the panel.
  - **Top regions** = a leaderboard (same rules, plot 360px, `drill` false, so no pointer; in the 340px panel the value axis has
    3 flat ticks, because 8-digit sums rotated and overlapped). The 3D view is the
    round 2 `map3d` figure, 70vh, in the same place.
  - **Phone map**: `dragmode: false` at <= 599px so a finger drag scrolls the page instead of panning the map; the mode
    bar's zoom and reset buttons still work. Desktop uses `pan`; wheel zoom stays off (`scrollZoom: false`).
- Honest data: the point count shown in `.chart-count` is the server's `shown`/`total` (`N of M points` or `N of
  M rows`). When `shown < total` the caption says so and nothing else; no smoothing, no fake trend line. Plotly
  default transitions are off (`transition: {duration: 0}`), so no chart animates on load.
- Cross-filter (AC-39): bar and donut categories are clickable (Plotly's own pointer cursor over a bar or slice is the
  only hint; no text and no icon is added). Click sets `f.<x_label>=<category>` and reloads; a second click on the same
  category removes it. With one value selected a donut drops out (its rule needs 2 to 5 slices), but a bar chart stays
  with the single remaining bar (seen in the ticket 437 review), which is the bar a second click un-filters; no
  "selected bar" style is drawn, the chip and the select already say what is applied. Mouse-only by nature; the dropdowns and chips are the keyboard and touch-reader route to the same result.
- Keyboard and screen reader: each `figure` has `aria-label` = chart title; each `.plot` has `role="img"` with
  `aria-label` = `<title>: <rule caption>`; the data is also in the first-20-rows table above/below.

## Global chart rules
Apply to every Plotly figure in every app (Explorer, Business, Map; AC-57). Each rule says what the code must do.
1. **Magnitude = sorted bars from zero.** Bars sort descending (Business leaderboard: top 10, then `Other` last, in
   `--muted` grey as its own trace with no pointer cursor, so it reads as the remainder, never a palette colour), the value axis starts at 0
   (`rangemode: "tozero"`), horizontal when labels are long, value printed on each bar in the leaderboard.
2. **Change over time = line.** One line per chart, time on x; no bars for time and no smoothing. A partial last
   period is not drawn (Business trend stops at the latest full period).
3. **Part-to-whole = stacked bar; donut only for 2 to 5 parts.** With 6 or more parts no donut is drawn. A part-to-whole
   chart with 6 or more parts must be one stacked bar from zero (none exists yet; the rule is for the next one).
4. **One y-axis always.** No `yaxis2`, no `overlaying`, no dual axis. Several measures make small multiples: one
   chart per measure (Business trends, one to three of them).
5. **Fixed categorical palette order, at most 8, then `Other`.** `--c1..--c8` in that order, never reshuffled by
   data; more than 8 categories fold into one `Other` in `--muted`. One series is always `--c1`.
6. **At most 3 colour series on a scatter or a map.** Map points are one sequential series plus an optional
   `--muted` series for rows without a value (2); scatter is 1. A fourth series is folded or dropped.
7. **Sequential = one hue, light to dark** (`--seq-lo` or `--seq-pt-lo` to `--seq-hi`: the same blue). **Diverging = two
   hues with a grey midpoint** (`--div-neg` orange, `--div-mid` grey, `--div-pos` blue; heatmap and change table).
   The midpoint is the zero of the data, never a hue.
8. **Legend at 2 or more series, direct labels at 4 or fewer.** One series has no legend (the title says what it is);
   with 2 to 4 series the series name is also printed at the end of its line or bar; with more than 4 only the legend.
9. **Every chart has a tooltip and a table toggle.** Tooltip (`hoverlabel`) on every mark, none of `hoverinfo: "none"`
   or `"skip"`; `View as table` (Components) shows the plotted values. The sparkline is not a chart, has no toggle
   and keeps its `<title>`.
10. **Thousands separators everywhere.** Axis ticks (`separators: ".,"`, `tickformat: ","`), tooltips (`:,`), bar
    labels (`%{x:,}`), cards, panel values, table cells and the table view; one decimal for percents (`+19.4%`).

## Motion rules
1. Only two moving things exist: the loading shimmer (real pending fetch) and the 160ms colour transition on
   buttons and View-as links. Drill, `View as`, `View as table` and `3D view` are instant swaps or page loads; the
   sparkline and cards do not animate. Nothing animates because data is "live"; the app does not poll.
2. No scroll reveals, no count-up numbers, no entrance animation of charts.
3. `prefers-reduced-motion: reduce` removes all transitions and animations (blanket rule at the end of the CSS).
   Plotly 3D rotation is user driven only (drag); never auto-rotate.

## Accessibility
- Contrast as in the token tables. Focus: 3px `--accent` outline, 2px offset, on every link and button
  (`:focus-visible`); contrast with the surface >= 3:1 in both themes.
- Tab order (Business, Map): skip, brand, export links, View-as links, filter controls, `Apply`, chips, crumbs, then
  for each figure its `View as table` button and its mode-bar buttons (and `3D view` first on the map), table links.
  Explorer is as in round 4. A table view's scroll box is focusable (`tabindex="0"`) so the keyboard can scroll it.
  Leaderboard drill by keyboard: the filter dropdowns and the crumbs do the same (the `keyboardBar` of round 4 also
  works); the 3D toggle is a button.
- Tab order (round 4): skip link, brand, page actions, chart mode-bar buttons (visible, 28px, ring on focus), table links.
  Landmarks: `header`, `main#main`. Mode-bar buttons have an `aria-label`.
- One `h1` per page, then `h2` per table (inside its `<caption>`), no skipped level; figures keep a figcaption
  title, not a heading. Tables have `caption` and `th scope`. Type badges carry text.
- The sparkline has `role="img"` and a label; the arrow is `aria-hidden` and the words `up`, `down`, `no change` carry it.
  The badge and View-as are text. On the phone the map must not trap the page scroll (see Map at 375px).
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
1. `dl.kpis`: a row of tiles, `repeat(auto-fit, minmax(150px, 1fr))`, 12px gap; 4 to 6 tiles fill the width.
2. `form.filters`: one row of fields that wraps, `Apply` last. No card around it: the controls themselves are white
   (surface) boxes on the page background.
3. `.chips-row` (only with an active filter): chips left to right, `Clear filters` last.
4. `.charts` grid, two columns; max 8 cards in **score order** (highest first, ties in the rule order of ARCHITECTURE
   "Round 4: interest score"). The first card spans both columns; the others sit two per row (cards 2 and 3, 4 and 5, 6
   and 7, 8 alone on the left, as the grid fills). Plot heights are unchanged (320px, 300 donut, 420 maps and heatmap):
   rank shows in the width and the position, not in extra height. Each card: title, rule caption ending in `· score
   0.NN`, `N of M`, plot.
5. Columns table (caption h2 `Columns`): column | type badge.
6. First rows table (caption h2 `First 20 rows`, the number comes from the server): `.data-table` scrolling
   inside its wrap, cells truncated with ellipsis at 28ch, headers in the file's own case.
The First rows table stays below every chart; it has no score and no caption line (gate 175). The KPIs and filters
come first because they say what the charts below are about.
375px: crumb, h1, buttons full width stacked (44px each), KPI tiles two per row, filter fields stacked full width
(44px each, `Apply` full width), chips wrapping, then charts one column in score order (plot 280px, maps and heatmap
340px), columns table, rows table (scrolls sideways in its box). Chart legends move below the plot. Nothing overflows
the page width.

### The shell, Business and Map (round 5)
The dashboard page is a shell plus one app body. Shell, in order: `.crumb`; `.page-head` with `.page-title` (h1, then
`.app-badge`) and `.actions`; `nav.view-as` (not rendered when only Explorer qualifies); then the body. Explorer's body
is the round 4 body above, unchanged. The filter form and chips are the same component in all three apps and sit
directly under the shell (Business and Map) or after the KPI strip (Explorer, as in round 4).

**Business, 1280px** (single column, `main` max 1200px), in this order:
1. `ul.cards`: one card per measure (1 to 3), `repeat(auto-fill, minmax(240px, 1fr))`, 12px gap, so 3 cards sit in a
   row of 4 slots and a lone card is not stretched across the page. The card order is the measure order (primary first).
2. `form.filters`, then `.chips-row` when a filter is active.
3. `nav.crumbs` (`All › region: North`); with no active categorical filter it holds just `All` as the current page.
4. `.trends`: one `figure.chart` per measure, `repeat(auto-fit, minmax(300px, 1fr))`: one measure fills the row, two
   share it, three sit in a row (about 380px each). Plot 260px.
5. `.biz-grid` (two columns from 900px, `1.2fr 1fr`, top aligned): left the leaderboard figure (`data-leaderboard`, plot
   420px), right the change table in a `.table-wrap` (`table.delta-table`, caption h2 `Change`, columns Category,
   Previous, Latest, Delta; numbers `.num`; the delta cell as in Components, its row in the leaderboard's order).
   Absent (and the leaderboard full width) when there is no previous period.
6. Columns table, First rows table, as in Explorer (First rows last).
**Business, 375px**: crumb, h1, badge, buttons stacked full width, View-as links (each at least 44px), cards one per
row (value 1.5rem, sparkline full card width), stacked full-width filters, chips, crumbs wrapping, trend charts one per
row (240px), leaderboard (420px), change table (scrolls inside its box), Columns, First rows. `figcaption` stacks:
title, rule, count, then the `View as table` button full height 44px at the start.

**Map, 1280px**: shell, filters and chips, then `.map-layout` with two columns: the map figure left (card with title,
rule, `N of M rows` and the `View as table` button on the right of the caption, then the 70vh
plot; the `3D view` button is in its own `.map-head` row above the layout so it stays reachable while the 2D figure is hidden) and `aside.map-panel` right, 340px wide and sticky at 16px: a `.panel-box` `Selected point` (a `dl` of column
and value, label column 40%, or the empty text) and a `.panel-box` with the top-regions figure. A hidden
`figure[data-kind="map3d"]` shares the map's place: `3D view` hides the 2D figure and shows it, pressed again swaps
back; both have the same height so the page does not jump. Then Columns and First rows.
**Map, 375px**: the same order in one column: map (70vh, finger drags scroll the page), then the panel (details, then
regions), then the tables. The caption buttons stack under the count. No horizontal scroll at any width.

## Honesty rules (for design review)
- Skeleton shimmer only while a fetch is pending. No fake progress bars, no "live" dots, no sparkline filler.
- The score is the server's number, printed as given; the order is the order of the data, not a styled ranking. Chips and
  selects show only filters that are in the URL; nothing is highlighted that is not applied.
- Every number on screen comes from the server response; chart counts are `shown`/`total` as given. The change arrow
  and percent are the server's `dir` and `pct`, printed as given. Sparklines and cards are drawn from the same sums as
  the trend; the trend stops at the latest full period so a half-finished month is never drawn as a fall.
- The badge says which rule matched; `View as` lists only apps the dataset really qualifies for. Delta tints scale
  with the real delta divided by the largest one, and zero is grey. Hexagon cells are true size; their colour is the
  count. Nothing pulses, counts up or auto-refreshes.
- Colour never carries meaning alone: type is a word, category is in the axis or legend, heatmap prints values.

## Changes this round
Design review (ticket 458, round 5), 1280 and 375 px, light and dark, a demo folder (shop.csv Business, places.csv Map,
60,000-point hexbin map, measures.csv Explorer, long-named TSV, unreadable file, notes.txt, a 404): scrollWidth equals the
viewport everywhere (no sideways scroll at 375), all drawn plots without `.plot-error`, no console error except the expected 404,
no tap target under 44px outside the Plotly mode bar. Fixed in `dashboard.js`: (1) Business trend lines start at y = 0 as the
spec says (they auto-ranged, so 14,000 to 16,000 looked like a swing); (2) phone map colour bar is horizontal under the map;
(3) top-regions bar has 3 flat ticks in the narrow panel. The `3D view` row is now documented as built. No token change.

Round 4 (ticket 429, architecture phase, Board gate 175): `databoot.css` gains `.kpis`, `.filters`/`.field`,
`.chips-row`/`.chips`, drops the map3d/country_map/heatmap grid span and adds `.charts > .chart:first-child` (full
width), and the phone rule gets two-column KPIs and full-width fields. The templates and `dashboard.js` do not use
them yet: the frontend ticket must emit exactly the markup in Components (`dl.kpis > div > dt + dd`, `form.filters >
.field`, `.chips-row > ul.chips`, `a.btn` `Clear filters`) and keep one `.chart-rule` per figure. Tab order is now:
skip, brand, export links, filter controls, `Apply`, chips, `Clear filters`, mode-bar buttons, table links. Contrast:
chip text is `--fg` on `--accent-soft` (> 12:1 both themes), chip border `--accent` against the page 5.7 / 7.5, control
border `--line-strong` 3.2 / 4.3 (>= 3:1 for a control edge). No new motion; reduced motion unchanged. No token change.

Design review (ticket 437, round 4), 1280, 800 and 375 px, light and dark, a demo folder (sales.csv with 3D map, lines,
histogram, bars, donut, scatter and, filtered by region + dates, a heatmap; countries.csv with country map; a long-named
TSV; an unreadable file; a notes.txt; a 404), keyboard pass in light and dark with reduced motion: scrollWidth equals
the viewport everywhere (no sideways scroll at 375), all plots drawn, no `.plot-error`, no console error except the
expected 404, KPI tiles (two per row at 375), filter fields (stacked, 44px), chips and `Clear filters` as specified,
first chart full width and the rest two per row from 900px, the First rows table last. Country map and histogram at half
width read fine at their current heights. Every Tab stop shows the 3px ring; the one exception is the browser's own
calendar button inside a date input, which Chrome rings itself. The only smaller-than-44px controls are the Plotly mode
bar buttons (28px, documented). Nothing fell short, so no template, CSS or script change. No token change.

Design review (ticket 413), 1280 and 375 px, light and dark, Home, three datasets (8 charts incl. 3D and country map; a
long-named TSV; an unreadable file), a 404: no sideways scroll (scrollWidth = viewport), all 10 plots drawn, no `.plot-error`,
no console error except the expected 404, tap targets >= 44px, `th` text-transform none, 40 Tab stops in dark with reduced
motion all show a >= 2px outline. Nothing fell short, so no template, CSS or script change. No token change.

Design review (ticket 410), 1280 and 375 px, light and dark, every page of a demo folder (3D map, country map, line, bar,
donut, histogram, scatter, unreadable and other files, a 404): no sideways scroll, no console error except the expected
404 of an unknown id, all charts drawn, tap targets >= 44px. One fix: the 3D map camera is pulled back (eye 1.8/1.8/1.2 at
desktop, 3/3/1.9 at <= 599px) because the lowest lat/lon tick labels were cut at the bottom of the scene at 1280 and the
`elev` axis title was cut at the left at 375. Layout `margin.b` stays 40 (ticket 407). No token change.

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

Round 5 (ticket 443, architecture phase, Board gate 179): `databoot.css` gains, with no template or script using them
yet (**inert until the frontend tickets emit exactly the markup in Components and "The shell, Business and Map"**):
`[hidden]{display:none!important}` (needed because `.chart` and `.btn` set `display`, so the hidden 3D figure and the
hidden `.plot` would otherwise show), `.page-title`, `.app-badge`, `.view-as`, `.btn[aria-pressed="true"]`,
`.table-toggle` (and a two-column figcaption: title block left, button right, one column at <= 599px; Explorer figcaptions
have no button, so they look as before), `.cards`/`.card`/`.spark`, `.crumbs`, `.biz-grid`, `.trends`,
`.delta-table td.delta`, `.map-layout`, `.map-panel`, `.plot-table-wrap`/`.plot-table`, `[data-leaderboard]` and
`[data-drill="false"]`. Tokens added: `--seq-pt-lo`, `--delta-max`. Contrast measured for the delta cells (`--fg` on the
full 35% tint: light 8.5 pos, 9.1 neg; dark 5.9 pos, 5.8 neg), for the point low end against land and sea (above) and
`--seq-hi` against the page (5.7 / 8.4). Checked in a scratch page at 1280 and 375 (light and dark): tints resolve,
hidden figure is `display: none`, no sideways scroll. Differences from the architecture text, for the frontend ticket:
(a) hex cells are a GeoJSON `choropleth`, not fixed-pixel hexagon markers (true size), (b) the table toggle keeps one
label and uses `aria-pressed`, (c) `dragmode: false` on the phone map, (d) trend lines are all `--c1`. Tab order and
reduced motion are as listed above; no new motion. Donut text in Charts and Cross-filter now says 2 to 5.
