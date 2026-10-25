"""Web app entry point. Run locally: uvicorn app.main:app --port 8000"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"title": "DataBoot"})


@app.get("/health")
def health():
    return {"ok": True}
