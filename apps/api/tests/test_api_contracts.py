from app.schemas import ConsentIn, CopingSessionCreateIn, CopingSessionPatchIn, EventIn, OidcCompletionIn, OnboardingIn, PreferencesIn, PushSubscriptionIn, QuitPlanUpdateIn
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError
import pytest
import base64

def test_onboarding_rejects_empty_pack():
    with pytest.raises(ValidationError):
        OnboardingIn(cigarettes_per_pack=0, remaining=20, start_mode="last_pack", age_confirmed=True, consent=True)


def test_onboarding_rejects_oversized_free_text():
    with pytest.raises(ValidationError):
        OnboardingIn(reasons="x" * 2001, remaining=20, start_mode="last_pack", age_confirmed=True, consent=True)

def test_onboarding_requires_adult_confirmation():
    with pytest.raises(ValidationError):
        OnboardingIn(start_mode="last_pack", remaining=20, consent=True)


def test_reconsent_requires_both_explicit_confirmations():
    with pytest.raises(ValidationError):
        ConsentIn(age_confirmed=True, consent=False)

def test_last_pack_requires_a_remaining_cigarette():
    with pytest.raises(ValidationError):
        OnboardingIn(start_mode="last_pack", remaining=0, age_confirmed=True, consent=True)

def test_preparation_requires_a_future_timezone_aware_target():
    with pytest.raises(ValidationError):
        OnboardingIn(start_mode="preparation", remaining=20, age_confirmed=True, consent=True)


def test_quit_plan_update_rejects_past_or_timezone_naive_target():
    with pytest.raises(ValidationError):
        QuitPlanUpdateIn(target_quit_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    with pytest.raises(ValidationError):
        QuitPlanUpdateIn(target_quit_at=datetime.now() + timedelta(days=1))


def test_quit_plan_update_accepts_future_timezone_aware_target():
    target = datetime.now(timezone.utc) + timedelta(days=1)
    assert QuitPlanUpdateIn(target_quit_at=target).target_quit_at == target


def test_quit_plan_numbers_are_bounded():
    assert QuitPlanUpdateIn(cigarettes_per_pack=25, pack_price=350).cigarettes_per_pack == 25
    with pytest.raises(ValidationError):
        QuitPlanUpdateIn(cigarettes_per_pack=0)
    with pytest.raises(ValidationError):
        QuitPlanUpdateIn(pack_price=1_000_001)

def test_event_accepts_craving():
    assert EventIn(kind="craving", intensity=5, client_event_id="test-event-1").kind == "craving"

def test_event_rejects_free_form_trigger():
    with pytest.raises(ValidationError):
        EventIn(kind="craving", trigger="free text", client_event_id="test-event-2")

def test_notification_limit_is_capped():
    with pytest.raises(ValidationError):
        PreferencesIn(max_daily=7)


def test_notifications_require_explicit_opt_in():
    assert PreferencesIn().enabled is False

def test_push_subscription_rejects_non_push_host():
    with pytest.raises(ValidationError):
        PushSubscriptionIn(endpoint="https://127.0.0.1/internal-resource", p256dh="x" * 8, auth="x" * 8)


def test_push_subscription_validates_cryptographic_key_material():
    endpoint = "https://fcm.googleapis.com/subscription"
    with pytest.raises(ValidationError):
        PushSubscriptionIn(endpoint=endpoint, p256dh="!!!!!!!!", auth="!!!!!!!!")

    p256dh = base64.urlsafe_b64encode(b"\x04" + b"x" * 64).decode().rstrip("=")
    auth = base64.urlsafe_b64encode(b"a" * 16).decode().rstrip("=")
    assert PushSubscriptionIn(endpoint=endpoint, p256dh=p256dh, auth=auth).auth == auth

def test_oidc_completion_rejects_unsafe_client_state():
    with pytest.raises(ValidationError):
        OidcCompletionIn(code="x" * 32, client_state="x" * 23 + "&redirect=attacker")


def test_coping_session_does_not_accept_free_text_trigger():
    with pytest.raises(ValidationError):
        CopingSessionCreateIn(client_session_id="session-123", trigger="my private note", intensity_before=5)


def test_completed_coping_session_requires_after_intensity():
    with pytest.raises(ValidationError):
        CopingSessionPatchIn(status="completed", technique="water")


def test_completed_coping_session_keeps_v1_outcome_backward_compatibility():
    payload = CopingSessionPatchIn(status="completed", technique="water", intensity_after=3)
    assert payload.outcome is None


def test_legacy_friends_trigger_remains_accepted_in_v1():
    assert EventIn(kind="craving", trigger="friends", intensity=3, client_event_id="legacy-friends-1").trigger == "friends"


def test_recovery_context_is_scoped_to_relapse_events():
    with pytest.raises(ValidationError):
        EventIn(kind="craving", relapse_context="afraid", client_event_id="wrong-context-1")
    assert EventIn(kind="relapse", relapse_context="afraid", client_event_id="right-context-1").relapse_context == "afraid"
