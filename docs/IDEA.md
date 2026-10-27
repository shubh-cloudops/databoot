# Round 3: the Board's suggestions

Bug (Board tested on Windows 11): Start-DataBoot.ps1 hardcodes `py -3.11`; machine has 3.12 + 3.14, so venv creation fails silently and the script crashes on .venv\Scripts\python.exe.
Fix: pick the newest installed Python 3.11-3.13 (try py -3.13, -3.12, -3.11, then `python` with a version check). After every native command (venv, pip) check $LASTEXITCODE; on failure print a clear message, delete the partial .venv, pause so the window stays open, exit 1.
Also log AC-25 per-sheet isolation for corrupt sheets (from round 2 QA).
Add a test that the launcher has no hardcoded single Python version.

Keep everything the earlier rounds built and the business's branding; change only what these suggestions ask.
