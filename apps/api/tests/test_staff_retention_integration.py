"""Staff cohort retention uses complete, non-cumulative D1/D7/D14 windows."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.auth import current_user
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import BehaviorEvent, CopingSession, QuitPlan, User


def test_retention_uses_exact_complete_windows(monkeypatch):
    now = datetime.utcnow()
    db = SessionLocal()
    admin = User(telegram_id="retention-window-admin", acquisition_source="retention_window_test", created_at=now)
    d7_and_d14 = User(telegram_id="retention-window-hit", acquisition_source="retention_window_test", created_at=now - timedelta(days=20))
    late_only = User(telegram_id="retention-window-late", acquisition_source="retention_window_test", created_at=now - timedelta(days=20))
    d1 = User(telegram_id="retention-window-d1", acquisition_source="retention_window_test", created_at=now - timedelta(days=3))
    too_young = User(telegram_id="retention-window-young", acquisition_source="retention_window_test", created_at=now - timedelta(days=1))
    db.add_all([admin, d7_and_d14, late_only, d1, too_young]); db.flush()
    db.add_all([
        BehaviorEvent(user_id=d7_and_d14.id, kind="craving", client_event_id="retention-d7-hit", created_at=d7_and_d14.created_at + timedelta(days=7, hours=12)),
        CopingSession(user_id=d7_and_d14.id, client_session_id="retention-d14-hit", source="dashboard", intensity_before=5, content_version="v1", status="active", started_at=d7_and_d14.created_at + timedelta(days=14, hours=12)),
        BehaviorEvent(user_id=late_only.id, kind="craving", client_event_id="retention-late-only", created_at=late_only.created_at + timedelta(days=16)),
        BehaviorEvent(user_id=d1.id, kind="craving", client_event_id="retention-d1-hit", created_at=d1.created_at + timedelta(days=1, hours=12)),
        BehaviorEvent(user_id=too_young.id, kind="craving", client_event_id="retention-young-hit", created_at=too_young.created_at + timedelta(hours=12)),
    ])
    db.commit()
    monkeypatch.setattr(settings, "admin_telegram_ids", admin.telegram_id)
    monkeypatch.setattr(settings, "acquisition_sources", "retention_window_test")
    app.dependency_overrides[current_user] = lambda: admin
    try:
        with TestClient(app) as client:
            response = client.get("/v1/admin/overview?period=30d&source=retention_window_test")
        assert response.status_code == 200
        assert response.json()["retention"] == {
            "d1": {"eligible": 3, "retained": 1, "rate": 0.3333},
            "d7": {"eligible": 2, "retained": 1, "rate": 0.5},
            "d14": {"eligible": 2, "retained": 1, "rate": 0.5},
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_first_action_requires_a_real_post_signup_24_hour_window(monkeypatch):
    now = datetime.utcnow()
    db = SessionLocal()
    admin = User(telegram_id="first-action-admin", acquisition_source="first_action_window", created_at=now)
    backdated = User(telegram_id="first-action-backdated", acquisition_source="first_action_window", created_at=now - timedelta(days=3))
    late = User(telegram_id="first-action-late", acquisition_source="first_action_window", created_at=now - timedelta(days=3))
    valid = User(telegram_id="first-action-valid", acquisition_source="first_action_window", created_at=now - timedelta(days=3))
    db.add_all([admin, backdated, late, valid]); db.flush()
    db.add_all([
        QuitPlan(user_id=backdated.id, phase="last_pack", remaining=5),
        QuitPlan(user_id=late.id, phase="last_pack", remaining=5),
        QuitPlan(user_id=valid.id, phase="last_pack", remaining=5),
        BehaviorEvent(user_id=backdated.id, kind="craving", client_event_id="first-action-before-signup", created_at=backdated.created_at - timedelta(minutes=1)),
        BehaviorEvent(user_id=late.id, kind="craving", client_event_id="first-action-after-window", created_at=late.created_at + timedelta(hours=25)),
        BehaviorEvent(user_id=valid.id, kind="craving", client_event_id="first-action-inside-window", created_at=valid.created_at + timedelta(hours=1)),
    ])
    db.commit()
    monkeypatch.setattr(settings, "admin_telegram_ids", admin.telegram_id)
    monkeypatch.setattr(settings, "acquisition_sources", "first_action_window")
    app.dependency_overrides[current_user] = lambda: admin
    try:
        with TestClient(app) as client:
            response = client.get("/v1/admin/overview?period=30d&source=first_action_window")
        assert response.status_code == 200
        assert response.json()["funnel"] == {
            "started": 4,
            "onboarded": 3,
            "first_action_24h": 1,
            "first_action_rate": 0.3333,
        }
    finally:
        app.dependency_overrides.clear()
        db.close()
