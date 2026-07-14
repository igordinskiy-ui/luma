"""Deterministic notification opt-in, quiet-hours and daily-limit rules."""
from datetime import datetime as RealDateTime, timezone

from app import notifications
from app.db import SessionLocal
from app.models import NotificationDelivery, NotificationPreference, User


class NoonUtc(RealDateTime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
        return value if tz else value.replace(tzinfo=None)


def test_notifications_require_opt_in_and_respect_quiet_hours_and_limit(monkeypatch):
    monkeypatch.setattr(notifications, "datetime", NoonUtc)
    db = SessionLocal()
    user = User(telegram_id="notification-rules-user", timezone="UTC")
    db.add(user); db.flush()
    preference = NotificationPreference(user_id=user.id, enabled=False, max_daily=1, quiet_start=22, quiet_end=9)
    db.add(preference); db.commit()
    try:
        assert notifications.can_send(db, user) is False

        preference.enabled = True
        preference.quiet_start, preference.quiet_end = 9, 18
        db.commit()
        assert notifications.can_send(db, user) is False

        preference.quiet_start, preference.quiet_end = 22, 9
        db.commit()
        assert notifications.can_send(db, user) is True

        db.add(NotificationDelivery(user_id=user.id, channel="telegram", template="check", status="sent", created_at=NoonUtc(2026, 7, 14, 11, 0)))
        db.commit()
        assert notifications.can_send(db, user) is False
    finally:
        db.close()
