"""Queued or scheduled deliveries must not dilute the failure-rate denominator."""
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import current_user
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import NotificationDelivery, User


def test_delivery_failure_rate_uses_only_terminal_attempts(monkeypatch):
    db = SessionLocal()
    admin = User(telegram_id="delivery-metric-admin", acquisition_source="delivery_metric_test")
    db.add(admin); db.flush()
    db.add_all([
        NotificationDelivery(user_id=admin.id, channel="telegram", template="sent", status="sent", created_at=datetime.utcnow()),
        NotificationDelivery(user_id=admin.id, channel="telegram", template="failed", status="failed", created_at=datetime.utcnow()),
        *[NotificationDelivery(user_id=admin.id, channel="pending", template=f"queued-{index}", status="queued", created_at=datetime.utcnow()) for index in range(8)],
    ])
    db.commit()
    monkeypatch.setattr(settings, "admin_telegram_ids", admin.telegram_id)
    monkeypatch.setattr(settings, "acquisition_sources", "delivery_metric_test")
    app.dependency_overrides[current_user] = lambda: admin
    try:
        with TestClient(app) as client:
            response = client.get("/v1/admin/overview?period=30d&source=delivery_metric_test")
        assert response.status_code == 200
        health = response.json()["notification_health"]
        assert health["delivery_failures_last_24h"] == 1
        assert health["delivery_failure_rate"] == 0.5
        assert response.json()["deliveries_last_24h"] == {"failed": 1, "queued": 8, "sent": 1}
    finally:
        app.dependency_overrides.clear()
        db.close()
