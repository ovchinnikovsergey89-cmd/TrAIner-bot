import re
import json
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from database.crud import UserCRUD
from services.ai_manager import AIManager  # <--- НОВЫЙ ИМПОРТ
from states.workout_states import WorkoutPagination
from keyboards.pagination import get_pagination_kb
from database.models import WorkoutLog

router = Router()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def clean_text(text: str) -> str:
    """Чистильщик текста (локальная доработка форматирования)"""
    if not text: return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    # Жирный шрифт для "День X"
    text = re.sub(r'(^|\n)(День \d+:.*?)(?=\n|$)', r'\1<b>\2</b>', text)
    # Жирный шрифт для "Советы"
    text = re.sub(r'(^|\n)(💡.*?)(?=\n|$)', r'\1<b>\2</b>', text)
    
    text = text.replace("###", "").replace("SPLIT", "")
    return text.strip()

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
# 2. КНОПКА "🤖 AI Тренировка" (Генерация)
# ==========================================
@router.message(Command("ai_workout"))
@router.message(F.text == "🤖 AI Тренировка")
async def request_ai_workout(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user or not user.workout_level:
        await message.answer("❌ Сначала заполните профиль (/start)!", parse_mode=ParseMode.HTML)
        return

    if user.current_workout_program:
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, создать новую", callback_data="confirm_new_workout")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_workout")]
        ])
        await message.answer(
            "⚠️ <b>Внимание!</b>\nУ тебя уже есть сохраненная программа. Если создать новую, старая удалится.\n\nПродолжить?",
            reply_markup=confirm_kb,
            parse_mode=ParseMode.HTML
        )
    else:
        await generate_workout_process(message, session, user, state)

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
async def generate_workout_process(message: Message, session: AsyncSession, user, state: FSMContext):
    loading_msg = await message.answer("🗓 <b>Тренер составляет программу... (20 сек)</b>", parse_mode=ParseMode.HTML)
    
    try:
        user_data = {
            "workout_days": user.workout_days,
            "goal": user.goal,
            "gender": user.gender,
            "weight": user.weight,
            "age": user.age,
            "workout_level": user.workout_level
        }
        
        # --- ИСПОЛЬЗУЕМ НОВЫЙ МЕНЕДЖЕР ---
        ai_service = AIManager()
        raw_pages = await ai_service.generate_workout_pages(user_data)
        
        if not raw_pages or (len(raw_pages) == 1 and "Ошибка" in raw_pages[0]):
            await loading_msg.edit_text("❌ Ошибка генерации. Попробуйте позже.")
            return

        cleaned_pages = [clean_text(p) for p in raw_pages]

        # 🔥 СОХРАНЯЕМ В БАЗУ ДАННЫХ 🔥
        pages_json = json.dumps(cleaned_pages, ensure_ascii=False)
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