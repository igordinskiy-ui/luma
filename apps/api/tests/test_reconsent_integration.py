"""Re-consent updates legal state without rewriting the user's active plan."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.auth import current_user
from app.config import settings
from app.db import SessionLocal
from app.main import app
from sqlalchemy import select

from app.models import ConsentRecord, QuitPlan, User


def test_reconsent_preserves_every_quit_plan_field(monkeypatch):
    monkeypatch.setattr(settings, "legal_documents_version", "2026-07-14-test")
    monkeypatch.setattr(settings, "legal_documents_digest", "a" * 64)
    db = SessionLocal()
    target = datetime.utcnow() + timedelta(days=9)
    user = User(telegram_id="reconsent-user", consent_version="outdated", consent_digest="b" * 64)
    db.add(user); db.flush()
    db.add(ConsentRecord(user_id=user.id, document_version="outdated", document_digest="b" * 64, source="legacy", age_confirmed=True, accepted_at=datetime.utcnow() - timedelta(days=30)))
    plan = QuitPlan(user_id=user.id, phase="preparation", remaining=17, cigarettes_per_pack=25, pack_price=321, reasons="keep this reason", target_quit_at=target)
    db.add(plan); db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            response = client.post("/v1/consent", json={"age_confirmed": True, "consent": True})
            assert response.status_code == 200
            assert response.json() == {"consent_version": "2026-07-14-test", "consent_digest": "a" * 64, "age_confirmed": True}
            repeated = client.post("/v1/consent", json={"age_confirmed": True, "consent": True})
            assert repeated.status_code == 200
            db.refresh(plan); db.refresh(user)
            assert (plan.phase, plan.remaining, plan.cigarettes_per_pack, plan.pack_price, plan.reasons, plan.target_quit_at) == (
                "preparation", 17, 25, 321, "keep this reason", target,
            )
            assert user.consent_version == "2026-07-14-test"
            assert user.consent_digest == "a" * 64
            assert user.age_confirmed_at is not None
            history = list(db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id).order_by(ConsentRecord.accepted_at)))
            assert [(item.document_version, item.document_digest, item.source) for item in history] == [
                ("outdated", "b" * 64, "legacy"),
                ("2026-07-14-test", "a" * 64, "reconsent"),
            ]
            assert client.get("/v1/bootstrap").json() == {"age_confirmed": True, "consent_current": True, "onboarded": True}
    finally:
        app.dependency_overrides.clear()
        db.close()
