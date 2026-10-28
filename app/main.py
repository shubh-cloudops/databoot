"""Web app entry point. Run locally: uvicorn app.main:app --port 8000"""
import json
from functools import lru_cache
from pathlib import Path

from urllib.parse import quote, urlencode

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import apps, business, catalog, config, export, filters, geo, profile, rules, xlsx

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["num"] = "{:,}".format  # the one thousands-separator filter for every count (gate 161)
templates.env.filters.update(fmt=business.fmt, signed=business.signed, spark=business.spark)  # Business page: floats, deltas, sparkline


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
    v = _view(d, filters.parse(request.query_params, d.columns, _base(d)[1]))
    f, det, shown = v["filters"], _detected(d), _shown(d, request.query_params)
    appq = (("app", shown),) if request.query_params.get("app") == shown else ()  # links keep app only if the URL had it

    def url(*pairs):
        q = urlencode(pairs)
        return f"/datasets/{d.id}" + ("?" + q if q else "")
    chips = [(label, url(*f[:i], *f[i + 1:], *appq)) for i, label in enumerate(v["labels"])]
    view_as = [(apps.NAMES[a], url(*f, ("app", a)), a == shown) for a in det["qualifies"]] if det["qualifies"] != ["explorer"] else []
    return templates.TemplateResponse(request, "dataset.html", {
        "title": f"{d.path} - DataBoot", "d": d, "types": v["mapping"], "rows": v["rows"][:20], "shown": shown,
        "badge": f"App: {apps.NAMES[det['app']]} (rule {det['rule']})", "view_as": view_as, "appq": bool(appq),
        "charts": _appview(d, f, "explorer")["charts"] if shown == "explorer" else [],
        "biz": _appview(d, f, "business", shown if appq else None) if shown == "business" else {},
        "geo": _appview(d, f, "map") if shown == "map" else {},
        "kpis": v["kpis"], "options": v["options"], "labels": v["labels"], "filters": f, "chips": chips,
        "clear": url(*appq), "query": urlencode(f + appq)})


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
    """(rows, mapping, typed_rows, options) of one dataset, computed once: types from the first 10,000 rows."""
    rows = catalog.load(d, config.get().max_rows)
    mapping = profile.classify(d.columns, rows)
    return rows, mapping, rules.typed(d.columns, rows, mapping), filters.options(d.columns, rows, mapping)


@lru_cache(maxsize=8)
def _view(d, f):
    """Rows, typed rows and KPIs of one dataset under filters f (a filters.parse tuple); types stay those of all rows."""
    rows, mapping, typed, options = _base(d)
    keep = filters.apply(f, d.columns, mapping, typed)
    if keep is not None:
        rows, typed = [rows[i] for i in keep], [typed[i] for i in keep]
    labels = filters.labels(f, d.columns, mapping)
    return {"rows": rows, "mapping": mapping, "options": options, "filters": f, "labels": labels,
            "typed": typed, "kpis": rules.kpis(d.columns, rows, typed, mapping)}


@lru_cache(maxsize=4)
def _detected(d):
    """Detected app of one dataset, on the unfiltered rows so the same file gives the same app under any filter."""
    _, mapping, typed, _ = _base(d)
    return apps.detect(d.columns, mapping, typed)


def _shown(d, params):
    """The app drawn: the valid `app` param when the dataset qualifies for it, else the detected app."""
    det = _detected(d)
    return params.get("app") if params.get("app") in det["qualifies"] else det["app"]


@lru_cache(maxsize=8)
def _appview(d, f, app, app_param=None):
    """Figures of one app under filters f."""
    if app == "explorer":
        v = _view(d, f)
        return {"charts": rules.charts(d.columns, v["typed"], v["mapping"], config.get())}
    if app == "business":
        v = _view(d, f)
        return business.view(d.columns, v["rows"], v["typed"], v["mapping"], f, v["options"], app_param)
    if app == "map":
        v = _view(d, f)
        return geo.view(d.columns, v["rows"], v["typed"], v["mapping"], config.get())
    return {}


@app.get("/api/datasets/{id}/app")
def dataset_app(request: Request, id: str):
    d = _dataset(id)
    f = filters.parse(request.query_params, d.columns, _base(d)[1])
    shown = _shown(d, request.query_params)
    return {"dataset": d.id, **_detected(d), "shown": shown, "filters": _view(d, f)["labels"],
            "charts": [],
            **_appview(d, f, shown, shown if request.query_params.get("app") == shown else None)}


@app.get("/api/datasets/{id}/charts")
def dataset_charts(request: Request, id: str):
    d = _dataset(id)
    f = filters.parse(request.query_params, d.columns, _base(d)[1])
    v = _view(d, f)
    return {"dataset": d.id, "charts": _appview(d, f, "explorer")["charts"], "kpis": v["kpis"], "filters": v["labels"]}


def _download(d, ext, body, media_type):
    name = Path(d.path).stem + (f"-{d.sheet}" if d.sheet else "") + "." + ext
    disposition = f'attachment; filename="{name}"'
    if not name.isascii() or '"' in name or "\\" in name:  # header values are latin-1: add the RFC 5987 form
        disposition = f"attachment; filename=\"export.{ext}\"; filename*=UTF-8''{quote(name)}"
    return Response(body, headers={"Content-Disposition": disposition}, media_type=media_type)


TITLES = {"business": "Business overview", "map": "Map overview"}


def _export(d, params):
    """(view, charts, title) of the shown app under the request's filters; Explorer has no title."""
    f = filters.parse(params, d.columns, _base(d)[1])
    v, shown = _view(d, f), _shown(d, params)
    a = _appview(d, f, shown)
    if shown == "business":
        return v, business.export(a), TITLES[shown]
    if shown == "map":
        return v, geo.export(a, d.columns, v["typed"], v["mapping"], config.get()), TITLES[shown]
    return v, a["charts"], None


@app.get("/datasets/{id}/export.xlsx")
def export_xlsx(request: Request, id: str):
    d = _dataset(id)
    v, charts, title = _export(d, request.query_params)
    return _download(d, "xlsx", xlsx.write(d, v["rows"], charts, filters.summary(v["labels"]), title), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/datasets/{id}/export.pptx")
def export_pptx(request: Request, id: str):
    d = _dataset(id)
    v, charts, title = _export(d, request.query_params)
    shown = len(v["rows"]) if v["filters"] else None
    return _download(d, "pptx", export.pptx(d, charts, filters.summary(v["labels"]), shown, title), "application/vnd.openxmlformats-officedocument.presentationml.presentation")
