"""Deterministic delivery fallback, expiry and retry coverage for the outbox worker."""
from datetime import datetime, timedelta

import pytest
from pywebpush import WebPushException
from sqlalchemy import select

from app import worker
from app.config import settings
from app.db import SessionLocal
from app.models import NotificationDelivery, NotificationPreference, OutboxEvent, PushSubscription, User


class FailingTelegram:
    async def send_message(self, _telegram_id: int, _text: str) -> None:
        raise RuntimeError("telegram unavailable")


def create_processing_event(name: str, *, attempts: int = 1, with_push: bool = True) -> tuple[int, int]:
    db = SessionLocal()
    user = User(telegram_id=name, timezone="UTC")
    db.add(user); db.flush()
    db.add(NotificationPreference(user_id=user.id, enabled=True, max_daily=5, quiet_start=0, quiet_end=0))
    if with_push:
        db.add(PushSubscription(user_id=user.id, endpoint=f"https://fcm.googleapis.com/{name}", p256dh="p256dh", auth="auth"))
    event = OutboxEvent(user_id=user.id, topic="notification.test", payload="{}", status="processing", attempts=attempts, locked_at=datetime.utcnow())
    db.add(event); db.commit()
    result = (user.id, event.id)
    db.close()
    return result


@pytest.mark.asyncio
async def test_telegram_failure_falls_back_to_web_push(monkeypatch):
    user_id, event_id = create_processing_event("710000001")
    calls: list[str] = []
    monkeypatch.setattr(settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(worker, "webpush", lambda subscription, **_kwargs: calls.append(subscription["endpoint"]))

    await worker.process_event(FailingTelegram(), event_id)

    db = SessionLocal()
    try:
        event = db.get(OutboxEvent, event_id)
        delivery = db.scalar(select(NotificationDelivery).where(NotificationDelivery.outbox_event_id == event_id))
        assert event is not None and event.status == "processed"
        assert delivery is not None and delivery.status == "sent" and delivery.channel == "web_push"
        assert delivery.attempts == 1 and delivery.sent_at is not None
        assert calls == ["https://fcm.googleapis.com/710000001"]
        assert db.scalar(select(PushSubscription).where(PushSubscription.user_id == user_id)) is not None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_expired_push_is_deleted_and_event_is_scheduled_for_retry(monkeypatch):
    user_id, event_id = create_processing_event("710000002")

    class GoneResponse:
        status_code = 410

    def expired_push(*_args, **_kwargs):
        raise WebPushException("subscription expired", response=GoneResponse())

    monkeypatch.setattr(settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(worker, "webpush", expired_push)

    await worker.process_event(FailingTelegram(), event_id)

    db = SessionLocal()
    try:
        event = db.get(OutboxEvent, event_id)
        delivery = db.scalar(select(NotificationDelivery).where(NotificationDelivery.outbox_event_id == event_id))
        assert event is not None and event.status == "pending" and event.next_attempt_at is not None
        assert event.error == "RuntimeError"
        assert delivery is not None and delivery.status == "failed"
        assert db.scalar(select(PushSubscription).where(PushSubscription.user_id == user_id)) is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_worker_stops_retrying_after_max_attempts(monkeypatch):
    _user_id, event_id = create_processing_event("710000003", attempts=worker.MAX_ATTEMPTS, with_push=False)
    monkeypatch.setattr(settings, "vapid_private_key", "")

    await worker.process_event(FailingTelegram(), event_id)

    db = SessionLocal()
    try:
        event = db.get(OutboxEvent, event_id)
        delivery = db.scalar(select(NotificationDelivery).where(NotificationDelivery.outbox_event_id == event_id))
        assert event is not None and event.status == "failed" and event.next_attempt_at is None
        assert event.error == "RuntimeError"
        assert delivery is not None and delivery.status == "failed" and delivery.attempts == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_malformed_legacy_push_key_cannot_crash_worker(monkeypatch):
    _user_id, event_id = create_processing_event("710000004")
    monkeypatch.setattr(settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(worker, "webpush", lambda *_args, **_kwargs: (_ for _ in ()).throw(IndexError("invalid key")))

    await worker.process_event(FailingTelegram(), event_id)

    db = SessionLocal()
    try:
        event = db.get(OutboxEvent, event_id)
        assert event is not None and event.status == "pending"
        assert event.next_attempt_at is not None
    finally:
        db.close()


def test_stale_event_at_attempt_limit_is_failed_not_reclaimed():
    _user_id, event_id = create_processing_event("710000005", attempts=worker.MAX_ATTEMPTS, with_push=False)
    db = SessionLocal()
    try:
        event = db.get(OutboxEvent, event_id)
        event.locked_at = datetime.utcnow() - timedelta(minutes=10)
        db.commit()
    finally:
        db.close()

    assert event_id not in worker.claim_events()
    db = SessionLocal()
    try:
        event = db.get(OutboxEvent, event_id)
        assert event is not None and event.status == "failed" and event.error == "attempt_limit"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_process_once_isolates_an_unexpected_event_failure(monkeypatch):
    _user_id, event_id = create_processing_event("710000006", attempts=worker.MAX_ATTEMPTS, with_push=False)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "vapid_private_key", "configured")
    monkeypatch.setattr(worker, "claim_events", lambda: [event_id])

    async def fail_event(_bot, _event_id):
        raise TypeError("unexpected row failure")

    monkeypatch.setattr(worker, "process_event", fail_event)
    assert await worker.process_once() == 1

    db = SessionLocal()
    try:
        event = db.get(OutboxEvent, event_id)
        assert event is not None and event.status == "failed" and event.error == "TypeError"
    finally:
        db.close()
