from datetime import datetime, timezone
from uuid import uuid4

from app.db import SessionLocal
from app.models import BehaviorEvent, User
from app.risk import assess


def test_behaviour_history_never_creates_a_user_risk_classification():
    db = SessionLocal()
    unique = uuid4().hex
    try:
        user = User(telegram_id=f"non-medical-boundary-{unique}")
        db.add(user)
        db.flush()
        for index in range(8):
            db.add(BehaviorEvent(
                user_id=user.id,
                kind="relapse",
                trigger="stress",
                intensity=5,
                note="",
                client_event_id=f"boundary-{unique}-{index}",
                created_at=datetime.now(timezone.utc),
            ))
        db.commit()

        compatibility_value, prompt, contexts = assess(db, user.id)

        assert compatibility_value == "low"
        assert prompt
        assert contexts == ["stress"]
    finally:
        db.close()


def test_dashboard_schema_keeps_only_the_deprecated_constant_compatibility_value():
    from app.schemas import DashboardOut

    annotation = DashboardOut.model_fields["risk"].annotation
    assert str(annotation) == "typing.Literal['low']"
