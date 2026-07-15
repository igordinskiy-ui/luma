"""Quit-journey lifecycle helpers shared by API flows and tests."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import QuitAttempt


MILESTONES: tuple[tuple[int, str], ...] = (
    (3600, "1 час"), (21600, "6 часов"), (43200, "12 часов"),
    (86400, "1 день"), (259200, "3 дня"), (604800, "7 дней"),
    (1209600, "14 дней"), (2592000, "30 дней"),
    (7776000, "90 дней"), (31536000, "1 год"),
)


@dataclass(frozen=True)
class JourneyStats:
    current_seconds: int
    best_seconds: int
    attempt_number: int
    next_milestone_seconds: int | None
    next_milestone_label: str | None


def elapsed_seconds(started_at: datetime, ended_at: datetime) -> int:
    return max(0, int((ended_at - started_at).total_seconds()))


def next_milestone(current_seconds: int) -> tuple[int | None, str | None]:
    for seconds, label in MILESTONES:
        if current_seconds < seconds:
            return seconds, label
    return None, None


def active_attempt(db: Session, user_id: int, *, locked: bool = False) -> QuitAttempt | None:
    query = select(QuitAttempt).where(QuitAttempt.user_id == user_id, QuitAttempt.ended_at.is_(None)).order_by(QuitAttempt.started_at.desc())
    if locked:
        query = query.with_for_update()
    return db.scalar(query)


def start_attempt(db: Session, user_id: int, at: datetime) -> QuitAttempt:
    # SessionLocal deliberately disables autoflush. Persist a just-closed
    # attempt before looking for an active one, otherwise the SELECT still
    # sees its old NULL ended_at value and silently reuses it.
    db.flush()
    current = active_attempt(db, user_id, locked=True)
    if current:
        return current
    attempt = QuitAttempt(user_id=user_id, started_at=at)
    db.add(attempt)
    return attempt


def close_active_attempt(db: Session, user_id: int, at: datetime, reason: str) -> QuitAttempt | None:
    current = active_attempt(db, user_id, locked=True)
    if current:
        current.ended_at = max(at, current.started_at)
        current.end_reason = reason
    return current


def journey_stats(db: Session, user_id: int, now: datetime) -> JourneyStats:
    attempts = list(db.scalars(select(QuitAttempt).where(QuitAttempt.user_id == user_id).order_by(QuitAttempt.started_at.asc())))
    durations = [elapsed_seconds(item.started_at, item.ended_at or now) for item in attempts]
    current = next((elapsed_seconds(item.started_at, now) for item in reversed(attempts) if item.ended_at is None), 0)
    milestone_seconds, milestone_label = next_milestone(current)
    return JourneyStats(current, max(durations, default=0), len(attempts), milestone_seconds, milestone_label)
