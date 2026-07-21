import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import run_test_preview  # noqa: E402


def test_running_preview_is_reused_without_reset(monkeypatch):
    monkeypatch.setattr(run_test_preview, "http_ready", lambda _url: True)
    monkeypatch.setattr(run_test_preview, "port_in_use", lambda _port: True)

    assert run_test_preview.should_start(reset=False) is False


def test_running_preview_must_be_stopped_before_reset(monkeypatch):
    monkeypatch.setattr(run_test_preview, "http_ready", lambda _url: True)

    with pytest.raises(RuntimeError, match="already running"):
        run_test_preview.should_start(reset=True)


def test_partial_or_unrelated_port_occupation_fails_clearly(monkeypatch):
    monkeypatch.setattr(run_test_preview, "http_ready", lambda _url: False)
    monkeypatch.setattr(run_test_preview, "port_in_use", lambda port: port == run_test_preview.API_PORT)

    with pytest.raises(RuntimeError, match=str(run_test_preview.API_PORT)):
        run_test_preview.should_start(reset=False)


def test_reset_removes_only_the_isolated_preview_database(monkeypatch, tmp_path):
    monkeypatch.setattr(run_test_preview, "STATE_DIR", tmp_path)
    preview_files = [tmp_path / f"preview.db{suffix}" for suffix in ("", "-shm", "-wal")]
    unrelated = tmp_path / "keep-me.db"
    for path in [*preview_files, unrelated]:
        path.write_text("test", encoding="utf-8")

    run_test_preview.reset_database()

    assert all(not path.exists() for path in preview_files)
    assert unrelated.read_text(encoding="utf-8") == "test"


def test_preview_opens_in_default_browser_unless_disabled(monkeypatch):
    opened = []
    monkeypatch.setattr(run_test_preview.webbrowser, "open", opened.append)

    run_test_preview.open_preview(no_open=False)
    run_test_preview.open_preview(no_open=True)

    assert opened == [f"http://127.0.0.1:{run_test_preview.WEB_PORT}/app"]
