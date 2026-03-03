import re
import json
import datetime
import time
import os
import asyncio
from aiogram import Bot
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, desc
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from faster_whisper import WhisperModel
from handlers.admin import is_admin
from utils.text_tools import clean_text
from database.crud import UserCRUD
from services.ai_manager import AIManager
from states.workout_states import WorkoutPagination, WorkoutRequest
from keyboards.pagination import get_pagination_kb
from database.models import WorkoutLog, ExerciseLog

router = Router()

whisper_model = WhisperModel("base", device="cpu", compute_type="default")

# ==========================================
# 1. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
async def show_workout_pages(message: Message, state: FSMContext, pages: list, from_db: bool = False, completed_days_direct: list = None):
    # 1. Сохраняем страницы и сбрасываем текущую на 0
    await state.update_data(workout_pages=pages, current_page=0)
    
    # Если передали список выполненных дней напрямую (при загрузке из БД)
    if completed_days_direct is not None:
        await state.update_data(completed_days=completed_days_direct)
        check_list = completed_days_direct
    else:
        # Иначе берем из памяти (или пустой, если это новая программа)
        data = await state.get_data()
        check_list = data.get("completed_days", [])
    
    await state.set_state(WorkoutPagination.active)
    
    current_page = 0
    page_text = pages[current_page]
    
    # 2. Получаем клавиатуру
    base_kb = get_pagination_kb(current_page, len(pages), page_type="workout")
    
    # 3. Логика кнопки "Выполнено"
    # Проверяем, не день отдыха ли это
    first_line = page_text.split('\n')[0].upper()
    rest_keywords = ["ВОССТАНОВЛЕНИЕ", "ОТДЫХ", "ВЫХОДНОЙ"]
    is_rest_day = any(word in first_line for word in rest_keywords)
    is_advice_page = current_page == len(pages) - 1

    rows = []
    # Добавляем кнопку выполнения ПЕРВЫМ рядом, если это не отдых и не советы
    if not is_rest_day and not is_advice_page:
        if current_page in check_list:
            btn_text, btn_cb = "🔄 Отменить выполнение", f"workout_undo_{current_page}"
        else:
            btn_text, btn_cb = "✅ Тренировка выполнена", "workout_done"
        rows.append([InlineKeyboardButton(text=btn_text, callback_data=btn_cb)])
        # Добавляем кнопку записи веса отдельным рядом
        rows.append([InlineKeyboardButton(text="📝 Записать рабочие веса", callback_data="log_weight_press")]) 
    # Добавляем остальные кнопки навигации
    if base_kb and base_kb.inline_keyboard:
        rows.extend(base_kb.inline_keyboard)

    final_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    # 4. Формируем текст
    prefix = "💾 <b>Твоя программа:</b>\n\n" if from_db else "🆕 <b>Программа готова:</b>\n\n"
    display_text = prefix + page_text
    if current_page in check_list:
         display_text += "\n\n🌟 <b>Эта тренировка выполнена!</b>"

    # 5. Отправка (с защитой от дублей)
    try:
        if isinstance(message, Message):
            await message.answer(display_text, reply_markup=final_keyboard, parse_mode="HTML")
        else:
            # Если это редактирование старого сообщения
            await message.edit_text(display_text, reply_markup=final_keyboard, parse_mode="HTML")
    except Exception:
        # Если редактирование не прошло (например, текст тот же), шлем новое
        await message.answer(display_text, reply_markup=final_keyboard, parse_mode="HTML")

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

# ==========================================
# 2. ОСНОВНЫЕ ХЕНДЛЕРЫ МЕНЮ
# ==========================================

# --- КНОПКА "📅 Моя программа" ---
@router.message(F.text == "📅 Моя программа")
async def show_saved_program(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Сначала заполни профиль! (/start)")
        return

    if user.current_workout_program:
        try:
            saved_pages = json.loads(user.current_workout_program)
            
            # 🔥 Достаем из базы реально выполненные дни
            stmt = select(WorkoutLog.workout_type).where(WorkoutLog.user_id == message.from_user.id)
            result = await session.execute(stmt)
            logs = result.scalars().all() 
            
            completed_days = []
            for log in logs:
                try:
                    # Извлекаем число из строки "День X" и превращаем в индекс (0, 1...)
                    day_num = int(log.split(" ")[-1]) - 1
                    completed_days.append(day_num)
                except: continue
            
            # Сохраняем и показываем
            await show_workout_pages(message, state, saved_pages, from_db=True, completed_days_direct=completed_days)
        except Exception as e:
            await message.answer("⚠️ Ошибка загрузки программы. Попробуйте создать новую.")
    else:
        await message.answer(
            "📭 <b>У тебя пока нет программы.</b>\n"
            "Нажми <b>🤖 AI Тренировка</b>, чтобы создать её.",
            parse_mode=ParseMode.HTML
        )

# ==========================================
# 2. КНОПКА "🤖 AI Тренировка" (ВЫБОР ТИПА ТРЕНИРОВКИ)
# ==========================================
@router.message(F.text == "🤖 AI Тренировка")
@router.message(Command("ai_workout"))
async def request_ai_workout(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user or not user.workout_level:
        await message.answer("❌ Сначала заполните профиль (/start)!")
        return

    # Создаем клавиатуру выбора типа тренировки
    type_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗓 Недельная программа", callback_data="select_weekly_workout")],
        [InlineKeyboardButton(text="⚡️ Разовая на сегодня", callback_data="select_quick_workout")]
    ])
    
    await message.answer(
        "<b>Какой формат тренировки тебе нужен?</b>\n\n"
        "🗓 <b>Недельная:</b> Полноценный план на неделю.\n"
        "⚡️ <b>Разовая:</b> Быстрая тренировка на сегодня под твои условия (инвентарь, время).",
        reply_markup=type_kb,
        parse_mode=ParseMode.HTML
    )

# --- ОБРАБОТЧИК: НЕДЕЛЬНАЯ ПРОГРАММА ---
@router.callback_query(F.data == "select_weekly_workout")
async def process_weekly_workout_selection(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, callback.from_user.id)
    
    # ПРОВЕРКА НАЛИЧИЯ СТАРОЙ ПРОГРАММЫ
    if user.current_workout_program:
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, создать новую", callback_data="confirm_new_workout")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_workout")]
        ])
        await callback.message.edit_text(
            "⚠️ <b>Внимание!</b>\nУ тебя уже есть сохраненная недельная программа. Если создать новую, старая удалится.\n\nПродолжить?",
            reply_markup=confirm_kb,
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.message.delete()
        await start_wishes_step(callback.message, state)

# --- ОБРАБОТЧИК: РАЗОВАЯ ТРЕНИРОВКА ---
@router.callback_query(F.data == "select_quick_workout")
async def process_quick_workout_selection(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="⏩ Составить без условий"))
    
    text = (
        "⚡️ <b>Быстрая тренировка на лету!</b>\n\n"
        "Где ты сейчас и что есть под рукой? Напиши мне:\n"
        "<i>- 'Я дома, есть только 20 минут и гантели 5кг'\n"
        "- 'Я на спортплощадке, хочу поработать на турниках'\n"
        "- 'Я в зале, но болит поясница, дай легкое кардио'</i>\n\n"
        "Или нажми кнопку ниже, чтобы получить стандартную тренировку с собственным весом."
    )
    
    await callback.message.answer(text, reply_markup=kb.as_markup(resize_keyboard=True), parse_mode=ParseMode.HTML)
    await state.set_state(WorkoutRequest.waiting_for_quick_workout_wishes)

# --- ЛОГИКА ПОДТВЕРЖДЕНИЯ И ПОЖЕЛАНИЙ ---
@router.callback_query(F.data == "confirm_new_workout")
async def confirm_new_workout_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await start_wishes_step(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "cancel_workout")
async def cancel_generation(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")

@router.message(WorkoutRequest.waiting_for_wishes)
async def process_workout_wishes(message: Message, session: AsyncSession, state: FSMContext):
    user_wishes = message.text
    
    data = await state.get_data()
    old_wishes = data.get("wishes", "")
    
    if old_wishes and user_wishes.lower() != "без изменений":
        combined_wishes = f"{old_wishes}. Дополнительно: {user_wishes}"
    else:
        combined_wishes = user_wishes

    await state.update_data(wishes=combined_wishes)
    user = await UserCRUD.get_user(session, message.from_user.id)
    
    await generate_workout_process(message, session, user, state, wishes=combined_wishes)

# --- РЕГЕНЕРАЦИЯ (Кнопка "Новая программа") ---
@router.callback_query(F.data == "regen_workout")
@router.callback_query(F.data == "refresh_ai_workout")
async def force_regen_workout(callback: CallbackQuery, state: FSMContext):
    await state.set_state(WorkoutRequest.waiting_for_wishes)
    await callback.message.answer(
        "📝 <b>Что добавить или изменить в новой программе?</b>\n\n"
        "Например: <i>'убери приседания'</i>, <i>'сделай упор на плечи'</i> или просто напиши <i>'без изменений'</i>.",
        parse_mode="HTML"
    )
    await callback.answer()

# ==========================================
# 3. ГЕНЕРАЦИЯ ПРОГРАММЫ (CORE)
# ==========================================
async def generate_workout_process(message: Message, session: AsyncSession, user, state: FSMContext, wishes: str = None):
    # --- 1. ЗАЩИТА ОТ СПАМА (Раз в 5 минут) ---
    user_data = await state.get_data()
    last_gen_time = user_data.get("last_workout_gen_time", 0)
    current_time = time.time()
    
    if current_time - last_gen_time < 300 and not is_admin(message.from_user.id):
        wait_time = int((300 - (current_time - last_gen_time)) / 60)
        await message.answer(f"⏳ <b>Подождите {wait_time if wait_time > 0 else 1} мин.</b>\nНейросети нужно время.")
        return

    # --- 2. ПРОВЕРКА ЛИМИТА ---
    if user.workout_limit <= 0:
        await message.answer(
            "🚀 <b>Упс! Попытки закончились</b>\n\n"
            "Вы использовали все бесплатные генерации. Чтобы составить новый план, получите Premium.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Получить Premium", callback_data="buy_premium")]]),
            parse_mode="HTML"
        )
        return
    
    await state.update_data(last_workout_gen_time=current_time)
    loading_msg = await message.answer("🗓 <b>Тренер изучает пожелания и составляет программу...</b>", parse_mode=ParseMode.HTML)
    
    try:
        user_data = {
            "workout_days": user.workout_days, "goal": user.goal, "gender": user.gender,
            "weight": user.weight, "age": user.age, "workout_level": user.workout_level,
            "name": user.name, "height": user.height, "wishes": wishes
        }
        
        # ГЕНЕРАЦИЯ
        ai_service = AIManager()
        raw_pages = await ai_service.generate_workout_pages(user_data)
        
        if not raw_pages or (len(raw_pages) == 1 and "Ошибка" in raw_pages[0]):
            await loading_msg.edit_text("❌ Ошибка генерации. Попробуйте позже.")
            return

        cleaned_pages = [clean_text(p) for p in raw_pages]

        # --- 3. СОХРАНЕНИЕ В БД ---
        pages_json = json.dumps(cleaned_pages, ensure_ascii=False)
        user.current_workout_program = pages_json
        user.workout_limit -= 1
        await session.commit()
        await UserCRUD.update_user(session, user.telegram_id, current_workout_program=pages_json)

        await loading_msg.delete()
        
        # 🔥 ВАЖНО: Очищаем список выполненных дней для НОВОЙ программы
        await state.update_data(completed_days=[])
        await show_workout_pages(message, state, cleaned_pages, from_db=False, completed_days_direct=[])
        
    except Exception as e:
        await loading_msg.edit_text(f"Ошибка: {e}")

# --- ЛОГИКА ГЕНЕРАЦИИ РАЗОВОЙ ТРЕНИРОВКИ ---
@router.message(WorkoutRequest.waiting_for_quick_workout_wishes)
async def process_quick_workout_wishes(message: Message, session: AsyncSession, state: FSMContext):
    user_wishes = message.text
    if user_wishes == "⏩ Составить без условий":
        user_wishes = "Стандартная тренировка с собственным весом на 30-40 минут."
        
    user = await UserCRUD.get_user(session, message.from_user.id)

    # --- 1. ЗАЩИТА ОТ СПАМА (Раз в 1 минуту) ---
    user_data_fsm = await state.get_data()
    last_gen_time = user_data_fsm.get("last_quick_workout_gen_time", 0)
    current_time = time.time()
    
    # Если прошло меньше 60 секунд И это НЕ админ
    if current_time - last_gen_time < 60 and not is_admin(message.from_user.id):
        wait_time = int(60 - (current_time - last_gen_time))
        await message.answer(f"⏳ <b>Подожди {wait_time} сек.</b>\nДай тренеру перевести дух.")
        return
        
    # Обновляем время последней генерации
    await state.update_data(last_quick_workout_gen_time=current_time)

    # --- 2. ПРОВЕРКА ЛИМИТОВ ---
    if not is_admin(message.from_user.id) and user.workout_limit <= 0:
        await message.answer(
            "🚀 <b>Упс! Попытки закончились</b>\n\n"
            "Вы использовали все бесплатные генерации.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Получить Premium", callback_data="buy_premium")]]),
            parse_mode="HTML"
        )
        return
    
    # Проверка лимитов и защита от спама такая же, как в generate_workout_process
    # (для экономии места в инструкции я не дублирую её, но ты можешь скопировать логику из generate_workout_process)

    loading_msg = await message.answer("⚡️ <b>Тренер составляет быструю тренировку...</b>", parse_mode=ParseMode.HTML)
    
    try:
        user_data = {
            "goal": user.goal,
            "gender": user.gender,
            "weight": user.weight,
            "age": user.age,
            "workout_level": user.workout_level,
            "name": user.name,
            "wishes": user_wishes 
        }
        
        ai_service = AIManager()
        # Создадим новый метод в AIManager для разовой тренировки
        workout_text = await ai_service.generate_single_workout(user_data) 
        
        if not workout_text or "Ошибка" in workout_text:
            await loading_msg.edit_text("❌ Ошибка генерации. Попробуйте позже.")
            return

        cleaned_text = clean_text(workout_text)
        
        # Для разовой тренировки не используем пагинацию, просто отправляем текст
        # И списываем 1 лимит
        user.workout_limit -= 1
        await session.commit()
        
        await loading_msg.delete()
        
        # Отправляем тренировку с кнопкой для возврата
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выполнил!", callback_data="quick_workout_done")]
        ])
        await message.answer(f"⚡️ <b>Твоя разовая тренировка:</b>\n\n{cleaned_text}", reply_markup=kb, parse_mode=ParseMode.HTML)
        
        # Сбрасываем состояние
        await state.clear()
        
    except Exception as e:
        await loading_msg.edit_text(f"Ошибка: {e}")

@router.callback_query(F.data == "quick_workout_done")
async def process_quick_workout_done(callback: CallbackQuery):
    # Убираем кнопку и поздравляем
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("🔥 Отличная работа! Тренировка засчитана.", show_alert=True)        

# ==========================================
# 4. ЛИСТАЛКА (ПАГИНАЦИЯ)
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
        
        # Защита от выхода за границы
        if target_page < 0 or target_page >= len(pages):
            await callback.answer("Это крайняя страница")
            return
            
        await state.update_data(current_page=target_page)
        completed_days = data.get("completed_days", [])
        page_text = pages[target_page]
        
        # Логика кнопок
        base_kb = get_pagination_kb(target_page, len(pages), page_type="workout")
        first_line = page_text.split('\n')[0].upper()
        rest_keywords = ["ВОССТАНОВЛЕНИЕ", "ОТДЫХ", "ВЫХОДНОЙ"]
        is_rest_day = any(word in first_line for word in rest_keywords)
        is_advice_page = target_page == len(pages) - 1

        rows = []
        if not is_rest_day and not is_advice_page:
            if target_page in completed_days:
                btn_text, btn_cb = "🔄 Отменить выполнение", f"workout_undo_{target_page}"
            else:
                btn_text, btn_cb = "✅ Тренировка выполнена", "workout_done"
            rows.append([InlineKeyboardButton(text=btn_text, callback_data=btn_cb)])
            # Добавляем кнопку записи веса отдельным рядом
            rows.append([InlineKeyboardButton(text="📝 Записать рабочие веса", callback_data="log_weight_press")])
        if base_kb and base_kb.inline_keyboard:
            rows.extend(base_kb.inline_keyboard)
        
        final_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

        display_text = page_text
        if target_page in completed_days:
            display_text += "\n\n🌟 <b>Эта тренировка выполнена!</b>"

        # 🔥 ЗАЩИТА ОТ ОШИБКИ "Not Modified"
        try:
            await callback.message.edit_text(text=display_text, reply_markup=final_keyboard, parse_mode=ParseMode.HTML)
        except TelegramBadRequest:
            await callback.answer() # Если текст тот же, просто закрываем часики

    except Exception as e:
        print(f"Ошибка пагинации: {e}")
        await callback.answer("Ошибка переключения")

@router.callback_query(F.data == "noop")
async def noop_btn(callback: CallbackQuery):
    await callback.answer()

# ==========================================
# 5. ОТМЕТКА ВЫПОЛНЕНИЯ (С ЗАЩИТОЙ)
# ==========================================
@router.callback_query(F.data == "workout_done")
async def process_workout_done(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    user_id = callback.from_user.id
    
    # --- 🛡 ЗАЩИТА ОТ НАКРУТКИ (1 тренировка в 12 часов) ---
    stmt = select(WorkoutLog).where(WorkoutLog.user_id == user_id).order_by(WorkoutLog.date.desc()).limit(1)
    result = await session.execute(stmt)
    last_log = result.scalar_one_or_none()

    if last_log:
        time_diff = datetime.datetime.now() - last_log.date
        # 12 часов = 43200 секунд
        if time_diff.total_seconds() < 43200:
            hours_left = int((43200 - time_diff.total_seconds()) / 3600)
            await callback.answer(f"⏳ Ты уже тренировался сегодня!\nСледующую можно отметить через {hours_left} ч.", show_alert=True)
            return
    # -------------------------------------------------------

    data = await state.get_data()
    current_page = data.get("current_page", 0)
    pages = data.get("workout_pages", [])
    completed_days = data.get("completed_days", [])
    
    # Сохраняем в БД
    new_log = WorkoutLog(
        user_id=user_id,
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
    
    # Обновляем сообщение (ставим кнопку "Отменить")
    base_kb = get_pagination_kb(current_page, len(pages), page_type="workout")
    rows = [[InlineKeyboardButton(text="🔄 Отменить выполнение", callback_data=f"workout_undo_{current_page}")]]
    
    if base_kb and base_kb.inline_keyboard:
        rows.extend(base_kb.inline_keyboard)
        
    final_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    
    try:
        page_text = pages[current_page] + "\n\n🌟 <b>Эта тренировка выполнена!</b>"
        await callback.message.edit_text(text=page_text, reply_markup=final_keyboard, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        await callback.answer() # Игнорируем, если текст не изменился

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

    # Возвращаем кнопку "Выполнено"
    base_kb = get_pagination_kb(target_page, len(pages), page_type="workout")
    page_text = pages[target_page]
    first_line = page_text.split('\n')[0].upper()
    rest_keywords = ["ВОССТАНОВЛЕНИЕ", "ОТДЫХ", "ВЫХОДНОЙ"]
    is_rest_day = any(word in first_line for word in rest_keywords)
    is_advice_page = target_page == len(pages) - 1

    rows = []
    if not is_rest_day and not is_advice_page:
        rows.append([InlineKeyboardButton(text="✅ Тренировка выполнена", callback_data="workout_done")])
            
    if base_kb and base_kb.inline_keyboard:
        rows.extend(base_kb.inline_keyboard)
            
    final_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    try:
        await callback.message.edit_text(text=page_text, reply_markup=final_keyboard, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        await callback.answer()

# ==========================================
# 6. ПРОЧИЕ ХЕНДЛЕРЫ
# ==========================================
@router.callback_query(F.data == "ai_chat")
async def redirect_to_chat(callback: CallbackQuery, state: FSMContext):
    from handlers.ai_chat import start_chat_logic
    await callback.answer()
    await start_chat_logic(callback.message, state)    

@router.callback_query(F.data == "confirm_new_cycle")
async def confirm_cycle_reset(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, обнулить историю", callback_data="execute_new_cycle")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_reset")]
    ])
    
    await callback.message.edit_text(
        "<b>Вы начинаете новый тренировочный цикл?</b>\n\n"
        "Это удалит историю выполненных тренировок... Программа тренировок останется.",
        reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "execute_new_cycle")
async def execute_cycle_reset(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    user_id = callback.from_user.id
    await session.execute(delete(WorkoutLog).where(WorkoutLog.user_id == user_id))
    # 2. 🔥 НОВОЕ: Удаляем историю рабочих весов в упражнениях
    await session.execute(delete(ExerciseLog).where(ExerciseLog.user_id == user_id))
    from database.models import WeightHistory
    await session.execute(delete(WeightHistory).where(WeightHistory.user_id == user_id))
    
    user = await UserCRUD.get_user(session, user_id)
    if user and user.weight:
        session.add(WeightHistory(user_id=user_id, weight=user.weight))
    
    await session.commit()
    await state.update_data(completed_days=[])
    
    await callback.message.edit_text("🚀 <b>Новый цикл запущен!</b>\nИстория очищена.", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "cancel_reset")
async def cancel_reset_handler(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Сброс отменен")

# ==========================================
# 7. ЗАПИСЬ РАБОЧИХ ВЕСОВ В УПРАЖНЕНИЯХ
# ==========================================
@router.callback_query(F.data == "log_weight_press")
async def start_log_exercise(callback: CallbackQuery, state: FSMContext):
    # Создаем клавиатуру с кнопкой "Завершить запись"
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Завершить запись")]],
        resize_keyboard=True,
        one_time_keyboard=False # Кнопка будет висеть, пока не нажмешь
    )
    await callback.message.answer(
        "📝 <b>Дневник тренировок</b>\n\n"
        "Напиши название упражнения, вес и количество повторений.\n"
        "<i>Например: Жим штанги лежа 80 10\n"
        "- Подтягивания 0 12</i>\n"
        "<b>Или: Запиши голосовое сообщение, со своими результатами.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(WorkoutRequest.waiting_for_weights)
    await callback.answer()

@router.message(WorkoutRequest.waiting_for_weights, F.text == "🔙 Завершить запись")
async def exit_log_exercise(message: Message, state: FSMContext):
    # Добавляем этот импорт здесь:
    from keyboards.main_menu import get_main_menu
    # Возвращаем главное меню вниз
    await message.answer("✅ <b>Запись весов завершена.</b>", reply_markup=get_main_menu(), parse_mode="HTML")
    
    # Возвращаем состояние пагинации
    await state.set_state(WorkoutPagination.active)
    
    # Заново отрисовываем текущую страницу тренировки, чтобы было удобно
    data = await state.get_data()
    pages = data.get("workout_pages")
    if pages:
        await show_workout_pages(message, state, pages, from_db=True)

# Ловим и ТЕКСТ, и ГОЛОС одной функцией
@router.message(WorkoutRequest.waiting_for_weights, F.text | F.voice)
async def handle_weights_input(message: Message, bot: Bot, session: AsyncSession, state: FSMContext):
    
    # 1. Проверка лимитов
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user or user.workout_limit <= 0:
        await message.answer("❌ <b>Лимит генераций тренировок исчерпан.</b>", parse_mode="HTML")
        return

    status_msg = await message.answer("⏳ <i>Обрабатываю данные...</i>", parse_mode="HTML")
    input_text = ""

    # ==========================================
    # 2. ЕСЛИ ЭТО ГОЛОСОВОЕ СООБЩЕНИЕ
    # ==========================================
    if message.voice:
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        temp_filename = f"voice_{message.from_user.id}.ogg"
        
        await bot.download_file(file.file_path, temp_filename)
        await asyncio.sleep(0.5)

        try:
            segments, _ = whisper_model.transcribe(temp_filename, beam_size=5, language="ru")
            input_text = "".join([segment.text for segment in segments]).strip()
        except Exception as e:
            print(f"Ошибка Whisper: {e}")
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        
        if not input_text:
            await status_msg.edit_text("📝 Не удалось разобрать слова. Пожалуйста, скажите чуть четче.")
            return
            
        await status_msg.edit_text(f"🎤 Вы сказали: <b>{input_text}</b>\n\n⏳ Анализирую...", parse_mode="HTML")
        
    # ==========================================
    # 3. ЕСЛИ ЭТО ОБЫЧНЫЙ ТЕКСТ
    # ==========================================
    else:
        input_text = message.text

    # ==========================================
    # 4. ОБЩАЯ ЧАСТЬ: ОТПРАВКА В ИИ И СОХРАНЕНИЕ
    # ==========================================
    try:
        # Списываем лимит
        await UserCRUD.reduce_limit(session, message.from_user.id, 'workout')
        
        state_data = await state.get_data()
        workout_type = state_data.get("workout_type", "Тренировка")

        # Твой ультимативный промпт
        parse_prompt = (
            "Ты — строгий фитнес-аналитик. Твоя задача: привести упражнение к ЕДИНОМУ СТАНДАРТУ для базы данных.\n\n"
            "ПРАВИЛА КАНОНИЧНОГО НАЗВАНИЯ:\n"
            "1. ФОРМУЛА: [Упражнение] + [Снаряд] + [Позиция] + [Угол].\n"
            "2. УГЛЫ: Если указаны градусы (30, 45 и т.д.), ОБЯЗАТЕЛЬНО добавь их в конец.\n"
            "   Пример: 'жим на наклонной 30 град' -> 'Жим штанги в наклоне 30'\n"
            "3. УДАЛЯЙ МУСОР: слова 'скамья', 'градусов', 'хваты', 'поочередно'.\n"
            "4. ТРЕНАЖЕРЫ: Смит, Хаммер заменяй на 'в тренажере'.\n\n"
            "СТРОГОЕ ПРАВИЛО: Верни результат списком. Формат:\n"
            "Оригинал | Каноничное | Вес | Повторы | Подходы\n"
            f"Текст: {input_text}"
        )
        
        manager = AIManager()
        ai_response = await manager.get_chat_response([{"role": "user", "content": parse_prompt}], {})
        
        # Парсим железобетонно
        lines = ai_response.strip().split('\n')
        saved_exercises = []
        
        for line in lines:
            parts = line.split('|')
            if len(parts) >= 5:
                try:
                    orig_name = parts[0].strip()
                    canon_name = parts[1].strip()
                    
                    weight_match = re.search(r"[\d\.]+", parts[2].strip().replace(',', '.'))
                    weight = float(weight_match.group(0)) if weight_match else 0.0
                    
                    reps_match = re.search(r"\d+", parts[3].strip())
                    reps = int(reps_match.group(0)) if reps_match else 0
                    
                    sets_match = re.search(r"\d+", parts[4].strip())
                    sets = int(sets_match.group(0)) if sets_match else 1
                    
                    new_log = WorkoutLog(
                        user_id=message.from_user.id,
                        workout_type=workout_type, 
                        exercise_name=orig_name,
                        canonical_name=canon_name,
                        weight=weight,
                        reps=reps,
                        sets=sets
                    )
                    session.add(new_log)
                    saved_exercises.append(f"🔹 <b>{canon_name}</b>\n└ {weight}кг x {reps} (подходов: {sets})")
                except Exception as parse_err:
                    print(f"⚠️ Ошибка парсинга: {line} | {parse_err}")
                    continue
        
        await session.commit()
        
        if saved_exercises:
            result_text = "✨ <b>Записано в дневник:</b>\n\n" + "\n\n".join(saved_exercises)
            result_text += "\n\n<i>✍️ Пиши/диктуй дальше или нажми «Завершить»</i>"
        else:
            result_text = "❌ Не удалось распознать упражнение. Напиши четче (напр: Жим лежа 80 10)."
            
        await status_msg.edit_text(result_text, parse_mode="HTML")

    except Exception as e:
        print(f"❌ Критическая ошибка ИИ: {e}")
        await status_msg.edit_text("🔧 Произошла ошибка при обработке данных.")    