from datetime import datetime
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from .models import Entitlement, User

# Everything remains free in beta. This single policy is the future paywall boundary.
FREE_BETA_FEATURES = {"core_quit_plan", "journal", "notifications", "progress"}

def has_feature(db: Session, user: User, feature: str) -> bool:
    if feature in FREE_BETA_FEATURES: return True
    now = datetime.utcnow()
    return db.scalar(select(Entitlement.id).where(Entitlement.user_id == user.id, Entitlement.feature == feature, or_(Entitlement.expires_at.is_(None), Entitlement.expires_at > now))) is not None
