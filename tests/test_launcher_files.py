import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def text(name):
    return (ROOT / name).read_text()


def test_bat_calls_ps1_with_bypass():
    bat = text("DataBoot.bat")
    assert "-ExecutionPolicy Bypass" in bat and "Start-DataBoot.ps1" in bat


def test_ps1_venv_and_docker_lines():
    ps1 = text("Start-DataBoot.ps1")
    for needle in ("FolderBrowserDialog", "-3.11", "--no-index --find-links wheels", "requirements.txt",
                   "-m app.launch", "docker info", "docker run --rm -d -p 8765:8765",
                   '-v "${Folder}:/data:ro"', "Start-Process http://localhost:8765/", "exit 1", "[switch]$Docker"):
        assert needle in ps1, needle


def test_ps1_candidates_in_order():
    line = next(l for l in text("Start-DataBoot.ps1").splitlines() if l.strip().startswith("$Candidates ="))
    assert [line.index(s) for s in ("-3.13", "-3.12", "-3.11", '"python"')] == sorted(
        line.index(s) for s in ("-3.13", "-3.12", "-3.11", '"python"'))
    assert line.count("-3.1") == 3


def test_ps1_version_check_and_no_hardcoded_venv():
    ps1 = text("Start-DataBoot.ps1")
    assert "(3, 11) <= sys.version_info[:2] <= (3, 13)" in ps1
    assert not re.search(r"py -3\.1\d+ -m venv", ps1)


def test_ps1_no_python_message_and_fail_order():
    ps1 = text("Start-DataBoot.ps1")
    assert 'Fail "DataBoot needs Python 3.12. Install it with: winget install -e --id Python.Python.3.12"' in ps1
    body = ps1[ps1.index("function Fail"):]
    body = body[:body.index("\n}")]
    pos = [body.index(s) for s in ("Remove-Item -Recurse -Force .venv", "Read-Host", "exit 1")]
    assert pos == sorted(pos)


def test_no_old_script_name():
    assert not (ROOT / ("Start-Data" + "OS.ps1")).exists()


def test_dockerfile():
    d = text("Dockerfile")
    assert d.startswith("FROM python:3.11-slim")
    for needle in ("requirements.txt", "COPY app/", "ENV DATABOOT_DATA=/data", "uvicorn", "app.main:app", "0.0.0.0", "8765"):
        assert needle in d, needle


def test_ps1_exit_code_checks_before_launch():
    ps1 = text("Start-DataBoot.ps1")
    launch = ps1.index("-m app.launch")
    for marker in ("-m venv .venv", "--find-links wheels", "\n        .venv\\Scripts\\python.exe -m pip install -r requirements.txt"):
        after = ps1[ps1.index(marker) + len(marker):]
        after = after.split("\n", 2)[1]  # the line directly after the command
        assert "$LASTEXITCODE -ne 0" in after and "Fail" in after, marker
    assert ps1.rindex("Fail ") < launch
