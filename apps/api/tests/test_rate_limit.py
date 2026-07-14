import pytest

from fastapi import HTTPException
from starlette.requests import Request

from app import rate_limit
from app.config import settings


def request(headers: list[tuple[bytes, bytes]] = []) -> Request:
    return Request({"type": "http", "method": "POST", "path": "/v1/events", "headers": headers, "client": ("127.0.0.1", 12345)})


def test_rate_limit_rejects_requests_over_limit(monkeypatch):
    class Redis:
        def incr(self, key): return 3
        def expire(self, key, seconds): raise AssertionError("existing bucket must not reset expiry")
        def close(self): pass

        @classmethod
        def from_url(cls, url): return cls()

    monkeypatch.setattr(rate_limit, "Redis", Redis)
    monkeypatch.setattr(settings, "app_environment", "development")
    with pytest.raises(HTTPException) as error:
        rate_limit.enforce(request(), "events", 2)
    assert error.value.status_code == 429


def test_rate_limit_fails_closed_in_production(monkeypatch):
    class Redis:
        @classmethod
        def from_url(cls, url): raise OSError("unavailable")

    monkeypatch.setattr(rate_limit, "Redis", Redis)
    monkeypatch.setattr(settings, "app_environment", "production")
    with pytest.raises(HTTPException) as error:
        rate_limit.enforce(request(), "events", 2)
    assert error.value.status_code == 503


def test_rate_limit_uses_caddy_verified_client_address(monkeypatch):
    seen = []

    class Redis:
        def incr(self, key):
            seen.append(key)
            return 1
        def expire(self, key, seconds): pass
        def close(self): pass

        @classmethod
        def from_url(cls, url): return cls()

    monkeypatch.setattr(rate_limit, "Redis", Redis)
    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "proxy_shared_secret", "secret")
    rate_limit.enforce(request([(b"x-kurilka-proxy", b"secret"), (b"x-real-ip", b"203.0.113.10")]), "events", 2)
    assert any(":203.0.113.10:" in key for key in seen)


def test_authenticated_rate_limit_uses_user_subject_not_shared_ip(monkeypatch):
    seen = []
    class Redis:
        def incr(self, key): seen.append(key); return 1
        def expire(self, key, seconds): pass
        def close(self): pass
        @classmethod
        def from_url(cls, url): return cls()
    monkeypatch.setattr(rate_limit, "Redis", Redis)
    rate_limit.enforce(request(), "events", 2, subject=42)
    assert any(":user-42:" in key for key in seen)
