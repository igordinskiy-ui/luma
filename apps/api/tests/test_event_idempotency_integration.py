"""Runs in CI's Python 3.12 environment with the full API dependency set."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from datetime import datetime, timedelta
from app.auth import current_user
from app.db import SessionLocal
from app.main import app
from app.models import QuitAttempt, QuitPlan, User

def test_repeated_offline_event_is_applied_once():
    db = SessionLocal()
    user = User(telegram_id="integration-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush(); db.add(QuitPlan(user_id=user.id, remaining=2, cigarettes_per_pack=20, phase="last_pack")); db.commit()
    app.dependency_overrides[current_user] = lambda: user
    payload = {"kind":"smoked","client_event_id":"offline-event-0001"}
    with TestClient(app) as client:
        first = client.post("/v1/events", json=payload)
        second = client.post("/v1/events", json=payload)
    app.dependency_overrides.clear()
    db.expire_all()
    plan = db.scalar(select(QuitPlan).where(QuitPlan.user_id == user.id))
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["duplicate"] is False and second.json()["duplicate"] is True
    assert plan is not None and plan.remaining == 1
    db.close()

def test_relapse_starts_two_hour_recovery_mode():
    db = SessionLocal()
    started_at = datetime.utcnow() - timedelta(days=2)
    user = User(telegram_id="recovery-integration-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    db.add(QuitPlan(user_id=user.id, remaining=0, cigarettes_per_pack=20, phase="quit", quit_started_at=started_at))
    db.add(QuitAttempt(user_id=user.id, started_at=started_at))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            response = client.post("/v1/events", json={"kind": "relapse", "client_event_id": "recovery-event-0001"})
            dashboard = client.get("/v1/dashboard")
        assert response.status_code == 200
        assert dashboard.status_code == 200
        assert dashboard.json()["recovery_until"] is not None
        assert dashboard.json()["recovery_until"].endswith("Z")
        assert len(dashboard.json()["recovery_steps"]) >= 3
        assert dashboard.json()["attempt_number"] == 2
        assert dashboard.json()["best_smoke_free_seconds"] >= 172800
        attempts = list(db.scalars(select(QuitAttempt).where(QuitAttempt.user_id == user.id).order_by(QuitAttempt.started_at)))
        assert len(attempts) == 2
        assert attempts[0].end_reason == "relapse"
    finally:
        app.dependency_overrides.clear()
        db.close()
