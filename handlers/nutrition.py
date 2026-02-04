import json
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup 
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

from database.crud import UserCRUD
from services.groq_service import GroqService 
from services.recipe_service import search_recipe_video
from states.workout_states import WorkoutPagination
from keyboards.pagination import get_pagination_kb

router = Router()

class RecipeState(StatesGroup):
    waiting_for_dish = State()

def clean_text(text: str) -> str:
    """Легкая чистка на случай, если ИИ добавит лишнего"""
    if not text: return ""
    # На случай если ИИ по привычке использует Markdown **жирный**
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = text.replace("###", "").replace("Menu:", "")
    return text.strip()

# --- 1. ГЕНЕРАЦИЯ НОВОГО МЕНЮ ---
@router.message(F.text == "🍏 Питание")
@router.callback_query(F.data == "nutrition")
@router.callback_query(F.data == "refresh_nutrition") # Кнопка "Сгенерировать заново"
async def start_nutrition_generation(event: Union[Message, CallbackQuery], session: AsyncSession, state: FSMContext):
    
    if isinstance(event, Message):
        message = event
    else:
        message = event.message
        await event.answer()
    
    user = await UserCRUD.get_user(session, event.from_user.id)
    if not user:
        await message.answer("Заполните профиль!")
        return
    
    msg = await message.answer("🍎 <b>Диетолог составляет меню...</b>", parse_mode=ParseMode.HTML)
    
    user_data = {
        "goal": user.goal, "gender": user.gender, 
        "weight": user.weight, "age": user.age,
        "height": user.height, "activity_level": user.activity_level
    }
    
    ai = GroqService()
    # Получаем список страниц (JSON)
    raw_pages = await ai.generate_nutrition_pages(user_data)
    
    if not raw_pages or (len(raw_pages) == 1 and "Ошибка" in raw_pages[0]):
        await msg.edit_text(f"❌ Ошибка генерации: {raw_pages[0] if raw_pages else 'Пустой ответ'}")
        return

    # Чистим (на всякий случай)
    cleaned_pages = [clean_text(p) for p in raw_pages]
    
    # 🔥 СОХРАНЯЕМ В БАЗУ ДАННЫХ 🔥
    pages_json = json.dumps(cleaned_pages, ensure_ascii=False)
    await UserCRUD.update_user(session, event.from_user.id, current_nutrition_program=pages_json)

    # Сохраняем в FSM для листания
    await state.update_data(nutrition_pages=cleaned_pages, current_nutrition_page=0)
    await state.set_state(WorkoutPagination.active)
    
    await msg.delete()
    
    await message.answer(
        text=cleaned_pages[0],
        reply_markup=get_pagination_kb(0, len(cleaned_pages), page_type="nutrition"),
        parse_mode=ParseMode.HTML
    )

# --- 2. ПРОСМОТР СОХРАНЕННОГО МЕНЮ ---
@router.message(F.text == "🍽 Мое меню")
async def show_saved_nutrition(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user or not user.current_nutrition_program:
        await message.answer("📭 У вас пока нет сохраненного меню.\nНажмите <b>🍏 Питание</b>.", parse_mode=ParseMode.HTML)
        return

    try:
        saved_pages = json.loads(user.current_nutrition_program)
        
        await state.update_data(nutrition_pages=saved_pages, current_nutrition_page=0)
        await state.set_state(WorkoutPagination.active)
        
        await message.answer(
            text=saved_pages[0],
            reply_markup=get_pagination_kb(0, len(saved_pages), page_type="nutrition"),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await message.answer(f"Ошибка загрузки меню: {e}")

# --- 3. ЛИСТАЛКА (Обновленная) ---
@router.callback_query(F.data.startswith("nutrition_page_"))
async def change_nutrition_page(callback: CallbackQuery, state: FSMContext):
    try:
        target_page = int(callback.data.split("_")[-1])
        data = await state.get_data()
        pages = data.get("nutrition_pages")
        
        if not pages:
            # Если бот перезагружался и FSM пустой — пробуем подтянуть из базы (через алерт)
            await callback.answer("Данные устарели. Нажмите '🍽 Мое меню'", show_alert=True)
            return
            
        if target_page < 0 or target_page >= len(pages):
            await callback.answer()
            return
            
        await state.update_data(current_nutrition_page=target_page)
        
        await callback.message.edit_text(
            text=pages[target_page],
            reply_markup=get_pagination_kb(target_page, len(pages), page_type="nutrition"),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await callback.answer(f"Ошибка: {e}")

# --- 4. ПОИСК РЕЦЕПТОВ (Без изменений) ---
@router.callback_query(F.data == "recipe_search")
async def start_recipe_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "👨‍🍳 <b>Поиск рецептов</b>\n\n"
        "Напиши название блюда (например: <i>Сырники</i>), и я найду видео.",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(RecipeState.waiting_for_dish)

@router.message(RecipeState.waiting_for_dish)
async def process_recipe_search(message: Message, state: FSMContext):
    if message.text.startswith('/'): return
    
    wait_msg = await message.answer("🔎 Ищу рецепт...")
    link, title, description = await search_recipe_video(message.text)
    await wait_msg.delete()
    
    if link:
        text = f"✅ <b>{title}</b>\nℹ️ {description}\n\n👇 <b>Смотреть:</b>\n{link}"
        await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
        await message.answer("Напиши еще блюдо или выбери действие в меню")
    else:
        await message.answer("😔 Ничего не нашел. Попробуй другое название.")