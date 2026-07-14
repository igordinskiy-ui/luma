from datetime import datetime

import pytest

from app.journal import decode_cursor, encode_cursor


def test_journal_cursor_round_trip():
    created = datetime(2026, 7, 14, 12, 30, 15, 123456)
    assert decode_cursor(encode_cursor(created, "coping", 42)) == (created, "coping", 42)


def test_journal_cursor_rejects_unknown_source():
    with pytest.raises(ValueError):
        decode_cursor("bm90LWFjdHVhbC1jdXJzb3I")
