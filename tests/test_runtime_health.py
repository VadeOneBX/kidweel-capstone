from fastapi.testclient import TestClient

from qops.runtime.app import app


def test_health_shape():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "qops-api"
    assert body["paper_only"] is True


def test_status_shape():
    client = TestClient(app)
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["paper_only"] is True
