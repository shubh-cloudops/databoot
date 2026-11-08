# DataBoot

**Drop in your data. Get a dashboard that fits it.** No AI, no cloud, no account. It runs on your own PC and works offline.

DataBoot looks at what is in your files (dates, numbers, categories, places, free text) and picks the right kind of app for them using fixed, written-down rules. The same file always gives the same result, and every choice can be explained.

## What it does

1. **One box for your data.** Drop one file, many files or a whole folder onto the round portal on the home screen.
2. **It reads and understands them.** CSV, TSV, Excel, JSON/JSONL, Parquet and GeoJSON. It profiles each column and shows a short scan log while it works.
3. **It builds the right app for the data.** The shape of the columns decides the layout:
   - **Business**: key figures, a trend, a top-10 leaderboard with drill-down, a change table
   - **Map**: points on a world map, grouped into cells when there are many
   - **Monitoring**: rolling average and spike markers over time
   - **Survey**: rating-scale answers, histograms and cross-tabs
   - **Explorer**: a general overview for anything else
4. **Glass tiles you can move.** Drag tiles to reorder them (or use Alt + arrow keys), expand one to full screen, flip any chart to its table, click a bar to filter everything else.
5. **Export.** PowerPoint and Excel files, ready to share.

## Why it is built this way

- **Rules, not AI.** An ordered rule table picks the app. Rules are easy to test, explain and trust.
- **Honest charts.** Bars start at zero, one y-axis only, donuts only for 2 to 5 parts, colour is never the only signal, and every chart has a table view.
- **Private by design.** Nothing leaves the machine. Maps use a bundled outline, not a web service. Files you upload go to a temporary folder that is deleted when the app closes (2 GB cap per upload).
- **Accessible.** Charts can be reached with the keyboard.

## Run it (Windows 11)

You need Python 3.11, 3.12 or 3.13.

1. Download or clone this repo.
2. Double-click `DataBoot.bat`.
3. A browser tab opens. Drop your data onto the portal.

The first run creates a private Python environment and installs what it needs. For very large drives, you can point the launcher at a folder instead of uploading:

```bat
DataBoot.bat -Folder D:\
```

## Under the hood

Python, FastAPI and Jinja templates, plotted with a local copy of Plotly.js. Exports use python-pptx and xlsxwriter. Tests use pytest and Playwright, including browser tests for the interface and speed targets (a 200,000-row CSV loads in about 5 seconds or less).

## Technologies used

| Area | Technology | What it does here |
|---|---|---|
| Language | Python 3.11 to 3.13 | All application logic: scanning, profiling, rules, exports |
| Web framework | FastAPI + Uvicorn | Local web server and the upload endpoint |
| Templates | Jinja2 | Server-rendered pages (the portal, scan log, tiles) |
| Front end | HTML, CSS, vanilla JavaScript | Glass-tile interface, drag and keyboard reorder, expand view. No front-end framework |
| Charts and maps | Plotly.js (bundled locally) | Charts and maps that work offline, using a bundled world outline |
| Data handling | Python standard library, pyarrow, openpyxl | Reads CSV, TSV, Excel, JSON, Parquet and GeoJSON and profiles every column |
| Exports | python-pptx, xlsxwriter | PowerPoint and Excel output |
| Launcher | Windows batch file + PowerShell | One-click start: finds a suitable Python, creates a virtual environment, installs pinned packages, opens the browser |
| Packaging | Python venv, pinned `requirements.txt`, `requirements-dev.txt` | Repeatable installs; test-only tools kept out of the runtime list |
| Testing | pytest, Playwright (Chromium) | Unit tests plus real-browser tests for the interface, accessibility and speed targets |
| Containers | Docker (optional) | A `Dockerfile` to run the app in a container instead of a local venv |
| Source control | Git, GitHub | Version history of every build ticket |

What this shows: Windows-first scripting and deployment, reproducible environments, offline-first design (no outside network calls), automated testing, and clear written specs.

For development: `pip install -r requirements-dev.txt`, then `python -m pytest -q`. The browser tests also need Playwright for Python and Chromium (`pip install playwright` and `playwright install chromium`), which are not in the requirements files.

## How it was built

This project was built through a spec, architecture, build and QA pipeline of AI coding agents, with a human reviewer (the "Board") approving or rejecting every phase. The product decisions, the rules and the acceptance criteria are written down in `docs/`: start with `docs/ARCHITECTURE.md` and `docs/DESIGN.md`.

## Not built yet

Directory and drive-explorer apps, a layout that adapts to how you use it, and a typed query bar.
