from datetime import datetime, timedelta

from app.journey import elapsed_seconds, next_milestone


def test_elapsed_seconds_never_becomes_negative():
    now = datetime.utcnow()
    assert elapsed_seconds(now, now - timedelta(seconds=5)) == 0


def test_next_milestone_is_strictly_ahead():
    assert next_milestone(0) == (3600, "1 час")
    assert next_milestone(3600) == (21600, "6 часов")


def test_final_milestone_has_no_false_target():
    assert next_milestone(400 * 86400) == (None, None)
