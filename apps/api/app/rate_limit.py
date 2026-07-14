import hmac
import time
from fastapi import HTTPException, Request
from redis import Redis
from .config import settings

def enforce(request: Request, bucket: str, limit: int, window_seconds: int = 60, subject: str | int | None = None) -> None:
    """Redis fixed-window limiter; availability failures are explicit in production."""
    proxy_secret = request.headers.get("x-kurilka-proxy", "")
    forwarded = request.headers.get("x-real-ip", "")
    client = forwarded if forwarded and settings.proxy_shared_secret and hmac.compare_digest(proxy_secret, settings.proxy_shared_secret) else (request.client.host if request.client else "unknown")
    identity = f"user-{subject}" if subject is not None else client
    key = f"kurilka:rate:{bucket}:{identity}:{int(time.time() // window_seconds)}"
    try:
        redis = Redis.from_url(settings.redis_url)
        try:
            count = redis.incr(key)
            if count == 1: redis.expire(key, window_seconds + 1)
        finally: redis.close()
    except Exception:
        if settings.app_environment == "production": raise HTTPException(503, "Rate limiter unavailable")
        return
    if count > limit: raise HTTPException(429, "Too many requests")
