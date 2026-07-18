import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import release_preflight  # noqa: E402
from content_manifest import release_content_digest  # noqa: E402
from legal_manifest import legal_documents_digest  # noqa: E402


def production_environment(*, public_launch: bool) -> dict[str, str]:
    password = "r" * 32
    origin = "https://app.example.test"
    return {
        "APP_ENVIRONMENT": "production",
        "PUBLIC_LAUNCH_ENABLED": str(public_launch).lower(),
        "SESSION_SECRET": "s" * 32,
        "PROXY_SHARED_SECRET": "p" * 32,
        "REDIS_PASSWORD": password,
        "DOMAIN": "app.example.test",
        "DATABASE_URL": "postgresql+psycopg://luma:secret@db:5432/luma",
        "REDIS_URL": f"redis://:{password}@redis:6379/0",
        "CORS_ORIGINS": origin,
        "TELEGRAM_WEBAPP_URL": origin,
        "RISK_ENGINE_VERSION": "baseline",
        "ACQUISITION_SOURCES": "direct,pilot_one",
    }


def test_closed_production_preview_passes_without_faking_external_approvals(monkeypatch, capsys):
    environment = production_environment(public_launch=False)
    environment["RISK_ENGINE_VERSION"] = "rules_v1"
    monkeypatch.setattr(release_preflight.os, "environ", environment)

    assert release_preflight.main() == 0
    assert "public user access and notifications are disabled" in capsys.readouterr().out


def test_public_launch_rejects_pending_legal_fields_and_non_baseline_scoring(monkeypatch, capsys):
    environment = production_environment(public_launch=True)
    environment.update({
        "TELEGRAM_WEBHOOK_SECRET": "w" * 24,
        "TELEGRAM_BOT_TOKEN": "123456:production-token",
        "TELEGRAM_OIDC_CLIENT_ID": "production-pwa-client",
        "TELEGRAM_OIDC_CLIENT_SECRET": "o" * 32,
        "TELEGRAM_OIDC_REDIRECT_URI": "https://app.example.test/api/v1/auth/oidc/callback",
        "CONTENT_REVIEW_STATUS": "approved",
        "CONTENT_APPROVED_DIGEST": release_content_digest(),
        "CONTENT_CATALOGUE_DIGEST": release_preflight.CONTENT_DIGEST,
        "LEGAL_DOCUMENTS_STATUS": "approved",
        "LEGAL_DOCUMENTS_VERSION": "2026-07-17",
        "LEGAL_DOCUMENTS_DIGEST": legal_documents_digest(),
        "RISK_ENGINE_VERSION": "rules_v1",
    })
    monkeypatch.setattr(release_preflight.os, "environ", environment)

    assert release_preflight.main() == 1
    errors = capsys.readouterr().err.replace("\\", "/")
    assert "RISK_ENGINE_VERSION must be baseline before public launch" in errors
    for name in ("consent.html", "privacy.html", "terms.html"):
        assert f"legal page is not approved: apps/web/public/{name}" in errors
    assert environment["TELEGRAM_BOT_TOKEN"] not in errors


def test_public_launch_requires_oidc_for_the_pwa_login_path(monkeypatch, capsys):
    environment = production_environment(public_launch=True)
    monkeypatch.setattr(release_preflight.os, "environ", environment)

    assert release_preflight.main() == 1
    errors = capsys.readouterr().err
    assert "TELEGRAM_OIDC variables are required together before public PWA launch" in errors


def test_preview_rejects_a_partially_configured_oidc_client(monkeypatch, capsys):
    environment = production_environment(public_launch=False)
    environment["TELEGRAM_OIDC_CLIENT_ID"] = "preview-client"
    monkeypatch.setattr(release_preflight.os, "environ", environment)

    assert release_preflight.main() == 1
    assert "TELEGRAM_OIDC variables must be configured together" in capsys.readouterr().err
