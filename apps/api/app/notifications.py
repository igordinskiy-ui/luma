from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .models import NotificationDelivery, NotificationPreference, User


def lock_delivery_barrier(db: Session, user_id: int) -> None:
    """Serialize opt-out/erasure with a provider attempt held in this transaction."""
    db.scalar(
        select(NotificationPreference)
        .where(NotificationPreference.user_id == user_id)
        .with_for_update()
    )

def can_send(db: Session, user: User, *, lock_preference: bool = False) -> bool:
    preference_query = select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    if lock_preference:
        preference_query = preference_query.with_for_update()
    pref = db.scalar(preference_query)
    if not pref or not pref.enabled: return False
    try: local_now = datetime.now(timezone.utc).astimezone(ZoneInfo(user.timezone))
    except Exception: local_now = datetime.now(timezone.utc)
    hour = local_now.hour
    quiet = pref.quiet_start <= hour or hour < pref.quiet_end if pref.quiet_start > pref.quiet_end else pref.quiet_start <= hour < pref.quiet_end
    if quiet: return False
    day_start_utc = datetime.combine(local_now.date(), time.min, tzinfo=local_now.tzinfo).astimezone(timezone.utc).replace(tzinfo=None)
    sent = db.scalar(select(func.count(NotificationDelivery.id)).where(NotificationDelivery.user_id == user.id, NotificationDelivery.status == "sent", NotificationDelivery.created_at >= day_start_utc)) or 0
    return sent < pref.max_daily

def create_delivery(db: Session, user: User, template: str, outbox_event_id: int | None = None) -> NotificationDelivery | None:
    # Keep the preference row locked until the provider attempt commits. A
    # concurrent opt-out therefore cannot return success while a later send is
    # still able to start from stale preference state.
    if not can_send(db, user, lock_preference=True): return None
    if outbox_event_id:
        existing = db.scalar(select(NotificationDelivery).where(NotificationDelivery.outbox_event_id == outbox_event_id))
        if existing:
            return None if existing.status == "sent" else existing
    # SQLAlchemy column defaults are applied on INSERT, while the worker
    # increments this new object before the first flush.
    delivery = NotificationDelivery(user_id=user.id, outbox_event_id=outbox_event_id, channel="telegram", template=template, status="queued", attempts=0)
    db.add(delivery); return delivery
