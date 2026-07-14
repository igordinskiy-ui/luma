"""Fail a production release early when its public launch contract is incomplete.

Run from the repository root on the deployment host, after exporting the same
environment used by Docker Compose. The script deliberately prints variable
names only, never their values.
"""

from __future__ import annotations

import os
import re
import runpy
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from content_manifest import release_content_digest
from legal_manifest import legal_documents_digest


ROOT = Path(__file__).resolve().parents[1]
LEGAL_PAGES = (ROOT / "apps" / "web" / "public" / "privacy.html", ROOT / "apps" / "web" / "public" / "terms.html")
CAMPAIGN_CODE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
PLACEHOLDER_PREFIX = "[" * 2
CONTENT_DIGEST = runpy.run_path(str(ROOT / "apps" / "api" / "app" / "content.py"))["CONTENT_DIGEST"]


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def public_origin(value: str) -> str | None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def main() -> int:
    env = os.environ
    errors: list[str] = []

    if env.get("APP_ENVIRONMENT") != "production":
        fail(errors, "APP_ENVIRONMENT must be production")

    for name, minimum in (("SESSION_SECRET", 32), ("PROXY_SHARED_SECRET", 32), ("TELEGRAM_WEBHOOK_SECRET", 24), ("REDIS_PASSWORD", 32)):
        if len(env.get(name, "")) < minimum:
            fail(errors, f"{name} must contain at least {minimum} characters")
    for name in ("DOMAIN", "TELEGRAM_BOT_TOKEN", "DATABASE_URL", "REDIS_URL"):
        if not env.get(name) or "change-me" in env[name]:
            fail(errors, f"{name} must be configured with a non-default value")

    redis = urlsplit(env.get("REDIS_URL", ""))
    if redis.scheme not in {"redis", "rediss"} or unquote(redis.password or "") != env.get("REDIS_PASSWORD", ""):
        fail(errors, "REDIS_URL must contain the URL-encoded REDIS_PASSWORD")
    if not env.get("DATABASE_URL", "").startswith(("postgresql://", "postgresql+psycopg://")):
        fail(errors, "DATABASE_URL must be a PostgreSQL URL")

    origins = {public_origin(value.strip()) for value in env.get("CORS_ORIGINS", "").split(",") if value.strip()}
    if not origins or None in origins:
        fail(errors, "CORS_ORIGINS must contain only HTTPS origins")
    if public_origin(env.get("TELEGRAM_WEBAPP_URL", "")) not in origins:
        fail(errors, "TELEGRAM_WEBAPP_URL must be an HTTPS origin listed in CORS_ORIGINS")
    oidc_values = tuple(env.get(name, "") for name in ("TELEGRAM_OIDC_CLIENT_ID", "TELEGRAM_OIDC_CLIENT_SECRET", "TELEGRAM_OIDC_REDIRECT_URI"))
    if any(oidc_values) and not all(oidc_values):
        fail(errors, "TELEGRAM_OIDC variables must be configured together")
    elif all(oidc_values):
        redirect = urlsplit(oidc_values[2])
        redirect_origin = f"{redirect.scheme}://{redirect.netloc}" if redirect.scheme and redirect.netloc else None
        if redirect.scheme != "https" or redirect_origin not in origins or redirect.path != "/api/v1/auth/oidc/callback" or redirect.query or redirect.fragment:
            fail(errors, "TELEGRAM_OIDC_REDIRECT_URI must use the public origin and /api/v1/auth/oidc/callback")

    if env.get("CONTENT_REVIEW_STATUS") != "approved":
        fail(errors, "CONTENT_REVIEW_STATUS must be approved")
    if env.get("CONTENT_APPROVED_DIGEST") != release_content_digest():
        fail(errors, "CONTENT_APPROVED_DIGEST must match all reviewed production copy")
    if env.get("CONTENT_CATALOGUE_DIGEST") != CONTENT_DIGEST:
        fail(errors, "CONTENT_CATALOGUE_DIGEST must match the runtime API catalogue")
    if env.get("LEGAL_DOCUMENTS_STATUS") != "approved":
        fail(errors, "LEGAL_DOCUMENTS_STATUS must be approved")
    version = env.get("LEGAL_DOCUMENTS_VERSION", "")
    if not version or version == "template" or PLACEHOLDER_PREFIX in version:
        fail(errors, "LEGAL_DOCUMENTS_VERSION must identify approved documents")
    if env.get("LEGAL_DOCUMENTS_DIGEST") != legal_documents_digest():
        fail(errors, "LEGAL_DOCUMENTS_DIGEST must match the committed privacy policy and terms")
    if env.get("RISK_ENGINE_VERSION") not in {"rules_v1", "baseline"}:
        fail(errors, "RISK_ENGINE_VERSION must be rules_v1 or baseline")

    for page in LEGAL_PAGES:
        try:
            contents = page.read_text(encoding="utf-8")
        except OSError:
            fail(errors, f"required legal page is unavailable: {page.relative_to(ROOT)}")
            continue
        if PLACEHOLDER_PREFIX in contents or "Шаблон для юридического утверждения" in contents or 'data-approval="pending"' in contents:
            fail(errors, f"legal page is not approved: {page.relative_to(ROOT)}")
        elif version and version not in contents:
            fail(errors, f"LEGAL_DOCUMENTS_VERSION is not displayed in {page.relative_to(ROOT)}")

    codes = [value.strip() for value in env.get("ACQUISITION_SOURCES", "").split(",") if value.strip()]
    if len(codes) != len(set(codes)) or any(not CAMPAIGN_CODE.fullmatch(value) for value in codes):
        fail(errors, "ACQUISITION_SOURCES must be unique short campaign codes")

    if errors:
        print("Production release preflight failed:", file=sys.stderr)
        print(*[f"- {message}" for message in errors], sep="\n", file=sys.stderr)
        return 1
    print("Production release preflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
