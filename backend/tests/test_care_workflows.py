from fastapi.testclient import TestClient

from server import app


def test_signup_and_login():
    with TestClient(app) as client:
        signup = client.post("/api/v1/auth/signup", json={"email": "patient@example.com", "password": "local-password", "name": "Synthetic Patient"})
        assert signup.status_code == 200
        login = client.post("/api/v1/auth/login", json={"email": "patient@example.com", "password": "local-password"})
        assert login.status_code == 200
        assert login.json()["access_token"]


def test_partner_signup_is_pending_and_cannot_login():
    with TestClient(app) as client:
        signup = client.post("/api/v1/auth/signup", json={"email": "lab@example.com", "password": "local-password", "role": "LAB", "name": "Synthetic Lab"})
        assert signup.status_code == 200
        assert signup.json()["status"] == "PENDING_APPROVAL"
        login = client.post("/api/v1/auth/login", json={"email": "lab@example.com", "password": "local-password"})
        assert login.status_code == 403
