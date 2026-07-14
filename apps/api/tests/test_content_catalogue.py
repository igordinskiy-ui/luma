import hashlib
import json

from app.content import BOT_BUTTONS, BOT_MESSAGES, CONTENT_DIGEST, CONTENT_VERSION, COPING, COPING_TECHNIQUES, PRE_QUIT_STEPS, RECOVERY_STEPS


def test_content_digest_covers_every_user_visible_catalogue():
    payload = {
        "version": CONTENT_VERSION,
        "bot_messages": BOT_MESSAGES,
        "bot_buttons": BOT_BUTTONS,
        "coping_techniques": COPING_TECHNIQUES,
        "coping_prompts": COPING,
        "pre_quit_steps": PRE_QUIT_STEPS,
        "recovery_steps": RECOVERY_STEPS,
    }
    expected = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert CONTENT_DIGEST == expected
    assert set(BOT_MESSAGES) == {"start", "craving"}
    assert set(BOT_BUTTONS) == {"open_app", "craving"}
