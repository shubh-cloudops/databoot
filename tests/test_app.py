from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_home_and_health():
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"ok": True}
