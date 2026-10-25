import asyncio
import logging
import time
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.deps import close_llm_clients, get_code_review_service
from app.models.review_level import ReviewLevel
from utils import render_review

logger = logging.getLogger(__name__)
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

MAX_CODE_LEN = 8000
REVIEW_COOLDOWN = 10.0

user_levels: dict[int, ReviewLevel] = {}
last_review: dict[int, float] = {}
# TODO: Redis/FSM — user_levels и last_review теряются при рестарте
LEVELS = {
    ReviewLevel.JUNIOR: "Junior",
    ReviewLevel.MIDDLE: "Middle",
    ReviewLevel.SENIOR: "Senior",
}


def get_level_keyboard():
    builder = InlineKeyboardBuilder()
    for level, title in LEVELS.items():
        builder.button(
            text=title,
            callback_data=f"level:{level.value}",
        )
    builder.adjust(3)
    return builder.as_markup()


@dp.message(CommandStart())
async def start_message(message: Message):
    await message.answer(
        "Привет! Пришли Python-код, и я сделаю AI-ревью.\n"
        "Выбери уровень проверки кода:",
        reply_markup=get_level_keyboard(),
    )


@dp.callback_query(F.data.startswith("level:"))
async def select_level(callback: CallbackQuery) -> None:
    if callback.data is None:
        await callback.answer()
        return
    try:
        level = ReviewLevel(callback.data.partition(":")[2])

    except ValueError:
        await callback.answer(
            "Неизвестный уровень.",
            show_alert=True,
        )
        return
    if callback.from_user is None:
        await callback.answer()
        return
    user_levels[callback.from_user.id] = level
    await callback.answer("Уровень сохранён!")
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"✅ Выбран уровень: <b>{escape(LEVELS[level])}</b>\n\n"
            "Отправь Python-код для ревью.",
            parse_mode="HTML",
        )


@dp.message(F.text)
async def review_message(message: Message):
    if message.from_user is None or message.text is None:
        return

    code = message.text
    user_id = message.from_user.id
    if code.startswith("/"):
        return

    level = user_levels.get(user_id)

    if level is None:
        await message.answer(
            "Сначала выбери уровень ревью:", reply_markup=get_level_keyboard()
        )
        return

    if len(code) > MAX_CODE_LEN:
        await message.answer(
            f"Код слишком длинный ({len(code)} символов, максимум {MAX_CODE_LEN}).\n"
            "Пришли файл поменьше или часть кода."
        )
        return

    now = time.monotonic()
    last = last_review.get(user_id, 0.0)
    wait = REVIEW_COOLDOWN - (now - last)
    if wait > 0:
        await message.answer(f"Подожди {wait:.0f} сек. перед следующим ревью.")
        return
    last_review[user_id] = now

    await message.answer("Начинаю ревью...")

    try:
        service = get_code_review_service()
        review = await service.create_review(code=code, level=level)

        messages = render_review(review)
        for text in messages:
            await message.answer(text, parse_mode="HTML")
    except RuntimeError as exc:
        logger.warning("Ошибка при AI-ревью: %s", exc)
        await message.answer(
            f"Не получилось сделать ревью: {escape(str(exc))}", parse_mode="HTML"
        )
    except Exception:
        logger.exception("Ошибка при AI-ревью")
        await message.answer("Ошибка при код-ревью. Попробуй позже.")


async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await close_llm_clients()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
