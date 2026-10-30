# PRD: DataBoot, an offline data-to-dashboard bootstrapper (round 7)

Round 7 adds a **new look and a one-box intake** (docs/IDEA.md, docs/BRIEF.md). The home page becomes one circular
drop portal with "Choose files" and "Choose folder"; uploads go to the local server into a temp folder and are
scanned as today. A scan screen shows a log from the real catalog, then the workspace opens. Every app and the
Explorer's charts sit in one shared glass-tile component, with tile interactions, a dark holographic theme only and
accessibility fixes. No AI, offline, no network requests, no new dependencies, no CDN. Everything under "Product
today" stays: scanning, classification, rules, figures and exports do not change.

## Problem
Owners of data (a pen drive, a disk or a folder of spreadsheets) cannot see what is in it without an analyst.
DataBoot reads the files and at once shows datasets and charts, fully offline, with no AI: fixed rules look at the
column types and pick the visuals. Charts can be taken away as editable XLSX and PPTX files.
This round: today the only way in is the launcher's folder argument, so a client who has a few files at hand cannot
just drop them in. The pages also look like a plain admin table; the Board wants a single, consistent "console"
look where every chart is the same kind of tile the user can move, enlarge and read as a table.

## Users
- **Data owner (client)**: non-technical; a Windows 11 laptop and some files, a folder or a drive. Starts the app
  with one click, drops files in and looks.
- **Operator**: installs it once on the client's machine; uses the launcher's -Folder option for large drives.

## Product today (rounds 1 to 6, kept)
1. Started on one folder; lists CSV, TSV, Excel (per sheet), JSON/JSONL, GeoJSON and Parquet datasets, an "Other
   files" inventory and a "Could not be read" list. Columns classified on the first 10,000 rows.
2. Ordered rule table, first match wins: R1 Map, R5 Survey, R2 Business, R4 Monitoring, R3 Explorer (gate 183;
   conditions in AC-43 and AC-64). Badge "App: <name> (rule <id>)", "View as", `app=` in the URL.
3. Explorer (8 scored charts, KPI strip), Business (KPI cards, trends, leaderboard, drill, change table), Map (2D,
   hexagons, side panel, top regions, 3D), Monitoring (period, tiles, main line, spikes), Survey (question bars,
   Likert, cross-tab, Respondents).
4. Filters, chips, click-to-filter, URL state; filtered XLSX/PPTX exports with native charts; table toggle and
   tooltip on every chart; number format by column role; launcher and optional Dockerfile.

## User stories
### Must (rounds 1 to 6, kept)
- M1-M43 as in round 6 (AC-1..AC-73). AC-73 reworded to gate 187 (Explorer PPTX "Data overview", no XLSX title).

### Must (round 7)
- M44. Drop portal. As a data owner, the home page shows one circular drop portal plus "Choose files" and "Choose
  folder" buttons, so I can drop or pick one file, many files or a folder (AC-74).
- M45. Upload. Picked or dropped files are sent to the local server (`/upload`), saved in a temp data folder with
  their relative paths kept (a folder's subfolders stay), and scanned exactly as a launcher folder would be
  (AC-75). The temp folder is deleted when the app exits (AC-76).
- M46. Cap. An upload over 2 GB is refused with a clear message that names the limit and the launcher's -Folder
  option for larger drives; nothing of it is kept (AC-77).
- M47. Scan screen. After an upload I see a log from the real catalog: per dataset its file, rows, role counts
  (T/N/C/G) and "-> APP (rule Rn)", unreadable files with their note, and "0 bytes uploaded to the internet"; then
  the workspace opens (AC-78).
- M48. Workspace. Dataset tabs, an archetype caption, the app badge, filter chips and a 12-column grid of tiles
  (AC-79).
- M49. One tile component for every app (Business, Map, Monitoring, Survey, Explorer) and the Explorer's charts;
  each tile is a landmark with a heading; tile content and figures unchanged (AC-80).
- M50. Reorder. Drag a tile by its header; the order is remembered per dataset (AC-81).
- M51. Expand. A tile opens full screen; Esc or a backdrop click closes it; filters still work inside (AC-82).
- M52. Dark holographic theme only; chart rules kept; contrast >= 4.5:1 (AC-83).
- M53. Motion: cursor glow and a staggered entrance under 0.6 s; none with reduced motion; no blur with reduced
  transparency (AC-84).
- M54. Keyboard: every clickable chart mark is reachable with Tab, shows a focus ring and acts on Enter/Space
  (AC-85).
- M55. Offline: the whole intake-to-workspace walk asks no other host (AC-86).

### Should
- S1-S3 as in round 6 (speed AC-41/AC-42 still met with the new pages; exports unchanged).
- S4. docs/DESIGN.md records the tokens and tile rules (AC-87).

### Could
- C1. Keyboard reorder of tiles (move buttons or keys) as an alternative to drag.
- C2. A progressive scan log (lines appear as files are read) instead of all at once.

## Round 7 definitions (defaults; Board to confirm)
- **Upload set**: one drop or one pick is one upload. Each upload gets a new temp folder; the app then scans that
  folder (it becomes the current data folder) and the previous upload's temp folder is deleted. A folder given to
  the launcher (-Folder) is only read, never written or deleted.
- **Cap**: 2 GB for the total of one upload (all its files), checked before and while writing; the limit is a
  setting (`DATABOOT_UPLOAD_CAP`, bytes) so tests can use a small cap.
- **Launcher**: the folder argument becomes optional; without it the app starts on an empty temp folder and the home
  page shows only the portal. With a folder, the home page shows the portal and, below it, the dataset, "Could not
  be read" and "Other files" tables as today (AC-1, AC-12, AC-15, AC-22 stay).
- **Scan log line**: `<file>[ - <sheet>]  <rows> rows  T<n> N<n> C<n> G<n>  -> <APP> (rule <id>)`, rows with
  thousands separators, APP in capitals and equal to `/api/datasets/<id>/app`; unreadable: `<file>  <note>`. Last
  line: "0 bytes uploaded to the internet". Then a button "Open workspace" (focused) opens the first dataset; it also
  opens by itself after the log is shown.
- **Archetype caption**: the role counts and the app's purpose in a few words (for example "T1 N2 C1 · business").
  Exact words are the designer's, in DESIGN.md; no generated sentences (AC-17).
- **Tile**: header (heading, drag handle, expand, table toggle), body (the existing figure, cards or table). KPI
  strip, card groups, tables (Columns, First rows, change table) are tiles too. Grid spans follow AC-34 (first chart
  tile full width, others half at desktop, full at phone).
- **Expand and filters**: clicking a bar inside the expanded tile applies the filter as on the page (URL, chip,
  counts); the page then shows that same tile expanded with the filtered figure.
- **Clickable marks**: bars and donut slices that filter or drill (Explorer, Business leaderboard, Survey bars, Map
  top regions). Map points are reached through the map's table view.

## Out of scope
- New apps, chart types, scanning or classification rules, export changes, new branding or logo.
- Uploads over 2 GB through the browser (the launcher's -Folder stays); upload over a network to a remote server.
- A light theme or OS light/dark switch (removed). Web fonts, CDN assets, new dependencies. Trends research (IDEA:
  trends off).

## Constraints
- No new dependency: `python-multipart` is not in requirements.txt, so `/upload` must not rely on FastAPI form
  parsing (for example one POST per file with its relative path, body streamed to disk). Upload paths are
  sanitised: no absolute paths, no `..`, nothing written outside the temp folder.
- The server binds 127.0.0.1 as today. All earlier tests stay green; a test that relied on the old look (light
  theme, page order) is changed only where this PRD changes the behaviour, and named in the tickets.
- Speed: AC-41 and AC-42 still met with the tile pages.
- Style follows docs/DESIGN.md, updated by the designer from the prototype (docs/reference/databoot-console.html,
  see open questions): bg #050a12, cyan #4de1ff, amber #ffb454, mono labels, system font stacks only. Global chart
  rules unchanged (one y-axis, sorted bars from zero, direction never by colour alone).
- Text allowed on pages stays as before plus the scan log lines, the portal labels, the cap message and tile
  controls. No generated sentences (AC-17).
- Team (IDEA): designer, frontend and backend; trends off.

## Branding
No business website capture and no docs/brand/ folder: docs/reference/ holds captures of deck.gl and
unstructured.io (third-party libraries from the round 1 idea, not the client's site). The Board chose (gate 160):
name DataBoot, system font, no logo, blank SVG favicon. This round the Board asks for a new theme (dark
holographic); name, no-logo and favicon stay. The prototype named as the visual contract is not in the repository.
