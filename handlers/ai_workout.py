import re
import json # <--- Нужно для сохранения списков в базу
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

from database.crud import UserCRUD
from services.groq_service import GroqService 
from states.workout_states import WorkoutPagination
from keyboards.pagination import get_pagination_kb

router = Router()

def clean_text(text: str) -> str:
    """Чистильщик текста"""
    if not text: return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    text = re.sub(r'(^|\n)(День \d+:.*?)(?=\n|$)', r'\1<b>\2</b>', text)
    text = text.replace("###", "").replace("SPLIT", "")
    return text

# --- 1. ГЕНЕРАЦИЯ НОВОЙ ПРОГРАММЫ ---
@router.message(Command("ai_workout"))
@router.message(F.text == "🤖 AI Тренировка")
@router.callback_query(F.data == "ai_workout")
@router.callback_query(F.data == "refresh_ai_workout")
async def start_workout_generation(event: Union[Message, CallbackQuery], session: AsyncSession, state: FSMContext):
    
    if isinstance(event, Message):
        message = event
    else:
        message = event.message
        await event.answer()

    user = await UserCRUD.get_user(session, event.from_user.id)
    if not user or not user.workout_level:
        await message.answer("❌ Сначала заполните профиль (/start)!", parse_mode=ParseMode.HTML)
        return
    
    loading_msg = await message.answer("🗓 <b>AI составляет новый график...</b>", parse_mode=ParseMode.HTML)
    
    user_data = {
        "workout_days": user.workout_days,
        "goal": user.goal,
        "gender": user.gender,
        "weight": user.weight,
        "age": user.age,
        "workout_level": user.workout_level
    }
    
    ai_service = GroqService()
    raw_pages = await ai_service.generate_workout_pages(user_data)
    
    if not raw_pages or (len(raw_pages) == 1 and "Ошибка" in raw_pages[0]):
        await loading_msg.edit_text(f"❌ Не удалось сгенерировать: {raw_pages[0] if raw_pages else 'Пустой ответ'}")
        return

    cleaned_pages = [clean_text(p) for p in raw_pages]

    # 🔥 СОХРАНЯЕМ В БАЗУ ДАННЫХ 🔥
    # Превращаем список в строку JSON, чтобы сохранить в одну ячейку таблицы
    pages_json = json.dumps(cleaned_pages, ensure_ascii=False)
    await UserCRUD.update_user(session, event.from_user.id, current_workout_program=pages_json)

    # Сохраняем во временную память (FSM) для быстрого листания
    await state.update_data(workout_pages=cleaned_pages, current_page=0)
    await state.set_state(WorkoutPagination.active)
    
    await loading_msg.delete()
    
    await message.answer(
        text=cleaned_pages[0],
        reply_markup=get_pagination_kb(0, len(cleaned_pages), page_type="workout"),
        parse_mode=ParseMode.HTML
    )

# --- 2. ПРОСМОТР СОХРАНЕННОЙ ПРОГРАММЫ ---
@router.message(F.text == "📅 Моя программа")
async def show_saved_program(message: Message, session: AsyncSession, state: FSMContext):
    """Достает программу из базы данных"""
    
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Ошибка профиля.")
        return

    # Проверяем, есть ли сохраненная программа
    if not user.current_workout_program:
        await message.answer(
            "📭 <b>У вас пока нет сохраненной программы.</b>\n\n"
            "Нажмите <b>'🤖 AI Тренировка'</b>, чтобы создать её.",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        # Превращаем строку из базы обратно в список
        saved_pages = json.loads(user.current_workout_program)
        
        # Загружаем в состояние (FSM), чтобы работали кнопки листания
        await state.update_data(workout_pages=saved_pages, current_page=0)
        await state.set_state(WorkoutPagination.active)
        
        await message.answer(
            text=saved_pages[0],
            reply_markup=get_pagination_kb(0, len(saved_pages), page_type="workout"),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        await message.answer(f"Ошибка загрузки программы: {e}")

# --- 3. ПЕРЕЛИСТЫВАНИЕ (Без изменений) ---
@router.callback_query(F.data.startswith("workout_page_"))
async def change_page(callback: CallbackQuery, state: FSMContext):
    try:
        target_page = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка данных")
        return

    data = await state.get_data()
    pages = data.get("workout_pages")
    
    if not pages:
        await callback.answer("Нажмите '📅 Моя программа' чтобы обновить.", show_alert=True)
        return
        
    if target_page < 0 or target_page >= len(pages):
        await callback.answer("Это последняя страница")
        return
        
    await state.update_data(current_page=target_page)
    
    try:
        await callback.message.edit_text(
            text=pages[target_page],
            reply_markup=get_pagination_kb(target_page, len(pages), page_type="workout"),
            parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest:
        await callback.answer()
    except Exception as e:
        await callback.answer(f"Ошибка: {e}")

@router.callback_query(F.data == "noop")
async def noop_btn(callback: CallbackQuery):
    await callback.answer()