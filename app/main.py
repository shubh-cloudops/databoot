"""Web app entry point. Run locally: uvicorn app.main:app --port 8000"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import catalog, config, profile, rules

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


@app.get("/api/datasets/{id}/charts")
def dataset_charts(id: str):
    d = _dataset(id)
    settings = config.get()
    rows = catalog.load(d, settings.max_rows)
    return {"dataset": d.id, "charts": rules.charts(d.columns, rows, profile.classify(d.columns, rows), settings)}
