"""Runs in CI's Python 3.12 environment with the full API dependency set."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.auth import current_user
from app.db import SessionLocal
from app.main import app
from app.models import BehaviorEvent, CopingSession, OutboxEvent, QuitAttempt, QuitPlan, User


def test_journal_cursor_has_no_duplicates_and_filters_server_side():
    db = SessionLocal()
    user = User(telegram_id="journal-integration-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    now = datetime.utcnow()
    for index in range(15):
        kind = "relapse" if index == 0 else "craving" if index % 2 else "smoked"
        db.add(BehaviorEvent(user_id=user.id, kind=kind, trigger="coffee", intensity=3, note="", relapse_context="one" if index == 0 else None, client_event_id=f"journal-event-{index:04d}", created_at=now - timedelta(minutes=index)))
    for index in range(8):
        db.add(CopingSession(user_id=user.id, client_session_id=f"journal-coping-{index:04d}", source="dashboard", trigger="stress", intensity_before=7, intensity_after=3, technique="water", outcome="helped", content_version="v1", status="completed", started_at=now - timedelta(minutes=index, seconds=30), updated_at=now))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            first = client.get("/v1/journal?period=all&limit=10")
            second = client.get("/v1/journal", params={"period": "all", "limit": 10, "cursor": first.json()["next_cursor"]})
            assert first.status_code == 200 and second.status_code == 200
            first_ids = {item["id"] for item in first.json()["items"]}
            second_ids = {item["id"] for item in second.json()["items"]}
            assert len(first_ids) == 10 and len(second_ids) == 10
            assert first_ids.isdisjoint(second_ids)
            assert first.json()["summary"]["total"] == 23
            assert first.json()["summary"]["top_trigger"] in {"coffee", "stress"}
            assert all(item["created_at"].endswith("Z") for item in first.json()["items"])
            assert all(item["editable_until"].endswith("Z") for item in first.json()["items"] if item["editable_until"])

            coping = client.get("/v1/journal?period=all&type=coping&trigger=stress")
            assert len(coping.json()["items"]) == 8
            assert all(item["type"] == "coping" for item in coping.json()["items"])
            assert all(item["outcome"] == "helped" for item in coping.json()["items"])
            assert any(item["relapse_context"] == "one" for item in first.json()["items"] if item["source"] == "event")
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_event_can_be_corrected_only_inside_fifteen_minute_window():
    db = SessionLocal()
    user = User(telegram_id="journal-edit-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    recent = BehaviorEvent(user_id=user.id, kind="craving", trigger="stress", intensity=4, note="before", client_event_id="journal-edit-recent", created_at=datetime.utcnow())
    expired = BehaviorEvent(user_id=user.id, kind="craving", trigger="coffee", intensity=3, note="old", client_event_id="journal-edit-expired", created_at=datetime.utcnow() - timedelta(minutes=16))
    db.add_all([recent, expired]); db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            corrected = client.patch(f"/v1/events/{recent.id}", json={"trigger": "coffee", "intensity": 2, "note": "after"})
            assert corrected.status_code == 200
            assert corrected.json()["trigger"] == "coffee"
            assert corrected.json()["intensity"] == 2
            assert corrected.json()["note"] == "after"
            assert corrected.json()["created_at"].endswith("Z")

            too_late = client.patch(f"/v1/events/{expired.id}", json={"note": "changed"})
            assert too_late.status_code == 409
            assert too_late.json()["error"]["code"] == "http_409"
            assert client.delete(f"/v1/events/{expired.id}").status_code == 409
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_accidental_last_cigarette_can_be_removed_and_auto_transition_is_reversed():
    db = SessionLocal()
    user = User(telegram_id="journal-delete-last-cigarette", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    db.add(QuitPlan(user_id=user.id, phase="last_pack", remaining=1, cigarettes_per_pack=20))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            created = client.post("/v1/events", json={"kind": "smoked", "client_event_id": "journal-delete-smoked-0001"})
            assert created.status_code == 200
            assert created.json()["phase"] == "quit"
            removed = client.delete(f"/v1/events/{created.json()['event_id']}")
            assert removed.status_code == 200
            assert removed.json() == {"status": "deleted", "phase": "last_pack", "remaining": 1}
            assert db.query(BehaviorEvent).filter_by(user_id=user.id).count() == 0
            assert db.query(QuitAttempt).filter_by(user_id=user.id).count() == 0
            assert db.query(OutboxEvent).filter_by(user_id=user.id).count() == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_accidental_relapse_reopens_the_previous_quit_period():
    db = SessionLocal()
    user = User(telegram_id="journal-delete-relapse", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    original_start = datetime.utcnow() - timedelta(days=2)
    db.add(QuitPlan(user_id=user.id, phase="quit", remaining=0, quit_started_at=original_start))
    db.add(QuitAttempt(user_id=user.id, started_at=original_start))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            created = client.post("/v1/events", json={"kind": "relapse", "client_event_id": "journal-delete-relapse-0001"})
            assert created.status_code == 200
            removed = client.delete(f"/v1/events/{created.json()['event_id']}")
            assert removed.status_code == 200
            db.expire_all()
            plan = db.query(QuitPlan).filter_by(user_id=user.id).one()
            attempts = db.query(QuitAttempt).filter_by(user_id=user.id).all()
            assert plan.phase == "quit" and plan.quit_started_at == original_start and plan.recovery_until is None
            assert len(attempts) == 1 and attempts[0].ended_at is None and attempts[0].end_reason is None
            assert db.query(OutboxEvent).filter_by(user_id=user.id).count() == 0
    finally:
        app.dependency_overrides.clear()
        db.close()
