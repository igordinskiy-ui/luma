import pytest

from app.analytics import validate_event


def test_client_health_accepts_only_server_shaped_session_hashes():
    session_hash = "a" * 32
    assert validate_event("client_session_started", {"session_hash": session_hash}) == {"session_hash": session_hash}
    assert validate_event("client_crash", {"session_hash": session_hash}) == {"session_hash": session_hash}
    with pytest.raises(ValueError):
        validate_event("client_crash", {"session_hash": "stack trace or URL"})


def test_analytics_rejects_unapproved_or_free_text_properties():
    with pytest.raises(ValueError):
        validate_event("behavior_recorded", {"kind": "craving", "trigger": "stress", "intensity": 3, "note": "private detail"})
    with pytest.raises(ValueError):
        validate_event("coping_started", {"source": "dashboard", "trigger": "coffee", "intensity": 7})
    with pytest.raises(ValueError):
        validate_event("onboarding_completed", {"phase": "preparation", "remaining_bucket": 20})
    with pytest.raises(ValueError):
        validate_event("unknown", {})
