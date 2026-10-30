# Brief: round 7

## Asked
A new look and a one-box intake for the existing app. The home page becomes one circular drop portal plus "Choose files" and "Choose folder"; uploads go to the local server (/upload) into a temp folder and are scanned as today. A scan screen shows a log fed by the real catalog, then opens the workspace. The workspace uses a shared glass-tile component for all apps and the Explorer's charts, with tile interactions, a dark holographic theme only, and accessibility fixes. DESIGN.md is updated. Everything earlier rounds built and the business's branding stay; only what the idea lists changes.

## Deliverable
A change to an existing web app (UI restyle plus a new upload path on the local server), with updated DESIGN.md and new tests. The visual contract is docs/reference/databoot-console.html. It must work offline, with no CDN and no new dependencies.

## Done when
- Home page is a circular drop portal plus "Choose files" and "Choose folder" (relative paths kept); 1 file, many files and a folder all upload and scan.
- Uploads land in a temp data folder that is deleted on exit; over 2 GB gives a clear message; larger drives still use the launcher's -Folder picker.
- Scan screen log shows, from the real catalog: file, rows, column roles (T/N/C/G), app and rule ("-> BUSINESS (rule R2)"), unreadable files with their note, and "0 bytes uploaded"; then the workspace opens.
- Workspace has dataset tabs with archetype caption, "App: ... rule ..." badge, filter chips and a 12-column tile grid. Business, Map, Monitoring, Survey, Explorer and the Explorer charts use one shared tile component; tile content and logic are unchanged.
- Tiles have cursor glow, header drag-reorder (order remembered per dataset in localStorage), full-screen expand (Esc or backdrop closes, filters still work inside), table toggle on every chart tile, tooltips, and a staggered entrance under 0.6 s.
- Dark holographic theme only (bg #050a12, cyan #4de1ff, amber #ffb454, mono labels, system fonts); no motion under reduced motion; no backdrop-filter blur under `prefers-reduced-transparency`; chart rules kept (one y-axis, sorted bars, direction never by colour alone).
- Accessibility: chart marks keyboard-focusable (Enter/Space), visible focus ring, contrast >= 4.5:1, tiles are landmarks with headings.
- Tests: the upload cases, temp-folder removal, over-cap message, the Playwright cases (drag reorder, expand/close, table toggle, cross-filter in the overlay), no external network requests, AC-41/AC-42 speed targets met, all earlier tests green. Exports unchanged.

## Unclear
- Which parts of the prototype are binding where it and the numbered list differ? The idea calls the prototype the "visual contract" but gives only a few tokens.
- Does the 2 GB cap apply per file or to the whole upload (many files, a folder)? The idea says "per upload".
- What exactly does "-> BUSINESS (rule R2)" mean beyond that example, and where are the rules defined? The idea names none.
- Should the scan log fill progressively or appear all at once? The idea only says it is fed by the real catalog.
- Is a small number of tiles shown per app or are all existing ones kept? ("existing tile content/logic is unchanged".)
- What is the contrast target for large text or decorative glow? Only body and labels are named.
- "Trends off" is stated for the team; what does it mean here? The idea doesn't say.

## Not asked
- New dependencies, CDN assets, web fonts or any network access.
- A light theme or an OS light/dark switch (these are to be replaced).
- Changes to exports, to scanning/classification rules, or to the business's branding.
- Uploads above 2 GB through the browser; the launcher's -Folder picker stays for that.
- New apps or new chart types beyond those listed.
- Anything else in earlier rounds' behaviour; it must stay and its tests stay green.
