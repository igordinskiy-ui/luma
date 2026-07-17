import json

import pytest
from fastapi import HTTPException

from app import oidc


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    def setex(self, key: str, _ttl: int, value: str):
        self.values[key] = value

    def getdel(self, key: str):
        return self.values.pop(key, None)

    def close(self):
        pass


def test_browser_exchange_is_bound_to_state_and_one_time(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(oidc, "_redis", lambda: redis)
    monkeypatch.setattr(oidc.secrets, "token_urlsafe", lambda _size: "completion-code-1234567890123456")

    code = oidc.create_browser_exchange("signed-session", "client-state-1234567890123456")

    assert oidc.consume_browser_exchange(code, "client-state-1234567890123456") == "signed-session"
    with pytest.raises(HTTPException, match="invalid or expired"):
        oidc.consume_browser_exchange(code, "client-state-1234567890123456")


def test_state_mismatch_consumes_exchange_to_prevent_replay(monkeypatch):
    redis = FakeRedis()
    redis.values["oidc-browser:completion-code-1234567890123456"] = json.dumps(
        {"access_token": "signed-session", "client_state": "client-state-1234567890123456"}
    )
    monkeypatch.setattr(oidc, "_redis", lambda: redis)

    with pytest.raises(HTTPException, match="completion is invalid"):
        oidc.consume_browser_exchange("completion-code-1234567890123456", "different-state-123456789012345")
    assert not redis.values
