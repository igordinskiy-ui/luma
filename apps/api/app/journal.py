"""Opaque journal cursor helpers."""
import base64
from datetime import datetime


def encode_cursor(created_at: datetime, source: str, item_id: int) -> str:
    raw = f"{created_at.isoformat()}|{source}|{item_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, str, int]:
    try:
        padded = value + "=" * (-len(value) % 4)
        timestamp, source, item_id = base64.urlsafe_b64decode(padded).decode().split("|", 2)
        if source not in {"event", "coping"}:
            raise ValueError
        return datetime.fromisoformat(timestamp), source, int(item_id)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid journal cursor") from exc
