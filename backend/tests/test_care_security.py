from fastapi.testclient import TestClient

from server import app


def test_protected_route_requires_authentication():
    with TestClient(app) as client:
        response = client.get("/api/v1/records")
    assert response.status_code == 401
