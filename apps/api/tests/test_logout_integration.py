"""Server logout must revoke an already issued bearer token."""
from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import User
from app.session import issue_session


def test_logout_rotates_auth_version_and_rejects_old_token(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "logout-integration-secret")
    db = SessionLocal()
    user = User(telegram_id="logout-integration-user")
    db.add(user); db.commit(); db.refresh(user)
    token = issue_session(user.id, user.auth_version)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with TestClient(app) as client:
            assert client.get("/v1/bootstrap", headers=headers).status_code == 200
            assert client.post("/v1/logout", headers=headers).status_code == 204
            assert client.get("/v1/bootstrap", headers=headers).status_code == 401
    finally:
        db.close()
