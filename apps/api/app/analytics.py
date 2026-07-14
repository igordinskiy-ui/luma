import json
import re
from sqlalchemy.orm import Session
from .models import AnalyticsEvent, User


_EVENT_PROPERTIES: dict[str, dict[str, set[object] | tuple[int, int] | type]] = {
    "client_session_started": {"session_hash": str},
    "client_crash": {"session_hash": str},
}


def validate_event(event_name: str, properties: dict | None) -> dict:
    values = properties or {}
    specification = _EVENT_PROPERTIES.get(event_name)
    if specification is None or set(values) != set(specification):
        raise ValueError("Analytics event does not match the approved schema")
    for name, constraint in specification.items():
        value = values[name]
        if isinstance(constraint, tuple):
            if type(value) is not int or not constraint[0] <= value <= constraint[1]:
                raise ValueError("Analytics event contains an invalid numeric value")
        elif constraint is str:
            if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
                raise ValueError("Analytics event contains an invalid session hash")
        elif value not in constraint:
            raise ValueError("Analytics event contains an invalid categorical value")
    return values


def track(db: Session, user: User, event_name: str, properties: dict | None = None) -> None:
    """Persist only whitelisted, non-text product signals."""
    values = validate_event(event_name, properties)
    db.add(AnalyticsEvent(user_id=user.id, event_name=event_name, properties=json.dumps(values, ensure_ascii=False)))
