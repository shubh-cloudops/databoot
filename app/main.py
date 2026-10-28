"""Web app entry point. Run locally: uvicorn app.main:app --port 8000"""
import json
from functools import lru_cache
from pathlib import Path

from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import catalog, config, export, profile, rules, xlsx

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["num"] = "{:,}".format  # the one thousands-separator filter for every count (gate 161)


@app.get("/")
def home(request: Request):
    cat = catalog.scan(config.get().data)
    return templates.TemplateResponse(request, "home.html", {"title": "DataBoot", "folder": config.get().data, "cat": cat})


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


@app.get("/datasets/{id}")
def dashboard(request: Request, id: str):
    d = _dataset(id)
    rows, charts = _charts(d)
    types = _base(d)[1]
    return templates.TemplateResponse(request, "dataset.html", {
        "title": f"{d.path} - DataBoot", "d": d, "types": types, "charts": charts, "rows": rows[:20],
        "points": {"map3d", "line", "scatter"}})


@app.get("/api/datasets/{id}/profile")
def dataset_profile(id: str):
    d = _dataset(id)
    types = _base(d)[1]
    folder = config.get().out / "profiles"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{d.id}.json").write_text(json.dumps(types))
    return types


@lru_cache(maxsize=4)
def _base(d):
    """(rows, mapping, typed_rows) of one dataset, computed once: types from the first 10,000 rows, cells cast once."""
    rows = catalog.load(d, config.get().max_rows)
    mapping = profile.classify(d.columns, rows)
    return rows, mapping, rules.typed(d.columns, rows, mapping)


def _charts(d):
    """(rows, charts) of one dataset: the same dicts feed the page and the exports."""
    rows, mapping, typed = _base(d)
    return rows, rules.charts(d.columns, typed, mapping, config.get())


@app.get("/api/datasets/{id}/charts")
def dataset_charts(id: str):
    d = _dataset(id)
    return {"dataset": d.id, "charts": _charts(d)[1]}


def _download(d, ext, body, media_type):
    name = Path(d.path).stem + (f"-{d.sheet}" if d.sheet else "") + "." + ext
    disposition = f'attachment; filename="{name}"'
    if not name.isascii() or '"' in name or "\\" in name:  # header values are latin-1: add the RFC 5987 form
        disposition = f"attachment; filename=\"export.{ext}\"; filename*=UTF-8''{quote(name)}"
    return Response(body, headers={"Content-Disposition": disposition}, media_type=media_type)


@app.get("/datasets/{id}/export.xlsx")
def export_xlsx(id: str):
    d = _dataset(id)
    return _download(d, "xlsx", xlsx.write(d, *_charts(d)), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/datasets/{id}/export.pptx")
def export_pptx(id: str):
    d = _dataset(id)
    return _download(d, "pptx", export.pptx(d, _charts(d)[1]), "application/vnd.openxmlformats-officedocument.presentationml.presentation")
