"""Privacy-safe client telemetry is idempotent and yields crash-free sessions."""
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth import current_user
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import AnalyticsEvent, User


def test_client_health_telemetry_is_idempotent_and_payload_free(monkeypatch):
    db = SessionLocal()
    admin = User(telegram_id="client-health-admin", acquisition_source="client_health_test")
    db.add(admin); db.commit(); db.refresh(admin)
    monkeypatch.setattr(settings, "admin_telegram_ids", admin.telegram_id)
    monkeypatch.setattr(settings, "acquisition_sources", "client_health_test")
    app.dependency_overrides[current_user] = lambda: admin
    first = "11111111-1111-4111-8111-111111111111"
    second = "22222222-2222-4222-8222-222222222222"
    try:
        with TestClient(app) as client:
            assert client.post("/v1/client-telemetry", json={"event": "session_started", "client_session_id": first}).status_code == 204
            assert client.post("/v1/client-telemetry", json={"event": "session_started", "client_session_id": first}).status_code == 204
            assert client.post("/v1/client-telemetry", json={"event": "crash", "client_session_id": first}).status_code == 204
            assert client.post("/v1/client-telemetry", json={"event": "session_started", "client_session_id": second}).status_code == 204
            overview = client.get("/v1/admin/overview?period=30d&source=client_health_test")
        assert overview.status_code == 200
        assert overview.json()["client_health"] == {"sessions": 2, "crashed": 1, "crash_free_rate": 0.5}
        assert db.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.user_id == admin.id, AnalyticsEvent.event_name == "client_session_started")) == 2
        payloads = " ".join(db.scalars(select(AnalyticsEvent.properties).where(AnalyticsEvent.user_id == admin.id)))
        assert first not in payloads and second not in payloads
        assert "stack" not in payloads and "url" not in payloads
    finally:
        app.dependency_overrides.clear()
        db.close()
