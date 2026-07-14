"""Runs in CI's Python 3.12 environment with the full API dependency set."""
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import current_user
from app.db import SessionLocal
from app.main import app
from app.models import AnalyticsEvent, CopingSession, User


def test_coping_session_is_idempotent_owned_and_exported():
    db = SessionLocal()
    user = User(telegram_id="coping-integration-user", age_confirmed_at=datetime.utcnow())
    other = User(telegram_id="coping-other-user", age_confirmed_at=datetime.utcnow())
    db.add_all([user, other]); db.commit()
    app.dependency_overrides[current_user] = lambda: user
    payload = {"client_session_id": "coping-session-0001", "source": "dashboard", "trigger": "coffee", "intensity_before": 7}
    try:
        with TestClient(app) as client:
            first = client.post("/v1/coping-sessions", json=payload)
            repeated = client.post("/v1/coping-sessions", json=payload)
            assert first.status_code == 201 and repeated.status_code == 201
            assert first.json()["id"] == repeated.json()["id"]
            session_id = first.json()["id"]

            selected = client.patch(f"/v1/coping-sessions/{session_id}", json={"technique": "water"})
            assert selected.status_code == 200
            completed = client.patch(f"/v1/coping-sessions/{session_id}", json={"status": "completed", "intensity_after": 3})
            assert completed.status_code == 200
            assert completed.json()["status"] == "completed"
            duplicate = client.patch(f"/v1/coping-sessions/{session_id}", json={"status": "completed", "intensity_after": 3})
            assert duplicate.status_code == 200
            assert duplicate.json()["status"] == "completed"
            assert client.patch(f"/v1/coping-sessions/{session_id}", json={"status": "active"}).status_code == 409

            app.dependency_overrides[current_user] = lambda: other
            assert client.patch(f"/v1/coping-sessions/{session_id}", json={"status": "paused"}).status_code == 404
            app.dependency_overrides[current_user] = lambda: user
            exported = client.get("/v1/privacy-export")
            assert any(item["client_session_id"] == payload["client_session_id"] for item in exported.json()["coping_sessions"])

        assert len(list(db.scalars(select(CopingSession).where(CopingSession.user_id == user.id)))) == 1
        analytics = list(db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.user_id == user.id).order_by(AnalyticsEvent.id)))
        assert analytics == []
        assert all("client_session_id" not in item.properties and "note" not in item.properties for item in analytics)
    finally:
        app.dependency_overrides.clear()
        db.close()
