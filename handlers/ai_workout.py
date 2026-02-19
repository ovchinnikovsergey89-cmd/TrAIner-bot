import time
import re
import json
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from states.workout_states import WorkoutPagination, WorkoutRequest
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from handlers.admin import is_admin
from utils.text_tools import clean_text
from database.crud import UserCRUD
from services.ai_manager import AIManager  # <--- НОВЫЙ ИМПОРТ
from states.workout_states import WorkoutPagination
from keyboards.pagination import get_pagination_kb
from database.models import WorkoutLog
from aiogram.utils.keyboard import ReplyKeyboardBuilder # Для кнопки пропуска

router = Router()

# Найти текущую функцию и заменить на эту:
async def show_workout_pages(message: Message, state: FSMContext, pages: list, from_db: bool = False):
    """Показывает первую страницу программы с кнопкой выполнения"""
    await state.update_data(workout_pages=pages, current_page=0)
    await state.set_state(WorkoutPagination.active)
    
    prefix = "💾 <b>Твоя сохраненная программа:</b>\n\n" if from_db else "🆕 <b>Новая программа готова:</b>\n\n"
    
    # --- ДОБАВЛЯЕМ КНОПКУ ВЫПОЛНЕНИЯ ---
    # Мы берем клавиатуру пагинации и добавляем в неё кнопку "Выполнено"
    keyboard = get_pagination_kb(0, len(pages), page_type="workout")
    
    # Добавляем кнопку отдельным рядом сверху или снизу
    keyboard.inline_keyboard.insert(0, [
        InlineKeyboardButton(text="✅ Тренировка выполнена", callback_data="workout_done")
    ])
    
    await message.answer(
        text=prefix + pages[0],
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

# ==========================================
# 1. КНОПКА "📅 Моя программа" (Только просмотр)
# ==========================================
@router.message(F.text == "📅 Моя программа")
async def show_saved_program(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Сначала заполни профиль! (/start)")
        return

    if user.current_workout_program:
        try:
            saved_pages = json.loads(user.current_workout_program)
            await show_workout_pages(message, state, saved_pages, from_db=True)
        except Exception as e:
            await message.answer("⚠️ Ошибка загрузки программы. Попробуйте создать новую.")
    else:
        await message.answer(
            "📭 <b>У тебя пока нет программы.</b>\n"
            "Нажми <b>🤖 AI Тренировка</b>, чтобы создать её.",
            parse_mode=ParseMode.HTML
        )

# ==========================================
# 2. КНОПКА "🤖 AI Тренировка" (С проверкой существующей программы)
# ==========================================
@router.message(F.text == "🤖 AI Тренировка")
@router.message(Command("ai_workout"))
async def request_ai_workout(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id) #
    if not user or not user.workout_level:
        await message.answer("❌ Сначала заполните профиль (/start)!") #
        return

    # --- ПРОВЕРКА НАЛИЧИЯ ПРОГРАММЫ ---
    if user.current_workout_program:
        # Создаем инлайн-клавиатуру для подтверждения
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, создать новую", callback_data="confirm_new_workout")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_workout")]
        ])
        await message.answer(
            "⚠️ <b>Внимание!</b>\nУ тебя уже есть сохраненная программа. Если создать новую, старая удалится.\n\nПродолжить?",
            reply_markup=confirm_kb,
            parse_mode=ParseMode.HTML
        ) #
    else:
        # Если программы нет — сразу спрашиваем пожелания
        await start_wishes_step(message, state)

# Вынесем отправку сообщения с пожеланиями в отдельную функцию для удобства
async def start_wishes_step(message: Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="⏩ Пропустить и составить обычную"))
    
    text = (
        "💪 <b>Хочешь добавить особые пожелания к программе?</b>\n\n"
        "Напиши их текстом (например: <i>'упор на грудные'</i>) или нажми кнопку ниже 👇"
    )
    
    await message.answer(
        text=text,
        reply_markup=kb.as_markup(resize_keyboard=True),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(WorkoutRequest.waiting_for_wishes)

# --- ИСПРАВЛЯЕМ ОБРАБОТЧИК ПОДТВЕРЖДЕНИЯ ---
@router.callback_query(F.data == "confirm_new_workout")
async def confirm_generation(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    # Теперь после нажатия "Да" переходим к сбору пожеланий
    await start_wishes_step(callback.message, state)

# 2. ЭТА ФУНКЦИЯ ДОЛЖНА ИДТИ СЛЕДУЮЩЕЙ — она ловит ваш текст
@router.message(WorkoutRequest.waiting_for_wishes)
async def process_workout_wishes(message: Message, session: AsyncSession, state: FSMContext):
    user_text = message.text
    
    # Сразу очищаем состояние, чтобы бот вернулся в обычный режим
    await state.clear() 
    
    if user_text == "⏩ Пропустить и составить обычную":
        wishes = "Особых пожеланий нет."
    else:
        wishes = user_text

    user = await UserCRUD.get_user(session, message.from_user.id)
    
    # Убираем кнопку пропуска, возвращая главное меню
    from keyboards.main_menu import get_main_menu
    await message.answer(f"✅ Принято: <i>\"{wishes}\"</i>\nСоставляю план...", 
                         reply_markup=get_main_menu(), 
                         parse_mode="HTML")
    
    # Запускаем саму генерацию
    await generate_workout_process(message, session, user, state, wishes=wishes)

# --- ОБРАБОТЧИКИ ПОДТВЕРЖДЕНИЯ ---
@router.callback_query(F.data == "confirm_new_workout")
async def confirm_generation(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.message.delete()
    user = await UserCRUD.get_user(session, callback.from_user.id)
    await generate_workout_process(callback.message, session, user, state)

@router.callback_query(F.data == "cancel_workout")
async def cancel_generation(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")

# --- КНОПКА "🔄 Новая программа" (из пагинации) ---
@router.callback_query(F.data == "regen_workout")
@router.callback_query(F.data == "refresh_ai_workout")
async def force_regen_workout(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.message.edit_text("🔄 Удаляю старую и создаю новую...")
    user = await UserCRUD.get_user(session, callback.from_user.id)
    await generate_workout_process(callback.message, session, user, state)

# --- ЛОГИКА ГЕНЕРАЦИИ (Service) ---
async def generate_workout_process(message: Message, session: AsyncSession, user, state: FSMContext, wishes: str = None):
    # --- ЗАЩИТА ОТ СПАМА (Раз в 5 минут) ---
    user_data = await state.get_data()
    last_gen_time = user_data.get("last_workout_gen_time", 0)
    current_time = time.time()
    
    if current_time - last_gen_time < 300 and not is_admin(message.from_user.id):
        wait_time = int((300 - (current_time - last_gen_time)) / 60)
        await message.answer(f"⏳ <b>Подождите {wait_time if wait_time > 0 else 1} мин.</b>\nНейросети нужно время.")
        return
    # --- ПРОВЕРКА ЛИМИТА ---
    if user.workout_limit <= 0:
        await message.answer(
            "🚀 <b>Упс! Попытки закончились</b>\n\n"
            "Вы использовали все бесплатные генерации. Чтобы составить новый план тренировок, получите <b>Premium-пакет</b>.\n\n"
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
    # Если всё ок, перед самой генерацией обновляем время:
    await state.update_data(last_workout_gen_time=current_time)

    # ... дальше твой код (loading_msg и т.д.)
    loading_msg = await message.answer("🗓 <b>Тренер изучает пожелания и составляет программу...</b>", parse_mode=ParseMode.HTML)
    
    try:
        user_data = {
            "workout_days": user.workout_days,
            "goal": user.goal,
            "gender": user.gender,
            "weight": user.weight,
            "age": user.age,
            "workout_level": user.workout_level,
            "name": user.name,
            "height": user.height,
            "wishes": wishes  # 🔥 ПЕРЕДАЕМ ПОЖЕЛАНИЯ
        }
        
        ai_service = AIManager()
        raw_pages = await ai_service.generate_workout_pages(user_data)
        # ... далее без изменений
        
        if not raw_pages or (len(raw_pages) == 1 and "Ошибка" in raw_pages[0]):
            await loading_msg.edit_text("❌ Ошибка генерации. Попробуйте позже.")
            return

        cleaned_pages = [clean_text(p) for p in raw_pages]

        # 🔥 СОХРАНЯЕМ В БАЗУ ДАННЫХ 🔥
        pages_json = json.dumps(cleaned_pages, ensure_ascii=False)
        user.current_workout_program = pages_json
        
        user.workout_limit -= 1 # Минус одна попытка
        await session.commit()  # Сохраняем всё в базу
        await UserCRUD.update_user(session, user.telegram_id, current_workout_program=pages_json)

        await loading_msg.delete()
        await show_workout_pages(message, state, cleaned_pages, from_db=False)
        
    except Exception as e:
        await loading_msg.edit_text(f"Ошибка: {e}")

# ==========================================
# 3. ЛИСТАЛКА (Пагинация)
# ==========================================
@router.callback_query(F.data.startswith("workout_page_"))
async def change_page(callback: CallbackQuery, state: FSMContext):
    try:
        target_page = int(callback.data.split("_")[-1])
        data = await state.get_data()
        pages = data.get("workout_pages")
        
        if not pages:
            await callback.answer("Данные устарели. Нажми 'Моя программа'", show_alert=True)
            return
            
        if target_page < 0 or target_page >= len(pages):
            await callback.answer("Это крайняя страница")
            return
            
        await state.update_data(current_page=target_page)

        # Получаем стандартную клавиатуру пагинации
        keyboard = get_pagination_kb(target_page, len(pages), page_type="workout")
        
        user_data = await state.get_data()
        completed_days = user_data.get("completed_days", [])

        if target_page < len(pages) - 1:
            if target_page in completed_days:
                btn_text = "🔄 Отменить выполнение"
                btn_callback = f"workout_undo_{target_page}"
            else:
                btn_text = "✅ Тренировка выполнена"
                btn_callback = "workout_done"
                
            keyboard.inline_keyboard.insert(0, [
                InlineKeyboardButton(text=btn_text, callback_data=btn_callback)
            ])
        
        # Проверяем, выполнена ли эта страница пользователем
        completed_days = data.get("completed_days", [])
        
        page_text = pages[target_page]
        if target_page in completed_days:
            page_text += "\n\n🌟 <b>Эта тренировка выполнена!</b>"

        # 🔥 ОДИН КОРРЕКТНЫЙ ВЫЗОВ ОБНОВЛЕНИЯ СООБЩЕНИЯ 🔥
        await callback.message.edit_text(
            text=page_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest:
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка пагинации: {e}")
        await callback.answer()

@router.callback_query(F.data == "noop")
async def noop_btn(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "workout_done")
async def process_workout_done(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    pages = data.get("workout_pages", [])
    completed_days = data.get("completed_days", [])
    
    # Сохраняем в БД
    new_log = WorkoutLog(
        user_id=callback.from_user.id,
        date=datetime.datetime.now(),
        workout_type=f"День {current_page + 1}"
    )
    session.add(new_log)
    await session.commit()
    
    # Сохраняем в память
    if current_page not in completed_days:
        completed_days.append(current_page)
        await state.update_data(completed_days=completed_days)

    await callback.answer("💪 Мощно! Тренировка засчитана!", show_alert=True)
    
    # МГНОВЕННО ОБНОВЛЯЕМ КНОПКУ И ТЕКСТ
    keyboard = get_pagination_kb(current_page, len(pages), page_type="workout")
    keyboard.inline_keyboard.insert(0, [
        InlineKeyboardButton(text="🔄 Отменить выполнение", callback_data=f"workout_undo_{current_page}")
    ])
    
    try:
        page_text = pages[current_page] + "\n\n🌟 <b>Эта тренировка выполнена!</b>"
        await callback.message.edit_text(
            text=page_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("workout_undo_"))
async def process_workout_undo(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    target_page = int(callback.data.split("_")[-1])
    data = await state.get_data()
    completed_days = data.get("completed_days", [])
    pages = data.get("workout_pages", [])

    # Удаляем из БД
    stmt = delete(WorkoutLog).where(
        WorkoutLog.user_id == callback.from_user.id,
        WorkoutLog.workout_type == f"День {target_page + 1}"
    )
    await session.execute(stmt)
    await session.commit()

    # Удаляем из памяти
    if target_page in completed_days:
        completed_days.remove(target_page)
        await state.update_data(completed_days=completed_days)

    await callback.answer("Выполнение отменено", show_alert=True)

    # ВОЗВРАЩАЕМ КНОПКУ "ВЫПОЛНЕНО"
    keyboard = get_pagination_kb(target_page, len(pages), page_type="workout")
    keyboard.inline_keyboard.insert(0, [
        InlineKeyboardButton(text="✅ Тренировка выполнена", callback_data="workout_done")
    ])

    await callback.message.edit_text(
        text=pages[target_page],
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )    

# Добавь этот хендлер в конец файлов
@router.callback_query(F.data == "ai_chat")
async def redirect_to_chat(callback: CallbackQuery, state: FSMContext):
    from handlers.ai_chat import start_chat_logic
    await callback.answer()
    await start_chat_logic(callback.message, state)    