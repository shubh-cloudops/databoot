"""Web app entry point. Run locally: uvicorn app.main:app --port 8000"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"title": "Home"})


@app.get("/health")
def health():
    return {"ok": True}
