import time
import re
import json
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
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
async def show_workout_pages(message: Message, state: FSMContext, pages: list, from_db: bool = False, completed_days_direct: list = None):
    # 1. Сохраняем состояние
    await state.update_data(workout_pages=pages, current_page=0)
    
    if completed_days_direct is not None:
        await state.update_data(completed_days=completed_days_direct)
        check_list = completed_days_direct
    else:
        data = await state.get_data()
        check_list = data.get("completed_days", [])
    
    await state.set_state(WorkoutPagination.active)
    
    current_page = 0
    page_text = pages[current_page]
    
    # 2. Получаем БАЗОВУЮ клавиатуру (стрелки и т.д.)
    base_kb = get_pagination_kb(current_page, len(pages), page_type="workout")
    
    # 3. ЛОГИКА КНОПКИ
    # Берем только самую первую строку (заголовок) для проверки
    first_line = page_text.split('\n')[0].upper()
    rest_keywords = ["ВОССТАНОВЛЕНИЕ", "ОТДЫХ", "ВЫХОДНОЙ"]
    is_rest_day = any(word in first_line for word in rest_keywords)
    is_advice_page = current_page == len(pages) - 1

    # Создаем новый список рядов для кнопок
    rows = []

    # Добавляем кнопку выполнения ПЕРВЫМ рядом, если это не отдых
    if not is_rest_day and not is_advice_page:
        if current_page in check_list:
            btn_text, btn_cb = "🔄 Отменить выполнение", f"workout_undo_{current_page}"
        else:
            btn_text, btn_cb = "✅ Тренировка выполнена", "workout_done"
        
        # ВАЖНО: Добавляем как список (ряд)
        rows.append([InlineKeyboardButton(text=btn_text, callback_data=btn_cb)])

    # Добавляем все остальные ряды из базовой клавиатуры (стрелки, советы и т.д.)
    if base_kb and base_kb.inline_keyboard:
        rows.extend(base_kb.inline_keyboard)

    # Создаем итоговый объект клавиатуры
    final_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    # 4. Формируем текст
    prefix = "💾 <b>Твоя программа:</b>\n\n" if from_db else "🆕 <b>Программа готова:</b>\n\n"
    display_text = prefix + page_text
    if current_page in check_list:
         display_text += "\n\n🌟 <b>Эта тренировка выполнена!</b>"

    # 5. ОТПРАВКА (строго один вызов)
    if isinstance(message, Message):
        await message.answer(display_text, reply_markup=final_keyboard, parse_mode="HTML")
    else:
        try:
            await message.edit_text(display_text, reply_markup=final_keyboard, parse_mode="HTML")
        except Exception:
            await message.answer(display_text, reply_markup=final_keyboard, parse_mode="HTML")

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
            # 🔥 Достаем из базы список выполненных дней
            from sqlalchemy import select
            from database.models import WorkoutLog
            
            stmt = select(WorkoutLog.workout_type).where(WorkoutLog.user_id == message.from_user.id)
            result = await session.execute(stmt)
            logs = result.scalars().all() # Получим список типа ["День 1", "День 2"]
            
            # Превращаем названия в индексы страниц (0, 1, 2...)
            completed_days = []
            for log in logs:
                try:
                    # Извлекаем число из строки "День X" и вычитаем 1
                    day_num = int(log.split(" ")[-1]) - 1
                    completed_days.append(day_num)
                except: continue
            
            # Сохраняем этот список в состояние (FSM)
            await state.update_data(completed_days=completed_days)
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
async def confirm_new_workout_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    # Сразу переходим к шагу с пожеланиями
    await start_wishes_step(callback.message, state)
    await callback.answer()

# 2. ЭТА ФУНКЦИЯ ДОЛЖНА ИДТИ СЛЕДУЮЩЕЙ — она ловит ваш текст
@router.message(WorkoutRequest.waiting_for_wishes)
async def process_workout_wishes(message: Message, session: AsyncSession, state: FSMContext):
    user_wishes = message.text
    
    # Получаем старые данные, чтобы сохранить контекст
    data = await state.get_data()
    old_wishes = data.get("wishes", "")
    
    # Объединяем старые пожелания с новыми
    if old_wishes and user_wishes.lower() != "без изменений":
        combined_wishes = f"{old_wishes}. Дополнительно: {user_wishes}"
    else:
        combined_wishes = user_wishes

    await state.update_data(wishes=combined_wishes)
    user = await UserCRUD.get_user(session, message.from_user.id)
    
    # Запускаем саму генерацию
    await generate_workout_process(message, session, user, state, wishes=combined_wishes)

# --- ОБРАБОТЧИКИ ПОДТВЕРЖДЕНИЯ ---
@router.callback_query(F.data == "confirm_new_workout")
async def confirm_new_workout_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    # Сразу переходим к шагу с пожеланиями
    await start_wishes_step(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "cancel_workout")
async def cancel_generation(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")

# --- КНОПКА "🔄 Новая программа" (из пагинации) ---
@router.callback_query(F.data == "regen_workout")
@router.callback_query(F.data == "refresh_ai_workout")
async def force_regen_workout(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.set_state(WorkoutRequest.waiting_for_wishes)
    
    # Можно отправить новое сообщение или отредактировать старое
    await callback.message.answer(
        "📝 <b>Что добавить или изменить в новой программе?</b>\n\n"
        "Например: <i>'убери приседания'</i>, <i>'сделай упор на плечи'</i> или просто напиши <i>'без изменений'</i>.",
        parse_mode="HTML"
    )
    await callback.answer()

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
        completed_days = data.get("completed_days", [])
        page_text = pages[target_page]
        
        # Формируем клавиатуру
        base_kb = get_pagination_kb(target_page, len(pages), page_type="workout")
        
        # Логика скрытия кнопки в дни отдыха
        # Берем только самую первую строку (заголовок) для проверки
        first_line = page_text.split('\n')[0].upper()
        rest_keywords = ["ВОССТАНОВЛЕНИЕ", "ОТДЫХ", "ВЫХОДНОЙ"]
        is_rest_day = any(word in first_line for word in rest_keywords)
        is_advice_page = target_page == len(pages) - 1

        # Собираем ряды кнопок безопасно
        rows = []
        if not is_rest_day and not is_advice_page:
            if target_page in completed_days:
                btn_text, btn_cb = "🔄 Отменить выполнение", f"workout_undo_{target_page}"
            else:
                btn_text, btn_cb = "✅ Тренировка выполнена", "workout_done"
            rows.append([InlineKeyboardButton(text=btn_text, callback_data=btn_cb)])
        
        if base_kb and base_kb.inline_keyboard:
            rows.extend(base_kb.inline_keyboard)
        
        final_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

        # 🔥 ВОТ ЭТОГО НЕ ХВАТАЛО: Готовим текст перед отправкой
        display_text = page_text
        if target_page in completed_days:
            display_text += "\n\n🌟 <b>Эта тренировка выполнена!</b>"

        await callback.message.edit_text(
            text=display_text,
            reply_markup=final_keyboard,
            parse_mode=ParseMode.HTML
        )
        await callback.answer()

    except Exception as e:
        print(f"Ошибка пагинации: {e}")
        await callback.answer("Ошибка переключения")

@router.callback_query(F.data == "noop")
async def noop_btn(callback: CallbackQuery):
    await callback.answer()

# ==========================================
# 4. ВЫПОЛНЕНИЕ / ОТМЕНА ТРЕНИРОВКИ
# ==========================================
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
    
    # МГНОВЕННО ОБНОВЛЯЕМ КНОПКУ (Безопасная сборка вместо .insert)
    base_kb = get_pagination_kb(current_page, len(pages), page_type="workout")
    rows = [[InlineKeyboardButton(text="🔄 Отменить выполнение", callback_data=f"workout_undo_{current_page}")]]
    
    if base_kb and base_kb.inline_keyboard:
        rows.extend(base_kb.inline_keyboard)
        
    final_keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    
    try:
        page_text = pages[current_page] + "\n\n🌟 <b>Эта тренировка выполнена!</b>"
        await callback.message.edit_text(
            text=page_text,
            reply_markup=final_keyboard,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        print(f"Ошибка отметки выполнения: {e}")

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

    # ВОЗВРАЩАЕМ КНОПКУ "ВЫПОЛНЕНО" (Безопасная сборка)
    base_kb = get_pagination_kb(target_page, len(pages), page_type="workout")
    page_text = pages[target_page]
    # Берем только самую первую строку (заголовок) для проверки
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

    await callback.message.edit_text(
        text=page_text,
        reply_markup=final_keyboard,
        parse_mode=ParseMode.HTML
    )    

# ==========================================
# 5. ПРОЧИЕ ХЕНДЛЕРЫ (Чат и Циклы)
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
        "Это удалит историю выполненных тренировок, чтобы ИИ мог составить "
        "новый точный анализ твоего прогресса. Программа тренировок останется.\n\n"
        "<i>Рекомендуется делать это раз в 4-8 недель.</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "execute_new_cycle")
async def execute_cycle_reset(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    user_id = callback.from_user.id
    from sqlalchemy import delete
    from database.models import WorkoutLog, WeightHistory
    
    await session.execute(delete(WorkoutLog).where(WorkoutLog.user_id == user_id))
    await session.execute(delete(WeightHistory).where(WeightHistory.user_id == user_id))
    
    user = await UserCRUD.get_user(session, user_id)
    if user and user.weight:
        session.add(WeightHistory(user_id=user_id, weight=user.weight))
    
    await session.commit()
    await state.update_data(completed_days=[])
    
    await callback.message.edit_text(
        "🚀 <b>Новый цикл запущен!</b>\n\n"
        "История тренировок и веса очищена. Теперь анализ будет строиться только на основе новых данных.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "cancel_reset")
async def cancel_reset_handler(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Сброс отменен")