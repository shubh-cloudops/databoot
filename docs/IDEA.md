# Round 2: the Board's suggestions

Dependencies: openpyxl, python-pptx, xlsxwriter, pyarrow are now installed in the prodagents-agent image. requirements.txt must list all four (pinned: xlsxwriter==3.3.0, python-pptx==1.0.2, openpyxl==3.1.5, pyarrow==26.0.0). Do NOT vendor libraries.
Engineer, in order:
1. Rewrite the xlsx export in app/xlsx.py on xlsxwriter, app/export.py on python-pptx, and xlsx reading on openpyxl (read_only=True).
2. Update ARCHITECTURE.md: drop "standard library only".
3. Table captions -> h2; Plotly modebar always visible.
4. Column headers show real names (remove CSS uppercase).
PM: add AC ids for G-1..G-7, reword AC-6 (Plotly 3D scatter) and AC-13 (Start-DataBoot.ps1); QA renames test_G_* to match.
Revert line-ending changes in flat.csv / optional.csv and add .gitattributes with `* text=auto`.

Keep everything the earlier rounds built and the business's branding; change only what these suggestions ask.
