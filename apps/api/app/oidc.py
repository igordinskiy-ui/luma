import base64
import hashlib
import hmac
import json
import re
import secrets
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException
from redis import Redis

from .config import settings

AUTH_URL = "https://oauth.telegram.org/auth"
TOKEN_URL = "https://oauth.telegram.org/token"
JWKS_URL = "https://oauth.telegram.org/.well-known/jwks.json"
ISSUER = "https://oauth.telegram.org"


def configured() -> bool:
    return bool(settings.telegram_oidc_client_id and settings.telegram_oidc_client_secret and settings.telegram_oidc_redirect_uri)


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def start_url(client_state: str) -> str:
    if not configured():
        raise HTTPException(503, "Telegram OIDC is not configured")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", client_state):
        raise HTTPException(400, "OIDC client state is invalid")
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    redis = _redis()
    try:
        redis.setex(f"oidc:{state}", 600, json.dumps({"verifier": verifier, "client_state": client_state}))
    finally:
        redis.close()
    return f"{AUTH_URL}?{urlencode({'client_id': settings.telegram_oidc_client_id, 'redirect_uri': settings.telegram_oidc_redirect_uri, 'response_type': 'code', 'scope': 'openid profile telegram:bot_access', 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256'})}"


async def exchange_code(code: str, state: str) -> tuple[str, str]:
    if not configured():
        raise HTTPException(503, "Telegram OIDC is not configured")
    redis = _redis()
    try:
        raw_state = redis.getdel(f"oidc:{state}")
    finally:
        redis.close()
    if not raw_state:
        raise HTTPException(400, "OIDC state is invalid or expired")
    try:
        saved_state = json.loads(raw_state)
        verifier, client_state = saved_state["verifier"], saved_state["client_state"]
    except (KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(400, "OIDC state is invalid")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(TOKEN_URL, data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.telegram_oidc_redirect_uri, "client_id": settings.telegram_oidc_client_id, "code_verifier": verifier}, auth=(settings.telegram_oidc_client_id, settings.telegram_oidc_client_secret))
        if response.is_error:
            raise HTTPException(401, "Telegram token exchange failed")
        id_token = response.json().get("id_token")
    if not id_token:
        raise HTTPException(401, "Telegram did not return an ID token")
    try:
        key = jwt.PyJWKClient(JWKS_URL).get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=settings.telegram_oidc_client_id, issuer=ISSUER)
        return str(claims.get("id") or claims["sub"]), client_state
    except Exception:
        raise HTTPException(401, "Telegram ID token validation failed")


def create_browser_exchange(access_token: str, client_state: str) -> str:
    """Store a one-time opaque completion code; never put a bearer in a URL."""
    code = secrets.token_urlsafe(32)
    redis = _redis()
    try:
        redis.setex(f"oidc-browser:{code}", 60, json.dumps({"access_token": access_token, "client_state": client_state}))
    finally:
        redis.close()
    return code


def consume_browser_exchange(code: str, client_state: str) -> str:
    if not 24 <= len(code) <= 128 or not 24 <= len(client_state) <= 128:
        raise HTTPException(400, "OIDC completion is invalid")
    redis = _redis()
    try:
        raw_exchange = redis.getdel(f"oidc-browser:{code}")
    finally:
        redis.close()
    if not raw_exchange:
        raise HTTPException(400, "OIDC completion is invalid or expired")
    try:
        exchange = json.loads(raw_exchange)
        if not hmac.compare_digest(exchange["client_state"], client_state):
            raise ValueError
        return exchange["access_token"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(400, "OIDC completion is invalid")
