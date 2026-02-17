from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.builders import get_main_menu
from services.rutube_service import search_exercise_video
from keyboards.main_menu import get_main_menu

router = Router()

class VideoState(StatesGroup):
    waiting_for_name = State()

# --- ОТМЕНА (Универсальная) ---
@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    
    # Очищаем состояние (это выведет юзера из поиска видео или из пожеланий AI)
    await state.clear()
    
    if current_state is None:
        await message.answer(
            "Нет активных действий для отмены.", 
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(
            "🚫 Действие отменено. Возвращаюсь в меню.", 
            reply_markup=get_main_menu()
        )

# --- ВХОД В ПОИСК (Эту оставляем без изменений) ---
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

# 2. Если нажали инлайн кнопку (из меню или после поиска)
@router.callback_query(F.data == "video_search")
async def cb_video_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_search_logic(callback.message, state)

# --- ОБРАБОТКА ПОИСКА ---
@router.message(VideoState.waiting_for_name)
async def process_video_search(message: Message, state: FSMContext):
    # Игнорируем команды, чтобы можно было нажать /cancel или кнопки меню
    if message.text.startswith('/'): return

    link, title, description = await search_exercise_video(message.text)
    
    if link:
        text = (
            f"✅ <b>{title}</b>\n"
            f"ℹ️ {description}\n\n"
            f"👇 <b>Смотреть варианты:</b>\n{link}"
        )
        await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
        
        # 🔥 ИЗМЕНЕНИЕ: Сбрасываем состояние и даем кнопку
        await state.clear()
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔍 Найти еще", callback_data="video_search"))
        
        await message.answer("Поиск завершен. Хотите найти что-то еще?", reply_markup=builder.as_markup())
    else:
        # При ошибке оставляем пользователя в состоянии поиска, чтобы он мог исправить опечатку
        await message.answer("❌ Не нашел видео. Попробуй написать точнее (например: 'Приседания').")