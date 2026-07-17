from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    auth_version: Mapped[int] = mapped_column(Integer, default=1)
    consent_version: Mapped[str] = mapped_column(String(32), default="")
    consent_digest: Mapped[str] = mapped_column(String(64), default="")
    consented_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    age_confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    acquisition_source: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        UniqueConstraint("user_id", "document_version", "document_digest", name="uq_consent_record_document"),
        CheckConstraint("source IN ('legacy','onboarding','reconsent')", name="ck_consent_record_source"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    document_version: Mapped[str] = mapped_column(String(32))
    document_digest: Mapped[str] = mapped_column(String(64), default="")
    source: Mapped[str] = mapped_column(String(24))
    age_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class QuitPlan(Base):
    __tablename__ = "quit_plans"
    __table_args__ = (CheckConstraint("remaining >= 0", name="ck_quit_plan_remaining_nonnegative"), CheckConstraint("phase IN ('preparation','last_pack','quit','paused')", name="ck_quit_plan_phase"), CheckConstraint("paused_from IS NULL OR paused_from IN ('preparation','last_pack','quit')", name="ck_quit_plan_paused_from"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    cigarettes_per_pack: Mapped[int] = mapped_column(Integer, default=20)
    remaining: Mapped[int] = mapped_column(Integer, default=0)
    pack_price: Mapped[float] = mapped_column(Float, default=0)
    phase: Mapped[str] = mapped_column(String(24), default="preparation")
    paused_from: Mapped[str] = mapped_column(String(24), nullable=True)
    quit_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    target_quit_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    recovery_until: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reasons: Mapped[str] = mapped_column(Text, default="")


class QuitAttempt(Base):
    __tablename__ = "quit_attempts"
    __table_args__ = (
        CheckConstraint("end_reason IS NULL OR end_reason IN ('paused','relapse','restarted')", name="ck_quit_attempt_end_reason"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    end_reason: Mapped[str] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BehaviorEvent(Base):
    __tablename__ = "behavior_events"
    __table_args__ = (UniqueConstraint("user_id", "client_event_id", name="uq_behavior_events_user_client_event"), CheckConstraint("kind IN ('smoked','craving','relapse')", name="ck_behavior_event_kind"), CheckConstraint("intensity IS NULL OR (intensity >= 1 AND intensity <= 5)", name="ck_behavior_event_intensity"), CheckConstraint("relapse_context IS NULL OR (kind = 'relapse' AND relapse_context IN ('one','day','days','afraid','angry','hopeless'))", name="ck_behavior_event_relapse_context"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    trigger: Mapped[str] = mapped_column(String(64), nullable=True)
    intensity: Mapped[int] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    relapse_context: Mapped[str] = mapped_column(String(24), nullable=True)
    client_event_id: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CopingSession(Base):
    __tablename__ = "coping_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "client_session_id", name="uq_coping_sessions_user_client_session"),
        CheckConstraint("source IN ('dashboard','journal','notification','offline')", name="ck_coping_session_source"),
        CheckConstraint("status IN ('active','paused','completed','abandoned')", name="ck_coping_session_status"),
        CheckConstraint("intensity_before >= 1 AND intensity_before <= 10", name="ck_coping_session_intensity_before"),
        CheckConstraint("intensity_after IS NULL OR (intensity_after >= 1 AND intensity_after <= 10)", name="ck_coping_session_intensity_after"),
        CheckConstraint("outcome IS NULL OR outcome IN ('helped','same','worse')", name="ck_coping_session_outcome"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    client_session_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(24))
    trigger: Mapped[str] = mapped_column(String(64), nullable=True)
    intensity_before: Mapped[int] = mapped_column(Integer)
    intensity_after: Mapped[int] = mapped_column(Integer, nullable=True)
    technique: Mapped[str] = mapped_column(String(32), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=True)
    content_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    topic: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    locked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    max_daily: Mapped[int] = mapped_column(Integer, default=3)
    quiet_start: Mapped[int] = mapped_column(Integer, default=22)
    quiet_end: Mapped[int] = mapped_column(Integer, default=9)

class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    outbox_event_id: Mapped[int] = mapped_column(Integer, nullable=True, unique=True)
    channel: Mapped[str] = mapped_column(String(24))
    template: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        Index(
            "uq_analytics_client_session_event",
            "user_id", "event_name", "properties",
            unique=True,
            sqlite_where=text("event_name IN ('client_session_started','client_crash')"),
            postgresql_where=text("event_name IN ('client_session_started','client_crash')"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_name: Mapped[str] = mapped_column(String(64), index=True)
    properties: Mapped[str] = mapped_column(Text, default="{}")
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Entitlement(Base):
    __tablename__ = "entitlements"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    feature: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(32), default="beta")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("category IN ('bug','idea','support','content')", name="ck_feedback_category"),
        CheckConstraint("status IN ('open','resolved')", name="ck_feedback_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(24))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
