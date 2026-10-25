from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_vendored_plotly_and_world_outlines_are_served_locally():
    js = client.get("/static/vendor/plotly/plotly.min.js")
    assert js.status_code == 200 and b"plotly.js v4.1.2" in js.content[:200]
    topo = client.get("/static/vendor/topojson/world_110m.json")
    assert topo.status_code == 200 and "countries" in topo.json()["objects"]
