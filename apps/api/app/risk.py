from sqlalchemy.orm import Session
from .content import intervention

def assess(db: Session, user_id: int) -> tuple[str, str, list[str]]:
    """Select a general self-help prompt without scoring the user's health.

    The service deliberately does not calculate addiction severity, relapse
    probability, a medical risk, or any other clinical/health inference.  The
    most recent user-selected context is used only to choose between the same
    catalogue of general, non-medical prompts.  The legacy ``risk`` return
    value remains constant for API compatibility and must not be shown as an
    assessment of the user.
    """
    from .models import BehaviorEvent
    from sqlalchemy import select

    events = list(db.scalars(
        select(BehaviorEvent)
        .where(BehaviorEvent.user_id == user_id)
        .order_by(BehaviorEvent.created_at.desc())
        .limit(5)
    ))
    triggers = [event.trigger for event in events if event.trigger]
    top = next((t for t in triggers if t), "default")
    return "low", intervention(top), list(dict.fromkeys(t for t in triggers if t))
