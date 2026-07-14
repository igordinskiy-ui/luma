from app.session import issue_session, session_subject
from app.config import settings


def test_signed_session_round_trip(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "unit-test-session-secret-32chars")
    assert session_subject(issue_session(42, 1)) == (42, 1)


def test_rejects_tampered_session(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "unit-test-session-secret-32chars")
    token = issue_session(42, 1)
    assert session_subject(token + "broken") is None
