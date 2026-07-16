"""Versioned catalogue of general, non-medical self-help prompts."""
import hashlib
import json

CONTENT_VERSION = "v1-draft"
EDITORIAL_STATUS = "pending_medical_content_and_legal_review"

BOT_MESSAGES = {
    "start": "Я помогу пройти путь от последней пачки к жизни без сигарет. Открой помощника и начни без давления.",
    "craving": "Тяга временна. Выпей воды, сделай 6 медленных выдохов и пройдись 2 минуты. Открой помощника, чтобы отметить контекст.",
}
BOT_BUTTONS = {"open_app": "Открыть помощника", "craving": "Меня тянет"}

COPING_TECHNIQUES = {
    "breathing": {"title": "Медленный выдох", "duration_seconds": 300, "instruction": "Вдыхай спокойно и делай выдох немного длиннее вдоха. Здесь не нужно делать идеально."},
    "water": {"title": "Стакан воды", "duration_seconds": 180, "instruction": "Пей небольшими глотками и замечай температуру воды."},
    "walk": {"title": "Короткая прогулка", "duration_seconds": 420, "instruction": "Смени пространство и пройди хотя бы несколько десятков шагов в удобном темпе."},
}

COPING = {
    "stress": "Сделай 6 медленных выдохов. Затем выпей воды и пройдись две минуты.",
    "coffee": "Смени привычный сценарий: вода вместо второй чашки и две минуты ходьбы.",
    "after_meal": "Встань из-за стола, почисти зубы или пожуй жвачку в течение пяти минут.",
    "alcohol": "Отложи алкоголь на сегодня и напиши человеку поддержки одну короткую фразу.",
    "default": "Тяга пройдёт. Поставь таймер на 5 минут: вода, движение и медленный выдох.",
}

# Shown only at the end of the last pack. These are deliberately concrete,
# brief behavioural preparations rather than medical instructions.
PRE_QUIT_STEPS = [
    "Убери зажигалки и пепельницы из быстрого доступа.",
    "Выбери замену ритуалу: вода, жвачка или короткая прогулка.",
    "Напиши одному человеку: «Я начинаю бросать, мне может понадобиться поддержка».",
    "Сохрани план на 5 минут: вода, движение, медленный выдох.",
]

RECOVERY_STEPS = [
    "Не обнуляй весь путь: зафиксируй, что произошло, без самообвинения.",
    "Убери оставшиеся сигареты и на ближайшие два часа смени привычный сценарий.",
    "Вода, короткая прогулка и один контакт с человеком поддержки.",
]

# The production approval is bound to these exact user-visible strings. Any
# editorial change produces a new digest and therefore closes the production
# gate until the revised catalogue has been reviewed again.
_PUBLIC_CONTENT = {
    "version": CONTENT_VERSION,
    "bot_messages": BOT_MESSAGES,
    "bot_buttons": BOT_BUTTONS,
    "coping_techniques": COPING_TECHNIQUES,
    "coping_prompts": COPING,
    "pre_quit_steps": PRE_QUIT_STEPS,
    "recovery_steps": RECOVERY_STEPS,
}
CONTENT_DIGEST = hashlib.sha256(
    json.dumps(_PUBLIC_CONTENT, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

def intervention(trigger: str | None) -> str:
    return COPING.get(trigger or "default", COPING["default"])
