from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from .content import COPING, intervention
from .config import settings

def assess(db: Session, user_id: int) -> tuple[str, str, list[str]]:
    # Delayed import keeps the content catalogue independently testable.
    from .models import BehaviorEvent
    since = datetime.utcnow() - timedelta(hours=24)
    events = list(db.scalars(select(BehaviorEvent).where(BehaviorEvent.user_id == user_id, BehaviorEvent.created_at >= since).order_by(BehaviorEvent.created_at.desc())))
    cravings = [e for e in events if e.kind == "craving"]
    relapses = [e for e in events if e.kind == "relapse"]
    triggers = [e.trigger for e in events if e.trigger][:5]
    score = min(10, len(cravings) * 2 + len(relapses) * 4 + sum((e.intensity or 0) >= 4 for e in cravings))
    # Environment-controlled beta flag. "baseline" keeps tailored coping
    # content but disables the evolving risk classification immediately.
    risk = "low" if settings.risk_engine_version == "baseline" else ("high" if score >= 6 else "medium" if score >= 3 else "low")
    top = next((t for t in triggers if t), "default")
    return risk, intervention(top), list(dict.fromkeys(t for t in triggers if t))
