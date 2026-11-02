# Design: DataBoot (round 7)

Stylesheet: `app/static/css/databoot.css` (all tokens and components below; linked by `app/templates/base.html`).
Sources: docs/PRD.md and docs/ARCHITECTURE.md ("Round 7: ..."), Board gates 160 and 189 and the IDEA's numbered list.
**Branding unchanged (gates 160 and 189): the name DataBoot, system fonts, no logo, the blank SVG favicon**
(`app/static/blank.svg`). **No docs/TRENDS.md this round (`team: -trends`), so no trend advice is used.** No external
fonts, images, icons or CDNs; the only graphics are inline SVG icons drawn here (move, expand) and CSS. The prototype
`docs/reference/databoot-console.html` is **not on disk** (gate 189 allows building from its description); this document
turns that description into tokens and rules. Where the description and the IDEA's numbered list differ, the list wins, so
the prototype's "(dev only) sample" button is not designed.

## Round 7 theme and tiles (read this first; it overrides the older sections that disagree)

**What changed.** One dark holographic theme replaces the light/dark pair; every page body is a 12-column grid of one shared
glass tile; Home becomes a drop portal; a scan log sits between upload and workspace. Everything below this section that
speaks of light mode, `prefers-color-scheme`, "no gradients, shadows or animation", "no entrance animation" or "no scroll
reveals" is **replaced** by this section (the older sections are kept for the component details that still hold). Behaviour,
routes, figures' data, the global chart rules (one y-axis, bars sorted and from zero, direction never by colour alone) and
exports do not change.

### Tokens (dark only; `:root` in the CSS, `color-scheme: dark`)
Contrast measured with the WCAG formula (`/tmp/c7.py`, not kept) against the **effective** surfaces: the page `--bg`
#050a12, the glass tile (top #0f1f34, bottom #070e19, from rgba(22,46,76,.58) and rgba(8,18,32,.50) over `--bg`) and the worst
case under the cursor glow (#193e54: the lightest tile colour with the glow at its 12% peak; I measured 16% to get margin,
the CSS uses 12%). Text needs 4.5:1, graphics and control edges 3:1. Pairs below are "bg / tile top / tile bottom / under glow".

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--bg` | #050a12 | page | |
| `--surface` | #0c1a2c | opaque stand-in for glass: hover labels, sticky table head, overlay, reduced-transparency tiles | |
| `--field` | #07111d | inputs, selects, type badge fill | fg 16.6, muted 7.8, `--line-strong` edge 5.1 |
| `--fg` | #e6f1fa | text | 17.3 / 14.5 / 16.9 / 9.9 |
| `--muted` | #93a9bf | captions, mono sublabels, `th` | 8.2 / 6.9 / 8.0 / 4.7 |
| `--accent` | #4de1ff (cyan) | tile titles, links, focus ring, primary button, current tab, brackets | 12.8 / 10.7 / 12.5 / 7.3 |
| `--on-accent` | #031018 | text on a cyan button | 12.4 |
| `--amber` | #ffb454 | filter chips, app badge, drag target, last scan line | 11.3 / 9.4 / 11.0 / 6.4 |
| `--danger` | #ff8a80 | unreadable notes, chart error, scan line with a note | 8.7 / 7.3 / 8.5 / 4.95 |
| `--ok`, `--warn` | #7ee787, #ffb454 | reserved; always with a text label | >= 7.3 everywhere |
| `--line` | rgba(120,220,255,.16) | hairlines, chart grid (decoration only) | n/a |
| `--tile-edge` | rgba(120,220,255,.22) | tile, table, header border (the prototype's value) | n/a |
| `--line-strong` | #5f8aa3 | button, input, badge edges (graphic) | 5.3 / 4.5 / 5.2 / 3.0 |
| `--accent-soft` | rgba(77,225,255,.14) | hover fill, current tab and View-as fill | fg on it 10.4 |
| `--amber-soft` | rgba(255,180,84,.14) | chip and badge fill | fg on it 11.0, amber on it 7.1 |
| `--glass` | linear-gradient(160deg, rgba(22,46,76,.58), rgba(8,18,32,.50)) | tile, table box, scan panel, portal message | |
| `--glass-shadow` | inset 0 1px 0 rgba(255,255,255,.08), 0 8px 32px rgba(0,0,0,.35) | the inner top highlight and the lift | |
| `--glow` | rgba(77,225,255,.12) | cursor glow peak | |
| `--blur`, `--tile-radius` | blur(14px), 14px | tile glass, tile corner | |
| `--delta-max` | 30% | most a change-table delta cell takes of the hue (was 35%) | `--fg` on the full tint: 5.9 cyan, 6.4 amber |

Chart palette (`--c1..--c8`, each >= 4.9:1 even under the glow; the series order is fixed, a one-series chart is `--c1`):
`#4de1ff #ffb454 #7ee787 #b79bf0 #ff8a7a #9aa9ff #d1a086 #f08ab8` (cyan, amber, green, violet, coral, periwinkle, tan, pink).
The donut (2 to 5 slices) uses `--c1..--c5`. Sequential scale `--seq-lo` #17405c to `--seq-hi` #4de1ff; map points and hexagons
start at `--seq-pt-lo` #3a8fb8 (5.5 on the page, 4.6 on the tile). Diverging scale: `--div-neg` #ffb454 (amber), `--div-mid`
#222b35, `--div-pos` #4de1ff (cyan): two hues with a neutral grey midpoint (saturation under 0.08, which AC-69 tests), still safe for red-green colour blindness, and the sign is
always in the text. `--div-mid` is 1.16:1 against the tile, so **every Likert segment keeps its 1px `--line-strong` edge** (unchanged)
and delta cells keep their signed text. `dashboard.js` reads every one of these as `#rrggbb` (except `--line`, which Plotly accepts as
rgba); keep them in that form. Heatmap, cross-tab and Likert cell text stays black or white by computed contrast.

Type: still the system stack `--font` for text, titles and buttons. New `--mono` use (system monospace: `ui-monospace, "Cascadia Mono",
Consolas, Menlo, monospace`; Cascadia Mono on the Windows 11 target): **labels** (`--t-label` 0.75rem = 12px, letter-spacing 0.06 to
0.08em): tile and table titles in `--accent`, sublabels, `View as`, field labels, KPI and card labels, chart rule and count, app badge,
archetype caption, tabs, the brand; and **figures**: KPI and card values at `--t-xl` (28px; 24px at <= 599px, the prototype's 24 to 32px
range), tile min/max values, scan log lines. **`text-transform` is for tile titles only** (Board gate 190):
`.ws-head h2` is mono, UPPERCASE (`text-transform: uppercase`) with letter-spacing, as in the prototype. The ban on `text-transform` applies to
table column headers: `th` shows names as read, and `tests/test_pages.py::test_headers_keep_their_case` checks only the CSS rules whose selector
targets `th`. Figure titles (`.chart-title`) and table caption `h2` also get **no** `text-transform`, because `tests/test_acceptance.py:481-488`
and `:1382` compare their `inner_text` in real case. The archetype caption is upper-cased by the server (`|upper`), and omits `G<n>` when it is zero. `th` stays in the sans font and in the file's case. Deltas are always
arrow + signed percent + word (`▲ +19.4% up`), never colour alone.

### Page shell
- **Header** (`.site-header`, sticky, 56px, `rgba(5,10,18,.78)` with `--blur`, `--tile-edge` bottom line): the brand `DataBoot` (mono,
  700, `--t-lg`, `--accent`) then `nav.tabs` (below). Opaque `--bg` with reduced transparency.
- **Tabs** `nav.tabs[aria-label="Datasets"] > ul > li > a`, inside `.site-header .inner`, outside `<main>`: one link per dataset
  (`path` or `path - sheet`), mono 12px, 44px high, `--muted`; hover `--fg` on `--accent-soft`; the current one has
  `aria-current="page"`, `--accent` text, a 2px `--accent` bottom edge and the soft fill. Names longer than 30 characters end in an
  ellipsis (`max-width: 30ch`). Many tabs scroll sideways inside the nav (`overflow-x: auto`), never the page. At >= 900px the tabs sit
  on the brand's row; at <= 599px the tabs take their own full-width row under the brand (`order: 3`). Tab order: skip, brand, tabs.
- **Page head** order: crumb, `.page-title` (h1, `.archetype`, `.app-badge`), actions, `View as`, controls (period links, filters,
  chips, Business crumbs), then the grid. `.archetype` and `.app-badge` share one wrapping line under the h1, and the figure heading
  `.chart-h` has no margin and the label font, so the shell adds no height above an untiled Map (test_AC_59 hovers every point at 1280x900).
- **Archetype caption**: `<div class="archetype">APP: BUSINESS · RULE R2 · T1 N2 C2 · 288 ROWS</div>` (exactly the architecture's
  string: G only when non-zero, rows with the plural word). Mono 12px, 0.08em, `--accent`. Not a `<p>`. The badge under it,
  `<span class="app-badge">App: Business (rule R2)</span>`, is an amber pill (mono 12px 600, `--amber` text and edge, `--amber-soft`
  fill). Chips (`.chips a`) are amber pills too: `--amber` edge and `×`, `--amber-soft` fill, `--fg` text (11.0:1), 44px high.
- **Controls** keep their components; they are re-skinned by the tokens only: `.btn` is `rgba(77,225,255,.06)` with a `--line-strong`
  edge, hover `--accent-soft` and an `--accent` edge; `.btn-primary` is solid `--accent` with `--on-accent` text; inputs are
  `--field`; View-as and period links use the same joined row with the cyan current state.

### The tile (`section.ws-tile`, one component for every app)
Markup is the architecture's macro (`_tile.html`): `section.ws-tile[data-tile][data-span][aria-label]` > `div.ws-head` (the `h2` when
the tile has its own heading, then the move and expand buttons) > the body. Parts:
1. **Surface**: `--glass` fill, 1px `--tile-edge` border, radius `--tile-radius`, `--glass-shadow`, `backdrop-filter: --blur`.
   Corner brackets: 16px L-shapes in `--accent`, top-left and bottom-right (`::before`, `::after`, 2px, decorative, `pointer-events:
   none`). Padding 16px (12px at <= 599px). Direct children of the grid only: `.grid > .ws-tile`.
2. **Header** (`.ws-head`): title left, **move handle** (the drag handle) and **expand** right, each a 44 x 44px button with a 16px inline SVG
   (`aria-hidden`), `--muted`, hover `--accent` on `--accent-soft` with a `--line-strong` edge. Title = mono 12px 600 `--accent`
   (`h2` in the head, or `<h2 class="chart-h">` inside a figure's figcaption, or `caption h2` in a table). When the head has no
   `h2` (figure and table tiles) it floats in the tile's top-right corner (8px in) and the title row of the body keeps 96px
   clear of it (`padding-right: 96px` on `figcaption` and `caption`). A title row is 44px tall so it lines up with the buttons;
   a figure's `View as table` button (44px) sits left of the two icon buttons in that same band, and under the count at <= 599px.
   Icons (use exactly these; no other graphic):
   - move (six-dot grip): `<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><g fill="currentColor"><circle cx="5.5" cy="3.5" r="1.25"/><circle cx="10.5" cy="3.5" r="1.25"/><circle cx="5.5" cy="8" r="1.25"/><circle cx="10.5" cy="8" r="1.25"/><circle cx="5.5" cy="12.5" r="1.25"/><circle cx="10.5" cy="12.5" r="1.25"/></g></svg>`
   - expand (four corners): `<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4"/></svg>`
   - In the overlay the expand button gets `data-open`: the CSS hides its SVG and draws a 28px `×` (`aria-label` becomes `Close <label>`).
   - The table toggle stays the text button `View as table` (`.btn.table-toggle`, `aria-pressed`), because tests and the tab order
     rely on it; every chart tile has it, tables and cards do not.
3. **Body**: the existing content, unchanged. Inside a tile the old cards flatten (the tile is the card): `figure.chart` loses its
   own fill, border and padding; `.table-wrap` loses its box and bleeds to the tile edges (negative margin = the tile padding) with
   its caption padded 16px; `ul.cards`, `ul.tiles`, `dl.kpis` keep their nested cards (`rgba(5,10,18,.35)`, 10px radius, `--line`
   border); the map panel's `.panel-box` loses its box. Old wrapper classes riding on a tile (`questions`, `trends`, `map-layout`,
   `monitor-fig`, `block`, `charts`) have their margin, grid and column rules neutralised by `.grid > .ws-tile` (2 classes beat 1),
   so a tile is always a single column flexbox.
4. **Grid** (`div.grid`, 16px gap, 12px at <= 599px): one column under 900px (also 600 to 899px, as before); from 900px twelve
   columns, `data-span` 12 (default), 6, 8 or 4 sets `grid-column: span N`. Default spans per app are the architecture table; the first
   Explorer chart is 12 and the rest 6 (AC-34), the map is 8 with its panel 4. A user's drag order only changes position; spans stay.
5. **States**: hover = the **cursor glow**, a radial `--glow` (peak alpha .12, radius 240px) at `--mx`/`--my`, which `tiles.js`
   sets on `pointermove` and clears on `pointerleave` (CSS puts the centre off-tile at -999px when unset, so a touch device shows
   none); dragging = `.is-dragging` (opacity .55, 2px dashed `--amber` outline); drop target = `.is-over` (2px solid `--amber`);
   `body.is-dragging` shows the grabbing cursor and disables text selection; focus = the usual 3px `--accent` ring on the buttons.
   The header and figcaption show a grab cursor (the drag zones), buttons and links keep the pointer.
6. **Overlay** (`dialog.overlay#tile-dialog`, native modal): full viewport, 16px padding (8px at <= 599px), `rgba(5,10,18,.88)` fill,
   backdrop `rgba(2,5,10,.72)` with a 6px blur. The tile moves in as `dialog.overlay > .ws-tile`: max 1200px wide, at least the viewport
   high minus padding, no entrance animation, no move handle, plots `max(360px, 100dvh - 190px)` high (leaderboards `max(420px, ...)`).
   The page behind does not scroll (`body:has(dialog.overlay[open])`). Esc, a click on the padding area (the dialog itself) or the
   `×` closes it; focus returns to the tile's expand button. Filters work inside it; a bar click reloads the page and the same tile
   opens again (architecture I7).
7. **Chart marks** that act on click (bars, donut slices) are keyboard stops made by `dashboard.js`: `:focus-visible` draws a 3px
   `--fg` (white) outline at 2px offset on the SVG path (white, not cyan, because the bars are cyan; 14.5:1 against the tile).
   Checked in a scratch page: Chromium paints the outline around an SVG `path` with that rule.

### Grid layout per app (desktop 1280, then 375)
Tiles in default order; "6/6" means two tiles per row at >= 900px. Everything is one column at <= 899px.
| App | Desktop (12 columns) |
|---|---|
| Explorer | `Key figures` 12 (the KPI strip, titled by the tile), chart 1 12, charts 2 to 8 in pairs of 6, `Columns` 12, `First 20 rows` 12 |
| Business | `Key figures` 12 (cards), trend tiles 6 each (a lone trend 12), leaderboard 6 and `Change` 6 (leaderboard 12 when there is no change table), `Columns` 12, `First 20 rows` 12 |
| Map | map 8 (the 2D/3D figure, the `3D view` button in its head), panel 4 (details and top regions; keeps its `h2`, `Selected point`), `Columns` 12, `First 20 rows` 12 |
| Monitoring | `Measures` 12 (the min/max tiles and their note), main line 12, `Columns` 12, `First 20 rows` 12 |
| Survey | question tiles 6 each, `Cross-tab` 12, `Respondents` 12 (absent without histograms), `Columns` 12, `First 20 rows` 12 |
At 375px every tile is full width, 12px padding, tile padding-right of the title row 96px so titles wrap early, nested cards one per row, the
`View as table` button under the count, tables scroll inside their own box, plots keep the heights of the older sections. Tab order is
visual order because tiles move in the DOM: skip, brand, tabs, export links, View as, period links, filters, chips, crumbs, then per tile
its move handle, expand, `View as table`, mode-bar buttons and marks, table links.

### Home: the portal (`/`)
`<h1>DataBoot</h1>`, then `div.portal-wrap` (centred, 24px above, 32px below), then, **only when the data folder holds files**, the three
round 1 tables (Datasets, Could not be read, Other files) unchanged and below it, each in a `.table-wrap` (now the glass box). The
`.muted.mono` folder path line stays under the h1 when a launcher folder was given.
```
<div class="portal-wrap">
  <div class="portal" id="portal" data-state="idle">
    <div class="portal-rings" aria-hidden="true"><i></i><i></i><i></i></div>
    <div class="portal-core">
      <h2 class="portal-title">Give me your data</h2>
      <div class="portal-actions"><button type="button" class="btn btn-primary">Choose files</button><button type="button" class="btn">Choose folder</button></div>
      <div class="portal-status" role="status"></div>
    </div>
  </div>
  <div class="note note-error portal-msg" role="alert" hidden>...cap message...</div>
</div>
```
The two file inputs are `hidden` and opened by the buttons (`webkitdirectory` on the folder one); the buttons are the keyboard route.
- **Portal**: a circle, `width: min(400px, 100% / 1.24)` (400px on a desktop; at <= 599px `100% / 1.3`, 264px at 375px, so the outer ring fits the column) and `aspect-ratio: 1`, border 1.5px
  `rgba(77,225,255,.5)`, a radial cyan glow inside (`.16` centre to transparent at 72%). Three dashed rings sit behind it at 4%, 8% and
  12% outside the edge (`.portal-wrap` has `overflow-x: clip`: a turning ring's box is wider than its circle and made Home scroll sideways at 375px, found in the round 7 design review, ticket 499) (cyan .35, cyan .24, amber .22). Title = the system sans at `--t-lg` 650 (an `h2`, because the page's h1 is
  the product name). Buttons are stacked, 220px wide at most (44px high). Contents are 70% of the width and centred.
- **States** by `data-state`: `idle`, `over` (a drag is over the portal: the border goes solid `--accent`, the glow doubles, a 3px
  `--accent-soft` halo) and `busy` (an upload is running). **The rings always turn slowly (24 s, 36 s reversed, 52 s per turn) in every
  state, idle too, as in the prototype (Board gate 190).** Only `@media (prefers-reduced-motion: reduce)` sets `animation: none`; `over`
  still shows the border and halo change then. `.portal-status` (mono, `--muted`) shows real progress only: `3 of 12 files`; empty at rest.
- **Cap and errors**: the message is a `.note.note-error.portal-msg` (`role="alert"`, max 560px, centred under the portal) with the
  server's text; the page keeps working. Nothing is listed or kept from a refused upload.
- Focus order: skip, brand, `Choose files`, `Choose folder`, then the tables' links. Only the portal is a drop target: a drop elsewhere is
  ignored (`intake.js` stops the browser from opening the file) and nothing else on the page highlights.

### Scan screen (`/scan`)
`section.scan` (glass panel, 900px max, 16px padding) holding `<h1>DataBoot</h1>` (the h1 is inside the panel, as built), `<ol class="scan-log" aria-live="polite">` and the
link `<a class="btn btn-primary" id="open-workspace">Open workspace</a>` (always visible, first stop). Lines are mono `--t-sm`,
`white-space: pre-wrap` so the double spaces of the architecture's format stay; each has a cyan `›` prompt (CSS, empty alt). Classes:
`li` plain = a dataset line in `--fg`; `li.bad` = an unreadable file with its note, `--danger` (the words carry it, not the colour);
`li.last` = `0 bytes uploaded to the internet` in `--amber`. `scan.js` sets `hidden` on every line, then removes it one by one
(every 350 ms at most, all within 2.5 s); a line that appears plays a 200 ms slide and fade (`log-in`), so the reveal is the only
motion. Honest: the lines are the already finished catalog result, so the pacing is a display delay, with **no spinner, no progress bar
and no "scanning..." text**. With reduced motion the lines still appear in turn but without the slide. With no JS all lines show.
At 375px the lines wrap (`overflow-wrap: anywhere`); the panel is full width.

### Motion rules
(Round 7: replaced; the full list is "Motion rules" in "Round 7 theme and tiles" above.) Short form: tiles enter one after another in
under 0.6 s, the portal rings always turn slowly (only reduced motion stops them), scan lines slide in as they appear, buttons fade 160 ms, the skeleton
shimmers only while a fetch is pending; reduced motion removes all of it; reduced transparency removes every blur. Plotly never animates
and nothing auto-rotates.

## Accessibility (adds to the older section)
- Contrast pairs are in the token table; body and label text >= 4.5:1 on every effective surface including under the glow.
- Focus: 3px `--accent` outline, 2px offset, on every control (cyan is 7.3 to 12.8:1 on every surface); chart marks use `--fg`.
- Each tile is a region named by its h2 (`aria-label` = the h2's text); move and expand buttons carry `aria-label` with the tile's name;
  `#ws-live` announces keyboard moves; the dialog is a native modal (focus trapped, Esc closes).
- Targets >= 44px for our controls (move and expand are 44 x 44); the Plotly mode bar stays 28px as before.
- Decoration (brackets, rings, glow, washes) is `aria-hidden` or pseudo-element only and never carries meaning.


## Earlier rounds (kept where round 7 does not override them)

**Round 6 delta** (Board gates 181-183: **branding unchanged** (gate 160), "Trends off" is a team setting, so no docs/TRENDS.md
and no trend advice is used; **no token change**: no new colour, size, space or motion value; no logo, font or image):
1. Two new app bodies in the same shell: **Monitoring** (R4: period links, tiles with sparkline, one main line with a
   7-point mean and spike markers) and **Survey** (R5: question grid, Likert stacked bars, cross-tab heatmap, Respondents).
2. New components built from old ones: `ul.tiles > li.card` (the Business card plus a min/max row), `nav.periods` (the View as
   links), `div.questions` (two-column figure grid), `form.crosstab` (the filter fields). New figure kinds `monitor`,
   `likert`, `crosstab` (Charts).
3. Gate 181 fix-ups that change this document: line charts keep Plotly's automatic y-range and only bars start at 0
   (Global chart rules 1 and 2; this reverses ticket 458's zero baseline on Business trends); Explorer bars (and Survey bars)
   carry the pointer cursor (Cross-filter); `· score 0.NN` is printed only in Explorer captions; counts read `1 point`, `1 of 1 row`;
   numbers follow the column role: no separators on identifier, temporal or year-like columns (Type scale, rule 10); the `3D view`
   button sits above the map figure (already documented since ticket 458).
4. Rule order for the badge and View as: R1 Map, R5 Survey, R2 Business, R4 Monitoring, R3 Explorer (gate 183). A dataset that
   qualifies for several apps lists them in that order.
Everything else (Explorer, Business, Map, Home) is unchanged.

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
4. (Round 6: Explorer only.) The rule caption ends in ` · score 0.NN`: same `.chart-rule` span and style, no new component. The score is
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
(Round 7: replaced.) A dark holographic instrument panel: near-black blue page, translucent glass tiles with a cyan hairline and
corner brackets, cyan as the one accent, amber for chips, the badge and drag targets, mono labels, and the charts carry the colour.
One theme only; the OS light or dark preference is ignored (`color-scheme: dark`). Decoration (two static washes, brackets, ring
dashes) is allowed but carries no meaning; the portal rings always turn slowly and only reduced motion stops them (Motion rules, gate 190).

## Colour tokens
(Round 7: replaced.) The light/dark token table of rounds 1 to 6 is gone; the one dark table is in "Round 7 theme and tiles" at the top.
Rules that still hold: colour is never the only carrier (type is a word, category is in the axis or legend, heatmap cells print their
values, Likert segments have an edge and a printed share, deltas have arrow, sign and word); a sequential scale is one hue, a diverging
scale has two hues around a neutral midpoint that is the zero of the data; bars of one series are all `--c1`.

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
| `--t-label` | 0.75rem, `--mono`, letter-spacing 0.06 to 0.08em | round 7 labels: tile and table titles, field labels, sublabels, counts (`text-transform: uppercase` on tile titles `.ws-head h2` only) |
Numbers in tables and counts use `font-variant-numeric: tabular-nums` and right-align (`.num`). Thousands
separators are used on counts and amounts (Board gate 161) through the `num` filter, but **by column role, not by the look of the
text** (gate 181, AC-59): a numerical amount shows `12,345`; a year-like column (name contains `year` or `yr`, or whole numbers all
1900-2100), an identifier (`id`, `*_id`, code, zip, phone) and a temporal column show `2024`, `10045`, never `2,024`. This holds in
tables, the Map side panel, tooltips, axis ticks and the table view. The server decides once per column (`plain` letters on chart dicts);
the browser never guesses from digits.

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
| `nav.periods > .view-as-label + ul > li > a` | Monitoring period links `7 days`, `30 days`, `90 days`, `All`: the View as joined row (same CSS, 44px high, current is `aria-current="page"`). Plain GET links, so the URL holds the period and Back works. At <= 599px the four links share the width as a four-column grid (centred, `--t-sm`), so they never wrap into a ragged pair of rows | hover, focus ring, current |
| `ul.tiles > li.card.tile` | Monitoring tile = the Business card (`.card-label` column name, `.card-value` latest value in `--t-xl`, `.card-change`) plus `dl.tile-range` (`Min 20  Max 60`: `dt` `--muted`, `dd` `--fg` in mono, tabular; whole values print whole, 20.5 keeps its decimal; corrected in round 7 from the old `20.0 / 60.0`, gate 186) and `.card-period` (`latest 2024-04-29`), then `svg.spark` (same component as Business, the period's values). Change is `▲ +5.1% up`, `▼ -0.4% down`, `▶ 0.0% no change`, neutral `--fg`, never green or red. With no previous period (`All`, or too little history) `.card-change.na` reads `n/a` in `--muted`, no arrow; with no data in the period `.card-value` reads `n/a` and there is no sparkline. One tile per numerical column; grid `repeat(auto-fill, minmax(240px, 1fr))`, one per row at <= 599px. Cards align to the top, so a short tile is not stretched | none |
| `div.questions > figure.chart` | Survey grid: two figures per row from 900px, one per row below, top aligned (a short Likert card is not stretched to the height of its neighbour). Used for question figures and for the Respondents histograms | as figure |
| `form.crosstab` | Survey cross-tab form: two `.field` selects labelled `Row question` and `Column question` (native, 44px) and `Apply` (`.btn`), laid out exactly like `form.filters`. Changing a select submits (JS), `Apply` works without JS | hover, focus ring |
| `.badge` | column type label (`numerical`, `categorical`, `temporal`, `geospatial`, `other`) in a pill, text always shown | |
| `.note`, `.note-error` | left-bar message, used for fixed labels like `could not be read` | |
| `.empty` | dashed box: "No charts for this dataset" style fixed label, only when `charts == []` | |
| `figure.chart` | card: figcaption on top (`.chart-title`, `.chart-rule`, `.chart-count`), `.plot` below. `.chart-rule` ends in ` · score 0.NN` **only in Explorer**; Business, Map, Monitoring and Survey print the rule alone (gate 181). `.chart-count` is `N of M points` or `N of M rows`, singular at exactly 1 (`1 of 1 row`, `1 point`) and plural at 0 (`0 of 5 rows`), in captions, tooltips and the Map panel | loading, drawn, error |
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
  - **Trend** (Business) = the line above, `--c1` 2px, one y-axis titled with the measure, **automatic y-range (not from 0**: gate 181
    reverses ticket 458; a line shows change, and zero would flatten 14,000 to 16,000), plot 260px
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
  - **Monitor** (Monitoring main line, kind `monitor`, plot 360px, 280px at 375): one y-axis (automatic range, so a small drift is
    visible), time on x. Traces in this order: the value line (`--c1` 2px, markers while `shown <= 40`); the **7-point mean**
    (`--muted`, 2px, `dash: "dash"`, named `7-point mean`, a derived line so it is grey and dashed, never a second measure); the
    **spikes** (`mode: "markers+text"`, diamond marker size 11 in `--c5` with a 1.5px `--surface` edge, `text: "spike"` in `--fg`,
    `textposition: "top center"`, named `spike`). The spike trace exists **only when the server lists spike points**: a quiet series has
    no `spike` text, no trace and no legend entry. Marker shape plus the word carry the meaning, not the colour. The legend is on
    (2 or 3 series) at the bottom, horizontal; line-end labels are not drawn because the mean overlies the value line (exception to
    Global rule 8, the legend names them). The mean and the spikes are computed over all points, the line is cut to the period, so
    the first points of a period already have a full window: nothing is drawn that the data does not contain. Tooltip: `time`,
    `value` (or `7-point mean`), separators by role.
  - **Likert** (Survey, kind `likert`): one horizontal 100% stacked bar per question (`barmode: "stack"`, one trace per level, x =
    share in percent, y = the question), x axis 0 to 100 with a `%` suffix, plot 180px (240px at 375 because the legend wraps).
    Colours (diverging, gate 183): levels before the neutral one run from `--div-neg` (strongest at the end of the scale) to
    lighter, the **neutral middle level is `--div-mid` (grey)**, levels after it run from lighter to `--div-pos`. The tint of a
    level is `--div-neg` or `--div-pos` mixed into `--div-mid` by (distance from the neutral / largest distance), so a 5-point scale
    has full and half tints and a 7-point scale thirds. Because `--div-mid` is almost the card colour in light mode, **every
    segment has a 1px `--line-strong` edge**; the neutral segment stays visible and the segments are separated without colour.
    Each segment prints its share (`40.0%`, one decimal) in black or white by computed contrast (>= 4.5:1, like heatmap cells) when it
    is at least 8% wide; narrower ones print nothing (the tooltip `level: count (pct%)` and the table view have it). Legend at the
    bottom, in scale order, every level listed even with count 0. The two sides use two hues and the sign is in the legend order and the
    level words, so colour is never the only carrier. Not clickable, no cursor change.
  - **Cross-tab** (Survey, kind `crosstab`): one `heatmap` of the counts, rows = the row question, columns = the column question,
    one-hue sequential scale `--seq-lo` to `--seq-hi` on the count (this is a count, not a signed value, so no diverging scale and
    no fixed range), every cell prints `count (pct%)` (the row percent, one decimal) in black or white by contrast, colour bar titled
    `count`. Plot 420px (340px at 375). Levels in scale order for Likert questions, otherwise by count. Wide tables scroll
    **inside their card** (`figure.chart` has `overflow-x: auto`; `dashboard.js` sets `--plot-w` on the plot to 120px + 88px per column so the
    cell text always fits); at <= 599px the colour bar is horizontal under the plot (72px bottom margin), as on the phone map.
    Cells with a count of 0 print `0 (0.0%)`. Not clickable.
  - **Question bars** (Survey, kind `bar`): the Explorer bar (`--c1`, horizontal when labels are long, sorted by count) with the
    leaderboard's `Other` rule: more than 10 values fold into one `Other` bar in `--muted` as its own trace, no pointer, clicks do
    nothing. The other bars carry the `bar-click` class and click sets the category filter (Cross-filter).
  - **Phone map**: `dragmode: false` at <= 599px so a finger drag scrolls the page instead of panning the map; the mode
    bar's zoom and reset buttons still work. Desktop uses `pan`; wheel zoom stays off (`scrollZoom: false`).
- Honest data: the point count shown in `.chart-count` is the server's `shown`/`total` (`N of M points` or `N of
  M rows`). When `shown < total` the caption says so and nothing else; no smoothing, no fake trend line. Plotly
  default transitions are off (`transition: {duration: 0}`), so no chart animates on load.
- Cross-filter (AC-39, AC-61): bar and donut categories are clickable. Plotly shows no pointer itself over bars, so **every figure whose
  bars filter (Explorer bars and Survey question bars) toggles the `bar-click` class** from `plotly_hover` / `plotly_unhover`
  (CSS `cursor: pointer`), the same class and handler as the Business leaderboard; donut slices keep Plotly's own pointer. The `Other`
  bar (Survey) and any bar that does not filter get `no-pointer`. No text and no icon is added. Click sets `f.<x_label>=<category>` and reloads; a second click on the same
  category removes it. With one value selected a donut drops out (its rule needs 2 to 5 slices), but a bar chart stays
  with the single remaining bar (seen in the ticket 437 review), which is the bar a second click un-filters; no
  "selected bar" style is drawn, the chip and the select already say what is applied. Mouse-only by nature; the dropdowns and chips are the keyboard and touch-reader route to the same result.
- Keyboard and screen reader: each `figure` has `aria-label` = chart title; each `.plot` has `role="img"` with
  `aria-label` = `<title>: <rule caption>`; the data is also in the first-20-rows table above/below.

## Global chart rules
Apply to every Plotly figure in every app (Explorer, Business, Map, Monitoring, Survey; AC-57). Each rule says what the code must do.
1. **Magnitude = sorted bars from zero (bars only).** Bars sort descending (Business leaderboard: top 10, then `Other` last, in
   `--muted` grey as its own trace with no pointer cursor, so it reads as the remainder, never a palette colour), the value axis starts at 0
   (`rangemode: "tozero"`), horizontal when labels are long, value printed on each bar in the leaderboard.
2. **Change over time = line, automatic y-range.** One measure per chart, time on x; no bars for time. **Lines never get a forced
   zero baseline** (gate 181, AC-62): the zero baseline is for bars only, so a 14,000 to 16,000 trend fills its plot. A derived line
   is allowed only when it is named and visibly different: the Monitoring 7-point mean (grey dashed) sits on the same axis as the
   data line; the data line itself is never smoothed. A partial last period is not drawn (Business trend stops at the latest full
   period).
3. **Part-to-whole = stacked bar; donut only for 2 to 5 parts.** With 6 or more parts no donut is drawn. A part-to-whole
   chart with 6 or more parts must be one stacked bar from zero (none exists yet; the rule is for the next one).
4. **One y-axis always** (the Monitoring mean shares the value axis). No `yaxis2`, no `overlaying`, no dual axis. Several measures make small multiples: one
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
10. **Thousands separators on counts and amounts, by column role** (not on ids, years or dates, see Type scale). Axis ticks (`separators: ".,"`, `tickformat: ","`), tooltips (`:,`), bar
    labels (`%{x:,}`), cards, panel values, table cells and the table view; one decimal for percents (`+19.4%`).

## Motion rules
1. (Round 6: unchanged. Period links, tiles and the cross-tab form add no motion: each is a page load.) Only two moving things exist: the loading shimmer (real pending fetch) and the 160ms colour transition on
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
- Tab order (Monitoring): skip, brand, export links, View-as links, period links, date range and `Apply`, chips, then the line figure's
  `View as table` button and mode-bar buttons, table links. (Survey): skip, brand, export links, View-as links, filter controls and
  `Apply`, chips, then each question figure's `View as table` button and mode-bar buttons in grid order, the cross-tab's two selects and
  `Apply`, its figure, the Respondents figures, table links. Every Survey bar click has the dropdowns as its keyboard route. The
  tile's sparkline is a labelled image, not a stop. The cross-tab card scrolls sideways only inside itself; its scroll box is reached by
  the mode-bar and the table view (a focusable `tabindex="0"` region), so the keyboard can read every column.
- Tab order (round 4): skip link, brand, page actions, chart mode-bar buttons (visible, 28px, ring on focus), table links.
  Landmarks: `header`, `main#main`. Mode-bar buttons have an `aria-label`.
- One `h1` per page, then `h2` per table (inside its `<caption>`), no skipped level; figures keep a figcaption
  title, not a heading. Tables have `caption` and `th scope`. Type badges carry text.
- The sparkline has `role="img"` and a label; the arrow is `aria-hidden` and the words `up`, `down`, `no change` carry it.
  The badge and View-as are text. On the phone the map must not trap the page scroll (see Map at 375px).
- `lang="en"`; zoom is not blocked; layout reflows at 320px with no horizontal page scroll.

## Page layouts
Both pages share the header (56px) and `main` (max 1200px).

### Home `/` (round 7: the portal comes first, see "Home: the portal" above; the tables below it are as here)
Desktop (>= 900px): h1 `DataBoot`; below it a `.muted` line with the scanned folder path (`.mono`). Then up to
three `.table-wrap` tables, 32px apart, each titled by `<caption><h2>` (Datasets, Could not be read, Other files):
1. Datasets: File path | Sheet | Rows (`.num`) | Columns (`.num`) | the file path is the link to `/datasets/{id}`.
2. Could not be read: File | Reason (`.note-error` text colour `--danger`).
3. Other files (file inventory): File | Type | Size (`.num`, bytes) | Modified (YYYY-MM-DD).
Empty tables are not rendered. If everything is empty, one `.empty` box shows the folder path.
375px: same order, one column. Tables keep all columns and scroll sideways inside their `.table-wrap`; File
column has `min-width: 12ch` and wraps long paths (`overflow-wrap: anywhere`). The link row is >= 44px tall.

### Dashboard `/datasets/{id}` (round 7: the page body is the tile grid of "Grid layout per app" above; this older order is the content of the tiles)
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

### Monitoring and Survey (round 6)
Same shell (`.crumb`, `.page-head` with title, badge `App: Monitoring (rule R4)` or `App: Survey (rule R5)` and actions, `nav.view-as`
when more than Explorer qualifies). Business and Survey list each other in View as when both qualify (a survey with a date and a
number can be read as Business).

**Monitoring, 1280px**, single column, in this order: (1) `nav.periods` (label `Period`, four links, `30 days` current by default);
it sits above the tiles it controls, though the architecture text lists tiles first (nothing depends on the order); (2) `ul.tiles`,
one tile per numerical column, three to four per row (`minmax(240px, 1fr)`); (3) `form.filters` with the date range only (there are
no categorical columns under R4) and `Apply`, then `.chips-row` when a range is active; (4) the main line `figure.chart[data-kind="monitor"]`
(`.monitor-fig`, full width, plot 360px, `View as table` in the caption); (5) Columns table; (6) First rows. No Business crumbs, no
leaderboard. **375px**: same order in one column: crumb, h1, badge, stacked buttons, View as, period links as a four-column row (each
>= 44px), tiles one per row (sparkline full width), the date fields stacked (44px), the figure (280px, legend below, wraps), Columns,
First rows (scrolls in its box). `All` shows `n/a` on every tile and no arrow, the line shows all points.

**Survey, 1280px**, in this order: (1) `form.filters` (a dropdown per categorical question, date range when a time column exists) and
chips; (2) `div.questions`: one figure per question in column order, two per row, a `bar` for a plain question and a `likert` for
a scale question, each with title, rule, `N of M rows`, `View as table`; there is no heading above the grid; (3) `section.block`
with `<h2>Cross-tab</h2>`, `form.crosstab` and the heatmap card full width (420px); (4) `section.block` with `<h2>Respondents</h2>` and a
`div.questions` of up to two histograms (`--c1`, as Explorer's); the section is absent when there are none; (5) Columns, First
rows. **375px**: one column in the same order, filters stacked, question figures one per row (bars 280px, Likert 240px), the
cross-tab selects stacked full width with `Apply` full width, the heatmap card scrolling sideways inside itself with a horizontal colour
bar, Respondents histograms one per row. A Likert bar's legend sits under the plot and wraps; nothing overflows the page width.

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
- Round 6: a Monitoring tile's change, min, max and sparkline are the server's period values; `All` and a missing previous period read
  `n/a`, never a made-up 0%. The `spike` label exists only on points the server flagged (|z| > 3 against the 30 points before), so a quiet
  series shows none. The 7-point mean is a named, dashed, grey second line and the data line is never smoothed. Likert segments are
  drawn at their real share, the neutral one in grey, every scale level listed even at 0. Cross-tab cell colour is the count, and its
  text gives count and row percent. Nothing animates because a dataset is "monitored": the page reads the file once.
- Colour never carries meaning alone: type is a word, category is in the axis or legend, heatmap prints values.

## Changes this round
Round 7 (ticket 485, architecture/design phase, Board gate 189, no TRENDS): **new tokens** (dark only: #050a12, #4de1ff, #ffb454, mono labels,
glass, glow, blur; `--delta-max` 35% to 30% because the cyan tint is brighter; chart palette re-cut around cyan and amber), **new
components** (tabs, archetype caption, portal, scan log, `.grid`, `.ws-tile`, `.ws-head`, `.ws-move`, `.ws-expand`, `dialog.overlay`, mark focus
ring) and **motion rules** (entrance under 0.6 s, always-turning portal rings, reduced motion, reduced transparency). `databoot.css`: the
`prefers-color-scheme` block is deleted and `:root` is the dark table, so **every existing page is already dark and re-skinned by tokens**
(buttons, inputs, chips amber, badges, cards, tables and chart boxes use the glass). The rules for the tile, grid, portal, scan log, tabs and
overlay are **inert until the frontend tickets emit exactly the markup in this file** (H7 portal, S7 scan, W7 tabs, archetype and tile macro,
I7 interactions, K7 marks); `.charts` keeps its old two-column rule only as `.charts:not(.grid)`, so Explorer is unchanged until W7 adds
`.grid`. Checked in a scratch page at 1280 and 375 (portal, scan log, tabs with a long name, a heading tile, a figure tile with a focusable
bar, a table tile, the overlay): no sideways scroll, tiles sit at spans 12/6/6 from 900px, the SVG bar shows the 3px white ring, reduced
motion sets `animation: none`. **Differences from the prototype description, for the Board**: (1) ~~the portal rings turn only while a drag
is over or an upload runs~~ (reversed by Board gate 190: the rings always turn, only reduced motion stops them); (2) no "(dev only) sample" button (list wins); (3) ~~tile titles keep their case in mono~~ (reversed by Board gate 190: tile titles are mono UPPERCASE with letter-spacing; `text-transform` is banned on `th` only); (4) the table toggle stays a text button, not an icon, so it keeps its label
and tab order. **Frontend notes**: `dashboard.js` still has `matchMedia("(prefers-color-scheme: dark)")` (T7 removes it); Plotly grid colour
is `--line` (rgba, .16) and the hover label fill is `--surface`; the mode bar icons are `--muted` (6.9:1 on the tile); heights of plots are
unchanged. The Min/Max example in Components now shows whole numbers (gate 186).

Design review (ticket 476, round 6), 1280, 800 and 375 px, light and dark, a demo folder (monitor, quiet, survey, shop, places, measures,
sales, an unreadable file, a 404): scrollWidth equals the viewport everywhere, no `.plot-error`, no console error but the expected 404, no
external request, no tap target under 44px outside the Plotly mode bar, Tab reaches every control with the `--accent` ring (the date
inputs ring each segment; the calendar icon uses the browser's own ring). Fixed in `dashboard.js`: (1) Likert segments now have the 1px
`--line-strong` edge and print their share (one decimal, black or white by computed contrast, only when >= 8% wide) as specified, so the
light-mode neutral segment is visible; (2) the cross-tab colour bar ticks are whole numbers (`dtick` at least 1, `tickformat ",d"`), a
count is never shown as 3.5. **No token change.**
Round 6 (ticket 464, architecture phase, Board gates 181-183): `databoot.css` gains `.tiles` (shares `.cards`), `.periods` (shares
`.view-as`, plus a four-column row at <= 599px), `.tile-range`, `.card-change.na`, `.monitor-fig`, `.questions` (two columns from 900px),
`.crosstab` (shares `.filters`), `data-kind` heights for `monitor` (360/280), `likert` (180/240) and `crosstab` (as heatmap), the crosstab
card's own horizontal scroll, and `.card` `align-content: start`. **Inert until the frontend tickets emit exactly the markup in Components
and "Monitoring and Survey (round 6)"**; the `monitor`, `likert` and `crosstab` builders, the `bar-click` class on Explorer bars, the
removal of the Business trend `tozero` and the score caption removal are script and template work, not done here. Checked in a scratch
page (tiles, periods, questions grid, crosstab form and card) at 1280 and 375 in light and dark: no sideways scroll, every control >=
44px, the period links fill the width at 375. Contrast: Likert and cross-tab cell text is picked by computed contrast (as the heatmap),
spike marker `--c5` against `--surface` is 5.4 light / 6.9 dark (>= 3:1 for a graphic), grey mean `--muted` 5.4 / 6.6. **No token change.**
Design review (ticket 458, round 5), 1280 and 375 px, light and dark, a demo folder (shop.csv Business, places.csv Map,
60,000-point hexbin map, measures.csv Explorer, long-named TSV, unreadable file, notes.txt, a 404): scrollWidth equals the
viewport everywhere (no sideways scroll at 375), all drawn plots without `.plot-error`, no console error except the expected 404,
no tap target under 44px outside the Plotly mode bar. Fixed in `dashboard.js`: (1) Business trend lines start at y = 0 as the
spec said then (reversed in round 6, gate 181: automatic range) (they auto-ranged, so 14,000 to 16,000 looked like a swing); (2) phone map colour bar is horizontal under the map;
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
