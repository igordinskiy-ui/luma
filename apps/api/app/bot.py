"""Telegram communications layer. Run separately with: python -m app.bot"""
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, Update, WebAppInfo

from .config import settings
from .content import BOT_BUTTONS, BOT_MESSAGES

dp = Dispatcher()


def app_keyboard() -> ReplyKeyboardMarkup:
    """Keep a useful one-tap craving fallback outside the Mini App."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BOT_BUTTONS["open_app"], web_app=WebAppInfo(url=settings.telegram_webapp_url))],
            [KeyboardButton(text=BOT_BUTTONS["craving"])],
        ],
        resize_keyboard=True,
    )


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        BOT_MESSAGES["start"],
        reply_markup=app_keyboard(),
    )


@dp.message(F.text == BOT_BUTTONS["craving"])
async def craving(message: Message):
    await message.answer(
        BOT_MESSAGES["craving"],
        reply_markup=app_keyboard(),
    )


async def main():
    if settings.app_environment == "production":
        raise RuntimeError("Polling is disabled in production; configure the webhook")
    if not settings.telegram_bot_token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN before starting the bot")
    bot = Bot(settings.telegram_bot_token)
    await dp.start_polling(bot)


async def handle_update(bot: Bot, payload: dict) -> None:
    """Used by FastAPI webhook endpoint in production."""
    await dp.feed_update(bot, Update.model_validate(payload))


if __name__ == "__main__":
    asyncio.run(main())
