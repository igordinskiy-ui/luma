import pytest
from app.config import settings, validate_security_settings
from app.content import CONTENT_DIGEST


def set_valid_production(monkeypatch):
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "public_launch_enabled", True)
    monkeypatch.setattr(settings, "session_secret", "x" * 32)
    monkeypatch.setattr(settings, "telegram_webhook_secret", "x" * 24)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-bot-token")
    monkeypatch.setattr(settings, "proxy_shared_secret", "x" * 32)
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://user:password@db:5432/kurilka")
    monkeypatch.setattr(settings, "redis_url", "redis://:" + "x" * 32 + "@redis:6379/0")
    monkeypatch.setattr(settings, "cors_origins", "https://app.example.test")
    monkeypatch.setattr(settings, "telegram_webapp_url", "https://app.example.test")
    monkeypatch.setattr(settings, "content_review_status", "approved")
    monkeypatch.setattr(settings, "content_approved_digest", CONTENT_DIGEST)
    monkeypatch.setattr(settings, "content_catalogue_digest", CONTENT_DIGEST)
    monkeypatch.setattr(settings, "legal_documents_status", "approved")
    monkeypatch.setattr(settings, "legal_documents_version", "2026-07-14")
    monkeypatch.setattr(settings, "legal_documents_digest", "a" * 64)
    monkeypatch.setattr(settings, "risk_engine_version", "rules_v1")

def test_production_rejects_short_session_secret(monkeypatch):
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "session_secret", "short")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        validate_security_settings()

def test_development_requires_private_session_secret(monkeypatch):
    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "session_secret", "")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        validate_security_settings()


def test_development_allows_unconfigured_external_services_with_session_secret(monkeypatch):
    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "session_secret", "x" * 32)
    validate_security_settings()

def test_production_rejects_unknown_risk_engine(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "risk_engine_version", "unreviewed")
    with pytest.raises(RuntimeError, match="RISK_ENGINE_VERSION"):
        validate_security_settings()

def test_production_requires_proxy_secret(monkeypatch):
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "session_secret", "x" * 32)
    monkeypatch.setattr(settings, "telegram_webhook_secret", "x" * 24)
    with pytest.raises(RuntimeError, match="PROXY_SHARED_SECRET"):
        validate_security_settings()

def test_production_requires_authenticated_redis(monkeypatch):
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "session_secret", "x" * 32)
    monkeypatch.setattr(settings, "telegram_webhook_secret", "x" * 24)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-bot-token")
    monkeypatch.setattr(settings, "proxy_shared_secret", "x" * 32)
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://user:password@db:5432/kurilka")
    monkeypatch.setattr(settings, "redis_url", "redis://redis:6379/0")
    with pytest.raises(RuntimeError, match="REDIS_URL must include"):
        validate_security_settings()

def test_production_requires_approved_legal_documents(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "legal_documents_status", "template")
    with pytest.raises(RuntimeError, match="LEGAL_DOCUMENTS_STATUS"):
        validate_security_settings()


def test_closed_production_preview_does_not_fake_public_approvals(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "public_launch_enabled", False)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")
    monkeypatch.setattr(settings, "content_review_status", "draft")
    monkeypatch.setattr(settings, "content_approved_digest", "")
    monkeypatch.setattr(settings, "content_catalogue_digest", "")
    monkeypatch.setattr(settings, "legal_documents_status", "template")
    monkeypatch.setattr(settings, "legal_documents_version", "")
    monkeypatch.setattr(settings, "legal_documents_digest", "")
    validate_security_settings()


def test_production_binds_approval_to_exact_content_catalogue(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "content_catalogue_digest", "0" * 64)
    with pytest.raises(RuntimeError, match="CONTENT_CATALOGUE_DIGEST"):
        validate_security_settings()


def test_production_rejects_non_https_cors_origin(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "cors_origins", "http://app.example.test")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_security_settings()


def test_production_requires_versioned_legal_documents(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "legal_documents_version", "template")
    with pytest.raises(RuntimeError, match="LEGAL_DOCUMENTS_VERSION"):
        validate_security_settings()


def test_production_requires_exact_legal_document_digest(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "legal_documents_digest", "draft")
    with pytest.raises(RuntimeError, match="LEGAL_DOCUMENTS_DIGEST"):
        validate_security_settings()


def test_production_requires_telegram_origin_in_cors(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "telegram_webapp_url", "https://other.example.test")
    with pytest.raises(RuntimeError, match="TELEGRAM_WEBAPP_URL"):
        validate_security_settings()


def test_production_rejects_free_text_acquisition_codes(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "acquisition_sources", "campaign one")
    with pytest.raises(RuntimeError, match="ACQUISITION_SOURCES"):
        validate_security_settings()


def test_production_rejects_partial_oidc_configuration(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "telegram_oidc_client_id", "client")
    monkeypatch.setattr(settings, "telegram_oidc_client_secret", "")
    monkeypatch.setattr(settings, "telegram_oidc_redirect_uri", "")
    with pytest.raises(RuntimeError, match="configured together"):
        validate_security_settings()


def test_production_requires_same_origin_oidc_callback(monkeypatch):
    set_valid_production(monkeypatch)
    monkeypatch.setattr(settings, "telegram_oidc_client_id", "client")
    monkeypatch.setattr(settings, "telegram_oidc_client_secret", "secret")
    monkeypatch.setattr(settings, "telegram_oidc_redirect_uri", "https://evil.example/api/v1/auth/oidc/callback")
    with pytest.raises(RuntimeError, match="same-origin HTTPS"):
        validate_security_settings()
