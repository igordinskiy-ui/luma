"""Runs in CI's Python 3.12 environment with the full API dependency set."""
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth import current_user
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import NotificationPreference, OutboxEvent, PushSubscription, User


def test_notification_opt_in_test_dedupe_and_unsubscribe(monkeypatch):
    db = SessionLocal()
    user = User(telegram_id="123456789")
    db.add(user); db.flush()
    db.add(NotificationPreference(user_id=user.id, enabled=True, max_daily=3, quiet_start=0, quiet_end=0))
    db.add(PushSubscription(user_id=user.id, endpoint="https://fcm.googleapis.com/test-notification", p256dh="p256dh-key", auth="auth-key"))
    db.commit()
    monkeypatch.setattr(settings, "telegram_bot_token", "configured-for-test")
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            first = client.post("/v1/notifications/test")
            repeated = client.post("/v1/notifications/test")
            assert first.status_code == 202 and repeated.status_code == 202
            assert first.json()["duplicate"] is False and repeated.json()["duplicate"] is True
            assert db.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.user_id == user.id, OutboxEvent.topic == "notification.test")) == 1

            removed = client.delete("/v1/push-subscription")
            assert removed.status_code == 204
            assert db.scalar(select(func.count(PushSubscription.id)).where(PushSubscription.user_id == user.id)) == 0

            preference = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
            preference.enabled = False; db.commit()
            assert client.post("/v1/notifications/test").status_code == 409
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_push_endpoint_cannot_be_silently_moved_between_users():
    db = SessionLocal()
    owner = User(telegram_id="push-owner")
    newcomer = User(telegram_id="push-newcomer")
    db.add_all([owner, newcomer]); db.flush()
    endpoint = "https://fcm.googleapis.com/shared-device-endpoint"
    db.add(PushSubscription(user_id=owner.id, endpoint=endpoint, p256dh="owner-key", auth="owner-auth"))
    db.commit()
    app.dependency_overrides[current_user] = lambda: newcomer
    try:
        with TestClient(app) as client:
            response = client.put("/v1/push-subscription", json={"endpoint": endpoint, "p256dh": "new-key-1", "auth": "new-auth-1"})
            assert response.status_code == 409
            db.expire_all()
            stored = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
            assert stored is not None and stored.user_id == owner.id and stored.p256dh == "owner-key"
    finally:
        app.dependency_overrides.clear()
        db.close()
