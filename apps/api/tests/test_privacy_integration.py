"""Runs in CI's Python 3.12 environment with the full API dependency set."""
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth import current_user
from app.db import SessionLocal
from app.main import app
from app.models import BehaviorEvent, ConsentRecord, CopingSession, PushSubscription, QuitAttempt, QuitPlan, User


def test_export_delete_and_fresh_onboarding_after_return():
    db = SessionLocal()
    user = User(telegram_id="privacy-lifecycle-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    db.add(ConsentRecord(user_id=user.id, document_version="2026-07-15", document_digest="a" * 64, source="onboarding", age_confirmed=True, accepted_at=datetime.utcnow()))
    other = User(telegram_id="privacy-consent-owner")
    db.add(other); db.flush()
    db.add(ConsentRecord(user_id=other.id, document_version="other", document_digest="b" * 64, source="legacy", age_confirmed=True, accepted_at=datetime.utcnow()))
    db.add(QuitPlan(user_id=user.id, phase="quit", remaining=0, cigarettes_per_pack=20, quit_started_at=datetime.utcnow()))
    db.add(QuitAttempt(user_id=user.id, started_at=datetime.utcnow()))
    db.add(BehaviorEvent(user_id=user.id, kind="craving", trigger="coffee", intensity=5, note="", client_event_id="privacy-event-0001"))
    db.add(CopingSession(user_id=user.id, client_session_id="privacy-coping-0001", source="dashboard", trigger="coffee", intensity_before=5, technique="water", content_version="v1", status="active"))
    db.add(PushSubscription(user_id=user.id, endpoint="https://fcm.googleapis.com/privacy-test", p256dh="p256dh-key", auth="auth-key"))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            exported = client.get("/v1/privacy-export")
            assert exported.status_code == 200
            payload = exported.json()
            assert payload["account"]["age_confirmed_at"] is not None
            assert len(payload["consent_history"]) == 1
            assert payload["consent_history"][0] | {"accepted_at": None} == {
                "document_version": "2026-07-15",
                "document_digest": "a" * 64,
                "source": "onboarding",
                "age_confirmed": True,
                "accepted_at": None,
            }
            assert payload["quit_plan"]["cigarettes_per_pack"] == 20
            assert len(payload["quit_attempts"]) == 1
            assert len(payload["coping_sessions"]) == 1
            assert len(payload["push_subscriptions"]) == 1

            assert client.delete("/v1/account").status_code == 204
            assert db.scalar(select(func.count(User.id)).where(User.telegram_id == "privacy-lifecycle-user")) == 0
            assert db.scalar(select(func.count(CopingSession.id)).where(CopingSession.user_id == user.id)) == 0
            assert db.scalar(select(func.count(PushSubscription.id)).where(PushSubscription.user_id == user.id)) == 0
            assert db.scalar(select(func.count(ConsentRecord.id)).where(ConsentRecord.user_id == user.id)) == 0
            assert db.scalar(select(func.count(ConsentRecord.id)).where(ConsentRecord.user_id == other.id)) == 1

            returning = User(telegram_id="privacy-lifecycle-user")
            db.add(returning); db.commit()
            app.dependency_overrides[current_user] = lambda: returning
            assert client.get("/v1/dashboard").status_code == 428
    finally:
        app.dependency_overrides.clear()
        db.close()
