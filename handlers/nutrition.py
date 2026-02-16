import json
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.exceptions import TelegramBadRequest

from database.crud import UserCRUD
from services.ai_manager import AIManager # <--- НОВЫЙ ИМПОРТ
from services.recipe_service import search_recipe_video
from keyboards.pagination import get_pagination_kb
from states.workout_states import WorkoutPagination

router = Router()

class RecipeState(StatesGroup):
    waiting_for_dish = State()

def clean_text(text: str) -> str:
    """Чистильщик текста для питания"""
    if not text: return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'(^|\n)(🍳|🍲|🥗|🛒|🥪)(.*?)(?=\n|$)', r'\1\2<b>\3</b>', text)
    text = text.replace("###", "").replace("Menu:", "")
    return text.strip()

async def show_pages(message: Message, state: FSMContext, pages: list, from_db: bool = False):
    if isinstance(pages, str):
        pages = [pages]
        
    await state.update_data(nutrition_pages=pages, current_nutrition_page=0)
    await state.set_state(WorkoutPagination.active)
    
    prefix = "💾 <b>Твое меню:</b>\n\n" if from_db else "✅ <b>Тренер составил меню:</b>\n\n"
    
    try:
        await message.answer(
            text=prefix + pages[0],
            reply_markup=get_pagination_kb(0, len(pages), page_type="nutrition"),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await message.answer(f"{prefix}{str(pages[0])[:3000]}...\n(обрезано)", parse_mode=ParseMode.HTML)

# --- ПРОСМОТР ---
@router.message(F.text == "🍽 Мое меню")
async def show_my_nutrition(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Сначала заполни профиль! (/start)")
        return
    if user.current_nutrition_program:
        try:
            pages = json.loads(user.current_nutrition_program)
            await show_pages(message, state, pages, from_db=True)
        except: 
            pages = [user.current_nutrition_program]
            await show_pages(message, state, pages, from_db=True)
    else:
        await message.answer("🤷‍♂️ Нет меню. Нажми <b>🍏 Питание</b>.", parse_mode=ParseMode.HTML)

# --- ГЕНЕРАЦИЯ ---
@router.message(F.text == "🍏 Питание")
@router.message(Command("ai_nutrition"))
async def request_ai_nutrition(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user: await message.answer("Сначала заполни профиль!"); return

    if user.current_nutrition_program:
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Новое меню", callback_data="confirm_new_nutrition")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_nutrition")]
        ])
        await message.answer("Тренер уже составлял меню. Сделать новое?", reply_markup=confirm_kb)
    else:
        await generate_nutrition_process(message, session, user, state)

@router.callback_query(F.data == "confirm_new_nutrition")
async def confirm_generation(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.message.delete()
    user = await UserCRUD.get_user(session, callback.from_user.id)
    await generate_nutrition_process(callback.message, session, user, state)

@router.callback_query(F.data == "cancel_nutrition")
async def cancel_generation(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")

async def generate_nutrition_process(message: Message, session: AsyncSession, user, state: FSMContext):
    status_msg = await message.answer(f"🍏 <b>Тренер рассчитывает калории и подбирает продукты...</b>", parse_mode=ParseMode.HTML)
    
    try:
        user_data = {
            "goal": user.goal, "gender": user.gender, "weight": user.weight, 
            "age": user.age, "activity_level": user.activity_level, "height": user.height,
        }
        
        # --- ИСПОЛЬЗУЕМ НОВЫЙ МЕНЕДЖЕР ---
        ai = AIManager()
        raw_pages = await ai.generate_nutrition_pages(user_data)
        
        cleaned_pages = [clean_text(p) for p in raw_pages if len(p) > 20]
        
        if not cleaned_pages:
            await status_msg.edit_text("⚠️ Тренер задумался и ничего не ответил. Попробуй еще раз.")
            return

        pages_json = json.dumps(cleaned_pages, ensure_ascii=False)
        await UserCRUD.update_user(session, user.telegram_id, current_nutrition_program=pages_json)
        
        await status_msg.delete()
        await show_pages(message, state, cleaned_pages, from_db=False)
        
    except Exception as e:
        await status_msg.edit_text(f"Ошибка: {e}")

# --- ЛИСТАЛКА ---
@router.callback_query(F.data.startswith("nutrition_page_"))
async def change_nutrition_page(callback: CallbackQuery, state: FSMContext):
    try:
        target_page = int(callback.data.split("_")[-1])
        data = await state.get_data()
        pages = data.get("nutrition_pages")
        
        if not pages or target_page < 0 or target_page >= len(pages):
            await callback.answer()
            return
            
        await state.update_data(current_nutrition_page=target_page)
        
        await callback.message.edit_text(
            text=pages[target_page],
            reply_markup=get_pagination_kb(target_page, len(pages), page_type="nutrition"),
            parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest: await callback.answer()
    except Exception: await callback.answer()

@router.callback_query(F.data == "regen_nutrition")
async def force_regen_nutrition(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    try: await callback.message.edit_text("🔄 Тренер переделывает...")
    except: await callback.message.answer("🔄 Тренер переделывает...")
    
    user = await UserCRUD.get_user(session, callback.from_user.id)
    await generate_nutrition_process(callback.message, session, user, state)

# --- ПОИСК РЕЦЕПТОВ ---
@router.callback_query(F.data == "recipe_search")
async def start_recipe_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("👨‍🍳 <b>Введи название блюда:</b>\n(например: <i>Сырники с изюмом</i>)", parse_mode=ParseMode.HTML)
    await state.set_state(RecipeState.waiting_for_dish)

@router.message(RecipeState.waiting_for_dish)
async def process_recipe_search(message: Message, state: FSMContext):
    if message.text.startswith('/'): return
    
    loading = await message.answer("🔎 Ищу рецепт...")
    try:
        link, title, desc = await search_recipe_video(message.text)
        await loading.delete()
        
        if link:
            await message.answer(f"✅ <b>{title}</b>\n{desc}\n\n👇 <b>Смотреть:</b>\n{link}", parse_mode=ParseMode.HTML)
        else:
            await message.answer("Не нашел рецепт :(")
    except Exception as e:
         await loading.edit_text("Ошибка поиска.")
    
    await state.clear()