from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import settings


ROOT = Path(__file__).resolve().parents[1]


def test_support_depth_migration_round_trips_on_sqlite(tmp_path, monkeypatch):
    database_url = f"sqlite:///{(tmp_path / 'support-depth.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))

    command.upgrade(config, "20260715_20")
    engine = create_engine(database_url)
    assert "outcome" not in {column["name"] for column in inspect(engine).get_columns("coping_sessions")}
    assert "relapse_context" not in {column["name"] for column in inspect(engine).get_columns("behavior_events")}

    command.upgrade(config, "20260717_21")
    assert "outcome" in {column["name"] for column in inspect(engine).get_columns("coping_sessions")}
    assert "relapse_context" in {column["name"] for column in inspect(engine).get_columns("behavior_events")}
    assert "ck_coping_session_outcome" in {item["name"] for item in inspect(engine).get_check_constraints("coping_sessions")}
    assert "ck_behavior_event_relapse_context" in {item["name"] for item in inspect(engine).get_check_constraints("behavior_events")}

    command.downgrade(config, "20260715_20")
    assert "outcome" not in {column["name"] for column in inspect(engine).get_columns("coping_sessions")}
    assert "relapse_context" not in {column["name"] for column in inspect(engine).get_columns("behavior_events")}
    engine.dispose()
