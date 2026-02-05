import re
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from services.groq_service import GroqService
from services.recipe_service import search_recipe_video
from keyboards.pagination import get_pagination_kb
from states.workout_states import WorkoutPagination

router = Router()

class RecipeState(StatesGroup):
    waiting_for_dish = State()

def clean_text(text: str) -> str:
    """Чистильщик текста + улучшатель читаемости"""
    if not text: return ""
    
    # HTML теги
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    # Убираем лишние заголовки, если ИИ их добавил
    text = text.replace("###", "").replace("Menu:", "")
    
    return text.strip()

def split_saved_program(full_text: str) -> list[str]:
    # Регулярка для разделения
    pattern = r'(?=\n(?:🍳|🍲|🥗|🛒|🍽))'
    pages = re.split(pattern, full_text)
    clean_pages = [p.strip() for p in pages if len(p.strip()) > 20]
    if not clean_pages: return [full_text]
    return clean_pages

async def show_pages(message: Message, state: FSMContext, pages: list, from_db: bool = False):
    await state.update_data(nutrition_pages=pages, current_nutrition_page=0)
    await state.set_state(WorkoutPagination.active)
    
    prefix = "💾 <b>Сохраненное меню:</b>\n\n" if from_db else "✅ <b>Конструктор меню готов:</b>\n\n"
    
    await message.answer(
        text=prefix + pages[0],
        # Тут мы передаем total_pages, а клавиатура сама решит, как их показывать
        reply_markup=get_pagination_kb(0, len(pages), page_type="nutrition"),
        parse_mode=ParseMode.HTML
    )

# --- ОБРАБОТЧИКИ (МЕНЮ / ГЕНЕРАЦИЯ) - ОСТАЮТСЯ ПРЕЖНИМИ ---
# (Ниже код стандартный, как был в прошлом ответе, копирую для целостности файла)

@router.message(F.text == "🍽 Мое питание")
async def show_my_nutrition(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Сначала заполни профиль! (/start)")
        return
    if user.current_nutrition_program:
        pages = split_saved_program(user.current_nutrition_program)
        await show_pages(message, state, pages, from_db=True)
    else:
        await message.answer("🤷‍♂️ Нет меню. Нажми <b>🍏 Питание</b>.", parse_mode=ParseMode.HTML)

@router.message(F.text == "🍏 Питание")
async def request_ai_nutrition(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user: await message.answer("Сначала заполни профиль!"); return

    if user.current_nutrition_program:
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Создать новое", callback_data="confirm_new_nutrition")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_nutrition")]
        ])
        await message.answer("У тебя уже есть меню. Создать новое?", reply_markup=confirm_kb)
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
    status_msg = await message.answer("🍏 <b>Составляю меню для вас...</b>", parse_mode=ParseMode.HTML)
    try:
        user_data = {"goal": user.goal, "gender": user.gender, "weight": user.weight, "age": user.age, "activity_level": user.activity_level, "height": user.height}
        ai = GroqService()
        raw_pages = await ai.generate_nutrition_pages(user_data)
        cleaned_pages = [clean_text(p) for p in raw_pages if len(p) > 50]
        
        if not cleaned_pages:
            await status_msg.edit_text("⚠️ Ошибка ИИ.")
            return

        full_program_text = "\n\n".join(cleaned_pages)
        await UserCRUD.update_user(session, user.telegram_id, current_nutrition_program=full_program_text)
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
            await callback.answer("Ошибка страницы")
            return
            
        await state.update_data(current_nutrition_page=target_page)
        
        # Редактируем сообщение (И КЛАВИАТУРА ПОМЕНЯЕТСЯ САМА)
        await callback.message.edit_text(
            text=pages[target_page],
            reply_markup=get_pagination_kb(target_page, len(pages), page_type="nutrition"),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await callback.answer()

@router.callback_query(F.data == "regen_nutrition")
async def force_regen_nutrition(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.message.edit_text("🔄 Пересоздаю...")
    user = await UserCRUD.get_user(session, callback.from_user.id)
    await generate_nutrition_process(callback.message, session, user, state)

@router.callback_query(F.data == "recipe_search")
async def start_recipe_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("👨‍🍳 Введи название блюда:", parse_mode=ParseMode.HTML)
    await state.set_state(RecipeState.waiting_for_dish)

@router.message(RecipeState.waiting_for_dish)
async def process_recipe_search(message: Message, state: FSMContext):
    if message.text.startswith('/'): return
    link, title, desc = await search_recipe_video(message.text)
    if link:
        await message.answer(f"✅ <b>{title}</b>\n{desc}\n\n👇 <b>Смотреть:</b>\n{link}", parse_mode=ParseMode.HTML)
    else:
        await message.answer("Не нашел рецепт :(")