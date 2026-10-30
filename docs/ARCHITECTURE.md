# Architecture: DataBoot (round 7)

**Round 7** (docs/PRD.md round 7, AC-74..AC-87, Board gate 189) keeps every behaviour below and adds a **one-box
intake** (drop portal, `/upload` into a temp folder, a scan screen) and a **new look** (one shared glass tile for
every app, tile interactions, dark holographic theme only, keyboard chart marks). No new dependency, no CDN, no web
font. Scanning, classification, rules, figures, the JSON contracts of `/app` and `/charts`, and exports do not
change. Sections "Round 7: ..." come first; the round 1-6 sections after them still hold unless a round 7 section
says otherwise.

No docs/TRENDS.md this round (docs/team.json: trends off; IDEA: "trends off"), so I used no trend advice.
**The prototype `docs/reference/databoot-console.html` is not on disk** (`find / -name 'databoot-console*'` finds
nothing; docs/reference/ holds only deck.gl and unstructured.io). Gate 189 says to build from its description in
that case; the Designer turns the description into DESIGN.md tokens. Where it and the IDEA's numbered list differ,
the list wins (gate 189), so the prototype's "(dev only) sample" button is **not built** (no list item asks for it).

**Gate 189 overrides the PRD on four points; I reworded AC-78, AC-79 and AC-81 (same ids) in acceptance.json.**
(a) Scan log (AC-78): lines appear **progressively, about 0.35 s apart and all within 2.5 s**; the "Open workspace"
link is visible from the start; the workspace opens by itself after the last line (PRD: all at once). (b) Archetype
caption (AC-79): **exactly the badge line** `APP: BUSINESS · RULE R2 · T1 N2 C2 · 288 ROWS` (PRD: role counts plus
words chosen by the designer). (c) Keyboard reorder C1 is **built** (AC-81): Alt+Left/Right or Alt+Up/Down on a
tile's move handle moves it one place, announced in an aria-live region. (d) Expanded overlay after a filter click
stays open on the same tile (PRD default, confirmed). Branding unchanged (gates 160, 189): DataBoot, system fonts,
no logo, blank SVG favicon.

## Round 7 changes at a glance
| # | Change | Files | AC | Role |
|---|---|---|---|---|
| U1 | Upload batch: begin / write (streamed) / finish, cap, path sanitising, temp folder lifecycle, cache reset; lifespan cleanup | `app/upload.py` (new, empty), `app/main.py` (3 routes, lifespan), `app/config.py` (`upload_cap`, done) | AC-75, AC-76, AC-77 | backend |
| L7 | Launcher folder optional: no folder -> an empty owned temp folder; PS1 dialog Cancel starts with no folder | `app/launch.py`, `Start-DataBoot.ps1` | AC-74, AC-76 | backend |
| S7 | Scan screen `GET /scan`: one line per dataset and unreadable file; `_summary(d)` | `app/main.py`, `scan.html` (new), `app/static/js/scan.js` (new) | AC-78 | backend (route, `_summary`) + frontend (page, JS) |
| D7 | DESIGN.md round 7: tokens, portal, tile, scan log, motion, overlay, focus ring, contrast pairs | `docs/DESIGN.md` | AC-87, AC-83 | designer (after this ticket, before the frontend tickets) |
| H7 | Home: portal + Choose files / Choose folder, drop, upload client, cap message | `home.html`, `app/static/js/intake.js` (new) | AC-74, AC-75, AC-77 | frontend |
| W7 | Workspace shell: dataset tabs, archetype caption; `tile` macro; every app template re-cut into tiles in one `.grid` | `base.html`, `dataset.html`, `_tile.html` (new), `_figure.html`, `app_*.html`, `_tables.html`, `app/main.py` (`tabs`, `summary` in the page context) | AC-79, AC-80 | frontend |
| I7 | Tile interactions: drag and keyboard reorder, localStorage order, expand dialog and reopen, glow, entrance | `app/static/js/tiles.js` (new), CSS | AC-81, AC-82, AC-84 | frontend |
| K7 | Keyboard chart marks (Tab, focus ring, Enter/Space = click) | `dashboard.js` (`keyboardMarks`, `apply`) | AC-85 | frontend |
| T7 | Dark theme only: delete the `prefers-color-scheme` block and the `dark` media listener; reduced motion and transparency | `databoot.css`, `dashboard.js` | AC-83, AC-84 | frontend (Designer's tokens) |
| Q7 | Acceptance tests AC-74..AC-87, offline walk, AC-41/42 re-timed, golden `/app` + `/charts` (AC-80) | `tests/test_acceptance.py`, new test files | all | QA |

Order: U1 + L7 and the D7 design ticket first (independent), then S7 and H7 (need U1), then W7, then I7, K7, T7
(need W7's markup), then QA. W7 moves markup that old browser tests select, so W7 runs the whole suite once at its
end (see "Round 7: tests that must change").

## Round 7: routes (sitemap: home, scan, dataset page; NAV = the "DataBoot" home link plus the dataset tabs)
| Method, path | Returns |
|---|---|
| GET `/` | Home: h1 DataBoot, the portal, then (when the data folder has files) the round 1 tables, unchanged |
| POST `/upload` | begin a batch (JSON contract below) |
| PUT `/upload/{batch}?path=<relative path>` | one file's bytes, streamed to disk |
| POST `/upload/{batch}/done` | the batch becomes the data folder; `{"next": "/scan"}` |
| GET `/scan` | Scan screen: server-rendered log of the current data folder (no JSON, no polling) |
| GET `/datasets/{id}` | as before, now in tiles; tabs for every dataset in the header |

All round 1-6 routes are unchanged. The scan page is reached after an upload (and by URL); it is not in the NAV.
No page polls: intake.js makes the upload calls once per upload; dashboard.js still fetches `/app` once.

## Round 7: upload (`app/upload.py`, routes in `app/main.py`)
No `python-multipart` (not installed, no new dependency): the browser sends **one raw request per file**, read with
`request.stream()` and written in chunks, so a 2 GB upload never sits in memory. JSON bodies use `await request.json()`.

**JSON contracts** (errors are FastAPI's `{"detail": "<text>"}`):
1. `POST /upload` body `{"files": [{"path": "sub/sales.csv", "size": 123}, ...]}` ->
   `200 {"batch": "<token>"}` (token = the temp folder's name, `[A-Za-z0-9_-]+`);
   `413 {"detail": <cap message>}` when `sum(size) > config.get().upload_cap` (nothing created);
   `400` for an empty list, a duplicate or a bad path (rules below).
2. `PUT /upload/{batch}?path=<path>` body = the file bytes (`application/octet-stream`) ->
   `200 {"path": "sub/sales.csv", "bytes": 123}`; `404` unknown batch; `400` a path not in the batch's list;
   `413 {"detail": <cap message>}` as soon as the batch's running byte total passes the cap: the batch folder is
   deleted at once (AC-77: none of that upload's files are kept or listed).
3. `POST /upload/{batch}/done` -> `200 {"next": "/scan"}`; `404` unknown batch. Effects: `DATABOOT_DATA` = the batch
   folder (the same switch `launch.run` uses; `config.get()` reads env on every call); the previous **upload**
   folder is deleted (only folders in `upload.OWNED` are ever deleted, never a launcher folder); the caches
   `catalog.scan`, `catalog.load`, `main._base`, `_view`, `_plain`, `_detected`, `_appview` are cleared, because a
   `Dataset` compares equal across folders (same path, sheet, kind, rows) and would serve the old file's rows.

**Cap message** (`upload.cap_message(total, cap)`, returned as `detail` and shown by the page in a `role="alert"`
box): `This upload is <total> and the limit is <cap>. For larger drives, start DataBoot with the launcher's -Folder
option.` Sizes >= 1 GiB print as GB with at most one decimal (`2 GB`, `2.4 GB`), smaller ones as `1,000 bytes`.
Default cap `2 * 1024**3` (`DATABOOT_UPLOAD_CAP`; added to `app/config.py` in this ticket), so the default message
names "2 GB" (AC-77); tests set a small cap. intake.js sums `File.size` first and shows the same text (built by
the same rule in JS) without sending anything; the server checks again (declared sizes, then real bytes).

**Paths** (`upload.safe(path) -> str | None`): `\` becomes `/`; reject empty, absolute (`/x`, `C:...`), any part that
is `..`, `.` or empty, any NUL; the resolved target must stay inside the batch folder (`resolve()` +
`is_relative_to`). The client sends paths **relative to the picked or dropped folder**: for a folder pick
(`webkitRelativePath` "picked/sub/sales.csv") or a dropped folder (`webkitGetAsEntry`, fullPath
"/picked/sub/sales.csv") it strips the first segment when every file shares it, so ids, paths and the scan equal a
launcher run on that folder (AC-75: `sub/sales.csv`). Single files send `File.name`. Hidden files are written;
`catalog.scan` skips them as today.

**Lifecycle**: `upload.begin` makes `tempfile.mkdtemp(prefix="databoot-upload-")` (system temp: outside the project
and any launcher folder, AC-76) and adds it to `OWNED`; `upload.cleanup()` deletes every `OWNED` folder. `main.app`
gets `FastAPI(lifespan=...)` whose shutdown calls `upload.cleanup()` (uvicorn runs it on Ctrl+C and on
`server.should_exit`; a TestClient runs it when used as a context manager, which is how QA tests AC-76). One upload
at a time: `begin` deletes any batch that was begun and not finished.
`# ponytail: a hard kill leaves the temp folder; the OS temp cleanup removes it.`

## Round 7: launcher (L7)
- `app/launch.py`: `folder` becomes `nargs="?"`. Without it, `run(upload.empty())`, where `upload.empty()` makes an
  owned empty temp folder (deleted on exit like an upload); the home page then shows only the portal. With a folder,
  behaviour is unchanged (`test_missing_folder_exits_2_with_one_line` keeps passing). A launcher folder is only read.
- `Start-DataBoot.ps1`: if the folder dialog is cancelled, start **without** a folder instead of `exit 1`
  (`-Docker` still needs a folder and keeps `exit 1`). Call `app.launch` with `$Folder` only when it is set
  (Windows PowerShell 5.1 drops empty string arguments, so use an `if`). Keep every needle of
  `tests/test_launcher_files.py` (FolderBrowserDialog, `-m app.launch`, `exit 1`, ...).

## Round 7: scan screen (S7)
`GET /scan` renders `scan.html` from `catalog.scan(config.get().data)` and, per dataset, `main._summary(d)` =
`{"app": det["app"], "rule": det["rule"], "T": n, "N": n, "C": n, "G": n}`: the counts of `temporal`,
`numerical`, `categorical`, `geospatial` in `_base(d)[1]` (the profile mapping, AC-2) and `det = _detected(d)`.
Markup (no `<p>` in main): `<h1>DataBoot</h1>`, `<ol class="scan-log" aria-live="polite">` with one `<li>` per line,
then `<a class="btn btn-primary" id="open-workspace" href="/datasets/<first id>">Open workspace</a>` (`/` when there
is no dataset). Lines (exact, AC-78):
- dataset: `<path>[ - <sheet>]  <rows|plural("row")>  T<n> N<n> C<n> G<n>  -> <APP> (rule <id>)`, APP =
  `det["app"].upper()`; e.g. data_dir sales.csv: `sales.csv  6 rows  T1 N1 C1 G0  -> BUSINESS (rule R2)` (counts checked with `profile.classify`);
- unreadable: `<path>[ - <sheet>]  <reason>`;
- last: `0 bytes uploaded to the internet`.
All lines are in the HTML (tests and no-JS read them). `scan.js` hides them on load and reveals one every
`min(350, 2500 / n)` ms; after the last it calls `location.assign` with `#open-workspace`'s href. Under reduced
motion the lines still appear in turn but without a fade.
`# ponytail: /scan profiles every dataset (one _base load each); a folder of many big files shows late; add a
background scan if the Board reports it.`

## Round 7: workspace shell (W7)
- `base.html` gets `{% block tabs %}` inside `.site-header` after the brand; `dataset.html` fills it with
  `<nav class="tabs" aria-label="Datasets"><ul>` one `<li><a href="/datasets/<id>">path[ - sheet]</a>` per dataset
  (`tabs` = `catalog.scan(...).datasets`, passed by the route), the current one `aria-current="page"`. The tabs sit
  **outside `<main>`** so main-only checks (`test_business_page.py:156` counts two `aria-current` in main) hold.
  Many datasets scroll sideways (Designer).
- Under the h1, `dataset.html` prints `<div class="archetype">` with `APP: {{ s.app|upper }} · RULE {{ s.rule }} ·
  T{{ s.T }} N{{ s.N }} C{{ s.C }}{% if s.G %} G{{ s.G }}{% endif %} · {{ d.rows|plural("row")|upper }}` (`s =
  _summary(d)`): `APP: BUSINESS · RULE R2 · T1 N1 C1 · 6 ROWS` for data_dir sales.csv. G is printed only when non-zero so
  the Board's example reads exactly. The badge `App: Business (rule R2)`, View as, filters and chips stay.
- The page body is one `<div class="grid" data-dataset="{{ d.id }}" data-app="{{ shown }}">` (12 columns at
  desktop, 1 column under 600 px) holding all tiles in the default order below. Filters form, chips, View as,
  Monitoring period links and the Business drill crumbs stay **above** the grid (page controls, not tiles). One
  `<dialog class="overlay" id="tile-dialog">` and one `<div class="sr-only" id="ws-live" aria-live="polite">` at the
  end of main.

## Round 7: tile component (W7; one macro for every app)
`app/templates/_tile.html`, `{% macro tile(key, label, span=12, extra="", heading=true) %}`, used with `{% call %}`:
```
<section class="ws-tile {{ extra }}" id="tile-{{ key }}" data-tile="{{ key }}" data-span="{{ span }}" aria-label="{{ label }}">
  <div class="ws-head">{% if heading %}<h2>{{ label }}</h2>{% endif %}
    <button type="button" class="ws-move" aria-label="Move {{ label }}">(icon)</button>
    <button type="button" class="ws-expand" aria-label="Expand {{ label }}" aria-haspopup="dialog">(icon)</button></div>
  {{ caller() }}
</section>
```
- Class `ws-tile`, not `tile`: `ul.tiles > li.card.tile` is the round 6 Monitoring card and tests select it.
- A `<section>` with an accessible name is a **region landmark**; its name (`aria-label`) is the text of an h2 inside
  the tile (AC-80). Where the body already has that heading, `heading=false`: **figures** wrap the caption title as
  `<figcaption><h2 class="chart-h"><span class="chart-title">…</span></h2> …` (the exact `<span
  class="chart-title">` string that `test_pages.py:66` reads and the `<figcaption>` count stay); **tables** keep
  `<caption><h2>Columns</h2></caption>` byte for byte (dozens of test literals); the **map panel** keeps its
  `<h2>Selected point</h2>`; Survey **Cross-tab** and **Respondents** keep their h2. Other tiles get the tile h2:
  Explorer `kpis` and Business `cards` "Key figures", Monitoring `tiles` "Measures" (Designer may rename; plain
  labels, AC-17).
- In a figure tile the `<figure>` is a **direct child** of the section, after `.ws-head`, so `.questions > .chart`
  matches when the tile carries `questions`. The table toggle stays inside figcaption (`.table-toggle`); the
  `#map3d-toggle` button moves into the map tile's `.ws-head`.
- **Keys, default spans** (desktop; 12 under 600 px) and `extra` (the old wrapper class, kept where tests use it as
  an ancestor):

| App | Tiles in default order: key span (extra) |
|---|---|
| Explorer | `kpis` 12 (`dl.kpis` inside), `chart-1` 12, `chart-2`..`chart-8` 6, `columns` 12, `rows` 12; the grid also has class `charts` (`test_filter_ui.py:80`, AC-34 widths); no charts -> `empty` 12 |
| Business | `cards` 12 (`ul.cards`), each trend `chart-N` 6 (`trends`), leaderboard `chart-N` 6 or 12 without a change table, `changes` 6, `columns` 12, `rows` 12 |
| Map | `map` 8 (`map-layout`: the 2D and the hidden 3D figure, 3D button), `panel` 4 (`aside.map-panel` with the region bar figure), `columns` 12, `rows` 12 |
| Monitoring | `tiles` 12 (`ul.tiles` and the `.note`), each `chart-N` 12 (`monitor-fig`), `columns` 12, `rows` 12 |
| Survey | each question `chart-N` 6 (`questions`), `crosstab` 12 (`block`: h2, form, figure), `respondents` 12 (`block`: h2, `<div class="questions">` with the histograms), `columns` 12, `rows` 12 |

## Round 7: tile interactions (`app/static/js/tiles.js`, I7; loaded by dataset.html after dashboard.js, `defer`)
- **Drag** (pointer events, not HTML5 drag and drop, so mouse, pen and touch share one path and Playwright
  `drag_to` works): `pointerdown` on `.ws-head` or a figure's `figcaption` (not on a button, link, select or input)
  of tile A, `pointerup` over tile B moves A into B's place (`B.before(A)` when A came after B, else `B.after(A)`).
  The move handle has `touch-action: none`; the rest of the header keeps page scrolling on touch.
- **Keyboard** (gate 189): on `.ws-move`, Alt+ArrowLeft/ArrowUp moves the tile one place earlier,
  Alt+ArrowRight/ArrowDown one later; focus stays on the handle; `#ws-live` says `<label> moved to position <i> of
  <n>`.
- **Order store**: after each move `localStorage["databoot.order.<dataset id>.<app>"] = JSON.stringify(keys)`. On
  load, stored keys come first in stored order, the rest follow in default order. Another dataset has another key,
  so it keeps its default order (AC-81). Tiles really move in the DOM, so Tab order = visual order.
- **Expand** (AC-82): `.ws-expand` leaves a placeholder comment where the tile is, moves the tile into
  `#tile-dialog`, calls `showModal()`, then `Plotly.Plots.resize` on each `.js-plotly-plot` inside (when
  `window.Plotly`). On `close` (Esc through the native `cancel`, a click whose target is the dialog itself = the
  backdrop, or the expand button again) the tile goes back to the placeholder, plots resize, and its `.ws-expand`
  gets focus (a probe showed Chromium 156 restores focus on Esc, but the tile moved, so focus it explicitly).
- **Reopen after a filter**: on `pagehide` with the dialog open, `sessionStorage["databoot.expand"] = "<dataset
  id>:<key>"`; on load, if it names this dataset and a present tile, open that tile and delete the entry. A bar click
  inside the overlay navigates as today (dashboard.js `crossFilter`: URL, chip and counts change) and the page comes
  back with the same tile expanded, filtered.
- **Glow**: `pointermove` on a tile sets `--mx`/`--my` (px) on it; CSS draws the radial glow from them. Not wired
  when `matchMedia("(prefers-reduced-motion: reduce)")` matches.
- **Entrance**: CSS only: `.ws-tile` gets an animation whose delay grows with `:nth-child` and is capped; the
  Designer picks values with **max delay + duration <= 0.6 s** (for example 30 ms steps capped at 300 ms, 240 ms).
  `@media (prefers-reduced-motion: reduce)`: `animation: none; transition: none` everywhere.
  `@media (prefers-reduced-transparency: reduce)`: `backdrop-filter: none` on every element and an opaque tile fill.

## Round 7: keyboard chart marks (K7, `dashboard.js`)
- `crossFilter` is split: `apply(c, value)` (today's URL toggle) is called by `plotly_click` and by the keyboard.
- `keyboardMarks(plot, c)` (same MutationObserver pattern as `keyboardBar`), only when `clickable(c)`: each bar
  `.point path` of trace 0 (never the grey Other trace) and each donut `.slice path` gets `tabindex="0"`,
  `role="button"`, `aria-label="<x_label>: <category>"`; Enter or Space calls `apply(c, category)` with the category
  taken from the trace by index (`gd.data[0].y[i]` for horizontal bars, `.x[i]` vertical, `labels[i]` donut). This
  covers Explorer bars and donuts, the Business leaderboard, Survey question bars and Map top regions (AC-85; the
  last-level leaderboard `data-drill=false` stays non-clickable). Focus ring: `:focus-visible` outline on the SVG
  path, colour and width from DESIGN.md.

## Round 7: theme (T7)
Dark only: `databoot.css` `:root` holds the Designer's dark tokens (`--bg: #050a12`, cyan `#4de1ff`, amber `#ffb454`,
`--mono` system monospace stack, `color-scheme: dark`); delete the `@media (prefers-color-scheme: dark)` block;
`dashboard.js` drops `var dark = matchMedia(...)` and listens to `phone` only. Charts read the tokens through
`tokens()`, so they follow. Global chart rules unchanged (one y-axis, bars sorted from zero, arrows + signed % +
text). No `@font-face`, no image, no external URL. Body and label text >= 4.5:1 against the **effective** tile
background (the glass gradient over `#050a12`); the Designer lists each pair in DESIGN.md.

## Round 7: tests that must change (name them in W7; grep before trusting line numbers)
- `tests/test_survey_page.py:28` order list: `'<div class="questions">'` -> `'class="ws-tile questions"'` (that
  wrapper string now appears only inside Respondents, after Cross-tab).
- Nothing else is planned to change: table captions, figcaption text, `.trends`, `.questions`, `.map-layout`,
  `.map-panel`, `ul.cards > li.card`, `ul.tiles > li.card.tile`, `.kpis`, `section.block`, `.charts` keep matching
  through the `extra` classes and the unchanged inner markup; server order checks (`test_business_page.py:152`,
  `test_survey_page.py:28`) follow the default tile order; `main` checks (`<p>` count, `aria-current` count) hold
  because the tabs are in the header and tiles add no `<p>`. A failure there is a W7 bug, not a test edit.
- Token-reading tests (AC-50 `--div-mid`, AC-69, `test_table_toggle.py`) read CSS at run time: re-run after T7.
- `test_AC_41`, `test_AC_42`, `tests/test_speed.py`: re-time with the tile pages; report the numbers, do not loosen.

## Round 7: fixtures (done in this ticket)
- `tests/conftest.py`: `files_of(root)` -> `{relative path: bytes}` of a folder (what a folder pick sends);
  `upload(client, files)` sends a batch the way intake.js does (begin, one PUT per file, done) and returns the first
  non-200 response or the done response. `make_client` now yields and, after each test, calls `upload.cleanup()`
  once it exists.
- `tests/fixtures/round6_api.json`: the round 6 `/api/datasets/{id}/app` and `/charts` responses of every dataset in
  `data_dir`, `archetypes_dir` and `round6_dir`, keyed `"<fixture>/<path>|<sheet>"` (16 datasets, written from
  commit bd6c14f; two runs were byte-identical). AC-80: QA compares the live responses to it.
- Upload cases: `data_dir` (one file `sales.csv`; many: `sales.csv` + `points.tsv`; folder: `files_of(data_dir)`,
  which has `sub/` and the unreadable files), `archetypes_dir` (`shop.csv` -> `BUSINESS (rule R2)`), and
  `monkeypatch.setenv("DATABOOT_UPLOAD_CAP", "1000")` for the cap.

## Round 7: decisions
1. **One raw request per file plus begin/done**, not multipart: no new dependency (PRD constraint), streaming keeps
   memory flat for 2 GB, and begin/done give the cap over the whole upload and the atomic switch of data folder.
2. **Switch the data folder through `DATABOOT_DATA`**: `config.get()` already reads env on every call and
   `launch.run` already sets it; every route keeps calling `config.get().data`, so nothing else changes.
3. **Tabs in the header, controls above the grid, tables keep their caption h2**: the many existing tests that read
   `main`, captions and container classes stay green (lesson: list each test line; here only one line changes).
4. **`aria-label` on the tile, equal to an h2 inside it** (not `aria-labelledby`): it needs no ids in table
   captions, whose literals dozens of tests check, and still gives a region named by its heading.
5. **Old wrapper classes ride on the tiles (`extra`)**: one flat grid is needed for reorder across all tiles, and the
   classes keep the round 5/6 browser selectors working without edits to test_acceptance.py.
6. **Pointer-event drag, DOM moves, localStorage key per dataset and app**: works with touch and Playwright, keeps
   Tab order equal to visual order, and different apps of one dataset have different tile sets.
7. **Native `<dialog>` for expand**: Esc, focus trap, backdrop and top layer come free; the reopen after a filter
   uses sessionStorage so the server and the URLs stay as they are.
8. **Golden JSON fixture for AC-80**: "figures' data the same as before round 7" is checked exactly, not by eye.


## Round 6 and earlier: overview

DataBoot scans one mounted folder or drive letter, profiles every dataset with fixed rules and draws the
charts those rules pick, fully offline. Sources: docs/PRD.md (round 6), docs/acceptance.json (AC-1..AC-73),
Board gates 160-183 (graphify-out/memory.md). **Round 6** keeps everything below and adds: the seven gate 181
fix-ups (number format by column role, plurals, Explorer bar cursor, score only in Explorer, line y-range, PPTX
title slide, the hexagon text at "Round 5: Map app") and two apps, **Monitoring** (R4) and **Survey** (R5), in the
same rule table, page shell, JSON route and exports. No new dependency, no new page path, no new route: two new
query params (`period`, and `row`/`col` for the cross-tab), so no sitemap or NAV change. Sections "Round 6: ..."
come first; the round 1-5 sections after them still hold unless a round 6 section says otherwise.

No docs/TRENDS.md this round (docs/team.json: trends off; gate 183: "trends off" is the team setting), so I used no
trend advice.

**Gate 183 overrides the PRD on six points; I reworded AC-59, AC-64, AC-67, AC-68 and AC-69 (same ids).**
(a) Evaluation order **R1 Map, R5 Survey, R2 Business, R4 Monitoring, R3 Explorer** (PRD: R1, R2, R4, R5, R3), so a
survey with a date and an age column opens as Survey, with Business in View as. (b) Rolling mean = **7-point**
trailing (PRD: 30); the spike z still uses the 30 points before each point. (c) Likert scales: agree, satisfied,
likely, frequency (never..always), 1..5 and **1..7** (PRD: agree and 1..5); whole-number 1..5 and 1..7 columns count
as C for R5 only. (d) Year-like name rule: the name contains `year` **or `yr`**. (e) Survey adds a **Respondents**
section: up to 2 numerical columns (not identifiers, not 1..7 answers) as histograms. (f) Exports: XLSX and PPTX
for both apps (as PRD S2).
**Architect addition to (a)/(c), found by probe:** with Survey walked before Business, the round 5 `shop.csv`
(date, store, channel, product, `units` = 1..7, revenue) would open as Survey, because `units` counts as a 1..7
answer and makes C = 4 of 6 columns. AC-64 says every round 5 fixture keeps its app, so **1..5/1..7 columns count as
C only when no other numerical column matches the AC-46 amount name rule** (`apps.MEASURE`). A sales file has an
amount; the Board's survey example (timestamp + age) has none. Reworded into AC-64; asked in open questions.
**Gate 181 item 6 vs AC-56 "Explorer exports unchanged":** every PPTX title slide now has a title line and the file
name under it (AC-63); Explorer has no app title, so its first line is `Explorer` (not "... overview", AC-73).
Its XLSX is unchanged.

Round 5 keeps everything rounds 1 to 4 built (that page is now the
**Explorer** app) and adds an ordered rule table that picks a **Map**, **Business** or **Explorer** app per
dataset, a badge, a "View as" switch, the Business and Map layouts, global chart rules (table toggle, tooltips,
separators, donut 2-5, one y-axis) and app-aware exports. No new dependency, no new page path: one new JSON route
(`/api/datasets/{id}/app`) and one new query param (`app`), so no sitemap or NAV change.

No docs/TRENDS.md this round (docs/team.json: trends off, gates 175 and 179), so I used no trend advice.

**Gate 179 overrides the PRD on four points; I reworded the ACs (same ids) in acceptance.json.**
(a) Primary amount / primary numeric (AC-46, AC-51): the first numerical column whose name contains
`amount|revenue|sales|total|price|value|cost|qty|quantity` (case-insensitive), else the first numerical column;
the KPI measures are up to 3 numerical columns in that same order (matching names first, then the rest, each group
in column order). The PRD's "first N column" is replaced. (b) Drill order (AC-49): categorical columns sorted by
distinct count ascending, ties by column order (PRD said column order). (c) Map top regions (AC-53): the country
column if present, else the categorical column with the fewest distinct values (>= 2), ranked by the sum of the
primary numeric, else by row count, top 10 + "Other" (PRD said first C column by row count). (d) Donut 2-5 (AC-16)
confirmed: the 6-value tests change (listed below). View-as hidden when only Explorer qualifies; Explorer exports
unchanged; AC-56 stays in this round.

**Gate 176 overrides this document (AC-40, new AC-42).** (a) First load: a 200,000-row CSV reaches the dashboard in
<= 5 s cold (AC-42): `profile.classify` looks at the first 10,000 rows only (deterministic; `total` for the 50% rule
is that sample size), plus the Counter lever below; charts and KPIs still use all loaded rows. (b) The PPTX title
slide line starts `Rows: M` unfiltered and `Rows: N of M` filtered (N filtered rows, M dataset rows), then
`, C columns`; the `Filters: ...` line stays. This replaces "keeps the dataset size line" in Exports.

**Gate 175 overrides the PRD on AC-38 and AC-39.** The PRD had C2 (second click removes the filter) as a Could and
no chips; the Board said "build C2 now" and "each active filter shows as a removable chip, plus Clear filters". I
reworded AC-38 (chips) and AC-39 (second click removes) in acceptance.json and moved C2 into PRD M13. Ids unchanged.

## Round 6 changes at a glance
| # | Change | Files | AC |
|---|---|---|---|
| F1 | Number format by column role: `apps.plain`, `apps.sep`; `_plain(d)` cache; `plain` axis key on chart dicts; First rows, Map panel rows, tooltips, table views | `app/apps.py`, `app/main.py`, `app/geo.py`, `_tables.html`, `dashboard.js` | AC-59, AC-55 |
| F2 | Plurals: `apps.plural`, Jinja `plural`; figure count, PPTX count line, hex hover text | `app/apps.py`, `app/main.py`, `_figure.html`, `app/export.py`, `dashboard.js` | AC-60, AC-17 |
| F3 | Explorer (and Survey) bars and donuts get the `bar-click` cursor whenever a click filters; DESIGN.md Cross-filter text | `dashboard.js` `barCursor`, DESIGN.md (Designer) | AC-61 |
| F4 | `· score` only in Explorer captions: `figure(c, score=true)` from `app_explorer.html` only | `_figure.html`, `app_explorer.html` | AC-35 |
| F5 | Line charts auto y-range: delete the `.trends` `rangemode = "tozero"` line; bars keep `tozero`; DESIGN.md | `dashboard.js` `render`, DESIGN.md (Designer) | AC-62 |
| F6 | PPTX title slide: title line (app title, or `Explorer`), then the file name in a smaller box | `app/export.py` `pptx` | AC-63 |
| F7 | "Round 5: Map app" hexagon text says choropleth cells (gate 180) | this document (done) | M35 |
| D2 | Rule table order R1, R5, R2, R4, R3; `roles` gains `L` (1..7 answer columns, amount guard) and `cols`; `NAMES`, `TITLES` | `app/apps.py`, `app/main.py` | AC-64 |
| P2 | `pick` (period, cross-tab row/col) in `_appview`, page links and exports | `app/main.py` | AC-66, AC-70 |
| MO1 | Monitoring figures: points per timestamp, period windows, tiles, main line with 7-point mean and 30-point spikes; export list | `app/monitoring.py` (new, empty) | AC-65..AC-67, AC-71 |
| MO2 | Monitoring page: tiles (SVG sparkline), period links, `monitor` builder | `app_monitoring.html`, `dashboard.js`, CSS (Designer) | AC-65..AC-67, AC-54 |
| SU1 | Survey figures: questions, Likert scales, question bars, Likert bars, cross-tab, Respondents histograms; export list | `app/survey.py` (new, empty) | AC-68..AC-71 |
| SU2 | Survey page: question grid, cross-tab form, Respondents, `likert` and `crosstab` builders | `app_survey.html`, `dashboard.js`, CSS (Designer) | AC-68..AC-70, AC-54 |
| Q6 | Week and year grain, Explorer-only exports, "2,024" never shown, offline walk of the new apps | tests only | AC-72, AC-73, AC-59, AC-9 |
| T3 | `round6_dir` fixture (monitor, quiet, survey, orders) with `monitor_rows()`, `survey_rows()`; roles test (done by the architect) | `tests/conftest.py`, `tests/test_archetype_fixtures.py` | AC-59, AC-64..AC-71 |

Order of tickets: F1-F6 first (gate 182), then D2 + P2 (they change `main.py` and the default app), then MO1/SU1
(backend), then MO2/SU2 (frontend, after the Designer's layouts), then QA.

## Round 6: detection (`app/apps.py`)
- `roles(...)` gains `cols = len(columns)` and `L` = numerical column indexes whose non-empty typed values are all
  whole numbers in 1..7 (at least one value), **set to `[]` when any other numerical column matches `MEASURE`**
  (architect guard, see the top). R1, R2 and R4 keep counting `L` columns as N.
- Rule table (the walker `detect` does not change; `qualifies` follows this order, so View-as lists e.g. Survey,
  Business, Explorer):
  ```python
  RULES = [("R1", "map", ...unchanged...),
           ("R5", "survey", lambda r: (c := len(r["C"]) + len(r["L"])) >= 4 and c >= 0.6 * r["cols"] and len(r["N"]) - len(r["L"]) <= 2),
           ("R2", "business", ...unchanged...),
           ("R4", "monitoring", lambda r: bool(r["T"] and r["N"] and not r["C"])),
           ("R3", "explorer", lambda r: True)]
  NAMES |= {"monitoring": "Monitoring", "survey": "Survey"}
  ```
  `main.TITLES |= {"monitoring": "Monitoring overview", "survey": "Survey overview"}`.
- Probe (ticket 463, a throwaway test over every fixture with these conditions): `data_dir`, `archetypes_dir`,
  `big_csv`, `big_sales_csv` keep their round 5 app and rule (shop.csv stays business/R2 only because of the guard);
  `round6_dir`: monitor.csv and quiet.csv `monitoring/R4` (qualifies monitoring, explorer), survey.csv `survey/R5`
  (qualifies survey, business, explorer), orders.csv `explorer/R3`.

## Round 6: number format by role (F1, AC-59, AC-55)
- `apps.plain(columns, mapping, typed) -> frozenset` of numerical column indexes that never get separators:
  identifier = name (lower-cased, stripped) is `id` or ends in `id` / `_id`, or contains `code`, `zip` or `phone`;
  year-like = name contains `year` or `yr`, or every non-empty value is a whole number in 1900..2100 (gate 183).
  Temporal and other columns are not numerical, so they never get separators anyway.
- `main._plain(d)` = `lru_cache(maxsize=4)` of `apps.plain` on the **unfiltered** typed rows (`_base`): a filter
  never changes a column's format. `make_client` must clear it (add `"_plain"` to the cache list in conftest).
- `apps.sep(v)` = today's `sep` lambda moved out of main.py (adds separators to the integer part of a number text);
  main registers it as the Jinja filter. It is only ever called for a column that is numerical and not in `plain`:
  - `_tables.html` First rows: `v|sep if types[col] == "numerical" and loop.index0 not in plain else v` (`plain`
    passed to the template).
  - Map side panel: `geo.view(..., settings, plain=frozenset())` writes `rows` cells through `apps.sep` for
    numerical non-plain columns; dashboard.js drops its own `sep()` regex and prints the cells as sent.
- Charts: `_appview` sets `c["plain"] = [axis letters]` on every chart dict (and `map3d`) whose `x_label`,
  `y_label` or `z_label` is a column in `plain` (`"x"`, `"y"`, `"z"`; `z` covers the map colour). dashboard.js:
  for a plain axis `hoverformat = ""` (no `,`), geo/3D/colour `hovertemplate` uses `%{z}` instead of `%{z:,}`, and
  `tableOf` prints `String(v)` for that column. Sums and counts the app computes (bar values, KPIs, tiles of
  non-plain columns) keep separators.
- orders.csv (`order_id` 10045.., `year` 2023/2024, `amount` 12,345..): First rows prints `10045`, `2024`,
  `12,345`; the Explorer histogram of `order_id` (first numerical) has `plain == ["x"]`.

## Round 6: fix-ups F2-F6
- **F2 plurals**: `apps.plural(n, word) = f"{n:,} {word}" + ("" if n == 1 else "s")`; Jinja filter
  `plural`. Figure count: `{{ c.shown|num }} of {{ c.total|plural(unit) }}`, where the unit (`point` for map3d,
  line, scatter, monitor; else `row`) follows M (AC-17: "1 of 1 row", "0 of 5 rows"). `export.pptx` count line the
  same way. Hex hover: map2d trace gets `text` = `plural(count, "point")` per cell (built in JS with the same rule),
  `hovertemplate: "%{text}<extra></extra>"`.
- **F3 cursor**: one JS helper `clickable(c)` = the condition `crossFilter` uses today (bar or donut, `c.drill !==
  false`, a `form.filters select[name="f.<x_label>"]` exists). `barCursor` runs for every clickable chart, not only
  for a boolean `c.drill`; it sets `bar-click` over a clickable point and `no-pointer` over the Other trace
  (`c.other && curveNumber > 0`).
- **F4 score**: `figure(c, hidden=false, score=false)`; only `app_explorer.html` calls `figure(c, score=true)`.
  Chart dicts keep their `score` key (the API is unchanged; test_rules L22).
- **F5 y-range**: delete `dashboard.js` L377 (`.trends` lines `rangemode = "tozero"`). Bars keep `rangemode
  "tozero"` from the bar builder (L93). No line builder (line, monitor) sets `rangemode`.
- **F6 title slide**: box 1 = `title or "Explorer"` (40 pt bold), box 2 = file name (+ ` - sheet`) at 24 pt, then
  the Rows line and the Filters line as today (both move down one box height; keep inside the slide).

## Round 6: request flow (P2)
```python
def _pick(d, shown, params):      # validated, hashable, part of the cache key
    if shown == "monitoring": return params.get("period") if params.get("period") in ("7", "30", "90", "all") else "30"
    if shown == "survey":                                      # defaults: the first two questions
        _, mapping, typed, _ = _base(d)
        return survey.pick(survey.questions(d.columns, mapping, typed), params.get("row"), params.get("col"))
    return None

@lru_cache(maxsize=8)
def _appview(d, f, app, app_param=None, pick=None):
    ...as round 5...
    if app == "monitoring": return monitoring.view(d.columns, v["typed"], v["mapping"], pick, config.get())
    if app == "survey":     return survey.view(d.columns, v["typed"], v["mapping"], _base(d)[2], pick, config.get())
```
- `dashboard`, `/app` and `_export` all pass `_pick(d, shown, request.query_params)`, so the page, its JSON and the
  exports show the same period / cross-tab (PRD constraint: deterministic).
- Like `appq`, `pickq` = the request's own `period` (or `row`, `col`) pairs **only when the URL had them**; chips,
  Clear filters and export links carry `f + appq + pickq`; View-as links carry `f` and the new app only (a period
  means nothing to another app). The filter form gets hidden inputs for `app` (as today) and for `pickq`.
- `survey.view` needs the unfiltered typed rows (`_base(d)[2]`) only to decide which questions are Likert and their
  levels, so a filter never changes a question's chart kind or its segment order.

## Round 6: Monitoring app (`app/monitoring.py`)
`view(columns, typed, mapping, period, settings)` on the filtered typed rows (the round 4 date range applies; there
are no category filters since C = 0). `export(view)` gives the export list.
- **Points**: time column = first T; rows with an empty time are dropped; rows with the same timestamp are averaged
  per numerical column (over that column's non-empty values); sorted by time. `last` = the latest timestamp.
- **Windows**: period `N` days (`"7"|"30"|"90"`): current = `t > last - N days`, previous = `last - 2N days < t <=
  last - N days` (half-open, no overlap); `"all"` = every point and no previous window.
- **Tiles** (one per numerical column, column order): `{"column", "latest", "min", "max", "mean", "previous",
  "pct", "dir", "spark"}`; `latest` = the column's value at the latest point in the current window that has one;
  `min`/`max` over the current window; `pct = round(100 * (mean - previous) / abs(previous), 1)` of the window means;
  `"all"`, an empty previous window or `previous == 0` give `pct = None` and the page prints `n/a` and no arrow;
  `dir` and the arrow + signed % + word rendering are exactly the Business card's (template code shared via a macro).
  `spark` = the current window's values stride-sampled to at most 60 (`rules._sample`), drawn as the same inline SVG
  as Business (`business.spark`). Tiles of a `plain` column print values without separators.
- **Main line** (primary = `apps.measures(...)[0]`): over **all** points (before the period cut): `mean[i]` =
  mean of `y[max(0, i - 6) .. i]` (7-point trailing, partial at the start, gate 183); `spike[i]` when `i >= 30`,
  `sd = pstdev(y[i-30:i]) > 0` and `|y[i] - fmean(y[i-30:i])| / sd > 3`. Use running sums of y and y² over the
  30-window (O(n); 200,000 rows must stay inside AC-42's 5 s). Then cut to the current window and stride-sample to
  `chart_cap`, always keeping the spike points.
  Chart dict: `_chart("monitor", f"{m} by {t}", t, m, f"temporal {t} + numerical {m}: line, 7-point rolling mean,
  spike |z| > 3 over 30 points", shown, total, {"x": [iso], "y": [...], "mean": [...], "spike": [positions in x]},
  score)`; `shown`/`total` = points drawn / points in the window. dashboard.js `monitor` builder: three traces on
  one y-axis: the value line (`--c1`), the rolling mean (muted, dashed, named `7-point mean`), and the spikes as
  `mode: "markers+text"`, `text: "spike"`, `textposition: "top center"` (marker + label, never colour alone).
  Legend on (2+ series). `tableOf`: columns time, value, 7-point mean, spike (`spike` or empty).
- **Payload**: `{"tiles": [...], "charts": [monitor], "period": "30", "periods": ["7", "30", "90", "all"],
  "latest": "2024-04-29T00:00:00"}`. No primary (cannot happen under R4, N >= 1) or no dated row: no chart, tiles
  `n/a`.
- **Page** (`app_monitoring.html`): tiles `<ul class="tiles">` (like `.cards`, no `<p>`), period links
  `<nav class="periods" aria-label="Period">` (`7 days`, `30 days`, `90 days`, `All`; current `aria-current`;
  each href = current `f` + `appq` + `period=`), the filter form (date range), the main line figure, Columns, First
  rows. Plain GET links: the URL is the state and Back works (decision 15).
- **Export** (`monitoring.export(view)`): `[tiles table (Column, Latest, Min, Max, Change %), line chart of the
  main line (kind "line", data x/y only)]`, ids `chart-1..`; title `Monitoring overview`.
- **Hand values** (monitor.csv, period 30; window 2024-03-31..2024-04-29, 30 points): temperature latest 20.0, min
  20.0, max 60.0, mean 24.2667 vs previous 23.1 -> `▲ +5.1% up`; humidity latest 54, min 50, max 54, 52.0 vs 52.0
  -> `▶ 0.0% no change`; quiet.csv temperature 23.0 vs 23.1 -> `▼ -0.4% down`. Spikes: monitor.csv exactly
  2024-04-10 (row 100); quiet.csv none. 7-point mean at 2024-04-10: 28.4286; at 2024-04-29: 23.0. Values from the
  ticket 463 probe; QA recomputes them by hand in the test from `monitor_rows()`.

## Round 6: Survey app (`app/survey.py`)
`view(columns, typed, mapping, base_typed, pick, settings)` on the filtered typed rows; `questions(columns,
mapping, typed) -> [index]`; `pick(questions, row, col) -> (row name, col name)`; `export(view)`.
- **Questions** = C columns plus the `roles` `L` columns (computed on the unfiltered rows), in column order. T, I and other N columns are not
  questions.
- **Likert** (`scale(values) -> (levels, neutral index) | None`, on `base_typed`): all non-empty values, compared
  lower-cased and stripped, lie on one known scale and there are at least 2 distinct values:
  ```python
  SCALES = [("strongly disagree", "disagree", ("neutral", "neither agree nor disagree"), "agree", "strongly agree"),
            ("very dissatisfied", "dissatisfied", ("neutral", "neither satisfied nor dissatisfied"), "satisfied", "very satisfied"),
            ("very unlikely", "unlikely", ("neutral", "neither likely nor unlikely"), "likely", "very likely"),
            ("never", "rarely", "sometimes", "often", "always"),
            (1, 2, 3, 4, 5), (1, 2, 3, 4, 5, 6, 7)]   # numbers: whole numbers; the first scale that holds every value wins
  ```
  `levels` = the scale's labels in order (the data's own spelling when present, else the first spelling above),
  all levels kept even with a count of 0; neutral = the middle level.
- **Non-Likert question**: `bar` dict, counts per `str(value)` over the view rows, `business._ranked` (top 10 by
  count desc, ties by name, then one `Other`), `"orientation": "h"`, `"other": bool`, no `drill` key, so the
  Explorer click filter (round 4) and the F3 cursor apply; `x_label` = the question column, `y_label` = `count`.
- **Likert question**: kind `"likert"`, data `{"levels": [...], "counts": [...], "pct": [...], "neutral": i}`;
  `pct` unrounded (sums to 100), shown with 1 decimal. JS `likert` builder: one horizontal stacked bar
  (`barmode: "stack"`, one trace per level, x = pct, y = [question]), colours: levels before neutral from
  `--div-neg` (strongest first), neutral `--div-mid` (grey), after it `--div-pos`; x axis 0..100 with `%` suffix;
  hover `level: count (pct%)`. Not clickable (numeric answers have no dropdown; a word Likert column does, but a
  100% bar has one category per trace, so no `crossFilter`).
- **Cross-tab**: `pick` = the two question names from the URL when both are questions, else the first two; kind
  `"crosstab"`, data `{"x": col levels, "y": row levels, "z": counts [[...]], "pct": row % [[...]] unrounded}`;
  levels in scale order for Likert questions, else by count desc then name (all values, no Other). JS `crosstab`
  builder: one `heatmap` trace, sequential one-hue scale on z, `text` = `count (pct%)` with 1 decimal,
  `texttemplate: "%{text}"`, colour bar titled `count`. Form `<form class="crosstab" method="get">` with two
  labelled selects `row` and `col` (options = questions), hidden inputs for `f`, `appq`; a change submits (JS) and an
  Apply button works without JS. Fewer than 2 questions: no cross-tab (cannot happen under R5).
- **Respondents**: up to 2 N columns that are not in `L` and not in `plain`, in column order, each
  `rules._histogram(columns, typed, {columns[i]: "numerical"}, settings)` (the rule picks the only numerical
  column), under `<h2>Respondents</h2>`. None: no section.
- **Ids and page order**: questions grid (bars and Likert bars in column order), cross-tab, Respondents; `chart-1..N`
  in that order. Payload `{"charts": [...], "questions": [names], "pick": [row, col]}`.
- **Page** (`app_survey.html`): filter form + chips (categorical dropdowns, date range when T exists), `<div
  class="questions">` grid (two per row at desktop, one at phone: Designer), cross-tab section with its form and
  figure, Respondents section, Columns, First rows.
- **Export** (`survey.export(view)`): one native `bar` per question (a Likert question becomes a bar of its counts
  in scale order, no Other), then the cross-tab as a `table` chart (head: row question, then the column levels;
  rows: counts), then the Respondents histograms; title `Survey overview`.
- **Hand values** (survey.csv, 40 rows, no filter): questions `gender, region, city, q_service, q_easy, q_visits,
  q_score`; bars: gender female 14, male 13, other 13; region East, North, South, West 10 each; city city00..city03
  4 each, city04..city09 3 each, then `Other` 6 (city10 + city11). Likert: q_service (satisfied scale) 6, 6, 6, 16,
  6 (15/15/15/40/15%); q_easy (agree) 8 each (20%); q_visits (frequency) 9, 9, 9, 9, 4; q_score (1..5) 5, 5, 5,
  15, 10. Cross-tab default gender x region (columns East, North, South, West): female 3, 4, 3, 4 (21.4, 28.6,
  21.4, 28.6%), male 3, 3, 4, 3 (23.1, 23.1, 30.8, 23.1%), other 4, 3, 3, 3. Respondents: `age` only
  (`respondent_id` is an identifier). From the ticket 463 probe; QA recomputes them from `survey_rows()`.

## Round 6: JSON contract additions (`GET /api/datasets/{id}/app`, fetched once on load, no polling)
- Every app: chart dicts may carry `"plain": ["x" | "y" | "z"]` (F1). New kinds: `monitor` (data `x`, `y`,
  `mean`, `spike`), `likert` (`levels`, `counts`, `pct`, `neutral`), `crosstab` (`x`, `y`, `z`, `pct`). They never
  reach the export writers (the `export` functions turn them into `line`, `bar` and `table`).
- Monitoring adds `tiles`, `period`, `periods`, `latest`; Survey adds `questions`, `pick`. Example:
  ```json
  {"dataset": "9c1e...", "app": "survey", "rule": "R5", "qualifies": ["survey", "business", "explorer"],
   "shown": "survey", "filters": [], "questions": ["gender", "region", "..."], "pick": ["gender", "region"],
   "charts": [{"id": "chart-1", "kind": "bar", "orientation": "h", "other": false, "...": "..."},
              {"id": "chart-4", "kind": "likert", "data": {"levels": ["Very dissatisfied", "..."], "counts": [6, 6, 6, 16, 6],
               "pct": [15.0, 15.0, 15.0, 40.0, 15.0], "neutral": 2}}]}
  ```
- `/api/datasets/{id}/charts` is unchanged (Explorer only).

## Round 5 changes at a glance
| # | Change | Files | AC |
|---|---|---|---|
| A1 | Rule table, roles, `detect`, `measures` (name rule); `GET /api/datasets/{id}/app`; `app` param; `_detected`, `_appview` caches; `_view` stops computing Explorer charts | `app/apps.py` (new, empty), `app/main.py` | AC-43, AC-45 |
| A2 | Page shell: badge, View-as links, one template per app body; old page tests pass `app=explorer` | `dataset.html` (+ includes), `app/main.py` | AC-44, AC-45 |
| B1 | Business figures: grain, periods, KPI cards, trend(s), leaderboard, drill order, crumbs, change table | `app/business.py` (new, empty) | AC-46..AC-50 |
| B2 | Business page: cards (sparkline SVG), breadcrumb, change table; leaderboard drill click in JS | `app/templates/`, `dashboard.js` | AC-46..AC-50, AC-55 |
| M1 | Map figures: valid coordinates, points or hexbin, row details, top regions, 3D chart | `app/geo.py` (new, empty) | AC-51..AC-53 |
| M2 | Map page: 70vh `scattergeo`, side panel, 3D toggle | templates, `dashboard.js`, CSS (Designer) | AC-51..AC-53, AC-55 |
| G1 | Global rules: table toggle on every Plotly figure, tooltips with separators, no `yaxis2`, donut 2-5 | `dashboard.js`, `app/rules.py` L175, DESIGN.md (Designer) | AC-16, AC-54, AC-55, AC-57 |
| E2 | App exports: `title`, a `table` kind, Business and Map section lists | `app/xlsx.py`, `app/export.py`, `app/main.py` | AC-56 |
| T2 | `archetypes_dir` fixture (shop, places, measures, sparse) and `shop_rows()`; cache clears in `make_client` (done by the architect) | `tests/conftest.py`, `tests/test_archetype_fixtures.py` | AC-43..AC-53 |
| N1 | No off-host request in any app, toggle or drill | Playwright test only (all assets already local) | AC-58 |

## Round 5: request flow
```python
@lru_cache(maxsize=4)
def _detected(d):                 # once per dataset, on the full UNFILTERED rows (PRD: same file, same app)
    rows, mapping, typed, options = _base(d)
    return apps.detect(d.columns, mapping, typed)   # {"app", "rule", "qualifies": [...]}, qualifies in RULES order

def _shown(d, params):            # app=<name> only when the dataset qualifies, else the detected app (AC-45)
    a = params.get("app")
    return a if a in _detected(d)["qualifies"] else _detected(d)["app"]

@lru_cache(maxsize=8)
def _appview(d, f, app):          # the shown app's figures under filters f
    v = _view(d, f)
    if app == "business": return business.view(d.columns, v["rows"], v["typed"], v["mapping"], f, v["options"])
    if app == "map":      return geo.view(d.columns, v["rows"], v["typed"], v["mapping"], config.get())
    return {"charts": rules.charts(d.columns, v["typed"], v["mapping"], config.get())}
```
- `_view(d, f)` loses its `"charts"` key and gains `"typed"` (the filtered typed rows): Business and Map pages
  must not pay for the 8 Explorer rules (2.8 s cold on 200,000 rows, round 4 probe), or AC-42 breaks. Every
  current `v["charts"]` (charts API, both exports, dashboard) becomes `_appview(d, f, "explorer")["charts"]`.
- `filters.parse` already ignores `app` (only `f.*`, `from`, `to`), so `f` and its caches are app-independent.
- Links that leave the page state (chips, Clear filters, breadcrumb, export links, View-as) carry `app=<shown>` **only
  when the request had a valid `app` param** (`appq = [("app", shown)]` else `[]`, appended after `f` in
  `urlencode`). With no param the URLs stay exactly as in round 4. dashboard.js keeps `location.search`, so the
  click filters and drills keep `app` by themselves.
- `make_client` clears `_detected` and `_appview` (already in conftest, guarded by `hasattr`).

## Round 5: detection (`app/apps.py`)
- **Roles** (`roles(columns, mapping, typed) -> dict`), from the existing types only (gate 179: no new profiler):
  `lat`, `lon` = the geospatial columns whose lower-cased stripped name is in `rules.LAT` / `rules.LON` (the pair
  `_map3d` uses; reuse those sets); `G` = both found; `T`, `N`, `C` = lists of temporal, numerical, categorical
  column indexes in column order (geospatial columns are their own type, so `N` never counts the pair); `I` =
  the rest. `coords` = rows where `_num(lat)` is in -90..90 and `_num(lon)` in -180..180 (typed rows, full).
- **Rule table**, walked in order, first true condition is the detected app; every true one is in `qualifies`:
  ```python
  RULES = [("R1", "map", lambda r: r["G"] and (len(r["N"]) <= 2 or r["coords"] >= 0.5 * r["rows"])),
           ("R2", "business", lambda r: r["T"] and r["C"] and r["N"]),
           ("R3", "explorer", lambda r: True)]
  ```
  Round 6 inserts R4-R7 rows before R3; `detect` does not change. `rows == 0`: share 0 (so only N <= 2 maps).
  `NAMES = {"map": "Map", "business": "Business", "explorer": "Explorer"}` for the badge and switch labels.
- `measures(columns, mapping) -> [index]`: `MEASURE = re.compile(r"amount|revenue|sales|total|price|value|cost|qty|quantity", re.I)`;
  `[i for i in N if MEASURE.search(columns[i])] + [i for i in N if not MEASURE.search(columns[i])]`, first 3.
  `[0]` is the primary amount (Business) and the primary numeric (Map). shop.csv: `revenue`, `units`.
- Detection reads the full loaded rows once (one pass over typed lat/lon); deterministic, no randomness.

## Round 5: Business app (`app/business.py`)
`view(columns, rows, typed, mapping, f, options)` works on the filtered view rows (filters apply to every app).
- **Time column** = first T; **grain** from `(last - first).days` of its non-empty dates: `<= 60` day, `<= 182`
  week (ISO, Monday start), `<= 1096` month, else year. Period key = its start `date`: `start(d)`, `nxt(p)`,
  `end(p) = nxt(p) - 1 day`, `prev(p) = start(p - 1 day)`.
- **Latest full** `L` = `start(last)` if `last == end(start(last))`, else `prev(start(last))` (day grain: always
  `start(last)`); **previous** `P = prev(L)`. A period with no rows sums to 0. `L < start(first)` (no full period):
  card value `n/a`. `P < start(first)` or `sum(P) == 0`: change `n/a`, no arrow.
- **Cards** (one per `apps.measures`): `{"column", "latest", "previous", "pct", "dir", "spark"}`; `pct =
  round(100 * (latest - previous) / abs(previous), 1)`; `dir` = `"up"` (▲), `"down"` (▼) or `"no change"` (▶)
  from the sign of `latest - previous`; the page prints arrow + `"+19.4%"` (sign always, `0.0%` for zero) + the
  `dir` word, never colour alone. `spark` = the sums of the last 12 periods ending at `L` (not before
  `start(first)`), drawn server-side as an inline `<svg><polyline>` with a `<title>` (not a Plotly chart: no table
  toggle, PRD assumption approved in gate 179).
  shop.csv (month grain, last date 2024-07-10, so L = June, P = May): revenue 7,392 vs 6,192 = ▲ +19.4% up; units
  72 vs 60 = ▲ +20.0% up.
- **Trend**: one `line` chart per measure (small multiples, never a second axis): x = period starts (ISO) from
  `start(first)` through `L`, zero-filled; y = sums. Periods after `L` (the partial one) are left out so the line
  does not end in a false drop; `shown`/`total` = periods drawn. Same dict shape as the round 4 line, so the
  existing JS builder draws it.
- **Drill order** = C columns sorted by `(len(options[c]), column index)` (gate 179). **Group column** = the first in
  that order with no `f.<c>` in `f`; **next** = the next unfiltered one after it; `drill = next is not None`.
  No unfiltered C column left: no leaderboard and no change table.
- **Leaderboard**: `bar` chart dict plus `"orientation": "h"`, `"drill": bool`, `"other": bool`; sums of the primary
  amount per `str(cell)` over all view rows, sorted `(-sum, name)`, top 10, then one `"Other"` = sum of the rest
  (only when there is a rest; `other` says the last bar is it). `x_label` = the group column (the JS click key).
- **Change table** (needs L and P): rows for the leaderboard's categories in its order (Other included):
  `{"category", "previous", "latest", "delta", "t"}`, `t = round(delta / max|delta|, 2)` (0 when all deltas are 0).
  The template prints the delta with its sign (`+1,200`, `-35`, `0`) and sets `class="delta pos|neg|zero"` and
  `style="--t: 0.42"`; the Designer mixes `--div-pos`/`--div-neg` with `--div-mid` (grey) by `|t|`.
- **Crumbs**: `[("All", href)] + [(f"{c}: {v}", href)]` for each active `f.<c>` on a C column, in drill order;
  each href keeps `from`/`to`, `app` and the crumbs before it; the last crumb is the current page
  (`aria-current="page"`, no link). Shown as `<nav class="crumbs" aria-label="Drill path">`, `›` separators.
- Drill click (dashboard.js): the existing `crossFilter` path with key `f.<x_label>` on the leaderboard when
  `c.drill`; the `Other` bar (`c.other` and last index) never navigates; with `drill` false nothing is attached and
  the figure gets `data-drill="false"` so the Designer can drop the pointer cursor. Back works (GET navigation).
  `crossFilter` returns early when `c.drill === false` (leaderboard at the last level, Map top regions); Explorer
  bars have no `drill` key and keep the round 4 click filter and toggle.
- Payload: `{"cards": [...], "charts": [trend..., leaderboard], "changes": [...] | None, "crumbs": [...],
  "grain": "month", "latest": "2024-06-01", "previous": "2024-05-01"}`.

## Round 5: Map app (`app/geo.py`)
`view(columns, rows, typed, mapping, settings)` on the view rows; primary = `apps.measures(...)[0]` or none.
- `pts` = rows with valid coordinates (same test as detection). `len(pts) <= 5000` (`HEX_AT = 5000`): chart
  `{"kind": "map2d", ..., "data": {"mode": "points", "lon", "lat", "color": [primary or None], "row": [view row
  index]}, "z_label": primary name or None, "columns": [...], "rows": [[cell as str]]}`; `rows` holds only the drawn
  rows (<= 5000), so the side panel needs no extra request. Points with a `None` colour go in a second trace in
  `--muted` (<= 2 series); each trace sets `customdata` = the point's position in `rows`, which the
  `plotly_click` handler uses to fill the panel `<dl>` (`columns[i]` / `rows[k][i]`, numbers with separators).
- `> 5000`: `"mode": "hex"`. Cell size `s = (max lon - min lon) / 40` (1.0 when the span is 0); pointy-top axial
  coordinates on the lon/lat plane: `q = (sqrt(3)/3 * lon - lat/3) / s`, `r = (2/3 * lat) / s`, cube-rounded; centre
  `lon = s * sqrt(3) * (q + r/2)`, `lat = s * 1.5 * r`. Data `{"lon", "lat", "count", "size": s}` sorted by `(q, r)`;
  `sum(count) == len(pts)`. JS (dashboard.js) draws **hexagon choropleth cells**: one GeoJSON `choropleth` trace
  whose features are hexagon polygons built from the server's centres and `size` (clockwise rings, clamped to
  lon +-180 / lat +-90; not hexagon markers: Board gate 180), colour = count on the sequential scale, hover
  `N points` (`1 point`, round 6 F2); a click shows the count in the panel. big_csv (60,000) is the test case.
- `shown`/`total` = `len(pts)` / `len(rows)` in both modes, printed `N of M rows` (rows with coordinates of view
  rows; AC-17 form). The template's `points` set does not include `map2d`.
- **Top regions** (gate 179): the country column (name in `rules.COUNTRY`, categorical or other) if any, else the C
  column with the fewest distinct values (>= 2, ties by column order); value = sum of the primary numeric per
  region, else row count; top 10 + `Other`; `bar` dict with `"orientation": "h"`, `"drill": False`. No such column:
  no chart (the panel shows only the details).
- **3D toggle** (Board gate 180): `"map3d"` = the Explorer `scatter3d` chart (`rules._map3d`, called with `z` = the
  primary numeric by the name rule, else the first numerical, so `z_label` is the primary or None); Explorer's own
  `map3d` keeps z = first numerical (AC-6/AC-27). The page renders a hidden `<figure data-kind="map3d" hidden>`; the
  `3D view` button (`aria-pressed`) hides the 2D figure, shows and (first time) draws the 3D one; again swaps back.
- Height (AC-51): `.app-map .chart[data-kind="map2d"] .plot { height: 70vh }` (Designer may tune within 65-75%);
  `layout.geo.fitbounds = "locations"`, projection `natural earth`, outline from the bundled topojson.
- Payload: `{"charts": [map2d, regions?], "map3d": {...} | None}`.

## Round 5: page and JSON contract
- **`GET /api/datasets/{id}/app[?app=&f.*&from&to]`** (fetched once by dashboard.js on load, no polling):
  ```json
  {"dataset": "3f2a9c01b7de", "app": "business", "rule": "R2", "qualifies": ["business", "explorer"],
   "shown": "business", "filters": [], "charts": [{"id": "chart-1", "kind": "line", "...": "..."}],
   "cards": [...], "changes": [...], "crumbs": [...], "map3d": null}
  ```
  `app`/`rule` are always the detected ones (AC-43: stable), `shown` is what the page draws; `charts` are the shown
  app's figures with `id`s `chart-1..N` in page order (Explorer: exactly `/charts`' list). Business-only and
  Map-only keys are present only for that app. `/api/datasets/{id}/charts` is unchanged (Explorer charts always).
- dashboard.js fetches `/app` + `location.search` instead of `/charts` and draws every `charts[i]` into
  `#chart-i` with the `build` map (new builder `map2d`; `bar` honours `c.orientation == "h"` and prints value
  labels `texttemplate: "%{x:,}"` when `c.orientation`), then `map3d` lazily on toggle.
- **Badge** `<span class="app-badge">App: Business (rule R2)</span>` in the page head (a span, not `<p>`:
  test_AC_17). **View as**: `<nav class="view-as" aria-label="View as">` with one link per `qualifies` entry
  (`?app=<name>` + current filters), the shown one `aria-current="page"`; absent when `qualifies == ["explorer"]`.
- **Template split**: `dataset.html` keeps crumb, head (h1, badge, exports), View-as, then
  `{% include "app_" ~ shown ~ ".html" %}`; `app_explorer.html` = today's body unchanged (KPI strip, form, chips,
  charts, tables); `_filters.html` (form + chips, shared) and a `figure` macro (figcaption: title, rule, count,
  `· score` only when the chart has a score, table toggle button). Business: cards, filters, crumbs, trend
  figure(s), leaderboard figure, change table, Columns, First rows. Map: filters, `<div class="map-layout">` with
  the map figure and `<aside class="map-panel" aria-live="polite">` (details `<dl>` + regions figure), hidden 3D
  figure, Columns, First rows. Layout and style: Designer.
- **Global rules in JS (AC-54, AC-55)**: after each `newPlot`, a `<button type="button" class="table-toggle"
  aria-pressed="false">View as table</button>` (server-rendered in the figcaption) toggles between `.plot` and a
  generated `<table class="plot-table">` of the traces just passed to Plotly (x/y, labels/values, lon/lat/colour or
  count, heatmap z with labels), numbers via `toLocaleString("en-US")`. Layout gets `separators: ".,"` and
  `hoverformat: ","` on every axis; geo, pie and 3D traces get a `hovertemplate` with `:,`. No builder may set
  `hoverinfo: "none"|"skip"` or `yaxis2`/`overlaying`. Donut: `rules._donut` `2 <= len(counts) <= 5`.
- **Exports (AC-56)**: both routes use `_shown(d, request.query_params)`; Explorer passes `_appview(...)["charts"]`
  and no title (round 4 output exactly). `xlsx.write(dataset, rows, charts, summary, title=None)` and `export.pptx(dataset, charts,
  summary, rows_shown, title=None)`. With a title: Summary sheet A1 = title, A2 = summary (Explorer: A1 = summary,
  unchanged); PPTX title slide first box = title. New chart kind `"table"` (`data: {"head": [...], "rows":
  [[...]]}`): XLSX sheet with the grid and no chart, PPTX a native table slide (generalise `export._table`).
  Business list = `[cards table (Measure, Previous, Latest, Change %), trend line(s), leaderboard bar, change
  table]`; Map list = `[scatter of lon (x) / lat (y), stride-sampled to chart_cap like `rules._scatter`, top
  regions bar]`. Built by `business.export(view)` / `geo.export(view)`; ids `chart-1..` in that order.

## Round 4 changes at a glance
| # | Change | Files | AC |
|---|---|---|---|
| S1 | Interest score per chart, computed on the full filtered rows inside each rule | `app/score.py` (new), `app/rules.py` | AC-32 |
| S2 | Charts sorted by score after the 8-chart cut (stable), ids renumbered in display order | `app/rules.py` `charts` | AC-33 |
| D1 | Data access: per-dataset cache of raw rows, column types, typed rows and dropdown options; per-filter cache of the view | `app/main.py`, `app/rules.py` `typed`, `app/profile.py` (speed only) | AC-41 |
| F1 | Filters: parse query params, apply, labels, canonical query string | `app/filters.py` (new), `app/main.py` | AC-37, AC-38 |
| K1 | KPI figures of the filtered rows | `app/rules.py` `kpis` | AC-36 |
| P1 | Page: KPI strip, filter form, chips, Clear filters, score in caption, first chart full width, filtered export links | `dataset.html`, `databoot.css` (Designer) | AC-34..AC-38 |
| J1 | dashboard.js: fetch with the page's query string, tidy form submit, Plotly click cross-filter with toggle | `app/static/js/dashboard.js` | AC-38, AC-39 |
| E1 | Exports take the same query params; XLSX `Summary` sheet (last), PPTX title slide filter line | `app/main.py`, `app/xlsx.py`, `app/export.py` | AC-40 |
| T1 | `big_sales_csv` fixture (200,000 rows), done by the architect | `tests/conftest.py` | AC-41 |

## Round 4: request flow (one function for page, API and exports)
```python
@lru_cache(maxsize=4)
def _base(d):                     # once per dataset: the slow part (classify is seconds on 200,000 rows)
    rows = catalog.load(d, config.get().max_rows)
    mapping = profile.classify(d.columns, rows)          # types from the UNFILTERED rows
    return rows, mapping, rules.typed(d.columns, rows, mapping), filters.options(d.columns, rows, mapping)

@lru_cache(maxsize=8)
def _view(d, f):                  # f = filters.parse(...) result: a hashable tuple
    rows, mapping, typed, options = _base(d)
    keep = filters.apply(f, d.columns, mapping, typed)   # list of row indexes, or None when f == ()
    rows_f = rows if keep is None else [rows[i] for i in keep]
    typed_f = typed if keep is None else [typed[i] for i in keep]
    return {"rows": rows_f, "mapping": mapping, "options": options, "filters": f,
            "labels": filters.labels(f, d.columns, mapping),
            "charts": rules.charts(d.columns, typed_f, mapping, settings),
            "kpis": rules.kpis(d.columns, rows_f, typed_f, mapping)}
```
- Every route that shows data calls `_view(d, filters.parse(request.query_params, d.columns, mapping))`: the
  dashboard page, `/api/datasets/{id}/charts` and both exports. With no (or only ignored) params `f == ()` and
  every route answers as before, plus the new keys (`score`, `kpis`, `filters`, Summary sheet, filter line).
- Column types come from the unfiltered rows, so a filter never changes a column's type, the dropdowns or which
  rules can run. The rules then run on the filtered rows, so a chart whose rule no longer matches (for example a
  donut on the filtered column, now 1 value) is simply not generated and not shown (gate 175).
- `rules.typed(columns, rows, mapping)`: a copy of the rows with numerical and geospatial cells as `_num(v)` and
  temporal cells as `_time(v)`, others as they are. `_num`/`_time` return typed values unchanged, so the rules
  keep calling them and still work on raw rows (unit tests pass raw rows). Raw rows stay for the First rows
  table, the XLSX Data sheet and % missing, so what the owner sees is what the file holds.
- The page and the API share the `_view` cache, so the dashboard's own fetch is a cache hit. `tests/conftest.py`
  `make_client` must call `main._base.cache_clear()` and `main._view.cache_clear()` (the ticket that adds them).
- `/api/datasets/{id}/profile` keeps calling `classify` and writing the JSON (AC-2); it may use `_base(d)[1]`.

## Round 4: filters (`app/filters.py`)
Query parameters (the same on `/datasets/{id}`, `/api/datasets/{id}/charts`, `export.xlsx`, `export.pptx`):

| Param | Meaning | Ignored when |
|---|---|---|
| `f.<column>=<value>` | rows where `str(cell) == value` in that column (the same `str()` key bars and donuts use) | column is not categorical in the mapping (so >50-distinct columns never filter, gate 175), value empty |
| `from=YYYY-MM-DD` | rows whose first temporal column is on or after that day (`_time(cell).date() >= from`) | no temporal column, not a valid `date.fromisoformat` |
| `to=YYYY-MM-DD` | on or before that day, inclusive | same |

- One value per column (gate 175): a repeated `f.region` keeps the last (`query_params[key]`). Filters on
  different columns and the date range combine with AND. A row with an empty or unparseable time is dropped as
  soon as `from` or `to` is set. A value not among the options is still applied (a stale shared link shows 0 rows
  and its chip, which removes it).
- `parse(params, columns, mapping) -> tuple`: canonical `((name, value), ...)` pairs, categorical params in column
  order, then `from`, then `to`; value strings as given (dates re-printed ISO). Hashable for `_view`'s cache, and
  `urllib.parse.urlencode(f)` is the canonical query string.
- `apply(f, columns, mapping, typed) -> list[int] | None`: `None` for `f == ()`, else the kept row indexes.
- `labels(f, columns, mapping) -> [str]`: `region = North`, `date from 2024-01-01`, `date to 2024-03-31` (the
  temporal column's real name). Used by the chips, the PPTX title slide and the XLSX Summary sheet.
- `summary(labels) -> str`: `"Filters: " + "; ".join(labels)`, or `"Filters: none"` (gate 175 wording).
- `options(columns, rows, mapping) -> {column: [values]}`: every categorical column, `sorted` distinct
  non-empty `str(cell)` of the unfiltered rows (at most 50 each, AC-3).
- Chip remove link: `"?" + urlencode([p for p in f if p != chip])`, or the bare page path when nothing is left.

## Round 4: interest score (`app/score.py`, used inside `app/rules.py`)
Each rule computes its chart's score from the full data it has before stride sampling, and passes it to
`_chart(..., score=...)`. `charts()` rounds every score with `round(s, 2)`, cuts to `MAX_CHARTS` in rule order
(unchanged selection), then `sorted(found, key=lambda c: -c["score"])` (stable: ties keep the rule order 3D map,
country map, line, bar, donut, histogram, scatter, heatmap), then sets `id = chart-1..N` in that display order.
Every score helper returns a float in 0..1 and returns 0 for fewer than 2 usable values, constant values or any
undefined result (`StatisticsError`, `ZeroDivisionError`, overflow).

| kind | Score | Input (full, before sampling) |
|---|---|---|
| line | `abs(spearman(range(n), sums))`: Pearson of average ranks (ties share the mean rank) | the per-time sums sorted by time (`sums` dict in `_lines`), value column = that line's own column |
| bar, donut | Gini: x sorted ascending, `2 * sum(i * x_i) / (n * sum(x)) - (n + 1) / n`, i = 1..n | the category totals drawn; any negative total or `sum(x) == 0` gives 0 |
| scatter | `abs(pearson(xs, ys))` | all point pairs (not the sample) |
| histogram | `min(1, abs(g1) / 3)`, `g1 = m3 / m2 ** 1.5` with population moments (divide by n) | all values |
| heatmap | largest `abs(z[i][j])`, `i != j`, `None` skipped | the matrix the chart draws |
| map3d, country_map | `0.6` | 0 when the chart has fewer than 2 points / countries |

Hand-checked on `data_dir` sales.csv (date, region, amount; script in /tmp, ticket 428): line 0.89 (rho -0.886),
histogram 0.34 (g1 1.024), bar 0.23 (Gini of 16, 23, 7 = 0.2319), donut 0.22 (Gini of 3, 2, 1 = 0.2222).
So sales.csv now shows line, histogram, bar, donut (was line, bar, donut, histogram). `pearson` is
`statistics.correlation` clamped to [-1, 1] (as the heatmap does now); Python 3.11 has no `method="ranked"`, so
`spearman` ranks by hand. Scores add no network request and no dependency (stdlib only).

## Round 4: KPIs (`rules.kpis(columns, rows, typed, mapping)`)
`{"rows": len(rows), "columns": len(columns), "missing_pct": round(100 * empty / (rows * columns), 1) (0 when no
cells), "sums": [{"column": name, "sum": s}, ...]}` for the first 3 numerical columns. `empty` counts raw cells
that are `None` or `""`. A sum is over the typed non-`None` values, printed as an `int` when whole, else
`round(s, 2)`; an all-empty column sums to 0. Page labels: `Rows`, `Columns`, `Missing`, `<column> (sum)`; every
figure through the `num` filter (`Missing` as `0.0%`).

## Round 4: speed (AC-41)
Measured in this image (16 cores, Python 3.11) on a 200,000-row CSV like `big_sales_csv` (/tmp probe, ticket 428):
`catalog.load` 0.41 s; `profile.classify` **20.9 s**; `rules.charts` on raw rows 4.4 s, on typed rows 2.8 s;
casting to typed rows once 1.3 s; a region filter (1 of 4) 0.01 s; charts on those 50,000 typed rows 0.7-1.0 s,
of which the heatmap is 0.41 s because it computes `pearson` for both triangles. Levers, all required:
1. `_base` cache (types and typed rows once per dataset), so a filter request pays only filter + rules + KPIs.
2. Heatmap: compute each pair once (`j > i`) and mirror it; z is symmetric, the result is identical.
3. `profile._kind`: count each distinct string once (`collections.Counter(strs)`, then `_parses` per key times its
   count): same result, and the 20 s first load drops a lot (categorical and number columns repeat values).
The AC-41 test first requests the charts API without filters (warm-up: load, classify, typed rows), then times one
request with `f.region=North` (not cached yet) and asserts `< 1.0` s.

## Round 3 changes at a glance (built, kept)
| # | Change | Files | AC |
|---|---|---|---|
| L1 | Launcher picks the newest Python 3.11-3.13 (`py -3.13`, `-3.12`, `-3.11`, then `python` with a version check) | `Start-DataBoot.ps1` | AC-28, AC-30 |
| L2 | `$LASTEXITCODE` checked after venv creation and both pip installs; one `Fail` path: message, delete `.venv`, pause, `exit 1` | `Start-DataBoot.ps1` | AC-29 |
| X1 | Per-sheet isolation: a corrupt sheet XML no longer fails the whole workbook (gate 171: build it) | `app/xlsx.py` (reader half only) | AC-25, AC-31 |
| D1 | Test-only packages move to `requirements-dev.txt` (gate 171) | `requirements.txt`, `requirements-dev.txt`, `README.md` | W-5 |
| T1 | Launcher text tests and the corrupt-sheet test | `tests/test_launcher_files.py`, `tests/test_acceptance.py` | AC-28..AC-31 |

**Gate 171 overrides the PRD on AC-31.** The PRD (ticket 417) read "log AC-25 per-sheet isolation" as "write the
gap down"; the Board answered "BUILD per-sheet isolation this round". I reworded AC-31 in acceptance.json to the
built behaviour (other sheets list and open; the corrupt one shows as `book.xlsx - <sheet>`, `not a valid xlsx`)
and changed PRD S4/C2 to match. Ids are unchanged.

Done by the architect (ticket 418), so engineers need not redo it:
- `requirements.txt` holds only runtime pins (fastapi, jinja2, uvicorn, pyarrow, openpyxl, python-pptx,
  xlsxwriter); new `requirements-dev.txt` = `-r requirements.txt` + `httpx==0.28.1`, `pytest==9.1.1`. README
  says `pip install -r requirements-dev.txt`. Nothing under `app/` imports httpx or pytest (grep), and the
  Dockerfile, launcher and `wheels\` download keep using `requirements.txt`, so clients no longer get test tools.
  The orchestrator's verify step lives in /opt/prodagents (not in this repo); it must install
  `requirements-dev.txt` (open question for the Board; the image already has both today).
- `tests/conftest.write_xlsx` accepts a sheet given as `bytes` and writes it verbatim as that sheet's XML, so a
  test can build `{"Good": [...], "Bad": b"<<not xml", "Also": [...]}`.

## Round 3: launcher design (L1, L2)
DataBoot.bat runs `powershell` (Windows PowerShell 5.1), not pwsh. The venv branch of `Start-DataBoot.ps1`
becomes the shape below. Folder dialog, folder check, the `-Docker` branch, the `wheels` offline install and the
final `.venv\Scripts\python.exe -m app.launch $Folder` stay as they are.

```powershell
function Fail($Message) {
    Write-Host $Message
    if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
    Read-Host "Press Enter to close" | Out-Null
    exit 1
}

# Newest Python 3.11-3.13 first; 3.14 is rejected until every pinned dependency ships wheels for it (gate 171).
$Candidates = @(@("py", "-3.13"), @("py", "-3.12"), @("py", "-3.11"), @("python"))
$Check = "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)"
```
- **Search** (AC-28): for each candidate, skip it if `Get-Command $c[0]` finds nothing; run
  `$rest = @($c | Select-Object -Skip 1); & $c[0] @rest -c $Check` with output to `$null`; the first with `$LASTEXITCODE -eq 0` is used for
  `-m venv .venv`. The version check runs for the `py` candidates too (one loop, and a broken `py` entry
  is skipped rather than trusted). None found: `Fail "DataBoot needs Python 3.12. Install it with: winget
  install -e --id Python.Python.3.12"` (exact text, gate 171).
- **Checks** (AC-29): after `-m venv .venv`: `if ($LASTEXITCODE -ne 0) { Fail "Could not create the Python
  environment (.venv)." }`; after the wheels pip install: `Fail "Could not install the packages from wheels."`;
  after the online pip install: `Fail "Could not install the packages (pip install -r requirements.txt)."`.
  Each message names its step. `exit 1` inside a function ends the script.
- **PowerShell 5.1 pitfall**: with `$ErrorActionPreference = "Stop"`, redirecting a native command's stderr
  (`2>$null`, `*>$null`) turns its first stderr line into a terminating NativeCommandError in 5.1. `py -3.13`
  prints "No suitable Python runtime found" to stderr when 3.13 is missing, so the probe would throw instead of
  moving on. Run the probe with `$ErrorActionPreference = "Continue"` set locally (inside a small function or a
  `try/finally` that restores it), or wrap the probe in `try { ... } catch { }`. Same for `Get-Command`: use
  `-ErrorAction SilentlyContinue`. There is no PowerShell in the image, so this cannot be run here; the
  engineer writes it carefully and the Board runs it on Windows.
- The venv is created with the same `$c[0] @rest -m venv .venv`. Keep the version list in one place
  (`$Candidates`) so AC-30's test can read it; do not leave a literal `py -3.11 -m venv` line.

## Round 3: per-sheet isolation design (X1)
Root cause, probed in /tmp (ticket 418): openpyxl 3.1.5 `load_workbook(read_only=True)` builds a
`ReadOnlyWorksheet` per sheet, and its `__init__` calls `_get_size()`, which parses the sheet XML until it meets
`<dimension>`. A sheet with no `<dimension>` (every `conftest.write_xlsx` workbook) or a sheet that is not XML is
parsed at load time, so one bad sheet makes `load_workbook` raise and `sheet_names` returns `not a valid xlsx`
for the whole file. (An xlsxwriter workbook truncated after its `<dimension>` already isolates today.)

Fix in `app/xlsx.py` only; `catalog.scan` already catches per sheet and builds `Unreadable(rel, reason, sheet)`
(catalog.py L95-99), so no catalog, template or route change:
- `_load(path, keep=None)`: copy the zip into a `BytesIO`, writing every worksheet part
  (`xl/worksheets/*.xml`, not `_rels`) as an empty sheet
  `<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>`, except
  the part named `keep`; then `load_workbook(copy, read_only=True, data_only=True)`. Styles, shared strings and
  workbook.xml are copied as they are, so dates and sheet order are unchanged. Not a zip / no workbook part /
  any open error: `ReadError("not a valid xlsx")` as today.
- `sheet_names(path)`: `_load(path)` (all blanked), so the list never parses a sheet; returns
  `book.sheetnames`; empty list still raises `not a valid xlsx`.
- `read_sheet(path, sheet)`: find the part of `sheet` (`book[sheet]._worksheet_path` on the all-blanked load,
  e.g. `xl/worksheets/sheet2.xml`), then `_load(path, keep=part)` and read as today. A parse error of that one
  sheet raises `not a valid xlsx`, which scan records with the sheet name.
- `path` may be a path or `BytesIO` (tests pass both); seek a `BytesIO` back to 0 before each copy.
- The /tmp probe gave, for `{"Good": [[a, d], [1, date]], "Bad": <truncated or b"<<x">, "Also": [...]}`:
  names `Good, Bad, Also`; Good and Also rows read (date as `datetime`); Bad raised `ParseError`.
- `_worksheet_path` is a private openpyxl attribute; openpyxl is pinned at 3.1.5 and the tests catch a change.
  Mark it with a `ponytail:` comment, and one for the copy cost: each sheet read rewrites the zip in memory
  (uncompressed `ZIP_STORED` is fine), so a workbook with N sheets is copied N + 1 times at scan.
- Known limit, not in scope: a sheet whose part is missing from the zip is dropped by openpyxl without an error,
  so it is neither listed nor in "Could not be read" (probe: names `Good, Also`).

## Round 2 changes (built, kept)
| # | Change | Files | AC |
|---|---|---|---|
| R1 | XLSX export on **xlsxwriter** | `app/xlsx.py` (writer half replaced) | AC-18, AC-23 |
| R2 | PPTX export on **python-pptx** | `app/export.py` (rewritten) | AC-18 |
| R3 | xlsx reading on **openpyxl** `read_only=True` | `app/xlsx.py` (reader half replaced) | AC-1, AC-12 |
| R4 | Parquet on **pyarrow only**, no stdlib fallback (gate 162) | `app/parquet.py` | AC-14, AC-20 |
| R5 | Table titles are `<caption><h2>…</h2></caption>`; headers keep their case | `home.html`, `dataset.html`, `databoot.css` | AC-22 |
| R6 | Plotly modebar always shown, buttons in Tab order | `dashboard.js`, `databoot.css` | AC-24 |
| R7 | Fixed notes `invalid JSON`, `not a valid parquet file`; `Unreadable.sheet` | `readers.py`, `parquet.py`, `catalog.py` | AC-12, AC-20 |
| R8 | Gate 162 chart items: country map sorted by value, map3d z title | `rules.py`, `dashboard.js` | AC-16 (W-3) |
| R9 | QA renames `test_G_1..7`, `test_G_thousands` to `test_AC_14..21` | `tests/test_acceptance.py` | all new ids |

Done by the architect (ticket 393): `xlsxwriter==3.3.0` added to requirements.txt; `.gitattributes` holds
`* text=auto` (every file in the index was already LF, `git ls-files --eol`, so nothing else renormalises);
`tests/fixtures/flat.csv` and `optional.csv` checked out to their committed bytes (gate 165); `test_G_7` now uses
a corrupt `.parquet` (gate 165) so the suite passes with pyarrow installed.

## Stack and constraints
- FastAPI + Jinja server-rendered pages; one vanilla JS module `app/static/js/dashboard.js` draws charts with
  Plotly. No framework, no build step.
- Python 3.11-3.13 (the image runs 3.11) plus pinned libraries in requirements.txt: fastapi, jinja2, uvicorn (httpx
  and pytest are in requirements-dev.txt since round 3), and for data
  formats **xlsxwriter==3.3.0, python-pptx==1.0.2, openpyxl==3.1.5, pyarrow==26.0.0** (gates 162/164/165). All
  four import in the agent image (`python3 -c "import xlsxwriter, pptx, openpyxl, pyarrow"` gave 3.3.0 / 1.0.2 /
  3.1.5 / 26.0.0). None is vendored: nothing under `app/` or the repo root may contain their sources (AC-23).
  python-pptx itself requires XlsxWriter (it writes the embedded chart workbooks with it), so the pins agree.
- Round 1's "standard library only" rule is gone. No pandas: our readers already give `(columns, rows)` lists.
- Vendored front-end assets (MIT, unchanged): `app/static/vendor/plotly/plotly.min.js` (4.1.2) and
  `app/static/vendor/topojson/world_110m.json`, `world_50m.json` (sane-topojson 4.0.0). These are static
  browser files, not Python libraries; AC-23 is about the four Python libraries.
- Every `Plotly.newPlot` passes config `{topojsonURL: "/static/vendor/topojson/", displaylogo: false,
  responsive: true, displayModeBar: true}` (was `"hover"`, AC-24). No request leaves the machine (AC-9).

## Modules
Round 3 touches only `app/xlsx.py` (reader: `_load(path, keep=None)`, X1) and `Start-DataBoot.ps1` (L1, L2);
the "Round 2" column below is what round 2 changed.

| File | Owns | Round 2 |
|---|---|---|
| `app/config.py` | `get() -> Settings` from env: `DATABOOT_DATA`, `DATABOOT_OUT`, `DATABOOT_MAX_ROWS` (200,000), `DATABOOT_MAP_CAP` (50,000), `DATABOOT_CHART_CAP` (5,000) | unchanged |
| `app/catalog.py` | `scan(folder) -> Catalog` (datasets, unreadable, others), stable ids, `load(dataset, max_rows)` | `Unreadable` gains `sheet: str \| None = None` |
| `app/readers.py` | csv, tsv, json, jsonl, geojson readers; `ReadError` and the fixed notes | `INVALID_JSON = "invalid JSON"` |
| `app/xlsx.py` | `sheet_names(path)`, `read_sheet(path, sheet)` on openpyxl; `write(dataset, rows, charts) -> bytes` on xlsxwriter | both halves replaced; hand-written OOXML deleted |
| `app/parquet.py` | `read(path) -> (columns, rows)` on pyarrow | stdlib reader, thrift and snappy code deleted |
| `app/profile.py` | `classify(columns, rows) -> {column: type}` | unchanged |
| `app/rules.py` | `charts(columns, rows, mapping, settings) -> [chart]`, sampling | country map order; map3d `z_label` |
| `app/export.py` | `pptx(dataset, charts) -> bytes` on python-pptx | rewritten; no import from `app.xlsx` |
| `app/launch.py`, `DataBoot.bat`, `Start-DataBoot.ps1`, `Dockerfile` | launcher | unchanged |
| `app/main.py` | routes, `num` filter, `_charts`, `_download` | unchanged |
| `app/templates/home.html`, `dataset.html` | pages | h2 inside each caption |
| `app/static/js/dashboard.js`, `app/static/css/databoot.css` | drawing, style | modebar; no uppercase `th` |

Round 4: new `app/filters.py` (`parse`, `apply`, `labels`, `summary`, `options`) and `app/score.py`
(`spearman`, `pearson`, `gini`, `skew`, each giving the 0..1 score); `app/rules.py` gains `typed`, `kpis`, a
`score` per chart and the sort; `app/main.py` replaces `_charts` with `_base` and `_view`; `xlsx.write` and
`export.pptx` gain a `summary` argument; `profile._kind` counts distinct strings once; `dataset.html`,
`databoot.css`, `dashboard.js` as in "Pages". Readers, catalog, launcher and config are unchanged.

Round 5: new `app/apps.py` (rule table, roles, `detect`, `measures`), `app/business.py` (`view`, `export`) and
`app/geo.py` (`view`, `export`), created empty by the architect; `app/main.py` gains `_detected`, `_shown`,
`_appview` and the `/app` route; `app/rules.py` donut 2-5 only; `xlsx.write`/`export.pptx` gain `title` and the
`table` kind; templates split per app; `dashboard.js` fetches `/app`, adds `map2d`, value labels, drill, table
toggle, 3D toggle. `profile`, `filters`, `score`, readers, catalog, launcher and config are unchanged.

Round 6: new `app/monitoring.py` (`view`, `export`) and `app/survey.py` (`SCALES`, `scale`, `pick`, `view`,
`export`), created empty by the architect; `app/apps.py` gains the R5/R4 rows, `L`/`cols` roles, `plain`, `sep`,
`plural`; `app/main.py` gains `_plain`, `_pick`, the `pick` cache key, `pickq` links and two `TITLES`; `geo.view`
takes `plain`; `export.pptx` title slide; templates `app_monitoring.html`, `app_survey.html`, `_figure.html`
(`score` flag, `plural`), `_tables.html` (`plain`); `dashboard.js` gains `monitor`, `likert`, `crosstab` builders,
`clickable`, plain axes, hex text, and loses the trends `tozero` and its `sep` regex. Readers, catalog, profile,
filters, score, xlsx, launcher and config are unchanged.

Round 7: new `app/upload.py` (`begin`, `write`, `finish`, `cleanup`, `empty`, `safe`, `cap_message`, `OWNED`;
created empty by the architect); `app/config.py` gains `upload_cap` (`DATABOOT_UPLOAD_CAP`, 2 GiB; done);
`app/main.py` gains the lifespan, the three upload routes, `/scan`, `_summary`, and `tabs`/`summary` in the page
context; `app/launch.py` folder optional; templates `scan.html`, `_tile.html` (new), every `app_*.html`,
`_figure.html`, `dataset.html`, `base.html`, `home.html`; JS `intake.js`, `scan.js`, `tiles.js` (new) and
`dashboard.js` (`keyboardMarks`, `apply`, no `dark` listener). Readers, catalog, profile, rules, apps, business,
geo, monitoring, survey, filters, score, xlsx and export are unchanged.

## Routes (sitemap: two pages, no nav beyond a "DataBoot" home link; unchanged)
| Method, path | Returns |
|---|---|
| GET `/` | Home: datasets table, "Could not be read" table, "Other files" table |
| GET `/datasets/{id}` | Dashboard page; 404 for unknown id; round 4: filter query params (see "Round 4: filters"); round 5 `app`; round 6 `period` (Monitoring), `row`/`col` (Survey cross-tab), also on `/app` and both exports |
| GET `/api/datasets` | `[{"id","path","sheet","kind","rows","columns"}]` (columns = count) |
| GET `/api/datasets/{id}/profile` | `{column: type}` (AC-2), also writes `<out>/profiles/{id}.json` |
| GET `/api/datasets/{id}/charts` | chart contract below (Explorer charts; unchanged in round 5) |
| GET `/api/datasets/{id}/app` | round 5: detection + the shown app's figures ("Round 5: page and JSON contract"); fetched once by dashboard.js on load with the page's query string (no polling) |
| GET `/datasets/{id}/export.pptx` | PPTX download (same filter params) |
| GET `/datasets/{id}/export.xlsx` | XLSX download (same filter params) |
| GET `/health` | `{"ok": true}` |
| `/static/...` | StaticFiles mount |

No page or route is added in round 4 (only query params), so no sitemap or NAV change. Round 5 adds the `app`
query param on the page and both exports, and the `/app` JSON route; still two pages, no NAV change. Round 6 adds
only query params (`period`, `row`, `col`); no route, no NAV change.

## Data access
- `scan(folder)`: `os.walk` (no symlink follow), skip names starting with `.`; sorted by relative path. Missing
  folder: empty catalog. Kind by lower-case extension: `.csv` csv, `.tsv`/`.tab` tsv, `.xlsx`/`.xlsm` xlsx (one
  dataset per sheet, each sheet loaded once at scan, gate 162), `.json` json, `.jsonl`/`.ndjson` jsonl,
  `.parquet` parquet, `.geojson` geojson. Anything else, `.xls` included, goes to `others` (type = extension,
  size in bytes, modified date YYYY-MM-DD).
- Any reader exception is caught per file (per sheet for xlsx) in `scan` and becomes
  `Unreadable(path, reason, sheet=None)`. `sheet` is the sheet name when one sheet of a workbook fails, else
  `None` (gate 162). The home table shows `path` and, when set, ` - sheet` after it. **Fixed reasons** (the
  only texts allowed in the reason cell):

  | Reason | When |
  |---|---|
  | `empty file` | size 0 (any kind) |
  | `no header row` | csv/tsv/xlsx sheet with no non-empty row |
  | `could not decode text` | csv/tsv not utf-8-sig and not cp1252 |
  | `invalid JSON` | `json.JSONDecodeError` in .json, .jsonl (any line) and .geojson |
  | `not a list of records` | valid JSON of the wrong shape (`{"a": 1}`, `[1, 2]`, geojson `[]`) |
  | `not a valid xlsx` | openpyxl cannot open the file or parse a sheet; workbook with no worksheets |
  | `not a valid parquet file` | **new**: any pyarrow error opening or reading the file (bad magic, bad footer, truncated) |
  | `unsupported parquet encoding` | pyarrow read it but a column is nested (struct, list, map: `field.type.num_fields > 0`) |
  | `could not read file` | any other exception (`catalog.FAILED`) |
- Dataset id: `hashlib.sha1(f"{path}|{sheet or ''}".encode()).hexdigest()[:12]`, stable across restarts.
- Rows read on demand by `load(dataset, settings.max_rows)` (`lru_cache(maxsize=4)`); `scan` is
  `lru_cache(maxsize=1)`; `make_client` clears both.
- Readers return cells as Python values: `None` for empty, `str`, `int`, `float`, `datetime`/`date`.
  - csv/tsv/json/jsonl/geojson: unchanged from round 1 (`csv` module, `utf-8-sig` then `cp1252`; JSON records,
    keys in first-seen order, nested values as `json.dumps`; geojson one row per feature plus `longitude`,
    `latitude`).
  - **xlsx (openpyxl)**: `wb = openpyxl.load_workbook(path, read_only=True, data_only=True)`; always
    `wb.close()` in `finally` (read-only keeps the file open). `sheet_names` = titles of `wb.worksheets` that
    have `iter_rows` (chartsheets are skipped). `read_sheet`: `ws.reset_dimensions()` first (some writers store
    a wrong `<dimension>`, which read-only mode trusts), then `ws.iter_rows(values_only=True)`. Cell mapping:
    `bool` -> `"TRUE"`/`"FALSE"` (as round 1, so booleans stay categorical), `datetime`/`date` kept, `time` ->
    `v.isoformat()`, `str` `""` -> `None`, numbers kept (openpyxl gives `int` for whole numbers). Rows with no
    non-`None` cell are dropped; the first kept row is the header; rows are padded or cut to its width.
    `path` may be a path or a `BytesIO` (tests pass `io.BytesIO`). Any exception other than `ReadError` ->
    `ReadError("not a valid xlsx")` (openpyxl raises `BadZipFile`, `InvalidFileException`, `KeyError`,
    `IndexError`, XML parse errors). Formula cells give their cached value (`data_only=True`).
    A probe in /tmp showed openpyxl gives the round 1 values for dd/mm/yyyy and numFmt 22 dates, a `0.00"d"`
    format staying a number, rich text joined, and booleans (as `True`/`False`, hence the mapping).
  - **parquet (pyarrow)**: `size == 0` -> `empty file`; `table = pyarrow.parquet.read_table(path)`, any
    exception -> `not a valid parquet file`; nested field -> `unsupported parquet encoding`; else
    `columns = _names(table.column_names)`, rows = `zip(*[c.to_pylist() for c in table.columns])` as lists.
    Every codec pyarrow supports is read (ZSTD, LZ4, BROTLI too), so `zstd.parquet` becomes a dataset (40x6).
    INT96 and TIMESTAMP give `datetime`, DATE gives `date`, as round 1.
- Header cleanup (`readers._names`): strip; empty header -> `column_N` (1-based); duplicates get `_2`, `_3`.
- Output folder `<out>` (default `./output`, git-ignored). The data folder is never written to.

## Classification (AC-3, unchanged)
Per column, over non-empty values of the loaded rows, first match wins:
1. **geospatial**: header lower-cased and stripped is `lat`, `lon`, `lng`, `latitude` or `longitude`.
2. **temporal**: every value is `date`/`datetime`; or ≥ 90% of `str` values parse with
   `datetime.fromisoformat` or `%d/%m/%Y`, `%m/%d/%Y`, `%Y/%m/%d`, `%d-%m-%Y`, `%d.%m.%Y`. A bare year stays numerical.
3. **numerical**: every value is `int`/`float` (not `bool`), or a numeric-looking `str`.
4. **categorical**: text with distinct count ≤ 50 and ≤ 50% of loaded rows (booleans included).
5. **other**: everything else, including all-empty columns.

## Routing rules (charts)
Built by `rules.charts` in this order, then cut to the first 8 (`MAX_CHARTS`):
| kind | When | Data |
|---|---|---|
| `map3d` | a lat and a lon geospatial column | x lon, y lat, z first numerical (else 0); rows with an empty lat or lon are not counted (`total`); stride-sampled to `map_cap` |
| `country_map` | a categorical/other column named `country`, `country_name`, `nation`, `iso3`, `iso_a3` | sum of first numerical per country (count if none), **sorted by value desc, then name** (gate 162, like bars); `locationmode` `ISO-3` when all values are 3 upper-case letters, else `country names` |
| `line` | temporal + numerical; first 2 numerical | sum per distinct timestamp, sorted, stride-sampled to `chart_cap` |
| `bar` | categorical; first 2 numerical, or 1 count chart | sum (or count) per value, sorted by value desc |
| `donut` | first categorical with 2 to 5 distinct values (round 5, gate 179; was 6) | row count per value |
| `histogram` | first numerical | 20 equal-width bins over min..max (max in the last bin); **min = max gives 1 bin** with edges `[min, max]` |
| `scatter` | 2+ numerical | first two numerical, rows with both values, stride-sampled to `chart_cap` |
| `heatmap` | 3+ numerical | Pearson r of the first 12 numerical, pairwise complete rows; `null` when undefined |

No rule matches -> `[]` (AC-7). Stride sampling: `step = ceil(n / cap)`, keep `points[::step]`, so shown ≤ cap.
`# ponytail: stride can miss peaks; use LTTB if owners ask.`

## Chart contract (`GET /api/datasets/{id}/charts[?f.<column>=v&from=YYYY-MM-DD&to=YYYY-MM-DD]`)
```json
{"dataset": "3f2a9c01b7de",
 "filters": ["region = North"],
 "kpis": {"rows": 3, "columns": 3, "missing_pct": 0.0, "sums": [{"column": "amount", "sum": 16}]},
 "charts": [
  {"id": "chart-1", "kind": "line", "title": "amount by date",
   "x_label": "date", "y_label": "amount (sum)",
   "rule": "temporal date + numerical amount: line, sum per date",
   "shown": 3, "total": 3, "score": 1.0,
   "data": {"x": ["2024-01-01", "..."], "y": [10, "..."]}}]}
```
**Round 4 additions**: `filters` (the labels, `[]` when none), `kpis` (see "Round 4: KPIs"), and `score` (float,
2 decimals) on every chart; `charts` is in score order and `id` follows that order. `rule` is unchanged (the page
appends the score). For `bar` and `donut`, `x_label` is the categorical column's name: dashboard.js uses it as
the cross-filter column. The page reads nothing from `filters`/`kpis` in JS (both are server-rendered); they are
there for tests and for the AC-37 "API matches the page" check.
`data` per kind: line/scatter `{"x": [], "y": []}`; bar `{"x": [categories], "y": [values]}`;
donut `{"labels": [], "values": []}`; histogram `{"edges": [n+1 floats], "counts": [n ints]}`;
heatmap `{"labels": [], "z": [[r or null]]}`; map3d `{"lon": [], "lat": [], "z": []}`;
country_map `{"locations": [], "values": [], "locationmode": "ISO-3" | "country names"}`.
**Round 2 addition**: a map3d chart also has `"z_label"`: the z column name, or `null` when z is the constant 0.
dashboard.js uses it as the scene z axis title and the colorbar title (gate 162). It is a new key on map3d only;
no test compares whole chart dicts (QA: grep for dict equality before relying on this).
Dates are ISO strings; `NaN`/`inf` become `null`. `shown`/`total` count points (map3d, line, scatter) or rows
(the other kinds). The same dicts feed the page, the JSON and both exports.

## Pages
- **Home** `/`: h1 `DataBoot`, the folder path, then three tables. Each table:
  `<table><caption><h2>Datasets</h2></caption>…`, likewise `Could not be read`, `Other files`. Empty tables are hidden.
- **Dashboard** `/datasets/{id}`: h1 file name (+ sheet); `<caption><h2>Columns</h2></caption>` table; one
  `<figure class="chart" id="chart-N" data-kind="...">` per chart with `<figcaption>` (title, `.chart-rule`,
  `.chart-count` "N of M points|rows"); `<caption><h2>First 20 rows</h2></caption>` table (the number is
  `rows|length|num`); links to both exports.
- **h2 inside caption (AC-22, gate 165)**: the `<caption>` stays, so the table keeps its accessible name; the h2
  puts it in the heading outline. CSS resets the h2 inside a caption to the caption's current look (font size,
  margin 0); the Designer owns the exact style. Headings: h1 page title, h2 table titles; figures keep their
  figcaption title (not a heading), so the outline is h1 > h2 with no skipped level.
- **Header case (AC-22)**: delete `text-transform: uppercase` (and the letter-spacing that goes with it) from the
  `th` rule in `databoot.css` (L89). Templates already print the names as read.
- **Modebar (AC-24)**: `displayModeBar: true`. Plotly's modebar is `opacity: 0` until hover in its own CSS; add
  `.js-plotly-plot .plotly .modebar { opacity: 1; }` to `databoot.css`. The buttons are `<a class="modebar-btn">`
  elements without `href`, so they are not focusable: after each `Plotly.newPlot(...)` resolves (and after each
  redraw on theme or breakpoint change), set `tabindex="0"` and `role="button"` on every `.modebar-btn` in that
  figure, copy `data-title` into `aria-label`, and on `keydown` Enter or Space call `btn.click()` and
  `preventDefault()`. The existing `.modebar-btn:focus-visible` ring (databoot.css L57) then shows.
- **Round 4 dashboard order** (top to bottom): crumb, page head (h1, export links), KPI strip, filter form,
  chips + Clear filters, charts grid, Columns table, First rows table (AC-34: the First rows table stays last;
  no score, no caption, gate 175). All of it is server-rendered from `_view`; a filter change is a normal GET
  navigation to the new URL, so every chart, count, KPI, chip and control comes from the server and the browser's
  Back button restores the previous filter state with no `pushState` code (AC-38).
  - **KPI strip**: `<dl class="kpis">` with one `<div><dt>Rows</dt><dd>3</dd></div>` per figure. No `<p>`:
    test_AC_17 rejects any `<p>` in main except the folder path.
  - **Filter form**: `<form class="filters" method="get" action="/datasets/{id}">`; one `<label>` + `<select
    name="f.<column>">` per key of `options` (first option `All`, value `""`; the active value `selected`); when
    a temporal column exists, `<input type="date" name="from">` and `name="to"` labelled `<column> from` /
    `<column> to`, preset from `f`; a submit button `Apply` (works with no JS). Only categorical columns get a
    dropdown (gate 175: >50 distinct values is not categorical).
  - **Chips**: `<ul class="chips">`, one `<li><a href="{remove link}" aria-label="Remove filter region =
    North">region = North</a></li>` per label (the Designer adds the ×), then `<a class="btn" href="/datasets/{id}">
    Clear filters</a>`; the whole list only when a filter is active.
  - **Caption**: `<span class="chart-rule">{{ c.rule }} · score {{ "%.2f"|format(c.score) }}</span>` (AC-35;
    test_AC_17 still finds `c["rule"]` in the figure and one `.chart-rule`).
  - **Grid (AC-34)**: `.charts > .chart:first-child { grid-column: 1 / -1 }`; the round 2 rule that makes
    map3d, country_map and heatmap span both columns is removed, so the others sit two per row from 900px and one
    per row below (the existing breakpoints; phone = the 599px narrow breakpoint, gate 175). The Designer owns
    the look.
  - **Export links** carry the canonical query: `href="/datasets/{id}/export.pptx{{ qs }}"`, `qs` = `"?" +
    urlencode(f)` or `""`.
- **Round 4 dashboard.js** (J1):
  - fetch `"/api/datasets/" + id + "/charts" + location.search` (same params, so the same cached `_view`).
  - Form tidy-up: on `change` of a select or date input, submit the form; on `submit`, set `disabled = true` on
    empty fields first so the URL holds only active filters (disabled fields are not sent).
  - Cross-filter (AC-39, C2): after `newPlot` of a `bar` or `donut`, `plot.on("plotly_click", ...)`: category =
    `pt.label` for donut, `pt.y` for a horizontal bar, else `pt.x`; key = `"f." + c.x_label`;
    `p = new URLSearchParams(location.search)`; if `p.get(key) === category` delete it (second click removes,
    gate 175) else `p.set(key, category)`; `location.assign(location.pathname + (p.toString() ? "?" + p : ""))`.
    `newPlot` replaces handlers on redraw (theme or breakpoint change), so attach after each draw.
- **Text rule (gate 160)**: only titles, axis labels, column names/types, `N of M` counts and the one-line rule
  caption. Fixed table headings and notes are labels.
- Style: plain, neutral, system sans, no logo, blank SVG favicon (gates 160, 165). The Designer owns the rest.

## Exports
Layout is unchanged from round 1 except the round 4 filter additions (AC-40):
- Both routes call `_view(d, f)` with the request's params: the Data sheet gets the filtered raw rows, every
  chart the filtered data, in score order (sheet `chart-1 …` = the top chart, as on the page).
- `xlsx.write(dataset, rows, charts, summary="Filters: none")`: after the chart sheets, a last sheet `Summary`
  with A1 = `summary`. Last, not second, so `Data` stays first (AC-18) and chart sheets keep `sheet2.xml…`.
- `export.pptx(dataset, charts, summary="Filters: none")`: the title slide gets a third text box with `summary`
  (14 pt) under the rows/columns line. The rows/columns line keeps the dataset size.
- main passes `filters.summary(view["labels"])`. Defaults keep direct calls in the unit tests working.

### XLSX: `app/xlsx.write(dataset, rows, charts) -> bytes` on xlsxwriter
- `xlsxwriter.Workbook(buf, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False,
  "strings_to_numbers": False, "nan_inf_to_errors": True, "default_date_format": "yyyy-mm-dd hh:mm:ss"})`.
  `strings_to_formulas: False` stops a cell like `=HYPERLINK(...)` from a data file becoming a live formula
  (CSV injection); `strings_to_urls: False` avoids Excel's hyperlink limit on big sheets.
- Sheet `Data`: header row = `dataset.columns`, then the loaded rows. Write each cell by type: `None` skipped,
  `bool` -> `write_boolean`, `datetime`/`date` -> `write_datetime` (default date format), `int`/`float` ->
  `write_number`, else `write_string` of `str(v)[:32767]` (Excel's cell limit).
- One sheet per chart, named `f"{chart['id']} {chart['kind']}"` (e.g. `chart-1 line`, ≤ 31 chars), with the
  chart's table at A1 (header row + data, the same `_table(c)` columns as round 1), and a native chart inserted
  at the cell right of the table:

  | kind | Table columns | xlsxwriter chart |
  |---|---|---|
  | line | x_label, y_label | `{"type": "line"}` |
  | bar, country_map | x_label, y_label | `{"type": "column"}` |
  | histogram | bin label `"a to b"` (each edge with 6 significant digits), count | `{"type": "column"}`, gap 0 |
  | donut | label, value | `{"type": "doughnut"}` |
  | scatter | x_label, y_label | `{"type": "scatter"}` |
  | map3d | lon label, lat label, `z` | `{"type": "scatter"}` of lon/lat (Office map charts need Bing, online) |
  | heatmap | `column`, then labels; r values | **no chart**; `conditional_format` `3_color_scale` on the r cells: min `#3B4CC0` (num -1), mid `#FFFFFF` (num 0), max `#B40426` (num 1) |
- Series ranges use the list form `[sheet, first_row, col, last_row, col]` so xlsxwriter quotes the sheet name
  (`'chart-1 line'!$A$2:$A$7`). Chart title = `title`; axis titles = `x_label`, `y_label`; value axis number
  format `#,##0` (thousands separators); legend off for single series. A chart with 0 rows gets its sheet and
  table but no chart (xlsxwriter needs at least one point).
- The workbook xlsxwriter writes has a proper `styles.xml`, so openpyxl opens it without the "Workbook contains
  no default style" warning (AC-23; the round 1 hand-written file caused it, seen in the ticket 393 test run).
- Filenames: `<file stem>[-<sheet>].xlsx`, `Content-Disposition: attachment` (unchanged, `main._download`).

### PPTX: `app/export.pptx(dataset, charts) -> bytes` on python-pptx
- `prs = Presentation()`; `prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)` (16:9; the default
  template is 4:3, 9144000 wide). Every slide uses `prs.slide_layouts[6]` ("Blank", checked) and text boxes,
  so slide text is exactly what we put there.
- Slide 1: text boxes with the display name (`path` file name + ` - sheet`) and `f"{rows:,} rows, {cols:,} columns"`.
- One slide per chart: title text box; then `slide.shapes.add_chart(type, x, y, cx, cy, data)`:
  line `XL_CHART_TYPE.LINE`, bar/country_map/histogram `COLUMN_CLUSTERED`, donut `DOUGHNUT` with
  `CategoryChartData` (categories = x or labels, `None` -> `""`; one series named y_label); scatter/map3d
  `XY_SCATTER` with `XyChartData` (points with a `None` coordinate skipped). python-pptx embeds a workbook with
  the chart data, so "Edit Data" works in PowerPoint (native, editable: AC-18). Axis titles = x_label/y_label,
  value axis `number_format = '#,##0'`, `number_format_is_linked = False`.
- Heatmap slide: `slide.shapes.add_table(n + 1, n + 1, …)` (native table), header row/column of labels, r
  cells as `f"{r:.2f}"` (empty for `null`) filled with the same blue-white-red scale (`_heat(r)` stays).
- Last text box on each chart slide: the rule caption, then `f"{shown:,} of {total:,} {points|rows}"`.
- XML-illegal control characters (`\x00-\x08\x0b\x0c\x0e-\x1f`) are removed from every string given to
  python-pptx (lxml raises on them); keep one `_clean_text` helper in export.py.
- Filenames: `<file stem>[-<sheet>].pptx` (unchanged).

## Launcher (AC-11, AC-13; venv branch changed in round 3, AC-28..AC-30)
`python -m app.launch <folder> [--port 8765] [--no-browser]`; `DataBoot.bat` calls `Start-DataBoot.ps1`
(venv by default; `-Docker` checks `docker info`, mounts `${Folder}:/data:ro`, runs the container, opens the
browser). The venv branch picks its Python and checks exit codes as in "Round 3: launcher design" above.
`Start-DataBoot.ps1` runs `pip install -r requirements.txt` (runtime pins only since round 3).
Dockerfile `python:3.11-slim` installs requirements.txt too. Offline client machines: the `wheels\` folder
(`pip download -r requirements.txt -d wheels` on a connected machine, Windows wheels) is used with `--no-index`.

## How each acceptance item is met
| AC | How | Test (QA, tests/test_acceptance.py) |
|---|---|---|
| AC-1 | `catalog.scan` walks subfolders; xlsx sheets via openpyxl (R3); home datasets table | `data_dir`: paths, `Revenue`/`Lookup` sheets, row and column counts |
| AC-2 | profile route returns `classify()` and writes `<out>/profiles/{id}.json` | JSON equals file content; keys = every column |
| AC-3 | `profile.classify` rules above | fixture: `Latitude`/`LON` geo, `date` temporal, `region` categorical, `comment` other |
| AC-4 | `line` rule; `figure[data-kind=line]`; Plotly draws it | sales.csv and book.xlsx Revenue; Playwright draw check |
| AC-5 | `bar` rule | sales.csv sums North 16, South 23, East 7 |
| AC-6 | `map3d` rule drawn as Plotly `scatter3d`; outlines from `/static/vendor/topojson/`; no off-host requests | points.tsv and cities.geojson have one, sales.csv none; Playwright: WebGL canvas, off-host requests aborted and counted 0 |
| AC-7 | `charts == []`, page 200 | notes.csv: types + table, no `<figure` |
| AC-8 | dashboard template | every dataset: Columns table and ≤ 20 rows |
| AC-9 | vendored Plotly + topojson; `topojsonURL` config | every `src`/`href` is local and 200; Playwright records no off-host request |
| AC-10 | stride sampling to `map_cap` | `big_csv`: `shown` ≤ 50,000, `total` 60,000, page shows `N of 60,000 points` |
| AC-11 | `app.launch.run` | injected `open_browser` gets `http://127.0.0.1:<port>/`, home 200 |
| AC-12 | per-file (per-sheet) try/except in `scan`; fixed reasons table | empty.csv `empty file`, broken.xlsx `not a valid xlsx`; others list and open |
| AC-13 | `Dockerfile`, `Start-DataBoot.ps1` | text checks: `docker info`, `:/data:ro`, `docker run`, `Start-Process`; no `Start-DataOS.ps1` |
| AC-14 | readers + pyarrow `parquet.read` (R4) | tsv/json/jsonl/geojson counts; **9** parquet fixtures (zstd now reads) at 40x6; profile and charts equal flat.csv |
| AC-15 | `others` list, home "Other files" table | manual.pdf `pdf 9 <date>`, old.xls `xls 2`; no `<a ` in that table; `.hidden.csv` absent |
| AC-16 | rules table above, 8-chart cap; round 5: donut only for 2 to 5 values (`rules._donut`) | donut, histogram, scatter, heatmap, country map values; many.csv ≤ 8 figures; a 5-value column gives a donut, a 6-value one none |
| AC-17 | figcaption has one `.chart-rule` and one `.chart-count`; round 6 F2 `plural` on M | per figure regex `[\d,]+ of [\d,]+ (points?\|rows?)` with the singular exactly when M is 1; no `<p>` in main except the folder path; a 1-row file shows `1 of 1 row` |
| AC-18 | xlsxwriter (R1) and python-pptx (R2) | openpyxl: first sheet `Data`, header = columns, `sum(len(ws._charts)) > 0`; python-pptx: `len(slides) == 1 + len(charts)`, some `shape.has_chart` |
| AC-19 | titles and h1 in templates | home `<title>DataBoot</title>`, dashboards `… - DataBoot`, no `DataOS` |
| AC-20 | pyarrow error -> `not a valid parquet file` (R4, R7) | corrupt `bad.parquet` (magic + zeros + footer length) in the "Could not be read" table with that reason; sales.csv still opens |
| AC-21 | `num` Jinja filter | big.csv `60,000`; `N of 60,000 points`; no unseparated 4+ digit number in main |
| AC-22 | `<caption><h2>` (R5); no `text-transform` on `th` | each of the 5 captions matches `<caption>\s*<h2>NAME</h2>\s*</caption>` (First rows: `First \d+ rows`); `databoot.css` has no `uppercase`; a mixed-case header (`Latitude`, `LON`) appears verbatim in `<th>` |
| AC-23 | requirements.txt pins; library writers | parse requirements.txt for the 4 exact pins; no file named `xlsxwriter`, `pptx`, `openpyxl`, `pyarrow` (dir or `.py`) under the repo outside `.venv`; `warnings.catch_warnings(record=True)` around `load_workbook` of an export: no message contains `no default style` |
| AC-24 | `displayModeBar: true`, modebar CSS opacity 1, focusable buttons (R6) | Playwright, no hover: first `.modebar` computed `opacity` is `1` and visible; pressing Tab from the page top reaches an element with class `modebar-btn` |
| AC-25 | per-sheet try/except in `scan` (round 2) plus X1 | existing `test_AC_25` (header-less `Lookup` sheet) stays; X1 adds the corrupt-XML case under AC-31 |
| AC-26 | `INVALID_JSON` note (round 2) | existing `test_AC_26` |
| AC-27 | `rules.py` country order, map3d `z_label` (round 2) | existing `test_AC_27` |
| AC-28 | L1: `$Candidates` = `py -3.13`, `py -3.12`, `py -3.11`, `python`; each must pass `$Check` (3.11 <= version <= 3.13) | text checks on `Start-DataBoot.ps1` (no PowerShell in the image): `"-3.13"`, `"-3.12"`, `"-3.11"` appear in that order inside the `$Candidates` line, then `"python"`; the script contains `(3, 11) <= sys.version_info[:2] <= (3, 13)`; `-m venv .venv` is called on the chosen candidate, not on a literal version |
| AC-29 | L2: `Fail` function; `$LASTEXITCODE -ne 0` check after venv and after each pip install; no-Python message | text checks: `function Fail` contains `Remove-Item -Recurse -Force .venv`, `Read-Host` and `exit 1`, in that order; the exact gate 171 message `DataBoot needs Python 3.12. Install it with: winget install -e --id Python.Python.3.12`; split the script at `-m venv .venv`, `--find-links wheels` and the online `pip install -r requirements.txt`: each piece after them holds `$LASTEXITCODE` before the next native command; every `Fail` call comes before the final `-m app.launch` line |
| AC-30 | L1 keeps all versions in one list | a test fails if `re.search(r"py -3\.1\d+ -m venv", ps1)` matches, or if `$Candidates` lacks any of 3.13/3.12/3.11 or holds them out of order (same parser as AC-28) |
| AC-31 | X1: `_load(path, keep)` blanks the other worksheet parts in an in-memory copy | `write_xlsx(data_dir / "book3.xlsx", {"Good": [("a","b"),(1,2)], "Bad": b"<<not xml", "Also": [("a","b"),(3,4)]})` and a second file whose `Bad` is a truncated sheet XML (e.g. `b'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>a'`): home "Could not be read" has `book3.xlsx - Bad` with `not a valid xlsx`; Good and Also are in `/api/datasets` and their pages and `/charts` return 200; `book3.xlsx` alone (no sheet) is not in the unreadable table |
| AC-32 | S1: `app/score.py` helpers called inside each rule on the full (filtered) data; `score` on every chart | `data_dir` sales.csv API: line 0.89, histogram 0.34, bar 0.23, donut 0.22 (hand values in "Round 4: interest score"); points.tsv map3d 0.6; unit tests of `score.gini([16, 23, 7])` ≈ 0.2319, `score.skew` of 10, 20, 5, 7, 3, 1 ≈ 0.3415, constant or 1-value inputs give 0, a scatter on y = 2x gives 1.0 |
| AC-33 | S2: round, cut to 8 in rule order, stable sort by `-score`, renumber ids | sales.csv kinds `["line", "histogram", "bar", "donut"]`, ids `chart-1..4`; a tie case keeps rule order (file `k\na\nb\na\nb\n`: bar and donut both score 0, so `["bar", "donut"]`); two requests give equal JSON; page `data-kind` order equals the API order |
| AC-34 | P1 grid CSS (`:first-child` spans `1 / -1`); First rows table after `.charts` in the template | Playwright at 1280 px: first figure width ≈ `.charts` width, figures 2 and 3 share a `top` and are each about half; at 390 px every figure is full width; in the HTML the `data-table` comes after the last `</figure>` |
| AC-35 | P1 caption `rule · score 0.NN`; round 6 F4: only `app_explorer.html` passes `score=true` | Explorer: per figure `.chart-rule` ends with `f" · score {c['score']:.2f}"` for the API chart at the same position; shop (Business), places (Map), monitor.csv, survey.csv default pages: no `.chart-rule` contains `score` |
| AC-36 | K1 `rules.kpis`; `<dl class="kpis">` | sales.csv: Rows 6, Columns 3, Missing 0.0%, amount (sum) 46; with `?f.region=North`: 3 and 16; `big_csv`: figures with separators (`60,000`) and test_AC_21 still green |
| AC-37 | F1 `filters.parse/apply/options`; form in the template | sales.csv page has `<select name="f.region">` with North/South/East and `type="date"` inputs `from`/`to`; notes.csv has no select; API with `f.region=North`: every `total` smaller than unfiltered, `kpis.rows == 3`; `from=2024-01-03&to=2024-01-05`: `kpis.rows == 3`; the page with the same params shows the same counts as the API |
| AC-38 | server-rendered filtered page; GET navigation; chips; Clear filters link | `/datasets/{id}?f.region=North`: `<option value="North" selected>`, chip `region = North`, KPI 3 rows; Playwright: pick South in the select, URL gains `f.region=South`, `page.go_back()` returns to the North URL and its KPI 3; click the chip's link, then `Clear filters`: URL has no `f.`, KPI 6 |
| AC-39 | J1 `plotly_click` on bar/donut; toggle | Playwright on sales.csv: `page.evaluate` emits a click via `document.getElementById(barId).querySelector('.plot').emit('plotly_click', {points: [{x: 'South', label: 'South', data: {}}]})` (Plotly's own handler path) or a real mouse click on the bar; URL has `f.region=South`, select shows South, KPI rows 2; same click again: no `f.region`, rows 6 |
| AC-40 | E1 `_view` in both export routes; Summary sheet last; title slide line | XLSX with `?f.region=North`: Data has 3 rows, first sheet `Data`, last `Summary` A1 `Filters: region = North`, bar sheet total 16; without params Summary A1 `Filters: none`; PPTX: slide 1 texts contain `Filters: region = North` / `Filters: none`, a chart's series values sum to the filtered total |
| AC-41 | D1 caches + heatmap pairs once + Counter in classify | `big_sales_csv`: GET charts (warm-up), then `time.perf_counter()` around GET charts `?f.region=North`: 200 and `< 1.0` s; `kpis.rows == 50000`; round 5: the same timing on `/app` (big_sales opens as Business) |
| AC-42 | `_base` once; round 5: `_view` no longer runs the Explorer rules, `_appview` runs only the shown app | existing test_AC_42; round 5 adds the cold `/datasets/{id}` (Business) and `/app` timing on `big_sales_csv`, and `big_csv` (Map, hexbin) `<= 5` s |
| AC-43 | A1 `apps.RULES`, `detect`, `_detected`; `/app` route | `archetypes_dir`: shop.csv `business`/`R2`, places.csv `map`/`R1`, measures.csv `explorer`/`R3`, sparse.csv not `map` (`explorer`/`R3`); `qualifies` of shop `["business", "explorer"]`, places `["map", "explorer"]`; two requests (and a request with filters) give equal `app`, `rule`, `qualifies` |
| AC-44 | A2 badge from `NAMES[app]` and `rule` | shop page has `App: Business (rule R2)`, measures `App: Explorer (rule R3)`, places `App: Map (rule R1)`, inside `class="app-badge"`; with `app=explorer` the badge still names the detected app |
| AC-45 | A2 View-as nav; `_shown` | shop page: `nav.view-as` links are exactly Business and Explorer, Business `aria-current`; measures page has no `view-as`; `?app=explorer` shows `data-kind="line"` from the Explorer rules and the KPI strip; `?app=map` on shop shows Business; Playwright: click Explorer, URL has `app=explorer`, reload keeps it |
| AC-46 | B1 cards, `apps.measures` | shop.csv `/app`: cards `[revenue, units]`; revenue latest 7392, previous 6192, pct 19.4, dir up; units 72, 60, 20.0; page shows `▲`, `+19.4%`, `up`, `7,392`; each card has an `<svg>` sparkline; a file whose dates all sit in one month (day grain over 2 days) or a previous sum of 0 shows `n/a` and no arrow |
| AC-47 | B1 trend per measure | shop.csv: 2 line charts (revenue, units), x = `2024-01-01`..`2024-06-01` (6 months, July left out), y equal to the month sums; no chart dict has `yaxis2`; grain boundaries by a unit test of the `business` grain helper (span in days: 60 days day, 61 week, 182 week, 183 month, 1096 month, 1097 year) |
| AC-48 | B1 leaderboard | shop.csv unfiltered: group column `channel` (2 bars, no Other); with `f.channel=web&f.store=North` the group is `product` (12 values): `p0` 800, `p11` 606, `p10` 600 … `p3` 206, then `Other` = 306 (`p2` 200 + `p1` 106); `orientation == "h"`; Playwright: every bar has a text label with separators (`fullLayout` text / `.bartext`) |
| AC-49 | B1 drill order and crumbs; J `crossFilter` on the leaderboard | `/app` drill order `channel`, `store`, `product` (2, 3, 12 distinct); Playwright on shop: click bar `web` -> URL `f.channel=web`, leaderboard `x_label == "store"`, crumb `All › channel: web`; click `North` -> `product`, `drill` false; clicking a product bar or `Other` does not navigate; click `All` -> no `f.`; `go_back()` returns to the previous level |
| AC-50 | B1 changes; template classes | shop.csv `changes` rows = leaderboard categories, `delta == latest - previous`; page cells print the sign (`+`/`-`), and computed `background-color` of a pos, a neg and a zero cell differ, zero equal to `--div-mid` |
| AC-51 | M1 map2d points; M2 70vh | places.csv: `map2d` trace is `scattergeo`, colour data = `pop`, colorbar title `pop`, colorscale two stops on `--seq`; Playwright at 1280x900 and 390x844: plot height / viewport height in 0.65..0.75; `topojsonURL` local |
| AC-52 | M1 hexbin | big_csv `/app`: `mode == "hex"`, `len(count) < 60000`, `sum(count) == 60000`; places.csv `mode == "points"` with 20 marks; Playwright: hover a cell shows `N points` with separators |
| AC-53 | M1 regions, rows; M2 panel, 3D toggle | places.csv: regions bar on `country`, x sums of `pop` per country descending; Playwright: click a point -> `.map-panel` shows its `country` and `pop` values; `3D view` -> `[data-kind=map3d]` visible with a WebGL canvas and the 2D figure hidden, press again -> back |
| AC-54 | G1 table toggle, hover, no second axis; round 6: `monitor`, `likert`, `crosstab` builders and `tableOf` cases | Playwright on shop (Business), places (Map), sales (`app=explorer`), monitor.csv and survey.csv (round 6): for every `.js-plotly-plot`, `Object.keys(gd._fullLayout)` has no `yaxis2` and no axis with `overlaying`; `hovermode !== false` and no trace `hoverinfo` in `none`/`skip`; each figure has one `.table-toggle`; clicking shows a `table.plot-table` whose row count equals the trace's point count, clicking again shows the plot |
| AC-55 | G1 separators; round 6 F1 exceptions by role | Business and Map pages: no unseparated 4+ digit number in `main` text (the AC-21 regex), nor in `.bartext`, tick labels or a hover label, except text of `plain` columns and date ticks; shop values `7,392`, places `20,000` |
| AC-56 | E2 `title`, `table` kind, `business.export`, `geo.export` | shop `export.xlsx?app=business`: sheets `Data`, `chart-1 table`, `chart-2 line`, `chart-3 line`, `chart-4 bar`, `chart-5 table`, `Summary`; Summary A1 `Business overview`, A2 `Filters: none`; PPTX slide 1 has `Business overview`, then table, line, line, bar (has_chart), table slides; places `?app=map`: `Map overview`, an XY scatter then a bar; sales.csv `?app=explorer` export equals the round 4 sheet list and Summary A1 `Filters: none` (Explorer unchanged) |
| AC-57 | Designer: DESIGN.md "Global chart rules" | text check: the section heading exists and lists each rule phrase in AC-57 |
| AC-58 | all assets local (AC-9); `/app` same origin | Playwright with `page.route("**/*")` counting non-`127.0.0.1` requests: open shop and places, drill, switch View-as, toggle 3D and a table: count 0; round 6 adds monitor.csv (pick each period, table toggle) and survey.csv (change the cross-tab, click a question bar) with the same count 0 (AC-9) |
| AC-59 | F1 `apps.plain`, `apps.sep`, `_plain`, `plain` axis key, geo rows formatted on the server | unit: `apps.plain` on orders.csv = {order_id, year}; names `yr_built`, `zip`, `phone_no`, `customer_code`, `ID` plain, `amount`, `paid` not; a `founded` column of 1990..2020 plain; orders.csv page (Explorer) First rows shows `10045`, `2024`, `12,345` and no `2,024`/`10,045`; Playwright: the order_id histogram hover and table view show `10045`-style text; a Map fixture with a `year` column: side panel shows `2024`; no page of round6_dir contains `2,024` |
| AC-60 | F2 `apps.plural`, `plural` filter, hex `text`, PPTX count | unit: `plural(1, "point") == "1 point"`, `plural(0, "point") == "0 points"`, `plural(1200, "row") == "1,200 rows"`; a 1-row CSV page shows `1 of 1 row`; a 5,001-point hex map with a 1-point cell hovers `1 point`; no page or PPTX text matches `\b1 (points\|rows)\b` |
| AC-61 | F3 `clickable(c)` + `barCursor` for Explorer bars; DESIGN.md (Designer) | Playwright on sales `app=explorer`: hover a bar -> the figure has class `bar-click` and the computed `cursor` of the drag layer is `pointer`; Business leaderboard same; DESIGN.md Cross-filter section text contains `Explorer` and `bar-click` (or "pointer") |
| AC-62 | F5 delete the trends `tozero`; bar builder keeps it; DESIGN.md (Designer) | Playwright: a Business file with month sums 14,000..16,000 (inline fixture): trend `_fullLayout.yaxis.range[0] > 0` and `rangemode` not `tozero`; the leaderboard `range[0] == 0`; monitor.csv main line `range[0] > 0`; DESIGN.md Global chart rules has "zero baseline" with "bars only" |
| AC-63 | F6 two boxes on slide 1 | python-pptx: slide 0 texts start `[title, file name]` for sales `app=explorer` (`Explorer`, `sales.csv`), shop `app=business` (`Business overview`, `shop.csv`), book.xlsx Revenue default (`Business overview`, `book.xlsx - Revenue`); font size of box 2 run < box 1 run |
| AC-64 | D2 rule order, `L`, amount guard | `/app`: monitor.csv and quiet.csv `monitoring`/`R4`, survey.csv `survey`/`R5` with `qualifies == ["survey", "business", "explorer"]`; badges `App: Monitoring (rule R4)`, `App: Survey (rule R5)`; every `data_dir`, `archetypes_dir`, `big_csv`, `big_sales_csv` dataset keeps its round 5 app/rule (shop.csv `business`/`R2`); inline: survey.csv without `submitted` still R5; 4 categoricals among 7 columns (57%) not R5; shop.csv with `revenue` removed (units 1..7 then counts as C: 4 of 5 columns) gives R5, which proves the guard |
| AC-65 | MO1 tiles; MO2 template | monitor.csv `/app` tiles (hand values in "Round 6: Monitoring app"): temperature 20.0 / 20.0 / 60.0, pct 5.1 up; humidity 0.0 no change; quiet.csv temperature -0.4 down; page shows `▲`, `+5.1%`, `up`, an `<svg>` per tile; `?period=all` every tile `n/a`, no arrow |
| AC-66 | P2 `_pick`, period links | monitor.csv page: 4 period links, `30 days` `aria-current`; `?period=7`: tile min/max and the main line `total` cover 7 points; reopening the URL keeps it; `?period=bad` shows 30; Playwright: click `90 days` -> URL has `period=90`, Back returns |
| AC-67 | MO1 main line; `monitor` builder | monitor.csv `/app` chart `monitor`: `spike == [index of 2024-04-10]`, `mean` at it 28.4286 and last 23.0 (2 decimals); quiet.csv `spike == []`; Playwright: one trace text `spike`, one y-axis, 2 line traces; quiet page has no `spike` text in the plot |
| AC-68 | SU1 question bars, Respondents; SU2 grid | survey.csv `/app`: bar counts as in the hand values (city Other 6); `orientation == "h"`; Playwright at 1280 px two question figures share a `top`, at 375 px one per row; `<h2>Respondents</h2>` with one histogram of `age` |
| AC-69 | SU1 `scale`, `likert` kind; JS `likert` builder | unit: `scale` of `["Agree", "neutral"]` is the agree scale, `[1, 3, 7]` the 1..7 scale, `["Never", "Often"]` frequency, `["yes", "no"]` None; survey.csv `likert` dicts levels in scale order, `sum(pct) == 100`; Playwright: neutral trace colour equals `--div-mid`, the first and last level colours differ in hue |
| AC-70 | SU1 cross-tab, `pick`; SU2 form | survey.csv `/app` crosstab gender x region counts and row % as hand values, each row of `pct` sums to 100 (1e-9); `?row=q_easy&col=gender` gives that pair; bad names fall back to the first two; Playwright: change the col select -> URL has `col=`, heatmap text shows `count (pct%)` with 1 decimal |
| AC-71 | MO1/SU1 `export`; `TITLES` | monitor.csv `export.xlsx?app=monitoring`: sheets `Data`, `chart-1 table`, `chart-2 line`, `Summary`; Summary A1 `Monitoring overview`; PPTX slide 1 `Monitoring overview`, a LINE chart slide; survey.csv `?app=survey`: 7 bar sheets (`has_chart`), a table, a histogram, `Summary` A1 `Survey overview` |
| AC-72 | round 5 grain (unchanged code) | QA inline files: daily sales over 100 days -> `grain == "week"`, trend x are Mondays, sums equal hand per-ISO-week sums, latest/previous cards match; monthly rows over 2020-01..2024-06 (> 1,096 days) -> `grain == "year"`, x `2020-01-01`..`2023-01-01` (2024 partial left out), sums per year |
| AC-73 | Explorer path of `_export` | measures.csv (Explorer only): XLSX sheets start `Data`, end `Summary`, Summary A1 `Filters: none` (no `overview`), a chart sheet with `ws._charts`; PPTX `len(slides) == 1 + len(/charts)`, each chart slide `has_chart` (or a table for a heatmap), slide 1's first line is `Data overview` (gate 187, ticket 480) |
| AC-74 | H7 `home.html` portal, `intake.js`; L7 | Server HTML of `/`: `<h1>DataBoot</h1>`, one portal element, `<input type="file" multiple>` (Choose files) and `<input type="file" webkitdirectory>` (Choose folder), each with a visible label; on `data_dir` the three captions follow the portal (index order) and `/` still has exactly one `<p` in main (test_pages:32); Playwright 1280 and 375: the portal box width == height and computed `border-radius` >= half its width; `set_input_files` on Choose files with 2 files ends on `/scan`; a synthetic `drop` event (DataTransfer with a File) uploads too |
| AC-75 | U1 routes, `upload.safe`; client path rule | `upload(client, …)` (conftest) for one file (`sales.csv`), two files, and `files_of(data_dir)`: `/api/datasets` rows (path, sheet, rows, columns) and each `/app` `app` equal a `make_client(data_dir)` run on the same files (ids equal too); unit: `safe("../x")`, `safe("/etc/x")`, `safe("C:/x")`, `safe("a//b")` are None, `safe("sub\\a.csv") == "sub/a.csv"`; a PUT with a path not declared -> 400; Playwright: `set_input_files` on Choose folder with a directory (Chromium sends `webkitRelativePath`) lists `sub/records.json` |
| AC-76 | U1 lifecycle, lifespan | `with TestClient(main.app) as c:` upload -> the folder `config.get().data` exists, is under `tempfile.gettempdir()`, not under the repo or the launcher folder; after the `with` it does not exist; a second upload deletes the first folder; `make_client(data_dir)` + upload + done: `data_dir` file list and bytes unchanged (`files_of` before == after); `launch.main([])` path: `upload.empty()` folder is in `OWNED` |
| AC-77 | U1 cap, `cap_message`; intake.js pre-check | `DATABOOT_UPLOAD_CAP=1000`: begin with sizes 600 + 600 -> 413, `detail` contains `1,000 bytes` and `-Folder`; begin that declares 10 bytes but PUTs 2,000 -> 413 and the batch folder is gone; the current data folder and `/api/datasets` are unchanged; unit `cap_message(3 * 2**30, 2 * 2**30)` contains `2 GB` and `-Folder`; Playwright with the small cap: the page shows the message in `[role=alert]` and sends no PUT (route log) |
| AC-78 | S7 `/scan`, `_summary`, `scan.js` | Upload `archetypes_dir` + `broken.xlsx`: `/scan` HTML has one `li` per dataset matching `^<path>(?: - <sheet>)?  [\d,]+ rows?  T\d+ N\d+ C\d+ G\d+  -> [A-Z]+ \(rule R\d\)$`, its APP == `/app` `app`.upper() and rule equal (shop.csv `-> BUSINESS (rule R2)`), a line `broken.xlsx  not a valid xlsx`, last line `0 bytes uploaded to the internet`; Playwright: `#open-workspace` visible at once, the second line is hidden at 0 ms and visible later, all lines visible by 2.5 s, then the URL is `/datasets/<first id>` |
| AC-79 | W7 tabs, archetype, grid | shop page: `nav.tabs` has one link per `/api/datasets` item and exactly one `aria-current="page"` (the shop link); `.archetype` text `APP: BUSINESS · RULE R2 · T1 N2 C3 · <rows> ROWS` built from `/app` and `/profile`; the badge `App: Business (rule R2)` and chips stay; Playwright 1280: `getComputedStyle(.grid).gridTemplateColumns` has 12 tracks; 375: no horizontal scroll |
| AC-80 | W7 `tile` macro on every app; golden JSON | For one dataset per app (sales `app=explorer`, shop, places, monitor, survey): every `figure.chart`, `ul.cards`, `ul.tiles`, `dl.kpis` and `table` has a `section.ws-tile` ancestor whose `aria-label` equals the text of an `h2` inside it (Playwright `get_by_role("region", name=…)` finds it); every tile has `.ws-move` and `.ws-expand`; `/app` and `/charts` of all 16 snapshot datasets equal `tests/fixtures/round6_api.json` |
| AC-81 | I7 drag, keyboard, order store | Playwright on survey: `drag_to` from tile 3's header to tile 1 -> `data-tile` order changes as specified; reload -> same order; another dataset (monitor) keeps its default order; focus `.ws-move` of tile 2, Alt+ArrowLeft -> it is first, `#ws-live` text contains `position 1 of`, focus still on that handle |
| AC-82 | I7 expand dialog, reopen | Playwright on sales `app=explorer`: click `.ws-expand` of `chart-3` (the bar) -> `dialog[open]` contains `#chart-3`, plot width > 0.8 × viewport; Esc -> no `dialog[open]`, tile back in the grid, `document.activeElement` is that `.ws-expand`; open again, click at the dialog's corner (backdrop) -> closed; open, click a bar -> URL has `f.region=`, a chip and the `N of M` count change, and after load `dialog[open]` holds `#chart-3` again |
| AC-83 | T7 tokens; D7 | CSS text: no `prefers-color-scheme`, no `@font-face`, `#050a12`, `#4de1ff`, `#ffb454` present; Playwright with `color_scheme="light"` and `"dark"`: `body` background `rgb(5, 10, 18)` both times; a tile label's computed `font-family` starts with the mono stack; contrast (WCAG formula in the test) of body text, tile titles, `.chart-rule`, `.chart-count`, table cells, chips and the archetype line against the backdrop computed from DESIGN.md's effective tile colour >= 4.5; AC-54/AC-62 checks still pass (one y-axis, bars from zero) |
| AC-84 | I7 glow; CSS entrance and media rules | Playwright: after load, `document.getAnimations()` on tiles: each `startTime + delay + duration <= 600`, then all `finished`; `mouse.move` over a tile changes its `--mx`; `emulate_media(reduced_motion="reduce")`: `getAnimations().length == 0` and `--mx` stays unset; CDP `Emulation.setEmulatedMedia` features `prefers-reduced-transparency: reduce` (Playwright has no option; probe in this ticket: Chromium 156 honours it) -> every element's computed `backdropFilter` is `none` |
| AC-85 | K7 `keyboardMarks`, `apply` | Playwright on sales `app=explorer` (bar and donut), shop (leaderboard), survey (question bar), places (top regions): Tab reaches a bar `path[tabindex="0"][role=button]`; its `:focus-visible` outline width > 0; Enter -> URL gains `f.<column>=<that category>`; Space on the same mark of the filtered page removes it; the Other bar and a `data-drill=false` leaderboard have no `tabindex` |
| AC-86 | all of the above, same origin | Playwright with `page.route("**/*")` logging hosts: open `/`, upload 2 files via Choose files, wait for the scan to open the workspace, drag a tile, expand and close it, toggle a table, expand a bar tile and click a bar: every request host is `127.0.0.1:<port>` (AC-9, AC-58 walk) |
| AC-87 | D7 (Designer) | Text check of DESIGN.md: a heading containing `round 7` (any case) whose section lists `#050a12`, `#4de1ff`, `#ffb454`, `mono`, `header`, `drag handle`, `expand`, `table toggle`, `12-column`, `0.6 s`, `reduced motion`, `reduced transparency` |

## Work items without AC ids: explicit checks
- **W-1 Unreadable.sheet (gate 162)**: a workbook where one sheet fails lists `book.xlsx - <sheet>` in "Could not
  be read" and the other sheets as datasets; `Unreadable("x.csv", "empty file").sheet is None`.
- **W-2 invalid JSON (gate 162)**: `{oops` in .json and a bad line in .jsonl give `invalid JSON`; `{"a": 1}` and
  `[1, 2]` keep `not a list of records`.
- **W-3 chart items (gate 162)**: records.json country map `locations` = `["Brazil", "Japan", "France"]` (203,
  125, 68); points.tsv map3d `z_label` is `"value"` and `null` for a lat/lon-only file.
- **W-4 line endings**: `git diff --stat tests/fixtures` empty; `.gitattributes` is exactly `* text=auto`.
- **W-5 dev requirements (gate 171, done in ticket 418)**: `requirements.txt` has no `pytest` and no `httpx`
  line; `requirements-dev.txt` starts with `-r requirements.txt` and pins `pytest==9.1.1`, `httpx==0.28.1`;
  README's install line names `requirements-dev.txt`. `test_AC_23` still finds the four library pins in
  requirements.txt. QA may add a text test for these lines.

- **W-6 hexagon text (M35, gate 180)**: "Round 5: Map app" says `hexagon choropleth cells` and no longer describes
  hexagon markers (`grep -n "choropleth cells" docs/ARCHITECTURE.md`). Done in ticket 463.
- **W-7 DESIGN.md (Designer, F3/F5)**: Cross-filter section names Explorer bars and the click cursor (AC-61);
  Global chart rules say the zero baseline is for bars only and lines keep the auto range (AC-62); the Monitoring
  and Survey layouts are described (tiles, period links, question grid, cross-tab, Respondents).

## Tests that must change with the code (name them in the tickets)
Round 6 (each edit goes in the ticket that changes the behaviour; grep before relying on line numbers):
- **F1**: `tests/conftest.py` `make_client` cache list gains `"_plain"`. `tests/test_geo.py` L32 rows stay
  (values < 1,000). `tests/test_map_page.py` tests that read the panel through the JS `sep` keep passing only if the
  server now sends `20,000` for `pop`: re-run `test_no_bare_four_digit_number_in_main_on_the_map_page`.
- **F2**: `tests/test_map_page.py` L81 (`"%{z:,}" in hovertemplate`) -> the hex trace has `text` and
  `"%{text}"`; L96 `label.split()[1] == "points"` holds for counts != 1. `tests/test_pages.py` L64/L82 and
  `tests/test_acceptance.py` L237, L393, L458, L912 keep `points`/`rows` (M > 1). test_AC_52 L1464 regex already
  allows `points?`.
- **F4**: `tests/test_pages.py` L66 and `tests/test_filter_ui.py::test_score_in_caption_matches_api` run with
  `app=explorer` already (check); any Business/Map page test that expects `· score` in a caption (grep `score` in
  test_business_page.py, test_map_page.py) flips to "no score".
- **F5**: a Business trend test asserting `rangemode == "tozero"` on `.trends` (grep `tozero`, `rangemode` in
  test_business_page.py, test_acceptance.py) flips; `tests/test_table_toggle.py` L56-62 (bar starts at 0) stays.
- **F6**: `tests/test_export_pptx.py` L64, L137, L149 slide 0 texts gain the title first: `["Explorer",
  "sales.csv", "Rows: 6, 3 columns", "Filters: none"]` etc.; `tests/test_export_apps.py` L31 (`[0] ==
  "sales.csv"` -> `[1]`), L47 (`[1]` Rows -> `[2]`), L89 (`"My title"` stays `[0]`); `tests/test_acceptance.py`
  L1055 (`texts(p.slides[0])` of AC-40: the Rows/Filters lines move one index), L1610, L1621 stay.
- **D2**: no round 5 fixture changes app (probe above); `tests/test_apps.py` tests that list `RULES` or `NAMES`
  exactly (grep `RULES`, `NAMES`) gain the new rows. `test_AC_43` qualifies lists stay.
- **MO/SU**: new test files only (`tests/test_monitoring.py`, `tests/test_survey.py`, their page tests).

Round 5 (each edit goes in the ticket that changes the behaviour):
- **A1/A2 ticket (default app switch)**: these fixtures change app: `sales.csv`, `sub/book.xlsx` Revenue, `staff.csv`
  and `big_sales_csv` become Business (R2); `points.tsv`, `sub/cities.geojson` and `big_csv` become Map (R1).
  `notes.csv`, `records.json`, `events.jsonl`, `num.csv`, many.csv stay Explorer. Every page request in the old tests
  that expects the Explorer layout passes `app=explorer`:
  - helpers: `tests/test_browser.py::dataset_path` and `tests/test_acceptance.py::_path` return the path with
    `?app=explorer`; callers that append a query (`test_filter_browser.py` L47 `+ "?f.region=South"`, and any
    `"?f."` concatenation, grep it) switch to `"&f..."`.
  - direct `client.get(f"/datasets/{…}")` in `test_acceptance.py` (L144, 157, 167, 174, 181, 191, 202, 236, 376,
    385, 431, 433, 456, 811, 888, 893-896), `test_pages.py` L43, L80, `test_filters.py` L78, `_page(live, …)` calls
    L486, 523, 581: add `?app=explorer` (a loop over all datasets may add it to every id: Explorer always qualifies).
  - test_AC_17 compares page figures with `/charts`; with `app=explorer` they are equal again. test_AC_38/39
    Playwright URLs keep `app=explorer` through `location.search`; assertions that the URL has no `f.` still hold,
    but any exact-URL equality must allow `app=explorer`.
  - `test_AC_42` and `tests/test_speed.py` time the default page: big_sales becomes Business. Keep them on the
    default (that is the AC-42 promise for Business) and re-time; report the number, do not loosen.
- **A1 ticket**: `_view` loses `"charts"`: no test reads it (grep `_view(` in tests: none).
- **G1 ticket (donut 2-5)**: `tests/test_rules_extra.py::test_donut_counts_and_limits` L25 `seven[:6]` -> `seven[:5]`
  with `[1] * 5`, and add `seven[:6]` gives no donut; `DESIGN.md` "Cross-filter" text "2 to 6 slices" and the
  palette line "Donut uses `--c1..--c6`" (Designer). Fixtures with 6 values: none found besides L25 (staff has 3
  departments, sales 3 regions, events 2 kinds); re-run test_rules_extra and test_AC_16.
- **G1 ticket (table toggle)**: every figure gains a `.table-toggle` button inside `<figcaption>`; test_AC_17 strips
  figcaptions before its `<p>` check and counts `chart-rule`/`chart-count` only, so it holds; a toggle label must
  not use those classes.
- **E2 ticket**: export routes use `_shown` (PRD S2: exports follow the shown app, and the page's export links
  carry `app` only when the URL had it), so a default `sales.csv` or `points.tsv` export becomes Business or Map.
  Route-level export tests that expect the round 4 sheets add `app=explorer` (`test_export_xlsx.py` L39 and every
  `export.xlsx`/`export.pptx` request in test_export_*, test_AC_18, test_AC_23, test_AC_40: grep them). Direct
  calls of `xlsx.write`/`export.pptx` in unit tests stay (the `title` default is `None`).

Round 4 (put each edit in the ticket that changes the behaviour; sales.csv order becomes line, histogram, bar,
donut; every XLSX gains a last `Summary` sheet):
- S1/S2 ticket: `tests/test_rules.py::test_sales_bar_and_line` L16 kinds order, L17 `line, bar = cs[:2]` (pick
  by kind), L22 the key set gains `"score"`. `test_export_xlsx.py::test_sales_download` L39 sheet list (`chart-2
  histogram`, `chart-3 bar`, `chart-4 donut`), L42 `chart_kinds` order, L49 `chart-4 histogram` -> `chart-2
  histogram`. `test_export_xlsx.py::test_scatter_and_heatmap_from_numeric_file` L130 order and L133 `sheet4.xml`
  if the heatmap moves (re-run, do not guess). `test_rules.py::test_big_map_is_sampled` and
  `test_pages.py::test_big_csv_counts_have_separators` L81 use `charts[0]` as the map3d: big.csv also has a
  histogram of `value` (score = its skew), so select the map by kind if it is no longer first.
- E1 ticket: `test_export_xlsx.py` L39 and L130 sheet lists end with `"Summary"`, L114 `["Data"]` ->
  `["Data", "Summary"]`; `test_export_pptx.py` checks on slide 0 texts, if any, gain `Filters: none`.
- Any test with a hard-coded chart order on the page (grep `data-kind`, `"chart-1"`, `[0]["kind"]`) is re-run.

Round 3:
- `tests/test_launcher_files.py:17` looks for the needle `"py -3.11"`, which L1 removes (the list holds
  `"py", "-3.11"`). Replace that needle with `"-3.11"` (or move the version checks to the AC-28/30 tests); keep
  every other needle (`FolderBrowserDialog`, `--no-index --find-links wheels`, `requirements.txt`,
  `-m app.launch`, docker lines, `exit 1`, `[switch]$Docker`).
- `tests/test_acceptance.py::test_AC_25`: its comment says a truncated sheet XML fails the whole workbook; after X1
  that is false. Update the comment; the corrupt-XML assertions go in the new `test_AC_31`.
- `tests/test_xlsx_read.py::test_broken` and `tests/test_catalog.py::test_failed_sheet_is_listed_with_its_name`
  must still pass unchanged (not-a-zip stays `not a valid xlsx` for the whole file; the monkeypatched
  `read_sheet` still gives `book.xlsx - Bad`).

Round 2 (done):
- `tests/test_parquet.py`: drop the `stdlib` fixture param and `test_snappy_copies` (fallback deleted, gate
  162); `test_unsupported_codec` (zstd) becomes "zstd reads, values equal flat.csv"; not-parquet bytes expect
  `not a valid parquet file`; nested schema keeps `unsupported parquet encoding`; `test_catalog_scan_lists_parquet`
  expects 3 datasets and no unreadable.
- `tests/test_readers.py` L84-85: `{oops` and the bad jsonl line expect `invalid JSON`.
- `tests/test_xlsx_read.py::test_shared_booleans_formats_and_gaps`: `_rewrite` adds `xl/sharedStrings.xml`
  without a content type or relationship, so openpyxl cannot find it (IndexError in a /tmp probe). Use
  `inlineStr` cells instead (the probe then gave the expected rows with `True`/`False` -> `"TRUE"`/`"FALSE"`).
- `tests/test_export_xlsx.py`: chart kinds, sheet names and ranges should still hold (xlsxwriter writes
  `xl/charts/chartN.xml` with `c:lineChart`, `c:barChart`, `c:doughnutChart`, `c:scatterChart`); the heatmap
  test reads `xl/worksheets/sheet2.xml` `conditionalFormatting` (xlsxwriter writes it there). Re-check, do not assume.
- `tests/test_export_pptx.py`: the embedded workbook is python-pptx's (`Sheet1`, not `Data`/`chart-1 line`) and
  its part names differ. Replace the L64-71 internals with python-pptx reopen checks: chart type per slide,
  `chart.plots[0].categories`, texts per slide. Keep `check_package` (python-pptx output is a valid package).
- `tests/test_acceptance.py`, `tests/test_pages.py`: `<caption>Columns</caption>`-style literals and `_rows_of`
  must accept `<caption><h2>…</h2></caption>`; test_G_1 expects 9 parquet datasets; then the rename (R9).

## Test fixtures (tests/conftest.py; round 3: `write_xlsx` takes raw sheet XML as `bytes`)
Round 7: `files_of`, `upload`, `make_client` cleanup and `tests/fixtures/round6_api.json`: see "Round 7: fixtures".
`data_dir` builds: `sales.csv`, `points.tsv`, `notes.csv`, `empty.csv`, `broken.xlsx`, `manual.pdf`,
`.hidden.csv`, `sub/records.json`, `sub/events.jsonl`, `sub/cities.geojson`, `sub/book.xlsx` (sheets `Revenue`
with Excel date cells, `Lookup`). `write_xlsx` stays hand-written: openpyxl reads it (with the harmless "no
default style" warning, which AC-23 only checks on exports). `big_csv` holds 60,000 lat/lng rows.
`make_client(folder)` sets the env and returns a TestClient. Parquet fixtures in `tests/fixtures/` (written once
by pyarrow) with CSV twins `flat.csv`, `optional.csv`. Playwright fixtures are function-scoped.
Round 4 (added by the architect): `big_sales_csv` -> folder with `sales.csv`, 200,000 rows of `date, region,
product, amount, qty` (region North/South/East/West by `i % 4`, so `f.region=North` keeps 50,000 rows; 12 x 28
dates; product 20 values; amount `i % 997`; qty 1..9), for AC-41. The hand-checked score values use `data_dir`
sales.csv. `make_client` must also clear `main._base` and `main._view` once they exist (D1 ticket).
Round 5 (added by the architect, roles checked by `tests/test_archetype_fixtures.py`): `archetypes_dir` -> folder
with `shop.csv` (`shop_rows()`: date, store 3, channel 2, product 12, units, revenue; 78 rows, 2024-01-05 ..
2024-07-10, month grain; hand values in "Round 5: Business app" and the AC-46/48 rows), `places.csv` (20 rows: lat,
lon, country 4 values, pop), `measures.csv` (a, b, c numerical), `sparse.csv` (lat/lon in 4 of 10 rows + a, b, c).
`big_csv` (60,000 points) is the hexbin case. `make_client` already clears `_detected` and `_appview` when they
exist. QA writes any extra edge file inline (as test_AC_18 does with num.csv).
Round 6 (added by the architect, roles checked by `tests/test_archetype_fixtures.py::test_round6_fixture_roles`):
`round6_dir` -> folder with `monitor.csv` (`monitor_rows()`: time, temperature, humidity; 120 daily rows from
2024-01-01; temperature 20 + i % 7 with 60.0 planted at 2024-04-10; humidity 50 + i % 5), `quiet.csv`
(`monitor_rows(spike=False)`), `survey.csv` (`survey_rows()`, 40 rows: submitted, respondent_id 1001.., age,
gender 3, region 4, city 12, q_service / q_easy / q_visits on the satisfied / agree / frequency scales
(`SURVEY_LEVELS`), q_score 1..5) and `orders.csv` (order_id 10045.., year 2023/2024, region 2, amount 12,345..;
12 rows, Explorer). Hand values are in "Round 6: Monitoring app" and "Round 6: Survey app". Week/year grain files
(AC-72) and the 14,000..16,000 trend (AC-62) are small enough for QA to write inline.

## Decisions
1. Office files on xlsxwriter (write), python-pptx (write) and openpyxl `read_only=True` (read), Parquet on
   pyarrow; pinned, not vendored (gates 162, 164, 165). This deletes roughly 500 lines of hand-written OOXML,
   thrift and snappy code, and the files open cleanly in Office.
2. No stdlib Parquet fallback (gate 162): pyarrow is a pinned runtime dependency, so a second reader is
   untested weight. Consequence: ZSTD/LZ4/BROTLI files now read (AC-14 counts 9 parquet datasets).
3. A corrupt Parquet file gets the new note `not a valid parquet file`; `unsupported parquet encoding` stays
   only for nested schemas, which the flat row model cannot show.
4. The PPTX no longer embeds our own workbook: python-pptx embeds its own, which is what makes "Edit Data" work.
   One writer per format instead of export.py importing xlsx internals.
5. xlsxwriter with `strings_to_formulas`, `strings_to_urls` and `strings_to_numbers` off: cells from client
   files are data, never formulas or links (CSV injection, hyperlink cap).
6. h2 inside `<caption>` rather than replacing the caption (gate 165): keeps the table name and adds the heading.
7. Modebar buttons made focusable with JS after each draw (Plotly renders `<a>` without `href`); CSS alone cannot
   put them in the Tab order.
8. Rows loaded on demand (LRU 4, 200,000-row cap), charts computed once server-side and shared by page, JSON and
   exports; server-rendered figures and captions (round 1, unchanged).
9. Vendored Plotly 4.1.2 and sane-topojson 4.0.0 stay: they are browser assets, the only way to be offline (AC-9).
10. (Round 3) Per-sheet isolation by blanking the other worksheet parts in an in-memory copy, not by calling
    openpyxl's `ExcelReader` steps by hand: public `load_workbook` stays the only entry point, so styles, shared
    strings and dates are read the way they are today, and the change stays inside `_load`. Cost: one in-memory
    zip copy per sheet read.
11. (Round 3) The version check runs on every candidate, `py` ones included: one loop, one rule (3.11-3.13), and a
    `py` launcher that maps `-3.13` to something odd is still checked. 3.14 is rejected (gate 171).
12. (Round 3) One `Fail` function for all four failure points (no Python, venv, wheels pip, online pip), so
    the cleanup, pause and exit code cannot drift apart between them.
13. (Round 3) Launcher tests are text checks: the image has no PowerShell (`which pwsh powershell` is empty,
    ticket 417), so the real run is the Board's on Windows.
14. (Round 3) AC-31 reworded rather than adding AC-32: gate 171 replaced the "log the gap" item with "build it",
    and a doc-only AC would describe behaviour that is no longer true.
15. (Round 4) Filter changes are plain GET navigations of a server-rendered page, not `pushState` + client
    re-render: the URL is the state, Back works natively, the page works without JS, and the KPI strip, chips,
    counts and dropdowns have one renderer (Jinja). Cost: a page load per change; the `_view` cache makes the
    dashboard's own API fetch a hit, and Plotly is served from the browser cache.
16. (Round 4) Column types come from the unfiltered rows; rules run on the filtered rows. Types, dropdowns and the
    date column stay put while filtering, and charts that no longer apply drop out (gate 175).
17. (Round 4) Scores are computed inside each rule, where the full pre-sampling data is, not from the chart dict:
    the dict holds a stride sample for line and scatter and bins for the histogram (PRD: full filtered rows).
18. (Round 4) Ids are renumbered after the sort, so `chart-1` is the top chart on the page, in the API, on the
    second PPTX slide and in the first XLSX chart sheet. Tests that named sheets by rule order change (listed).
19. (Round 4) Query params `f.<column>` with a prefix, not bare column names: a column named `from` or `to`
    cannot clash with the date range, and unknown params are ignored safely. Readable in a shared link.
20. (Round 4) The XLSX `Summary` sheet goes last: `Data` stays first (AC-18) and existing `sheetN.xml` positions
    of chart sheets do not move. The summary text is built once (`filters.summary`) and passed to both writers.
21. (Round 4) Speed by caching and two exact-result fixes (heatmap pairs once, distinct strings classified once),
    not by sampling for scores: the PRD fixes scores on the full filtered rows, and the measured budget fits.
    `# ponytail:` mark the `_view` cache (8 entries, memory = filtered row lists) and the typed-rows copy.
22. (Round 5) The detector is a list of `(rule id, app, condition)` walked in order: R4-R7 are new rows before R3,
    `qualifies` comes free (every true row), and the badge text is `rule id` + app name. No class hierarchy.
23. (Round 5) Detection runs on the unfiltered rows and is cached per dataset: a filter never changes the app,
    so the badge, switch and URL stay stable (PRD: same file, same app).
24. (Round 5) Drill-down is the round 4 `f.<column>` filter plus a computed group column, not a new `drill=` param:
    Back, chips, exports and shared links already work, and the breadcrumb is derived from `f`.
25. (Round 5) One JSON route `/app` for the shown app's figures, with the same chart dict shape the Explorer uses:
    the existing JS builders (line, bar) and both export writers take Business and Map charts unchanged; only
    `map2d` (JS) and `table` (writers) are new kinds. `/charts` stays as the Explorer contract for old tests.
26. (Round 5) `_view` stops computing Explorer charts; each app computes only its own figures in `_appview`, so a
    200,000-row Business or Map page does not pay for 8 unused rules (AC-42).
27. (Round 5) Hexbin cells are computed by the server (centres and size) and drawn by dashboard.js as one GeoJSON
    `choropleth` of hexagons (Board gate 180): true geographic size, no new library, exact counts for the test.
    `# ponytail:` cells live on the lon/lat plane (they stretch away from the equator); project first if owners map
    polar data.
28. (Round 5) KPI sparklines are server-rendered SVG polylines, not Plotly figures: 3 tiny charts would each need
    a Plotly instance, a mode bar and a table toggle (PRD assumption approved, gate 179).
29. (Round 5) The trend stops at the latest full period: a partial last period would draw a false drop (honest
    chart rule). Its rows still count in the leaderboard, which covers all view rows (PRD).
30. (Round 5) The Map 3D toggle reuses the Explorer `map3d` chart with z = the primary numeric (Board gate 180);
    `rules._map3d` takes an optional `z` index, so Explorer (z = first numerical, AC-6, AC-27) is unchanged.
31. (Round 6) Number format is decided once per column from its role on the unfiltered rows (`apps.plain`) and
    carried as data (`plain` columns, `plain` axes), not by matching rendered text: the Board asked for role, not
    regex (gate 181), and the browser cannot tell a year 2024 from an amount 2024.
32. (Round 6) The amount guard on 1..7 answer columns: without it the R5-before-R2 order (gate 183) turns the round 5
    shop.csv (a `units` 1..7 column) into a Survey, which AC-64 forbids; an amount column is the one signal a sales
    file has and a survey does not. `# ponytail:` name heuristic; a survey that also holds an amount-named column
    (for example `price_paid`) does not count its 1..7 answers and opens as Survey only if its text questions alone
    meet R5. Board asked in open questions.
33. (Round 6) Period and cross-tab picks are plain GET params in the URL, rendered by the server like filters
    (decision 15): Back, shared links and exports work without client state. They join the `_appview` cache key.
34. (Round 6) Rolling mean (7) and spike window (30) are different windows on purpose (gate 183): the mean smooths,
    the spike test needs enough history. Running sums keep both O(n) on 200,000 rows (AC-42).
35. (Round 6) New figure kinds (`monitor`, `likert`, `crosstab`) live only on the page; each app's `export`
    maps them to the kinds the writers already know (`line`, `bar`, `table`), so xlsx.py needs no change.
36. (Round 6) Likert levels and kinds are decided on the unfiltered rows: a filter that leaves only "Agree" must not
    turn the question into a plain bar or reorder its segments.