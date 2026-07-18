"""Scheduled check-ins respect opt-in, quiet hours, limits and deduplication."""
from datetime import datetime

from sqlalchemy import func, select

from app import notifications, worker
from app.db import SessionLocal
from app.models import NotificationDelivery, NotificationPreference, OutboxEvent, QuitPlan, User


class TenUtc(datetime):
    @classmethod
    def utcnow(cls):
        return cls(2026, 7, 14, 10, 0, 0)

    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 14, 10, 0, 0, tzinfo=tz)


class FifteenUtc(datetime):
    @classmethod
    def utcnow(cls):
        return cls(2026, 7, 14, 15, 0, 0)

    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 14, 15, 0, 0, tzinfo=tz)


def add_quit_user(db, telegram_id: str, *, enabled: bool, max_daily: int = 3, quiet_start: int = 22, quiet_end: int = 9) -> User:
    user = User(telegram_id=telegram_id, timezone="UTC")
    db.add(user); db.flush()
    db.add(QuitPlan(user_id=user.id, phase="quit", remaining=0))
    db.add(NotificationPreference(user_id=user.id, enabled=enabled, max_daily=max_daily, quiet_start=quiet_start, quiet_end=quiet_end))
    return user


def test_scheduler_creates_history_only_for_currently_sendable_users(monkeypatch):
    db = SessionLocal()
    allowed = add_quit_user(db, "schedule-allowed", enabled=True, max_daily=1)
    muted = add_quit_user(db, "schedule-muted", enabled=False)
    quiet = add_quit_user(db, "schedule-quiet", enabled=True, quiet_start=9, quiet_end=18)
    db.commit()
    monkeypatch.setattr(worker, "utc_now", TenUtc.utcnow)
    monkeypatch.setattr(notifications, "datetime", TenUtc)

    assert worker.schedule_checkins() == 1
    assert worker.schedule_checkins() == 0

    check = SessionLocal()
    try:
        assert check.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.user_id == allowed.id)) == 1
        assert check.scalar(select(func.count(NotificationDelivery.id)).where(NotificationDelivery.user_id == allowed.id, NotificationDelivery.status == "scheduled")) == 1
        assert check.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.user_id.in_([muted.id, quiet.id]))) == 0

        check.add(NotificationDelivery(user_id=allowed.id, channel="telegram", template="sent", status="sent", created_at=TenUtc.utcnow()))
        check.commit()
    finally:
        check.close()

    monkeypatch.setattr(worker, "utc_now", FifteenUtc.utcnow)
    monkeypatch.setattr(notifications, "datetime", FifteenUtc)
    assert worker.schedule_checkins() == 0
    db.close()
