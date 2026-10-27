from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _lines(name):
    return [ln.strip() for ln in (ROOT / name).read_text().splitlines() if ln.strip()]


def test_runtime_requirements_have_no_test_tools():
    lines = _lines("requirements.txt")
    assert not [ln for ln in lines if ln.lower().startswith(("pytest", "httpx"))]
    for pin in ("fastapi", "jinja2", "uvicorn"):
        assert any(ln.startswith(pin + "==") for ln in lines), pin
    for pin in ("pyarrow==26.0.0", "openpyxl==3.1.5", "python-pptx==1.0.2", "xlsxwriter==3.3.0"):
        assert pin in lines


def test_dev_requirements_add_test_tools():
    lines = _lines("requirements-dev.txt")
    assert lines[0] == "-r requirements.txt"
    assert "pytest==9.1.1" in lines
    assert "httpx==0.28.1" in lines


def test_readme_names_dev_requirements():
    assert "requirements-dev.txt" in (ROOT / "README.md").read_text()


def test_clients_install_runtime_requirements_only():
    for name in ("Dockerfile", "Start-DataBoot.ps1"):
        text = (ROOT / name).read_text()
        assert "requirements.txt" in text
        assert "requirements-dev" not in text


def test_app_does_not_import_test_tools():
    for path in (ROOT / "app").glob("*.py"):
        for ln in path.read_text().splitlines():
            ln = ln.strip()
            assert not ln.startswith(("import httpx", "from httpx", "import pytest", "from pytest")), path
