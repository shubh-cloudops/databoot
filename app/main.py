"""Web app entry point. Run locally: uvicorn app.main:app --port 8000"""
import json
from functools import lru_cache
from pathlib import Path

from urllib.parse import quote, urlencode

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import apps, business, catalog, config, export, filters, geo, monitoring, profile, rules, survey, upload, xlsx


@asynccontextmanager
async def _lifespan(_):
    yield
    upload.cleanup()  # the temp folders of browser uploads go with the process (AC-76)


app = FastAPI(lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["num"] = "{:,}".format  # the one thousands-separator filter for every count (gate 161)
templates.env.filters.update(sep=apps.sep, plural=apps.plural)  # sep: cell text of a numerical column
templates.env.filters.update(fmt=business.fmt, signed=business.signed, spark=business.spark)  # Business page: floats, deltas, sparkline


@app.get("/")
def home(request: Request):
    cat = catalog.scan(config.get().data)
    return templates.TemplateResponse(request, "home.html", {"title": "DataBoot", "folder": config.get().data, "cat": cat, "cap": config.get().upload_cap})


@app.post("/upload")
async def upload_begin(request: Request):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "body must be JSON")
    files = body.get("files") if isinstance(body, dict) else body
    return {"batch": upload.begin(files, config.get().upload_cap)}


@app.put("/upload/{batch}")
async def upload_file(request: Request, batch: str, path: str = ""):
    return {"path": upload.safe(path), "bytes": await upload.write(batch, path, request.stream(), config.get().upload_cap)}


@app.post("/upload/{batch}/done")
def upload_done(batch: str):
    upload.finish(batch)
    catalog.scan.cache_clear()  # a Dataset compares equal across folders: stale rows would be served
    catalog.load.cache_clear()
    for cache in (_base, _view, _plain, _detected, _appview):
        cache.cache_clear()
    return {"next": "/scan"}


@app.get("/health")
def health():
    return {"ok": True}


def _summary(d):
    """App, rule and the T/N/C/G role counts of the profile mapping of one dataset (scan log and archetype caption)."""
    kinds = list(_base(d)[1].values())
    det = _detected(d)
    return {"app": det["app"], "rule": det["rule"], **{k: kinds.count(t) for k, t in
            (("T", "temporal"), ("N", "numerical"), ("C", "categorical"), ("G", "geospatial"))}}


@app.get("/scan")
def scan(request: Request):
    cat = catalog.scan(config.get().data)
    return templates.TemplateResponse(request, "scan.html", {
        "title": "DataBoot", "cat": cat, "lines": [(d, _summary(d)) for d in cat.datasets],
        "first": cat.datasets[0].id if cat.datasets else None})


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
    pickq = _pickq(shown, request.query_params)  # likewise period / row / col; View-as links never carry it
    pick = _pick(d, shown, request.query_params)

    def url(*pairs):
        q = urlencode(pairs)
        return f"/datasets/{d.id}" + ("?" + q if q else "")
    chips = [(label, url(*f[:i], *f[i + 1:], *appq, *pickq)) for i, label in enumerate(v["labels"])]
    view_as = [(apps.NAMES[a], url(*f, ("app", a)), a == shown) for a in det["qualifies"]] if det["qualifies"] != ["explorer"] else []
    return templates.TemplateResponse(request, "dataset.html", {
        "title": f"{d.path} - DataBoot", "d": d, "types": v["mapping"], "rows": v["rows"][:20], "plain": _plain(d), "shown": shown,
        "badge": f"App: {apps.NAMES[det['app']]} (rule {det['rule']})", "view_as": view_as, "appq": bool(appq),
        "charts": _appview(d, f, "explorer")["charts"] if shown == "explorer" else [],
        "biz": _appview(d, f, "business", shown if appq else None) if shown == "business" else {},
        "geo": _appview(d, f, "map") if shown == "map" else {},
        "mon": _appview(d, f, "monitoring", None, pick) if shown == "monitoring" else {},
        "sur": _appview(d, f, "survey", None, pick) if shown == "survey" else {}, "pickq": pickq,
        "tabs": catalog.scan(config.get().data).datasets, "summary": _summary(d),
        "kpis": v["kpis"], "options": v["options"], "labels": v["labels"], "filters": f, "chips": chips,
        "clear": url(*appq, *pickq), "query": urlencode(f + appq + pickq)})


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
def _plain(d):
    """Plain numerical column indexes of one dataset, on the unfiltered rows: a filter never changes a column's format."""
    _, mapping, typed, _ = _base(d)
    return apps.plain(d.columns, mapping, typed)


@lru_cache(maxsize=4)
def _detected(d):
    """Detected app of one dataset, on the unfiltered rows so the same file gives the same app under any filter."""
    _, mapping, typed, _ = _base(d)
    return apps.detect(d.columns, mapping, typed)


def _shown(d, params):
    """The app drawn: the valid `app` param when the dataset qualifies for it, else the detected app."""
    det = _detected(d)
    return params.get("app") if params.get("app") in det["qualifies"] else det["app"]


def _pick(d, shown, params):
    """Validated, hashable request state of the shown app (part of the _appview cache key): Monitoring period, Survey row/col."""
    if shown == "monitoring":
        return params.get("period") if params.get("period") in monitoring.PERIODS else "30"
    if shown == "survey":
        _, mapping, typed, _ = _base(d)
        return survey.pick(survey.questions(d.columns, mapping, typed), params.get("row"), params.get("col"))
    return None


def _pickq(shown, params):
    """The request's own period (Monitoring) or row/col (Survey) pairs, only those the URL had."""
    keys = {"monitoring": ("period",), "survey": ("row", "col")}.get(shown, ())
    return tuple((k, params[k]) for k in keys if k in params)


@lru_cache(maxsize=8)
def _appview(d, f, app, app_param=None, pick=None):
    """Figures of one app under filters f; each chart dict gets `plain`, the axis letters whose label is a plain column."""
    out = _appview_figures(d, f, app, app_param, pick)
    names = {d.columns[i] for i in _plain(d)}
    for c in [*out.get("charts", []), out.get("map3d")]:
        if c:
            c["plain"] = [a for a in "xyz" if c.get(a + "_label") in names]
    return out


def _appview_figures(d, f, app, app_param, pick):
    if app == "explorer":
        v = _view(d, f)
        return {"charts": rules.charts(d.columns, v["typed"], v["mapping"], config.get())}
    if app == "business":
        v = _view(d, f)
        return business.view(d.columns, v["rows"], v["typed"], v["mapping"], f, v["options"], app_param)
    if app == "map":
        v = _view(d, f)
        return geo.view(d.columns, v["rows"], v["typed"], v["mapping"], config.get())
    if app == "monitoring":
        v = _view(d, f)
        return monitoring.view(d.columns, v["typed"], v["mapping"], pick, config.get())
    if app == "survey":
        v = _view(d, f)
        return survey.view(d.columns, v["typed"], v["mapping"], _base(d)[2], pick, config.get())
    return {}


@app.get("/api/datasets/{id}/app")
def dataset_app(request: Request, id: str):
    d = _dataset(id)
    f = filters.parse(request.query_params, d.columns, _base(d)[1])
    shown = _shown(d, request.query_params)
    return {"dataset": d.id, **_detected(d), "shown": shown, "filters": _view(d, f)["labels"],
            "charts": [],
            **_appview(d, f, shown, shown if request.query_params.get("app") == shown else None,
                       _pick(d, shown, request.query_params))}


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


TITLES = {"business": "Business overview", "map": "Map overview", "monitoring": "Monitoring overview",
          "survey": "Survey overview"}


def _export(d, params):
    """(view, charts, title) of the shown app under the request's filters; Explorer has no title."""
    f = filters.parse(params, d.columns, _base(d)[1])
    v, shown = _view(d, f), _shown(d, params)
    a = _appview(d, f, shown, None, _pick(d, shown, params))
    if shown == "business":
        return v, business.export(a), TITLES[shown]
    if shown == "map":
        return v, geo.export(a, d.columns, v["typed"], v["mapping"], config.get()), TITLES[shown]
    if shown == "monitoring":
        return v, monitoring.export(a), TITLES[shown]
    if shown == "survey":
        return v, survey.export(a), TITLES[shown]
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
    return _download(d, "pptx", export.pptx(d, charts, filters.summary(v["labels"]), shown, title or "Data overview"), "application/vnd.openxmlformats-officedocument.presentationml.presentation")
