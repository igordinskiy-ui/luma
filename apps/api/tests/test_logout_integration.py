"""Server logout must revoke an already issued bearer token."""
import importlib

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import NotificationPreference, PushSubscription, User
from app.session import issue_session


def test_logout_rotates_auth_version_and_rejects_old_token(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "logout-integration-secret-at-least-32")
    main_module = importlib.import_module("app.main")
    original_barrier = main_module.lock_delivery_barrier
    barrier_calls = []
    monkeypatch.setattr(main_module, "lock_delivery_barrier", lambda session, user_id: (barrier_calls.append(user_id), original_barrier(session, user_id))[1])
    db = SessionLocal()
    user = User(telegram_id="logout-integration-user")
    db.add(user); db.commit(); db.refresh(user)
    db.add(NotificationPreference(user_id=user.id, enabled=True))
    db.add(PushSubscription(user_id=user.id, endpoint="https://push.example/logout-device", p256dh="key", auth="auth"))
    db.commit()
    token = issue_session(user.id, user.auth_version)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with TestClient(app) as client:
            assert client.get("/v1/bootstrap", headers=headers).status_code == 200
            assert client.post("/v1/logout", headers=headers).status_code == 204
            assert client.get("/v1/bootstrap", headers=headers).status_code == 401
            db.expire_all()
            assert barrier_calls == [user.id]
            assert db.scalar(select(PushSubscription).where(PushSubscription.user_id == user.id)) is None
    finally:
        db.close()
