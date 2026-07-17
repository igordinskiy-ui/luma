import hashlib
import json

from app.content import BOT_BUTTONS, BOT_MESSAGES, CONTENT_DIGEST, CONTENT_VERSION, COPING, COPING_TECHNIQUES, PRE_QUIT_STEPS, RECOVERY_SCENARIOS, TRIGGERS


def test_content_digest_covers_every_user_visible_catalogue():
    payload = {
        "version": CONTENT_VERSION,
        "bot_messages": BOT_MESSAGES,
        "bot_buttons": BOT_BUTTONS,
        "triggers": TRIGGERS,
        "coping_techniques": COPING_TECHNIQUES,
        "coping_prompts": COPING,
        "pre_quit_steps": PRE_QUIT_STEPS,
        "recovery_scenarios": RECOVERY_SCENARIOS,
    }
    expected = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert CONTENT_DIGEST == expected
    assert set(BOT_MESSAGES) == {"start", "craving"}
    assert set(BOT_BUTTONS) == {"open_app", "craving"}


def test_support_catalogue_has_beta_depth_and_routing_metadata():
    assert len(TRIGGERS) >= 10
    assert len(COPING_TECHNIQUES) >= 8
    assert len(RECOVERY_SCENARIOS) >= 6
    assert all(len(item["steps"]) >= 3 for item in COPING_TECHNIQUES.values())
    assert all(item["best_for"] and len(item["intensity"]) == 2 for item in COPING_TECHNIQUES.values())
