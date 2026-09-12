from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_status():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # "database" reflects real connectivity - "ok" if Postgres is reachable,
    # "unreachable" otherwise (e.g. no DB running while iterating on the API).
    assert body["database"] in {"ok", "unreachable"}
