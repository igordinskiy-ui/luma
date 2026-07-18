"""Pause/resume returns to the exact phase instead of guessing from counts."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.auth import current_user
from app.db import SessionLocal
from app.main import app
from app.models import QuitAttempt, QuitPlan, User


def test_preparation_pause_only_resumes_preparation():
    db = SessionLocal()
    user = User(telegram_id="pause-preparation-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    db.add(QuitPlan(user_id=user.id, phase="preparation", remaining=20, target_quit_at=datetime.utcnow() + timedelta(days=7)))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            paused = client.put("/v1/quit-plan", json={"phase": "paused"})
            assert paused.status_code == 200
            dashboard = client.get("/v1/dashboard")
            assert dashboard.json()["phase"] == "paused"
            assert dashboard.json()["paused_from"] == "preparation"
            assert client.put("/v1/quit-plan", json={"phase": "last_pack"}).status_code == 409
            resumed = client.put("/v1/quit-plan", json={"phase": "preparation"})
            assert resumed.status_code == 200
            assert client.get("/v1/dashboard").json()["paused_from"] is None
            assert client.put("/v1/quit-plan", json={"phase": "last_pack"}).status_code == 200
            assert client.put("/v1/quit-plan", json={"phase": "quit"}).status_code == 200
            quit_dashboard = client.get("/v1/dashboard").json()
            assert quit_dashboard["phase"] == "quit"
            assert quit_dashboard["remaining"] == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_preparation_plan_cannot_clear_its_target_date():
    db = SessionLocal()
    user = User(telegram_id="preparation-target-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    target = datetime.utcnow() + timedelta(days=7)
    db.add(QuitPlan(user_id=user.id, phase="preparation", remaining=20, target_quit_at=target))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            rejected = client.put("/v1/quit-plan", json={"target_quit_at": None})
            assert rejected.status_code == 422
            db.expire_all()
            assert db.query(QuitPlan).filter_by(user_id=user.id).one().target_quit_at == target
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_preparation_target_preserves_the_instant_across_timezones():
    db = SessionLocal()
    user = User(telegram_id="preparation-timezone-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    db.add(QuitPlan(user_id=user.id, phase="preparation", remaining=20, target_quit_at=datetime.utcnow() + timedelta(days=7)))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        local_target = datetime.now(timezone(timedelta(hours=3))) + timedelta(days=8)
        expected_utc = local_target.astimezone(timezone.utc).replace(tzinfo=None)
        with TestClient(app) as client:
            updated = client.put("/v1/quit-plan", json={"target_quit_at": local_target.isoformat()})
            assert updated.status_code == 200
            db.expire_all()
            assert db.query(QuitPlan).filter_by(user_id=user.id).one().target_quit_at == expected_utc
            assert client.get("/v1/quit-plan").json()["target_quit_at"] == expected_utc.isoformat() + "Z"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_plan_calculation_inputs_can_change_without_replacing_history():
    db = SessionLocal()
    user = User(telegram_id="plan-calculation-inputs-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    db.add(QuitPlan(user_id=user.id, phase="last_pack", remaining=8, cigarettes_per_pack=20, pack_price=240, reasons="keep"))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            updated = client.put("/v1/quit-plan", json={"cigarettes_per_pack": 25, "pack_price": 315.5})
            assert updated.status_code == 200
            current = client.get("/v1/quit-plan").json()
            assert current["cigarettes_per_pack"] == 25
            assert current["pack_price"] == 315.5
            assert current["remaining"] == 8 and current["reasons"] == "keep"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_quit_pause_closes_attempt_and_resume_starts_a_new_period():
    db = SessionLocal()
    started = datetime.utcnow() - timedelta(days=1)
    user = User(telegram_id="pause-quit-user", age_confirmed_at=datetime.utcnow())
    db.add(user); db.flush()
    db.add(QuitPlan(user_id=user.id, phase="quit", remaining=0, quit_started_at=started))
    db.add(QuitAttempt(user_id=user.id, started_at=started))
    db.commit()
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as client:
            assert client.put("/v1/quit-plan", json={"phase": "paused"}).status_code == 200
            paused = client.get("/v1/dashboard").json()
            assert paused["paused_from"] == "quit"
            assert paused["best_smoke_free_seconds"] >= 86400
            assert client.put("/v1/quit-plan", json={"phase": "quit"}).status_code == 200
            resumed = client.get("/v1/dashboard").json()
            assert resumed["phase"] == "quit"
            assert resumed["attempt_number"] == 2
    finally:
        app.dependency_overrides.clear()
        db.close()
