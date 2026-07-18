"""Reliable outbox worker: database claims + Redis singleton lock for beta deployments."""
import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import and_, delete, or_, select, update
from pywebpush import WebPushException, webpush
from .api_time import utc_epoch, utc_now
from .config import public_launch_open, settings, validate_security_settings
from .db import SessionLocal
from .models import AnalyticsEvent, Feedback, NotificationDelivery, OutboxEvent, PushSubscription, QuitPlan, User
from .notifications import can_send, create_delivery
from .risk import assess
from .redis_lock import OUTBOX_WORKER_LOCK_KEY, release_worker_lock

MAX_ATTEMPTS = 5


def retention_cleanup(now: datetime | None = None) -> dict[str, int]:
    """Delete only categories covered by configured retention periods."""
    db = SessionLocal(); current = now or utc_now()
    try:
        statements = {
            "outbox": delete(OutboxEvent).where(OutboxEvent.status.in_(["processed", "failed"]), OutboxEvent.created_at < current - timedelta(days=settings.outbox_retention_days)),
            "deliveries": delete(NotificationDelivery).where(NotificationDelivery.created_at < current - timedelta(days=settings.delivery_retention_days)),
            "analytics": delete(AnalyticsEvent).where(AnalyticsEvent.created_at < current - timedelta(days=settings.analytics_retention_days)),
            "feedback": delete(Feedback).where(Feedback.status == "resolved", Feedback.resolved_at < current - timedelta(days=settings.feedback_retention_days)),
        }
        result = {name: db.execute(statement).rowcount or 0 for name, statement in statements.items()}
        db.commit(); return result
    finally: db.close()

def claim_events() -> list[int]:
    db = SessionLocal()
    try:
        now = utc_now()
        stale_before = now - timedelta(minutes=5)
        db.execute(update(OutboxEvent).where(OutboxEvent.status == "processing", OutboxEvent.locked_at < stale_before, OutboxEvent.attempts >= MAX_ATTEMPTS).values(status="failed", error="attempt_limit", locked_at=None))
        stale = and_(OutboxEvent.status == "processing", OutboxEvent.locked_at < stale_before, OutboxEvent.attempts < MAX_ATTEMPTS)
        pending = and_(OutboxEvent.status == "pending", OutboxEvent.attempts < MAX_ATTEMPTS, or_(OutboxEvent.next_attempt_at.is_(None), OutboxEvent.next_attempt_at <= now))
        events = list(db.scalars(select(OutboxEvent).where(or_(pending, stale)).order_by(OutboxEvent.id).with_for_update(skip_locked=True).limit(25)))
        for event in events:
            event.status, event.locked_at, event.attempts = "processing", now, event.attempts + 1
        db.commit(); return [event.id for event in events]
    finally: db.close()

async def process_event(bot: Bot | None, event_id: int) -> None:
    db = SessionLocal()
    try:
        event = db.get(OutboxEvent, event_id)
        if not event or event.status != "processing": return
        user = db.get(User, event.user_id)
        if not user or event.topic not in {"behavior.craving", "recovery.requested", "quit_plan.created", "scheduled.checkin", "notification.test"}:
            event.status = "processed"; db.commit(); return
        _, intervention, _ = assess(db, user.id)
        template = "test" if event.topic == "notification.test" else "coping" if event.topic == "behavior.craving" else "recovery"
        delivery = create_delivery(db, user, template, event.id)
        if not delivery:
            event.status = "processed"; db.commit(); return
        delivery.attempts += 1
        try:
            if not bot: raise RuntimeError("Telegram delivery is not configured")
            await bot.send_message(int(user.telegram_id), intervention)
            delivery.status, delivery.sent_at, event.status = "sent", utc_now(), "processed"
        except Exception as exc:
            subscriptions = list(db.scalars(select(PushSubscription).where(PushSubscription.user_id == user.id)))
            sent_web_push = False
            if settings.vapid_private_key and subscriptions:
                for subscription in subscriptions:
                    try:
                        await asyncio.to_thread(webpush, {"endpoint": subscription.endpoint, "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth}}, data=intervention, vapid_private_key=settings.vapid_private_key, vapid_claims={"sub": settings.vapid_subject})
                        sent_web_push = True
                    except WebPushException as push_error:
                        response = getattr(push_error, "response", None)
                        if getattr(response, "status_code", None) in {404, 410}:
                            db.delete(subscription)
                    except Exception:
                        # Existing rows may predate current key validation, and
                        # provider libraries can reject malformed key material
                        # with non-WebPushException types. One subscription must
                        # never terminate the shared worker.
                        continue
            if sent_web_push:
                delivery.channel, delivery.status, delivery.sent_at, event.status = "web_push", "sent", utc_now(), "processed"
            else:
                delivery.status = "failed"
                # Provider exceptions can contain endpoints or response bodies.
                event.error = type(exc).__name__
                if event.attempts >= MAX_ATTEMPTS: event.status = "failed"
                else:
                    event.status = "pending"
                    event.next_attempt_at = utc_now() + timedelta(minutes=2 ** event.attempts)
        db.commit()
    finally: db.close()

async def process_once() -> int:
    if not public_launch_open(): return 0
    if not settings.telegram_bot_token and not settings.vapid_private_key: return 0
    bot = Bot(settings.telegram_bot_token) if settings.telegram_bot_token else None
    try:
        event_ids = claim_events()
        for event_id in event_ids:
            try:
                await process_event(bot, event_id)
            except Exception as exc:
                # Keep one corrupt row or provider/library defect from taking
                # down delivery for every user. The durable row still follows
                # the bounded retry policy and exposes only an exception type.
                db = SessionLocal()
                try:
                    event = db.get(OutboxEvent, event_id)
                    if event and event.status == "processing":
                        event.error = type(exc).__name__
                        if event.attempts >= MAX_ATTEMPTS:
                            event.status = "failed"
                        else:
                            event.status = "pending"
                            event.next_attempt_at = utc_now() + timedelta(minutes=2 ** event.attempts)
                        db.commit()
                finally:
                    db.close()
        return len(event_ids)
    finally:
        if bot: await bot.session.close()

def schedule_checkins() -> int:
    """Create at most one deterministic check-in per quit user at 10/15/20 local time."""
    if not public_launch_open(): return 0
    db = SessionLocal(); created = 0
    try:
        now = utc_now()
        for plan in db.scalars(select(QuitPlan).where(QuitPlan.phase == "quit")):
            user = db.get(User, plan.user_id)
            if not user: continue
            try: local = now.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(user.timezone))
            except Exception: continue
            if local.hour not in {10, 15, 20} or local.minute > 1: continue
            # Do not manufacture outbox/delivery history for muted users,
            # quiet hours or an already exhausted local-day allowance.
            if not can_send(db, user): continue
            marker = f"scheduled-{local:%Y%m%d%H}"
            exists = db.scalar(select(NotificationDelivery.id).where(NotificationDelivery.user_id == user.id, NotificationDelivery.template == marker))
            if exists: continue
            db.add(OutboxEvent(user_id=user.id, topic="scheduled.checkin", payload="{}"))
            db.add(NotificationDelivery(user_id=user.id, channel="pending", template=marker, status="scheduled"))
            created += 1
        db.commit()
    finally: db.close()
    return created

async def main():
    validate_security_settings()
    redis = Redis.from_url(settings.redis_url)
    last_retention = 0.0
    try:
        while True:
            # A single beta worker avoids duplicate Telegram sends; DB row claims remain the durable guard.
            lock_token = str(uuid.uuid4())
            if await redis.set(OUTBOX_WORKER_LOCK_KEY, lock_token, ex=30, nx=True):
                try:
                    schedule_checkins()
                    await process_once()
                    await redis.set("kurilka:worker:heartbeat", str(utc_epoch()), ex=120)
                    if time.monotonic() - last_retention >= 3600:
                        retention_cleanup()
                        last_retention = time.monotonic()
                finally:
                    await release_worker_lock(redis, lock_token)
            await asyncio.sleep(15)
    finally: await redis.aclose()

if __name__ == "__main__": asyncio.run(main())
