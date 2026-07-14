import pytest
from datetime import datetime

from fastapi import HTTPException

from app.config import settings
from app.main import current_consented_user
from app.models import User


def test_current_document_version_is_required(monkeypatch):
    monkeypatch.setattr(settings, "legal_documents_version", "2026-07-14")
    monkeypatch.setattr(settings, "legal_documents_digest", "a" * 64)
    with pytest.raises(HTTPException) as error:
        current_consented_user(User(telegram_id="1", consent_version="2026-06-01"))
    assert error.value.status_code == 428


def test_matching_document_version_allows_product_access(monkeypatch):
    monkeypatch.setattr(settings, "legal_documents_version", "2026-07-14")
    monkeypatch.setattr(settings, "legal_documents_digest", "a" * 64)
    user = User(telegram_id="1", consent_version="2026-07-14", consent_digest="a" * 64, age_confirmed_at=datetime.utcnow())
    assert current_consented_user(user) is user


def test_matching_version_with_different_digest_requires_reconsent(monkeypatch):
    monkeypatch.setattr(settings, "legal_documents_version", "2026-07-14")
    monkeypatch.setattr(settings, "legal_documents_digest", "a" * 64)
    user = User(telegram_id="1", consent_version="2026-07-14", consent_digest="b" * 64, age_confirmed_at=datetime.utcnow())
    with pytest.raises(HTTPException) as error:
        current_consented_user(user)
    assert error.value.status_code == 428


def test_adult_confirmation_is_required(monkeypatch):
    monkeypatch.setattr(settings, "legal_documents_version", "2026-07-14")
    monkeypatch.setattr(settings, "legal_documents_digest", "a" * 64)
    with pytest.raises(HTTPException) as error:
        current_consented_user(User(telegram_id="1", consent_version="2026-07-14", consent_digest="a" * 64))
    assert error.value.status_code == 428
