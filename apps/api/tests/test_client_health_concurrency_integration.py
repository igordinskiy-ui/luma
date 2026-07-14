"""Concurrent duplicate telemetry requests persist a single event."""
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import AnalyticsEvent, User
from app.session import issue_session


def test_concurrent_client_session_start_is_applied_once(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "client-health-concurrency-secret-at-least-32")
    db = SessionLocal()
    user = User(telegram_id="client-health-concurrency")
    db.add(user); db.commit(); db.refresh(user)
    token = issue_session(user.id, user.auth_version)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"event": "session_started", "client_session_id": "33333333-3333-4333-8333-333333333333"}

    def send() -> int:
        with TestClient(app) as client:
            return client.post("/v1/client-telemetry", headers=headers, json=payload).status_code

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(lambda _: send(), range(8)))
        assert statuses == [204] * 8
        db.expire_all()
        assert db.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.user_id == user.id, AnalyticsEvent.event_name == "client_session_started")) == 1
    finally:
        db.close()
