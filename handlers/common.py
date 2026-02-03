from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode

from keyboards.builders import get_main_menu
from services.rutube_service import search_exercise_video

router = Router()

class VideoState(StatesGroup):
    waiting_for_name = State()

# --- ОТМЕНА ---
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных действий.", reply_markup=get_main_menu())
        return
    await state.clear()
    await message.answer("🚫 Отменено.", reply_markup=get_main_menu())

# --- ВХОД В ПОИСК (КНОПКА ИЛИ CALLBACK) ---
async def start_search_logic(message: Message, state: FSMContext):
    await message.answer(
        "🎥 <b>Поиск упражнений (RuTube 🇷🇺)</b>\n\n"
        "Напиши название упражнения (например: <i>Жим лежа</i>), "
        "и я найду видео с техникой.",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(VideoState.waiting_for_name)

# 1. Если нажали кнопку в меню
@router.message(F.text == "🎥 Техника")
async def btn_video_search(message: Message, state: FSMContext):
    await start_search_logic(message, state)

# 2. Если нажали инлайн кнопку (если где-то осталась)
@router.callback_query(F.data == "video_search")
async def cb_video_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_search_logic(callback.message, state)

# --- ОБРАБОТКА ПОИСКА ---
@router.message(VideoState.waiting_for_name)
async def process_video_search(message: Message, state: FSMContext):
    if message.text.startswith('/'): return

    link, title, description = await search_exercise_video(message.text)
    
    if link:
        text = (
            f"✅ <b>{title}</b>\n"
            f"ℹ️ {description}\n\n"
            f"👇 <b>Смотреть варианты:</b>\n{link}"
        )
        await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
        await message.answer("Напиши еще название или /cancel")
    else:
        await message.answer("Ошибка поиска.")