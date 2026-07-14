"""Runs in CI's Python 3.12 environment with the full API dependency set."""
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import AnalyticsEvent, Feedback, NotificationDelivery, OutboxEvent, User
from app.worker import retention_cleanup


def test_retention_removes_only_expired_terminal_records(monkeypatch):
    db = SessionLocal(); now = datetime.utcnow()
    user = User(telegram_id="retention-integration-user")
    db.add(user); db.flush()
    db.add_all([
        OutboxEvent(user_id=user.id, topic="old", payload="{}", status="processed", created_at=now - timedelta(days=31)),
        OutboxEvent(user_id=user.id, topic="pending", payload="{}", status="pending", created_at=now - timedelta(days=31)),
        NotificationDelivery(user_id=user.id, channel="telegram", template="old", status="sent", created_at=now - timedelta(days=91)),
        AnalyticsEvent(user_id=user.id, event_name="account_deleted", properties="{}", created_at=now - timedelta(days=181)),
        Feedback(user_id=user.id, category="idea", body="old resolved", status="resolved", resolved_at=now - timedelta(days=366), created_at=now - timedelta(days=400)),
    ])
    db.commit(); db.close()
    for name, value in (("outbox_retention_days", 30), ("delivery_retention_days", 90), ("analytics_retention_days", 180), ("feedback_retention_days", 365)):
        monkeypatch.setattr(settings, name, value)

    result = retention_cleanup(now)

    check = SessionLocal()
    try:
        assert result == {"outbox": 1, "deliveries": 1, "analytics": 1, "feedback": 1}
        assert check.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.user_id == user.id)) == 1
    finally: check.close()
