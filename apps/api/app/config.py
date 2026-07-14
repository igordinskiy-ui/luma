from urllib.parse import unquote, urlsplit
import re
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./kurilka.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173"
    telegram_bot_token: str = ""
    telegram_webapp_url: str = "http://localhost:5173"
    app_environment: str = "development"
    session_secret: str = ""
    session_ttl_seconds: int = 86400
    development_auth_enabled: bool = False
    telegram_webhook_secret: str = ""
    telegram_auth_max_age_seconds: int = 900
    telegram_oidc_client_id: str = ""
    telegram_oidc_client_secret: str = ""
    telegram_oidc_redirect_uri: str = ""
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:support@example.com"
    content_review_status: str = "draft"
    content_approved_digest: str = ""
    content_catalogue_digest: str = ""
    legal_documents_status: str = "template"
    legal_documents_version: str = ""
    legal_documents_digest: str = ""
    risk_engine_version: str = "rules_v1"
    admin_telegram_ids: str = ""
    acquisition_sources: str = ""
    proxy_shared_secret: str = ""
    max_request_body_bytes: int = 262144
    outbox_retention_days: int = 30
    delivery_retention_days: int = 90
    analytics_retention_days: int = 180
    feedback_retention_days: int = 365


settings = Settings()

# Local development must not silently sign bearer sessions with a public,
# empty key. An ephemeral key keeps the zero-config workflow while making
# sessions intentionally expire when the development process restarts.
if settings.app_environment != "production" and len(settings.session_secret) < 32:
    settings.session_secret = secrets.token_urlsafe(32)


def _public_origin(value: str) -> str | None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def approved_acquisition_sources() -> set[str]:
    return {value.strip() for value in settings.acquisition_sources.split(",") if value.strip()}


def validate_security_settings() -> None:
    if settings.app_environment not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENVIRONMENT must be development, test, or production")
    for name in ("outbox_retention_days", "delivery_retention_days", "analytics_retention_days", "feedback_retention_days"):
        if not 1 <= getattr(settings, name) <= 3650:
            raise RuntimeError(f"{name.upper()} must be between 1 and 3650")
    if len(settings.session_secret) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters")
    if settings.app_environment != "production":
        return
    if len(settings.telegram_webhook_secret) < 24: raise RuntimeError("TELEGRAM_WEBHOOK_SECRET must contain at least 24 characters")
    if len(settings.proxy_shared_secret) < 32: raise RuntimeError("PROXY_SHARED_SECRET must contain at least 32 characters")
    if not settings.telegram_bot_token: raise RuntimeError("TELEGRAM_BOT_TOKEN must be configured in production")
    if not settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")) or "change-me" in settings.database_url:
        raise RuntimeError("DATABASE_URL must point to a configured production database")
    if not settings.redis_url or "change-me" in settings.redis_url:
        raise RuntimeError("REDIS_URL must point to a configured production Redis instance")
    redis = urlsplit(settings.redis_url)
    if redis.scheme not in {"redis", "rediss"} or len(unquote(redis.password or "")) < 32:
        raise RuntimeError("REDIS_URL must include a Redis password of at least 32 characters in production")
    if settings.content_review_status != "approved": raise RuntimeError("CONTENT_REVIEW_STATUS must be approved before production launch")
    from .content import CONTENT_DIGEST
    if not re.fullmatch(r"[a-f0-9]{64}", settings.content_approved_digest):
        raise RuntimeError("CONTENT_APPROVED_DIGEST must identify the reviewed production copy")
    if settings.content_catalogue_digest != CONTENT_DIGEST:
        raise RuntimeError("CONTENT_CATALOGUE_DIGEST must match the runtime content catalogue")
    if settings.legal_documents_status != "approved": raise RuntimeError("LEGAL_DOCUMENTS_STATUS must be approved before production launch")
    placeholder_prefix = "[" * 2
    if not settings.legal_documents_version or placeholder_prefix in settings.legal_documents_version or settings.legal_documents_version == "template":
        raise RuntimeError("LEGAL_DOCUMENTS_VERSION must identify the approved public documents")
    if not re.fullmatch(r"[a-f0-9]{64}", settings.legal_documents_digest):
        raise RuntimeError("LEGAL_DOCUMENTS_DIGEST must identify the exact approved privacy policy and terms")
    origins = {_public_origin(value.strip()) for value in settings.cors_origins.split(",") if value.strip()}
    if not origins or None in origins:
        raise RuntimeError("CORS_ORIGINS must contain only HTTPS public origins in production")
    webapp_origin = _public_origin(settings.telegram_webapp_url)
    if not webapp_origin or webapp_origin not in origins:
        raise RuntimeError("TELEGRAM_WEBAPP_URL must be an HTTPS origin listed in CORS_ORIGINS in production")
    oidc_values = (settings.telegram_oidc_client_id, settings.telegram_oidc_client_secret, settings.telegram_oidc_redirect_uri)
    if any(oidc_values) and not all(oidc_values):
        raise RuntimeError("TELEGRAM_OIDC_CLIENT_ID, TELEGRAM_OIDC_CLIENT_SECRET and TELEGRAM_OIDC_REDIRECT_URI must be configured together")
    if all(oidc_values):
        redirect = urlsplit(settings.telegram_oidc_redirect_uri)
        redirect_origin = f"{redirect.scheme}://{redirect.netloc}" if redirect.scheme and redirect.netloc else None
        if redirect.scheme != "https" or redirect_origin not in origins or redirect.path != "/api/v1/auth/oidc/callback" or redirect.query or redirect.fragment:
            raise RuntimeError("TELEGRAM_OIDC_REDIRECT_URI must be the same-origin HTTPS /api/v1/auth/oidc/callback URL")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) for value in approved_acquisition_sources()):
        raise RuntimeError("ACQUISITION_SOURCES must contain only short approved campaign codes")
    if settings.risk_engine_version not in {"rules_v1", "baseline"}: raise RuntimeError("RISK_ENGINE_VERSION must be rules_v1 or baseline")
