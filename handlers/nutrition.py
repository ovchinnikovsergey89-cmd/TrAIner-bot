import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
# 👇 ДОБАВЛЕНА ЭТА СТРОКА (исправляет ошибку NameError)
from aiogram.fsm.state import State, StatesGroup 
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

from database.crud import UserCRUD
from services.groq_service import GroqService 
from services.recipe_service import search_recipe_video
from states.workout_states import WorkoutPagination
from keyboards.pagination import get_pagination_kb

router = Router()

# Теперь Python знает, что такое StatesGroup
class RecipeState(StatesGroup):
    waiting_for_dish = State()

def clean_text(text: str) -> str:
    """Умная чистка текста для красивого меню"""
    if not text: return ""
    
    # 1. Убираем Markdown жирный шрифт (**текст** -> <b>текст</b>)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # 2. Убираем Markdown курсив (*текст* -> <i>текст</i>)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    # 3. Делаем заголовки (Завтрак, Обед) жирными, если ИИ забыл
    text = re.sub(r'(^|\n)(🍳|🍲|🍗|🥛|🥗) (.*?)(?=\n|$)', r'\1\2 <b>\3</b>', text)

    # 4. Убираем технический мусор
    text = text.replace("###", "").replace("Menu:", "")
    
    return text.strip()

# --- ГЕНЕРАЦИЯ МЕНЮ ---
@router.message(F.text == "🍏 Питание")
@router.callback_query(F.data == "nutrition")
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
    
    msg = await message.answer("🍎 <b>Составляю вкусное меню...</b>", parse_mode=ParseMode.HTML)
    
    user_data = {
        "goal": user.goal, "gender": user.gender, 
        "weight": user.weight, "age": user.age
    }
    
    ai = GroqService()
    # Получаем страницы (ИИ делает 3 варианта)
    raw_pages = await ai.generate_nutrition_pages(user_data)
    
    if not raw_pages:
        await msg.edit_text("Ошибка генерации.")
        return

    # Чистим текст и фильтруем пустые страницы
    cleaned_pages = [clean_text(p) for p in raw_pages if len(p) > 50]
    
    if not cleaned_pages:
         await msg.edit_text("ИИ вернул пустой ответ. Попробуйте еще раз.")
         return

    await state.update_data(nutrition_pages=cleaned_pages, current_nutrition_page=0)
    await state.set_state(WorkoutPagination.active)
    
    await msg.delete()
    
    await message.answer(
        text=cleaned_pages[0],
        reply_markup=get_pagination_kb(0, len(cleaned_pages), page_type="nutrition"),
        parse_mode=ParseMode.HTML
    )

# --- ЛИСТАЛКА ---
@router.callback_query(F.data.startswith("nutrition_page_"))
async def change_nutrition_page(callback: CallbackQuery, state: FSMContext):
    try:
        target_page = int(callback.data.split("_")[-1])
        data = await state.get_data()
        pages = data.get("nutrition_pages")
        
        if not pages or target_page < 0 or target_page >= len(pages):
            await callback.answer("Ошибка страниц")
            return
            
        await state.update_data(current_nutrition_page=target_page)
        
        await callback.message.edit_text(
            text=pages[target_page],
            reply_markup=get_pagination_kb(target_page, len(pages), page_type="nutrition"),
            parse_mode=ParseMode.HTML
        )
    except:
        await callback.answer()

# --- ПОИСК РЕЦЕПТОВ ---
@router.callback_query(F.data == "recipe_search")
async def start_recipe_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "👨‍🍳 <b>Поиск рецептов</b>\n\n"
        "Напиши название блюда (например: <i>Сырники</i>), "
        "и я найду видео-рецепт.",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(RecipeState.waiting_for_dish)

@router.message(RecipeState.waiting_for_dish)
async def process_recipe_search(message: Message, state: FSMContext):
    if message.text.startswith('/'): return

    link, title, description = await search_recipe_video(message.text)
    
    if link:
        text = (
            f"✅ <b>{title}</b>\n"
            f"ℹ️ {description}\n\n"
            f"👇 <b>Смотреть рецепты:</b>\n{link}"
        )
        await message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
        await message.answer("Напиши еще блюдо или /cancel")
    else:
        await message.answer("Ошибка поиска.")