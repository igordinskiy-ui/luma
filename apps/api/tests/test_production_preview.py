from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def configure_preview(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "public_launch_enabled", False)
    monkeypatch.setattr(settings, "session_secret", "s" * 32)
    monkeypatch.setattr(settings, "proxy_shared_secret", "p" * 32)
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://user:password@db:5432/kurilka")
    monkeypatch.setattr(settings, "redis_url", "redis://:" + "r" * 32 + "@redis:6379/0")
    monkeypatch.setattr(settings, "cors_origins", "https://preview.example.test")
    monkeypatch.setattr(settings, "telegram_webapp_url", "https://preview.example.test")
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")
    monkeypatch.setattr(settings, "content_review_status", "draft")
    monkeypatch.setattr(settings, "legal_documents_status", "template")


def test_preview_exposes_health_and_launch_status_but_blocks_user_api(monkeypatch):
    configure_preview(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/v1/launch-status").json() == {"public_launch_enabled": False}
        blocked = client.post("/v1/auth/telegram", json={"init_data": "not-used"})
        assert blocked.status_code == 503
        assert blocked.json()["error"]["code"] == "public_launch_disabled"
        assert blocked.headers["retry-after"] == "3600"
