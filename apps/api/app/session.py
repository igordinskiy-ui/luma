import base64
import hashlib
import hmac
import json
import time
from .config import settings


def _session_secret() -> bytes:
    if len(settings.session_secret) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters")
    return settings.session_secret.encode()

def issue_session(user_id: int, auth_version: int) -> str:
    payload = {"sub": user_id, "ver": auth_version, "exp": int(time.time()) + settings.session_ttl_seconds}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_session_secret(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"

def session_subject(token: str) -> tuple[int, int] | None:
    try:
        raw, signature = token.split(".", 1)
        expected = hmac.new(_session_secret(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected): return None
        data = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        return (int(data["sub"]), int(data["ver"])) if data["exp"] >= time.time() else None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
