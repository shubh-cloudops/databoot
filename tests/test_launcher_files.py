from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def text(name):
    return (ROOT / name).read_text()


def test_bat_calls_ps1_with_bypass():
    bat = text("DataBoot.bat")
    assert "-ExecutionPolicy Bypass" in bat and "Start-DataBoot.ps1" in bat


def test_ps1_venv_and_docker_lines():
    ps1 = text("Start-DataBoot.ps1")
    for needle in ("FolderBrowserDialog", "py -3.11", "--no-index --find-links wheels", "requirements.txt",
                   "-m app.launch", "docker info", "docker run --rm -d -p 8765:8765",
                   '-v "${Folder}:/data:ro"', "Start-Process http://localhost:8765/", "exit 1", "[switch]$Docker"):
        assert needle in ps1, needle


def test_no_old_script_name():
    assert not (ROOT / ("Start-Data" + "OS.ps1")).exists()


def test_dockerfile():
    d = text("Dockerfile")
    assert d.startswith("FROM python:3.11-slim")
    for needle in ("requirements.txt", "COPY app/", "ENV DATABOOT_DATA=/data", "uvicorn", "app.main:app", "0.0.0.0", "8765"):
        assert needle in d, needle
