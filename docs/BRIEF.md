# Brief: round 3

## Asked
Fix a bug the Board found on Windows 11: Start-DataBoot.ps1 hardcodes `py -3.11`. The machine has Python 3.12 and 3.14, so venv creation fails silently and the script then crashes on `.venv\Scripts\python.exe`.
The launcher should pick the newest installed Python from 3.11 to 3.13. It tries `py -3.13`, `py -3.12`, `py -3.11`, then `python` with a version check.
After every native command (venv, pip) it checks `$LASTEXITCODE`. On failure it prints a clear message, deletes the partial `.venv`, pauses so the window stays open, and exits 1.
Also log AC-25 per-sheet isolation for corrupt sheets (this came from round 2 QA), and add a test that the launcher has no hardcoded single Python version.

## Deliverable
A change to an existing project: the Start-DataBoot.ps1 launcher script, a log entry for AC-25 per-sheet isolation, and one new test.

## Done when
- On a machine with Python 3.12 and 3.14 (no 3.11), the launcher creates the venv and starts without crashing.
- The launcher tries `py -3.13`, `-3.12`, `-3.11` in that order, then `python` with a version check, and only accepts 3.11 to 3.13.
- If the venv or pip step fails, the launcher prints a clear message, removes the partial `.venv`, pauses, and exits with code 1.
- Corrupt sheets are logged under AC-25 per-sheet isolation.
- A test fails if the launcher hardcodes a single Python version.
- Everything earlier rounds built still works, and the branding is unchanged.

## Unclear
- "Log AC-25 per-sheet isolation for corrupt sheets": does this mean writing a runtime log message when a corrupt sheet is skipped, or recording AC-25 in a project document such as a QA log? Where should the log go?
- What should happen if no Python 3.11 to 3.13 is found at all? The idea names the failure checks for venv and pip only. Should it use the same message, pause and exit 1?
- Should the `python` fallback accept only 3.11 to 3.13, or any version at or above 3.11?
- Which pip command should be checked? The idea says "venv, pip" without naming specific commands.

## Not asked
- Supporting Python 3.14 or versions older than 3.11.
- Changes to branding, layout, or features from earlier rounds.
- Changes to other scripts, or to platforms other than Windows.
- Any new feature beyond the fix, the AC-25 logging, and the one test.
