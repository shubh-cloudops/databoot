# Web app template

FastAPI with server-rendered Jinja pages and pytest. No build step, no JavaScript framework.

- Run: `uvicorn app.main:app --port 8000`
- Test: `python -m pytest -q`
- Pages live in `app/templates/`, routes in `app/main.py`, tests in `tests/`.
