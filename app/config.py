"""Settings from environment variables, read on every call so tests can monkeypatch them."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    data: Path       # folder scanned, read-only (DATABOOT_DATA)
    out: Path        # profiles and exports go here (DATABOOT_OUT)
    max_rows: int    # rows read per dataset for profiling and charts
    map_cap: int     # points sent to the browser per 3D map (AC-10)
    chart_cap: int   # points sent per line or scatter chart
    upload_cap: int  # bytes allowed in one browser upload, all files together (AC-77)


def get() -> Settings:
    env = os.environ.get
    return Settings(
        data=Path(env("DATABOOT_DATA", ROOT / "sample-data")),
        out=Path(env("DATABOOT_OUT", ROOT / "output")),
        max_rows=int(env("DATABOOT_MAX_ROWS", 200_000)),
        map_cap=int(env("DATABOOT_MAP_CAP", 50_000)),
        chart_cap=int(env("DATABOOT_CHART_CAP", 5_000)),
        upload_cap=int(env("DATABOOT_UPLOAD_CAP", 2 * 1024 ** 3)),
    )
