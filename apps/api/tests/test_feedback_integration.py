"""Runs in CI's Python 3.12 environment with the full API dependency set."""
import pytest

from fastapi.testclient import TestClient

from app.auth import current_user
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import User


def test_feedback_is_exported_and_staff_can_triage(monkeypatch):
    db = SessionLocal()
    user = User(telegram_id="feedback-integration-user")
    db.add(user)
    db.commit()
    db.refresh(user)
    monkeypatch.setattr(settings, "admin_telegram_ids", user.telegram_id)
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            created = client.post("/v1/feedback", json={"category": "idea", "body": "Add a shorter check-in."})
            assert created.status_code == 201
            feedback_id = created.json()["feedback_id"]

            overview = client.get("/v1/admin/overview")
            assert overview.status_code == 200
            assert overview.json()["open_feedback"] >= 1
            assert set(overview.json()["retention"]) == {"d1", "d7", "d14"}
            assert "mute_rate" in overview.json()["notification_health"]

            queue = client.get("/v1/admin/feedback")
            assert queue.status_code == 200
            assert any(item["id"] == feedback_id for item in queue.json())
            assert all("user_id" not in item for item in queue.json())

            resolved = client.patch(f"/v1/admin/feedback/{feedback_id}", json={"status": "resolved"})
            assert resolved.status_code == 200
            assert resolved.json()["status"] == "resolved"

            export = client.get("/v1/privacy-export")
            assert export.status_code == 200
            assert any(item["body"] == "Add a shorter check-in." for item in export.json()["feedback"])
    finally:
        app.dependency_overrides.clear()
        db.close()
