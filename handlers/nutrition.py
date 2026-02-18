import time
import json
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import KeyboardButton

from handlers.admin import is_admin
from states.workout_states import WorkoutRequest
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
# 1. Начало: Проверка профиля и старого меню
# 1. Основной вход через кнопку или команду
@router.message(F.text == "🍏 Питание")
@router.message(Command("ai_nutrition"))
async def request_ai_nutrition(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user: 
        await message.answer("Сначала заполни профиль!")
        return

    # Проверка на наличие старого меню
    if user.current_nutrition_program:
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Новое меню", callback_data="confirm_new_nutrition")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_nutrition")]
        ])
        await message.answer("Тренер уже составлял меню. Сделать новое?", reply_markup=confirm_kb)
    else:
        await ask_nutrition_wishes(message, state)

# 2. Обработка кнопки подтверждения
@router.callback_query(F.data == "confirm_new_nutrition")
async def confirm_generation(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await ask_nutrition_wishes(callback.message, state)

# 3. Функция запроса пожеланий (продуктов)
async def ask_nutrition_wishes(message: Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="⏩ Пропустить (ем всё)"))
    
    await message.answer(
        "🥗 <b>У тебя есть предпочтения по еде?</b>\n\n"
        "Напиши продукты, которые нужно <b>исключить</b> (например: <i>брокколи, лук, лактоза</i>) "
        "или просто нажми кнопку ниже 👇",
        reply_markup=kb.as_markup(resize_keyboard=True),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(WorkoutRequest.waiting_for_nutrition_wishes)

# 4. Хендлер, который принимает текст и запускает процесс

@router.message(WorkoutRequest.waiting_for_nutrition_wishes)
async def process_nutrition_wishes(message: Message, state: FSMContext, session: AsyncSession):
    wishes = message.text
    if wishes == "⏩ Пропустить (ем всё)":
        wishes = "Нет особых предпочтений"
    
    # ✅ Добавляем подтверждение выбора (как в тренировках)
    await message.answer(f"✅ <b>Принято:</b> \"{wishes}\"", parse_mode=ParseMode.HTML)
    
    # ⏳ Создаем исчезающее сообщение
    from keyboards.main_menu import get_main_menu
    status_msg = await message.answer(
        "👨‍🍳 <b>Тренер составляет меню...</b>", 
        reply_markup=get_main_menu(),
        parse_mode=ParseMode.HTML
    )
    
    user = await UserCRUD.get_user(session, message.from_user.id)
    
    # Передаем status_msg в функцию генерации, чтобы потом его удалить
    await generate_nutrition_process(message, session, user, state, wishes, status_msg)

# 5. Сама генерация (добавлен аргумент wishes)
async def generate_nutrition_process(message: Message, session: AsyncSession, user, state: FSMContext, wishes: str, status_msg: Message = None):
    # --- ЗАЩИТА ОТ СПАМА ---
    user_data = await state.get_data()
    last_gen_time = user_data.get("last_nutrition_gen_time", 0)
    current_time = time.time()

    if current_time - last_gen_time < 300 and not is_admin(message.from_user.id):
        wait_time = int((300 - (current_time - last_gen_time)) / 60)
        await message.answer(f"⏳ <b>Подождите {wait_time if wait_time > 0 else 1} мин.</b>\nНейросети нужно время.")
        return
    # --- ПРОВЕРКА ЛИМИТА ---
    if user.workout_limit <= 0:
        if status_msg: await status_msg.delete()
        await message.answer(
            "🚀 <b>Упс! Попытки закончились</b>\n\n"
            "Вы использовали все бесплатные генерации. Чтобы составить новое меню, получите <b>Premium-пакет</b>.\n\n"
            "💎 <b>Premium это:</b>\n"
            "├ 50 новых планов тренировок\n"
            "├ 100 вопросов личному AI-тренеру\n"
            "└ Доступ ко всем функциям без ограничений",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Получить Premium", callback_data="buy_premium")]
            ]),
            parse_mode="HTML"
        )
        return
    
    # Обновляем время
    await state.update_data(last_nutrition_gen_time=current_time)

    # ... дальше идет try:
    try:
        user_data = {
            "goal": user.goal, "gender": user.gender, "weight": user.weight, 
            "age": user.age, "activity_level": user.activity_level, "height": user.height,
            "name": user.name, "wishes": wishes 
        }
        
        ai_service = AIManager()
        raw_pages = await ai_service.generate_nutrition_pages(user_data)
        
        if not raw_pages or "❌" in raw_pages[0]:
            if status_msg: await status_msg.delete() # Удаляем статус при ошибке
            await message.answer("❌ Сервер перегружен, попробуй позже.")
            return

        # Сохраняем в базу (Вариант 2, который мы обсуждали)
        import json
        user.current_nutrition_program = json.dumps(raw_pages, ensure_ascii=False)
        user.workout_limit -= 1
        await session.commit()

        # 🔥 УДАЛЯЕМ сообщение "Тренер составляет меню..." перед показом результата
        if status_msg:
            try:
                await status_msg.delete()
            except:
                pass

        # Отправляем результат с пагинацией
        from keyboards.pagination import get_pagination_kb
        await message.answer(
            raw_pages[0],
            parse_mode=ParseMode.HTML,
            reply_markup=get_pagination_kb(0, len(raw_pages), "nutrition")
        )
            
        await state.clear()

    except Exception as e:
        if status_msg: await status_msg.delete()
        print(f"Ошибка: {e}")
        await message.answer("❌ Ошибка при отображении меню.")
        
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
@router.callback_query(F.data.startswith("nutrition_page_")) # Поменял : на _
async def change_nutrition_page(callback: CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем номер страницы (разделитель теперь подчеркивание)
        page = int(callback.data.split("_")[-1])
        
        user = await UserCRUD.get_user(session, callback.from_user.id)
        if not user or not user.current_nutrition_program:
            await callback.answer("❌ Программа не найдена.", show_alert=True)
            return

        pages = json.loads(user.current_nutrition_program)
        
        if page < 0 or page >= len(pages):
            await callback.answer()
            return

        from keyboards.pagination import get_pagination_kb
        
        await callback.message.edit_text(
            pages[page],
            parse_mode=ParseMode.HTML,
            reply_markup=get_pagination_kb(page, len(pages), "nutrition")
        )
        await callback.answer()

    except TelegramBadRequest:
        await callback.answer()
    except Exception as e:
        print(f"Ошибка пагинации: {e}")
        await callback.answer()

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
    # Если пользователь ввел команду, сбрасываем поиск
    if message.text.startswith('/'): 
        await state.clear()
        return
    
    loading = await message.answer("🔎 Ищу...")
    try:
        # Поиск видео или рецепта через твой сервис
        link, title, desc = await search_recipe_video(message.text)
        await loading.delete()
        
        if link:
            # 1. Сначала отправляем сам результат (видео/рецепт)
            await message.answer(
                f"🎬 <b>{title}</b>\n\n{desc}\n\n<a href='{link}'>Смотреть видео</a>",
                parse_mode=ParseMode.HTML
            )
            
            # 2. Создаем кнопку "Найти еще"
            search_again_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Найти еще", callback_data="recipe_search")]
            ])
            
            # 3. Отправляем пояснение (как в тренировках)
            await message.answer(
                "✅ Поиск завершен. Найти что-то еще?",
                reply_markup=search_again_kb
            )
            
            # Сбрасываем состояние, чтобы кнопки главного меню снова работали корректно
            await state.clear()
            
        else:
            # Если ничего не нашли
            retry_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="recipe_search")]
            ])
            await message.answer(
                "❌ Ничего не нашлось. Попробуешь другое название?", 
                reply_markup=retry_kb
            )
            await state.clear()
            
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        if 'loading' in locals(): await loading.delete()
        await message.answer("❌ Ошибка при поиске. Попробуй позже.")
        await state.clear()