"""Telegram acquisition attribution accepts only signed, allowlisted, first-touch codes."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import AnalyticsEvent, User


def signed_init_data(token: str, telegram_id: int, start_param: str) -> str:
    fields = {"auth_date": str(int(time.time())), "user": json.dumps({"id": telegram_id}), "start_param": start_param}
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_telegram_acquisition_is_allowlisted_and_first_touch(monkeypatch):
    token = "integration-bot-token"
    monkeypatch.setattr(settings, "telegram_bot_token", token)
    monkeypatch.setattr(settings, "acquisition_sources", "community_a,community_b")
    monkeypatch.setattr(settings, "session_secret", "integration-session-secret-at-least-32-characters")

    with TestClient(app) as client:
        assert client.post("/v1/auth/telegram", json={"init_data": signed_init_data(token, 720000001, "community_a")}).status_code == 200
        assert client.post("/v1/auth/telegram", json={"init_data": signed_init_data(token, 720000002, "free text from attacker")}).status_code == 200
        assert client.post("/v1/auth/telegram", json={"init_data": signed_init_data(token, 720000002, "community_b")}).status_code == 200
        assert client.post("/v1/auth/telegram", json={"init_data": signed_init_data(token, 720000001, "community_b")}).status_code == 200

    db = SessionLocal()
    try:
        first = db.scalar(select(User).where(User.telegram_id == "720000001"))
        late = db.scalar(select(User).where(User.telegram_id == "720000002"))
        assert first is not None and first.acquisition_source == "community_a"
        assert late is not None and late.acquisition_source == "community_b"
    finally:
        db.close()


def test_signed_campaign_is_traced_to_first_action_without_private_payloads(monkeypatch):
    token = "integration-bot-token"
    telegram_id = 720000003
    source = "campaign_trace"
    monkeypatch.setattr(settings, "telegram_bot_token", token)
    monkeypatch.setattr(settings, "acquisition_sources", source)
    monkeypatch.setattr(settings, "admin_telegram_ids", str(telegram_id))
    monkeypatch.setattr(settings, "session_secret", "integration-session-secret-at-least-32-characters")

    with TestClient(app) as client:
        authenticated = client.post(
            "/v1/auth/telegram",
            json={"init_data": signed_init_data(token, telegram_id, source)},
        )
        assert authenticated.status_code == 200
        headers = {"Authorization": f"Bearer {authenticated.json()['access_token']}"}

        onboarded = client.post(
            "/v1/onboarding",
            headers=headers,
            json={
                "timezone": "Europe/Moscow",
                "cigarettes_per_pack": 20,
                "remaining": 7,
                "pack_price": 240,
                "reasons": "private reason must not enter analytics",
                "start_mode": "last_pack",
                "target_quit_at": None,
                "age_confirmed": True,
                "consent": True,
            },
        )
        assert onboarded.status_code == 200

        first_action = client.post(
            "/v1/events",
            headers=headers,
            json={
                "kind": "craving",
                "trigger": "coffee",
                "intensity": 3,
                "note": "private note must not enter analytics",
                "client_event_id": "acquisition-first-action-0001",
            },
        )
        assert first_action.status_code == 200

        overview = client.get(
            f"/v1/admin/overview?period=30d&source={source}",
            headers=headers,
        )
        assert overview.status_code == 200
        data = overview.json()
        assert data["filters"] == {"period": "30d", "source": source}
        assert data["funnel"]["started"] == 1
        assert data["funnel"]["onboarded"] == 1
        assert data["funnel"]["first_action_24h"] == 1

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.telegram_id == str(telegram_id)))
        assert user is not None and user.acquisition_source == source
        events = list(db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.user_id == user.id)))
        assert events == []
        analytics_payload = " ".join(event.properties for event in events)
        assert "private reason" not in analytics_payload
        assert "private note" not in analytics_payload
        assert str(telegram_id) not in analytics_payload
    finally:
        db.close()
