"""Give every pytest invocation a freshly migrated, disposable database."""

from __future__ import annotations

import os
import tempfile
import gc
from pathlib import Path

from alembic import command
from alembic.config import Config


API_ROOT = Path(__file__).resolve().parents[1]
_DATABASE_DIR = tempfile.TemporaryDirectory(prefix="luma-pytest-")
_DATABASE_PATH = Path(_DATABASE_DIR.name) / "integration.db"

# conftest is imported before test modules, so app.config and app.db bind only
# to this per-run database. This keeps reruns deterministic without deleting a
# developer's local kurilka.db or relying on a pristine CI workspace.
os.environ["DATABASE_URL"] = f"sqlite:///{_DATABASE_PATH.as_posix()}"

_ALEMBIC = Config(str(API_ROOT / "alembic.ini"))
_ALEMBIC.set_main_option("script_location", str(API_ROOT / "alembic"))
command.upgrade(_ALEMBIC, "head")


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    from app.db import engine
    from sqlalchemy.orm import close_all_sessions

    close_all_sessions()
    engine.dispose()
    gc.collect()
    _DATABASE_DIR.cleanup()
