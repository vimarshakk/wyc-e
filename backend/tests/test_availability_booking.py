from fastapi.testclient import TestClient

from server import app


def test_availability_requires_authentication():
    with TestClient(app) as client:
        response = client.post("/api/v1/availability", json={"starts_at": "2026-11-10T10:00:00Z", "ends_at": "2026-11-10T10:30:00Z"})
    assert response.status_code == 401
