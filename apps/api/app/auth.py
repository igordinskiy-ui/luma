"""Telegram signed payload verification and current-user dependency."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User
from .session import issue_session, session_subject

def telegram_auth_context(init_data: str) -> tuple[str, str | None]:
    if not settings.telegram_bot_token: raise HTTPException(503, "Telegram authentication is not configured")
    fields = dict(parse_qsl(init_data, keep_blank_values=True)); received_hash = fields.pop("hash", "")
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not received_hash or not hmac.compare_digest(expected, received_hash): raise HTTPException(401, "Invalid Telegram signature")
    try:
        auth_date = int(fields["auth_date"])
        if auth_date > time.time() + 60 or time.time() - auth_date > settings.telegram_auth_max_age_seconds: raise ValueError
        start_param = fields.get("start_param")
        return str(json.loads(fields["user"])["id"]), start_param
    except (KeyError, ValueError, TypeError): raise HTTPException(401, "Expired or invalid Telegram user")


def telegram_user_id(init_data: str) -> str:
    return telegram_auth_context(init_data)[0]

def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): raise HTTPException(401, "Authentication required")
    subject = session_subject(auth[7:])
    if not subject: raise HTTPException(401, "Invalid or expired session")
    user_id, auth_version = subject
    user = db.scalar(select(User).where(User.id == user_id, User.auth_version == auth_version))
    if not user: raise HTTPException(401, "Session user no longer exists")
    return user
