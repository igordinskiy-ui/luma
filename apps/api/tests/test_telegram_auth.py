import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.auth import telegram_auth_context
from app.config import settings


def signed_init_data(token: str, **values: str) -> str:
    fields = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 42}), **values}
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_signed_telegram_start_param_is_available_for_allowlisted_attribution(monkeypatch):
    token = "test-bot-token"
    monkeypatch.setattr(settings, "telegram_bot_token", token)
    assert telegram_auth_context(signed_init_data(token, start_param="tg_community_a")) == ("42", "tg_community_a")


def test_tampered_start_param_is_rejected(monkeypatch):
    token = "test-bot-token"
    monkeypatch.setattr(settings, "telegram_bot_token", token)
    with pytest.raises(Exception):
        telegram_auth_context(signed_init_data(token, start_param="tg_community_a") + "&start_param=attacker")
