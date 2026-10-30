# Round 7: the Board's suggestions

Round 7: new look and one-box intake. Visual contract = docs/reference/databoot-console.html (open it in a browser: layout, glass tiles, portal, scan log, interactions). Offline, no CDN, no new dependencies; every existing behaviour and test stays green.
1. INTAKE: the home page is one circular drop portal plus "Choose files" and "Choose folder" (file inputs, webkitdirectory keeps relative paths). Files are POSTed to the local server (/upload) into a temp data folder (deleted on exit), then scanned as today. Cap 2 GB per upload with a clear message; larger drives still use the launcher's folder picker (-Folder). 1 file, many files and a folder must all work.
2. SCAN SCREEN: after intake show a log fed by the real catalog: file, rows, column roles (T/N/C/G), app and rule ("-> BUSINESS (rule R2)"), unreadable files with their note, "0 bytes uploaded" to the internet. Then open the workspace.
3. WORKSPACE: dataset tabs with archetype caption, "App: ... rule ..." badge, filter chips, a 12-column grid of glass tiles. Shared tile component for ALL apps (Business, Map, Monitoring, Survey, Explorer) and the Explorer's charts; the existing tile content/logic is unchanged.
4. TILE INTERACTIONS: cursor glow; drag a tile by its header to reorder (order remembered per dataset in localStorage); expand to a full-screen overlay (Esc / backdrop closes, filters keep working inside); table toggle on every chart tile (already required); tooltips; staggered entrance under 0.6 s.
5. STYLE: dark holographic theme only (tokens from the prototype: bg #050a12, cyan #4de1ff, amber #ffb454, mono labels). Replace OS light/dark styling; keep the global chart rules (one y-axis, sorted bars, direction never by colour alone). System fonts only. Reduced motion: no animation. Also remove backdrop-filter blur when `prefers-reduced-transparency` is set.
6. ACCESSIBILITY: all clickable chart marks keyboard-focusable (Enter/Space), visible focus ring, text contrast >= 4.5:1 for body and labels, tiles are landmarks with headings.
7. Update DESIGN.md with the tokens and tile rules; exports are unchanged.
Tests: upload one file, many files and a folder; temp folder removed on exit; over-cap message; Playwright: drag reorder, expand/close, table toggle, cross-filter inside the overlay; no external network requests; AC-41/AC-42 speed targets still met; all earlier tests green.
Team: designer + frontend + backend; trends off.

Keep everything the earlier rounds built and the business's branding; change only what these suggestions ask.
