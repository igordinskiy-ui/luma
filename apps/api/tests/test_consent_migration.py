from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import settings


ROOT = Path(__file__).resolve().parents[1]


def test_consent_history_migration_backfills_only_prior_acceptances(tmp_path, monkeypatch):
    database = tmp_path / "consent-migration.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))

    command.upgrade(config, "20260714_19")
    engine = create_engine(database_url)
    accepted_at = "2026-07-14 10:30:00"
    with engine.begin() as connection:
        connection.execute(text(
            """INSERT INTO users
            (telegram_id, timezone, consent_version, consented_at, age_confirmed_at)
            VALUES
            ('legacy-adult', 'Europe/Moscow', '2026-07-14', :accepted_at, :accepted_at),
            ('legacy-no-age', 'Europe/Moscow', '2026-07-14', :accepted_at, NULL),
            ('never-consented', 'Europe/Moscow', '', NULL, NULL)"""
        ), {"accepted_at": accepted_at})

    command.upgrade(config, "head")
    with engine.connect() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("users")}
        assert "consent_digest" in columns
        rows = connection.execute(text(
            """SELECT users.telegram_id, consent_records.document_version,
                      consent_records.document_digest, consent_records.source,
                      consent_records.age_confirmed, consent_records.accepted_at
               FROM consent_records
               JOIN users ON users.id = consent_records.user_id
               ORDER BY users.telegram_id"""
        )).mappings().all()

    assert [row["telegram_id"] for row in rows] == ["legacy-adult", "legacy-no-age"]
    assert all(row["document_version"] == "2026-07-14" for row in rows)
    assert all(row["document_digest"] == "" and row["source"] == "legacy" for row in rows)
    assert [bool(row["age_confirmed"]) for row in rows] == [True, False]
    assert all(str(row["accepted_at"]).startswith("2026-07-14 10:30:00") for row in rows)
    engine.dispose()
