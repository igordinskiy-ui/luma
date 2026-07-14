"""Bootstrap state keeps login recovery separate from onboarding and consent."""
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import current_user
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import QuitPlan, User


def test_bootstrap_reports_each_gate_without_requiring_consent():
    db = SessionLocal()
    user = User(telegram_id="bootstrap-new-user")
    db.add(user)
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            initial = client.get("/v1/bootstrap")
            assert initial.status_code == 200
            assert initial.json() == {
                "age_confirmed": False,
                "consent_current": not bool(settings.legal_documents_version),
                "onboarded": False,
                "legal_documents_version": settings.legal_documents_version,
                "legal_documents_digest": settings.legal_documents_digest,
            }

            user.age_confirmed_at = datetime.utcnow()
            user.consent_version = settings.legal_documents_version
            user.consent_digest = settings.legal_documents_digest
            db.add(QuitPlan(user_id=user.id, phase="preparation", remaining=20))
            db.commit()

            ready = client.get("/v1/bootstrap")
            assert ready.status_code == 200
            assert ready.json() == {
                "age_confirmed": True,
                "consent_current": True,
                "onboarded": True,
                "legal_documents_version": settings.legal_documents_version,
                "legal_documents_digest": settings.legal_documents_digest,
            }
    finally:
        app.dependency_overrides.clear()
        db.close()
