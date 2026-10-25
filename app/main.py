"""Web app entry point. Run locally: uvicorn app.main:app --port 8000"""
import json
from pathlib import Path

from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import catalog, config, profile, rules, xlsx

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"title": "DataBoot"})


@app.get("/health")
def health():
    return {"ok": True}


def _dataset(id):
    for d in catalog.scan(config.get().data).datasets:
        if d.id == id:
            return d
    raise HTTPException(404, "unknown dataset")


@app.get("/api/datasets")
def datasets():
    return [{"id": d.id, "path": d.path, "sheet": d.sheet, "kind": d.kind, "rows": d.rows, "columns": len(d.columns)}
            for d in catalog.scan(config.get().data).datasets]


@app.get("/api/datasets/{id}/profile")
def dataset_profile(id: str):
    d = _dataset(id)
    types = profile.classify(d.columns, catalog.load(d, config.get().max_rows))
    folder = config.get().out / "profiles"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{d.id}.json").write_text(json.dumps(types))
    return types


def _charts(d):
    """(rows, charts) of one dataset: the same dicts feed the page and the exports."""
    settings = config.get()
    rows = catalog.load(d, settings.max_rows)
    return rows, rules.charts(d.columns, rows, profile.classify(d.columns, rows), settings)


@app.get("/api/datasets/{id}/charts")
def dataset_charts(id: str):
    d = _dataset(id)
    return {"dataset": d.id, "charts": _charts(d)[1]}


@app.get("/datasets/{id}/export.xlsx")
def export_xlsx(id: str):
    d = _dataset(id)
    name = Path(d.path).stem + (f"-{d.sheet}" if d.sheet else "") + ".xlsx"
    disposition = f'attachment; filename="{name}"'
    if not name.isascii() or '"' in name or "\\" in name:  # header values are latin-1: add the RFC 5987 form
        disposition = f"attachment; filename=\"export.xlsx\"; filename*=UTF-8''{quote(name)}"
    return Response(xlsx.write(d, *_charts(d)), headers={"Content-Disposition": disposition},
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
