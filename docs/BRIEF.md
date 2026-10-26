# Brief: round 2
## Asked
Apply the Board's suggestions to the existing project, in the order given. Switch the file-format code to libraries (xlsxwriter, python-pptx, openpyxl) and list four dependencies in requirements.txt with pinned versions. Update ARCHITECTURE.md to drop "standard library only". Make small display changes (table captions, Plotly modebar, column header text). The PM adds and rewords acceptance criteria, QA renames tests to match, and the line-ending changes in two CSV fixtures are reverted.

## Deliverable
A change to the existing project (code, requirements.txt, ARCHITECTURE.md, acceptance criteria, tests, .gitattributes). Nothing new is built from scratch.

## Done when
- requirements.txt lists xlsxwriter==3.3.0, python-pptx==1.0.2, openpyxl==3.1.5 and pyarrow==26.0.0, and no libraries are vendored.
- The xlsx export in app/xlsx.py uses xlsxwriter, app/export.py uses python-pptx, and xlsx reading uses openpyxl with read_only=True.
- ARCHITECTURE.md no longer says "standard library only".
- Table captions are h2 headings, the Plotly modebar is always visible, and column headers show their real names (CSS uppercase removed).
- Acceptance criteria have ids for G-1..G-7, AC-6 (Plotly 3D scatter) and AC-13 (Start-DataBoot.ps1) are reworded, and the test_G_* tests are renamed to match.
- Line-ending changes in flat.csv and optional.csv are reverted, and .gitattributes exists with `* text=auto`.

## Unclear
- What are G-1..G-7, and what id format should they get? The idea does not define them.
- What should the reworded AC-6 and AC-13 say? Only their subjects are named, not the new wording.
- What should the test_G_* tests be renamed to? Presumably the new AC ids, but the idea does not say.
- Which tables have captions that become h2? All of them, or only some?
- Is app/export.py an export to PowerPoint? The idea only says "on python-pptx".
- What is pyarrow for? It is to be listed, but no code change uses it.
- "Revert" the CSV line endings to which state, the last commit? And should `* text=auto` renormalize other existing files?

## Not asked
- Vendoring any library.
- Any use of pyarrow in code.
- Changes to branding or to anything the earlier rounds built, beyond the items listed.
- New features, new export formats or new pages.
- Changes to the Plotly chart type beyond rewording AC-6 and making the modebar visible.
