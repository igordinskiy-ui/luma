from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_development_auth_requires_explicit_non_production_opt_in(monkeypatch):
    with TestClient(app) as client:
        assert "/v1/auth/development" not in client.get("/openapi.json").json()["paths"]

        monkeypatch.setattr(settings, "app_environment", "development")
        monkeypatch.setattr(settings, "development_auth_enabled", False)
        assert client.post("/v1/auth/development").status_code == 404

        monkeypatch.setattr(settings, "development_auth_enabled", True)
        response = client.post("/v1/auth/development")
        assert response.status_code == 200
        session = response.json()
        assert session["token_type"] == "bearer"
        assert client.get("/v1/bootstrap", headers={"Authorization": f"Bearer {session['access_token']}"}).status_code == 200

        monkeypatch.setattr(settings, "app_environment", "test")
        assert client.post("/v1/auth/development").status_code == 404

        monkeypatch.setattr(settings, "app_environment", "production")
        monkeypatch.setattr(settings, "public_launch_enabled", True)
        assert client.post("/v1/auth/development").status_code == 404
