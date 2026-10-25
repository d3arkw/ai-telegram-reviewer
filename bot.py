import asyncio
import logging
import time
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.config import settings
from app.deps import close_llm_clients, get_code_review_service
from app.models.review_level import ReviewLevel
from utils import render_review

logger = logging.getLogger(__name__)
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

MAX_CODE_LEN = 8000
REVIEW_COOLDOWN = 10.0

user_levels: dict[int, ReviewLevel] = {}
last_review: dict[int, float] = {}
user_providers: dict[int, dict] = {}
ROUTER_MODELS = [
    ("qwen/qwen3.7-flash", "Qwen 3.7 Flash — 3.14₽/13₽ за 1M"),
    ("inclusionai/ling-3.0-flash", "Ling 3.0 Flash — 2.20₽/6₽ за 1M"),
    ("minimax/minimax-m3.1-flash", "MiniMax M3.1 Flash — 9₽/52₽ за 1M"),
]
# TODO: Redis/FSM — user_levels и last_review теряются при рестарте
LEVELS = {
    ReviewLevel.JUNIOR: "Junior",
    ReviewLevel.MIDDLE: "Middle",
    ReviewLevel.SENIOR: "Senior",
}


LEVEL_BUTTONS = {
    "Junior": ReviewLevel.JUNIOR,
    "Middle": ReviewLevel.MIDDLE,
    "Senior": ReviewLevel.SENIOR,
}


def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Junior")
    builder.button(text="Middle")
    builder.button(text="Senior")
    builder.button(text="⚙️ Провайдер")
    builder.adjust(3, 1)
    return builder.as_markup(resize_keyboard=True)


def get_level_keyboard():
    builder = InlineKeyboardBuilder()
    for level, title in LEVELS.items():
        builder.button(
            text=title,
            callback_data=f"level:{level.value}",
        )
    builder.adjust(3)
    return builder.as_markup()


class ProviderSetup(StatesGroup):
    waiting_key = State()


def get_provider_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✨ Gemini (бесплатно)", callback_data="provider:gemini")
    builder.button(text="🔀 RouterAI (свой ключ)", callback_data="provider:routerai")
    builder.adjust(1)
    return builder.as_markup()


def get_router_models_keyboard():
    builder = InlineKeyboardBuilder()
    for model_id, title in ROUTER_MODELS:
        builder.button(text=title, callback_data=f"routermodel:{model_id}")
    builder.adjust(1)
    return builder.as_markup()


@dp.message(CommandStart())
async def start_message(message: Message):
    await message.answer(
        "Привет! Пришли Python-код, и я сделаю AI-ревью.\n"
        "Уровень: Middle, провайдер: Gemini. Меняется кнопками снизу",
        reply_markup=get_main_keyboard(),
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


@dp.message(F.text == "⚙️ Провайдер")
async def provider_menu(message: Message):
    if message.from_user is None:
        return
    current = user_providers.get(message.from_user.id, {}).get("provider", "gemini")
    await message.answer(
        f"Текущий провайдер: {current}.\nВыбери:",
        reply_markup=get_provider_keyboard(),
    )


@dp.callback_query(F.data == "provider:gemini")
async def provider_gemini(callback: CallbackQuery):
    if callback.from_user is None:
        await callback.answer()
        return
    user_providers[callback.from_user.id] = {
        "provider": "gemini",
        "router_key": None,
        "router_model": None,
    }
    await callback.answer("Gemini включён ✅")
    if isinstance(callback.message, Message):
        await callback.message.answer("Провайдер: ✨ Gemini (бесплатно). Присылай код.")


@dp.callback_query(F.data == "provider:routerai")
async def provider_routerai(callback: CallbackQuery, state: FSMContext):
    if callback.from_user is None:
        await callback.answer()
        return
    await state.set_state(ProviderSetup.waiting_key)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer("Пришли свой RouterAI API-ключ одним сообщением:")


@dp.message(ProviderSetup.waiting_key, F.text)
async def router_key_received(message: Message, state: FSMContext):
    if message.from_user is None or message.text is None:
        return
    if message.text.startswith("/"):
        await state.clear_state()
        return
    key = message.text.strip()
    if len(key) < 10:
        await message.answer("Похоже, это не ключ. Пришли ещё раз:")
        return
    user_settings = user_providers.get(message.from_user.id, {})
    user_settings.update(
        {"provider": "routerai", "router_key": key, "router_model": None}
    )
    user_providers[message.from_user.id] = user_settings
    await state.clear_state()
    await message.answer(
        f"Ключ сохранён (...{escape(key[-4:])}). Теперь выбери модель:",
        reply_markup=get_router_models_keyboard(),
    )


@dp.callback_query(F.data.startswith("routermodel:"))
async def router_model_chosen(callback: CallbackQuery):
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return
    model = callback.data.partition(":")[2]
    user_settings = user_providers.get(callback.from_user.id, {})
    if not user_settings.get("router_key"):
        await callback.answer("Сначала введи ключ.", show_alert=True)
        return
    user_settings.update({"provider": "routerai", "router_model": model})
    user_providers[callback.from_user.id] = user_settings
    await callback.answer("Модель сохранена ✅")
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Провайдер: 🔀 RouterAI, модель: {escape(model)}. Присылай код."
        )


@dp.message(F.text.in_(LEVEL_BUTTONS))
async def level_buttons(message: Message):
    if message.from_user is None or message.text is None:
        return
    level = LEVEL_BUTTONS[message.text]
    user_levels[message.from_user.id] = level
    await message.answer(
        f"Уровень: {message.text} ✅\nПрисылай код.",
        reply_markup=get_main_keyboard(),
    )


@dp.message(F.text)
async def review_message(message: Message):

    if message.from_user is None or message.text is None:
        return

    code = message.text
    user_id = message.from_user.id
    if code.startswith("/"):
        return
    if code in LEVEL_BUTTONS or code == "⚙️ Провайдер":
        return

    level = user_levels.get(user_id, ReviewLevel.MIDDLE)
    user_settings = user_providers.get(user_id, {})
    provider = user_settings.get("provider", "gemini")

    if provider == "routerai" and not user_settings.get("router_key"):
        await message.answer(
            "Для RouterAI нужен твой API-ключ. Нажми «⚙️ Провайдер» и введи ключ."
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
        service = get_code_review_service(
            provider=provider,
            router_key=user_settings.get("router_key"),
            router_model=user_settings.get("router_model"),
        )
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
