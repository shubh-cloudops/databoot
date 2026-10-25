# Brief: round 1

## Asked
Build software that reads a data source (a pen drive, hard drive, disk, file or folder) and immediately turns what it finds into datasets, dashboards, graphs and 3D maps, so the owner can understand the data without anyone narrating it. The idea's last section says the software, not an AI, does this: fixed rules look at the data types and pick the visuals, with no language model, no text generation and no internet. It is to run offline on clients' machines, compared to an OS that detects hardware and draws a desktop. The idea also says it must run within 16GB RAM and on hardware like an RTX 3050 laptop.

## Deliverable
A locally run, offline web application (backend plus browser dashboard), packaged so a non-technical client can start it with one click.

## Done when
- Pointed at a folder or drive, the app reads CSV and Excel files and creates a dataset from each, with no internet.
- Each column is classified as geospatial, temporal, categorical or numerical, and the result is saved as a JSON mapping.
- Rules choose the charts from those types: time series for temporal plus numerical, bar chart for categorical plus numerical, 3D map for geospatial.
- A dashboard appears in the browser with its layout built from those rules, and all its scripts and styles are served locally.
- Large datasets are cut down (batched or downsampled) so the 16GB RAM limit and the 3D map hold up.
- One click on the client's machine starts everything and opens the dashboard in the default browser.

## Unclear
- "Any" file type is named, but the detailed steps only cover CSV, Excel and JSON. Are PDFs, Word files, SQL, shapefiles and GeoJSON required this round?
- Are the PowerPoint, Excel report and Power BI exports from the earlier sections still wanted, or does "without narrating" replace them?
- Is the single-click launcher Windows-only (PowerShell) and Docker-based, as written, or must it run elsewhere too?
- Does "read a pen drive/disk" mean a mounted folder, or reading raw or unmounted devices?
- What does "complete story" mean without text: is any written summary or caption allowed, or only visuals?
- What should the app do when a file has no geospatial, temporal or categorical columns?
- Are other chart types beyond the three listed rules expected?
- The idea mixes three versions (AI agents, local LLM, rule-based). Is the rule-based one the only one in scope?

## Not asked
- Any AI or language model, whether cloud or local.
- Internet access, cloud hosting or a SaaS version.
- Written narration or generated insights text.
- Power BI integration (it appears only in the superseded AI version).
- Multi-user accounts, logins or client management.
