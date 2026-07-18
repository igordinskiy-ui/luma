from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
import base64
import binascii
import re
from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator
from .api_time import utc_iso


class ApiOut(BaseModel):
    """Response model that never emits timezone-ambiguous datetime strings."""
    @field_serializer("created_at", "updated_at", "recovery_until", "target_quit_at", check_fields=False)
    def serialize_utc_datetime(self, value: datetime | None) -> str | None:
        return utc_iso(value)

class OnboardingIn(BaseModel):
    timezone: str = "Europe/Moscow"
    cigarettes_per_pack: int = Field(20, ge=1, le=100)
    remaining: int = Field(0, ge=0, le=100)
    pack_price: float = Field(0, ge=0, le=1_000_000, allow_inf_nan=False)
    reasons: str = Field("", max_length=2000)
    start_mode: Literal["preparation", "last_pack", "quit"]
    target_quit_at: datetime | None = None
    age_confirmed: Literal[True]
    consent: Literal[True]

    @model_validator(mode="after")
    def validate_start(self):
        if self.start_mode == "last_pack" and self.remaining < 1:
            raise ValueError("Last-pack mode requires at least one remaining cigarette")
        if self.start_mode == "quit" and self.remaining != 0:
            raise ValueError("Quit mode requires zero remaining cigarettes")
        if self.start_mode == "preparation":
            if not self.target_quit_at or not self.target_quit_at.tzinfo:
                raise ValueError("Preparation mode requires a timezone-aware target date")
            if self.target_quit_at <= datetime.now(timezone.utc):
                raise ValueError("Target date must be in the future")
        return self

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        if len(value) > 64: raise ValueError("Timezone is too long")
        try: ZoneInfo(value)
        except Exception as exc: raise ValueError("Timezone is invalid") from exc
        return value


class ConsentIn(BaseModel):
    age_confirmed: Literal[True]
    consent: Literal[True]

class EventIn(BaseModel):
    kind: str = Field(pattern="^(smoked|craving|relapse)$")
    trigger: Literal["stress", "anger", "boredom", "coffee", "after_meal", "driving", "work_break", "social", "friends", "alcohol", "focus", "hands", "outside", "habit", "physical"] | None = None
    intensity: int | None = Field(None, ge=1, le=5)
    note: str = Field("", max_length=1000)
    client_event_id: str = Field(min_length=8, max_length=64)
    relapse_context: Literal["one", "day", "days", "afraid", "angry", "hopeless"] | None = None

    @model_validator(mode="after")
    def relapse_context_matches_kind(self):
        if self.relapse_context is not None and self.kind != "relapse":
            raise ValueError("relapse_context is only valid for relapse events")
        return self

class AuthIn(BaseModel):
    init_data: str = Field(min_length=10, max_length=16384)

class OidcCompletionIn(BaseModel):
    code: str = Field(min_length=24, max_length=128)
    client_state: str = Field(pattern=r"^[A-Za-z0-9_-]{24,128}$")

class EventPatchIn(BaseModel):
    trigger: Literal["stress", "anger", "boredom", "coffee", "after_meal", "driving", "work_break", "social", "friends", "alcohol", "focus", "hands", "outside", "habit", "physical"] | None = None
    intensity: int | None = Field(None, ge=1, le=5)
    note: str | None = Field(None, max_length=1000)


class CopingSessionCreateIn(BaseModel):
    client_session_id: str = Field(min_length=8, max_length=64)
    source: Literal["dashboard", "journal", "notification", "offline"] = "dashboard"
    trigger: Literal["stress", "anger", "boredom", "coffee", "after_meal", "driving", "work_break", "social", "friends", "alcohol", "focus", "hands", "outside", "habit", "physical"] | None = None
    intensity_before: int = Field(ge=1, le=10)


class CopingSessionPatchIn(BaseModel):
    technique: Literal["breathing", "delay", "change_place", "walk", "water", "hands", "mouth", "grounding", "focus_sprint", "social_exit", "urge_surf", "support_message"] | None = None
    status: Literal["active", "paused", "completed", "abandoned"] | None = None
    intensity_after: int | None = Field(None, ge=1, le=10)
    outcome: Literal["helped", "same", "worse"] | None = None

    @model_validator(mode="after")
    def completion_has_result(self):
        # Outcome was added after intensity_after. Old /v1 clients remain
        # valid; the endpoint derives a deterministic outcome when omitted.
        if self.status == "completed" and self.intensity_after is None:
            raise ValueError("Completed coping session requires intensity_after")
        return self

class PreferencesIn(BaseModel):
    enabled: bool = False
    max_daily: int = Field(3, ge=0, le=6)
    quiet_start: int = Field(22, ge=0, le=23)
    quiet_end: int = Field(9, ge=0, le=23)

class QuitPlanUpdateIn(BaseModel):
    remaining: int | None = Field(None, ge=0, le=100)
    cigarettes_per_pack: int | None = Field(None, ge=1, le=100)
    pack_price: float | None = Field(None, ge=0, le=1_000_000, allow_inf_nan=False)
    phase: Literal["preparation", "last_pack", "quit", "paused"] | None = None
    reasons: str | None = Field(None, max_length=2000)
    target_quit_at: datetime | None = None

    @field_validator("target_quit_at")
    @classmethod
    def validate_target_quit_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("Target date must include a timezone")
        if value <= datetime.now(timezone.utc):
            raise ValueError("Target date must be in the future")
        return value

class EventOut(ApiOut):
    id: int
    kind: str
    trigger: str | None
    intensity: int | None
    note: str
    relapse_context: Literal["one", "day", "days", "afraid", "angry", "hopeless"] | None = None
    created_at: datetime

class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=2048)
    p256dh: str = Field(min_length=8, max_length=1024)
    auth: str = Field(min_length=8, max_length=1024)

    @field_validator("endpoint")
    @classmethod
    def validate_push_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        allowed_hosts = {"fcm.googleapis.com", "updates.push.services.mozilla.com", "push.services.mozilla.com", "web.push.apple.com"}
        if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in allowed_hosts:
            raise ValueError("Push endpoint host is not allowed")
        return value

    @field_validator("p256dh")
    @classmethod
    def validate_p256dh(cls, value: str) -> str:
        decoded = _decode_push_key(value)
        if len(decoded) != 65 or decoded[0] != 4:
            raise ValueError("p256dh must be an uncompressed P-256 public key")
        return value

    @field_validator("auth")
    @classmethod
    def validate_auth_secret(cls, value: str) -> str:
        if len(_decode_push_key(value)) != 16:
            raise ValueError("auth must be a 16-byte push secret")
        return value


def _decode_push_key(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Push key must use base64url encoding")
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Push key must use base64url encoding") from exc

class FeedbackIn(BaseModel):
    category: Literal["bug", "idea", "support", "content"]
    body: str = Field(min_length=3, max_length=2000)

class FeedbackStatusIn(BaseModel):
    status: Literal["open", "resolved"]


class ClientTelemetryIn(BaseModel):
    event: Literal["session_started", "crash"]
    client_session_id: str = Field(pattern=r"^[0-9a-f-]{36}$")

class DashboardOut(ApiOut):
    phase: str
    paused_from: str | None = None
    remaining: int
    cigarettes_per_pack: int
    pack_price: float
    smoke_free_seconds: int
    best_smoke_free_seconds: int
    attempt_number: int
    next_milestone_seconds: int | None = None
    next_milestone_label: str | None = None
    avoided_cigarettes: int
    saved_money: float
    # Deprecated v1 compatibility field. It is constant and is not a personal
    # health, addiction or relapse-risk classification.
    risk: Literal["low"]
    intervention: str
    reasons: str
    recent_triggers: list[str]
    preparation_steps: list[str]
    recovery_until: datetime | None = None
    recovery_steps: list[str]
    updated_at: datetime | None = None
    target_quit_at: datetime | None = None
