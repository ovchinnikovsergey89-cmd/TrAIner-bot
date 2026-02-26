import html
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from database.crud import UserCRUD
from database.models import WorkoutLog, ExerciseLog
from states.user_states import EditForm
from keyboards.main_menu import get_main_menu
from keyboards.builders import (
    get_gender_keyboard,
    get_activity_keyboard,
    get_goal_keyboard,
    get_workout_level_keyboard,
    get_workout_days_keyboard
)

router = Router()

# --- ВСПОМОГАТЕЛЬНЫЕ ДАННЫЕ ---
GENDER_MAP = {"male": "👨 Мужской", "female": "👩 Женский"}
GOAL_MAP = {
    "weight_loss": "📉 Похудение", 
    "maintenance": "⚖️ Поддержание", 
    "muscle_gain": "💪 Набор массы",
    "recomposition": "🔄 Рекомпозиция"
}
LEVEL_MAP = {"beginner": "👶 Новичок", "intermediate": "👨‍🎓 Любитель", "advanced": "🏆 ПРО"}
ACTIVITY_MAP = {
    "sedentary": "🪑 Сидячий", "light": "🚶 Малая", 
    "moderate": "🏃 Средняя", "high": "🏋️ Высокая", "extreme": "🔥 Экстремальная"
}

# --- 1. ГЕНЕРАЦИЯ КРАСИВОГО ТЕКСТА С РАНГОМ ---
async def get_full_profile_text(user, session: AsyncSession) -> str:
    # Считаем тренировки
    stmt = select(func.count(WorkoutLog.id)).where(WorkoutLog.user_id == user.telegram_id)
    result = await session.execute(stmt)
    total_workouts = result.scalar() or 0

    # Вычисляем ранг
    if total_workouts < 3:
        rank = "🌱 Новичок"
    elif total_workouts < 10:
        rank = "🥉 Любитель"
    elif total_workouts < 30:
        rank = "🥈 Опытный атлет"
    elif total_workouts < 50:
        rank = "🥇 Машина"
    else:
        rank = "👑 Киборг-убийца"

    txt_name = html.escape(user.name or "Атлет")
    txt_age = user.age or "-"
    txt_height = f"{user.height} см" if user.height else "-"
    txt_weight = f"{user.weight} кг" if user.weight else "-"
    txt_gender = GENDER_MAP.get(user.gender, "-")
    txt_goal = GOAL_MAP.get(user.goal, user.goal)
    txt_level = LEVEL_MAP.get(user.workout_level, "-")
    act_val = user.activity_level
    txt_activity = ACTIVITY_MAP.get(act_val, act_val) if act_val else "-"
    txt_days = f"{user.workout_days} дн/нед" if user.workout_days else "-"
    
    txt_time = f"{user.notification_time}:00" if user.notification_time is not None else "Откл"
    status = "🌟 <b>Premium</b>" if user.is_premium else "🆓 <b>Бесплатный</b>"
    
    return (
        f"👤 <b>Профиль: {txt_name}</b>\n"
        f"──────────────────\n"
        f"🏆 <b>Ранг:</b> {rank}\n"
        f"💪 <b>Всего тренировок:</b> {total_workouts}\n"
        f"──────────────────\n"
        f"🎂 <b>Возраст:</b> {txt_age} | {txt_gender}\n"
        f"📏 <b>Рост:</b> {txt_height} | ⚖️ <b>Вес:</b> {txt_weight}\n"
        f"──────────────────\n"
        f"🏃 <b>Активность:</b> {txt_activity}\n"
        f"🎯 <b>Цель:</b> {txt_goal}\n"
        f"💪 <b>Уровень:</b> {txt_level}\n"
        f"📅 <b>Режим:</b> {txt_days}\n"
        f"──────────────────\n"
        f"💎 <b>Статус:</b> {status}\n"
        f"📊 <b>Остаток лимитов:</b>\n"
        f"├ 🍏 Питание/Трен/Анализ: <b>{user.workout_limit}</b>\n"
        f"└ 💬 Вопросы AI: <b>{user.chat_limit}</b>\n"
        f"──────────────────\n"
        f"⏰ <b>Уведомления:</b> {txt_time}"
    )

# --- 2. ГЕНЕРАЦИЯ КЛАВИАТУРЫ ---
def get_profile_keyboard(user):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Редактировать данные", callback_data="open_edit_menu"))
    
    # Кнопка Premium
    if not user.is_premium or (user.workout_limit is not None and user.workout_limit < 5):
        kb.row(InlineKeyboardButton(text="💎 Получить Premium / Пополнить", callback_data="buy_premium"))
    kb.row(InlineKeyboardButton(text="📖 Дневник весов", callback_data="exercise_diary"))
    kb.row(InlineKeyboardButton(text="🔔 Время уведомлений", callback_data="change_notif_time"))
    kb.row(InlineKeyboardButton(text="🔄 Начать новый цикл", callback_data="confirm_new_cycle"))
    
    return kb.as_markup()

# --- 3. ПРОСМОТР ПРОФИЛЯ ---
@router.message(F.text == "👤 Профиль")
@router.message(Command("profile"))
async def show_profile_view(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Сначала пройдите регистрацию: /start")
        return
    
    # Получаем красивый текст с рангом
    text = await get_full_profile_text(user, session)

    await message.answer(
        text=text, 
        reply_markup=get_profile_keyboard(user),
        parse_mode="HTML"
    )

# --- 4. МЕНЮ РЕДАКТИРОВАНИЯ ---
@router.callback_query(F.data == "open_edit_menu")
async def show_edit_menu(event, session: AsyncSession, state: FSMContext):
    await state.clear()
    
    message = event if isinstance(event, Message) else event.message
    user_id = event.from_user.id
    user = await UserCRUD.get_user(session, user_id)
    if not user: return

    base_text = await get_full_profile_text(user, session)
    text = base_text + "\n\n👇 <b>Выберите параметр для изменения:</b>"

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⚖️ Вес", callback_data="prof_weight"),
           InlineKeyboardButton(text="📏 Рост", callback_data="prof_height"),
           InlineKeyboardButton(text="🎂 Возраст", callback_data="prof_age"))
    kb.row(InlineKeyboardButton(text="🎯 Цель", callback_data="prof_goal"),
           InlineKeyboardButton(text="🏃 Активность", callback_data="prof_activity"))
    kb.row(InlineKeyboardButton(text="💪 Уровень", callback_data="prof_level"),
           InlineKeyboardButton(text="📅 Дни", callback_data="prof_days"))
    kb.row(InlineKeyboardButton(text="👫 Пол", callback_data="prof_gender"))
    kb.row(InlineKeyboardButton(text="✅ Готово (Закрыть)", callback_data="close_edit_menu"))

    if isinstance(event, CallbackQuery):
        await message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "close_edit_menu")
async def close_edit(callback: CallbackQuery, session: AsyncSession):
    user = await UserCRUD.get_user(session, callback.from_user.id)
    text = await get_full_profile_text(user, session)
    
    await callback.message.edit_text(
        text=text,
        reply_markup=get_profile_keyboard(user),
        parse_mode="HTML"
    )

# --- 5. ЛОГИКА ВВОДА ДАННЫХ ---
async def return_to_edit(message: Message, session: AsyncSession, state: FSMContext):
    await show_edit_menu(message, session, state)

@router.callback_query(F.data == "prof_weight")
async def ask_weight(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⚖️ Введите новый вес (кг):")
    await state.set_state(EditForm.weight)

@router.message(EditForm.weight)
async def save_weight(message: Message, state: FSMContext, session: AsyncSession):
    try:
        val = float(message.text.replace(',', '.'))
        if 30 <= val <= 250:
            await UserCRUD.update_user(session, message.from_user.id, weight=val)
            await message.answer("✅ Вес сохранен.")
            await return_to_edit(message, session, state)
        else: await message.answer("❌ Введите реальный вес (30-250).")
    except: await message.answer("❌ Введите число.")

# (Аналогично для Роста и Возраста)
@router.callback_query(F.data == "prof_height")
async def ask_height(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📏 Введите новый рост (см):")
    await state.set_state(EditForm.height)

@router.message(EditForm.height)
async def save_height(message: Message, state: FSMContext, session: AsyncSession):
    try:
        val = float(message.text.replace(',', '.'))
        if 100 <= val <= 250:
            await UserCRUD.update_user(session, message.from_user.id, height=val)
            await return_to_edit(message, session, state)
    except: await message.answer("❌ Введите число.")

@router.callback_query(F.data == "prof_age")
async def ask_age(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎂 Введите новый возраст:")
    await state.set_state(EditForm.age)

@router.message(EditForm.age)
async def save_age(message: Message, state: FSMContext, session: AsyncSession):
    if message.text.isdigit() and 10 <= int(message.text) <= 100:
        await UserCRUD.update_user(session, message.from_user.id, age=int(message.text))
        await return_to_edit(message, session, state)
    else: await message.answer("❌ Введите число (10-100).")

# Кнопки выбора (Цель, Активность и т.д.)
@router.callback_query(F.data == "prof_goal")
async def ask_goal(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("🎯 Выберите цель:", reply_markup=get_goal_keyboard())

@router.message(F.text.in_(GOAL_MAP.values()))
async def save_goal(message: Message, session: AsyncSession, state: FSMContext):
    code = next((k for k, v in GOAL_MAP.items() if v == message.text), None)
    if code:
        await UserCRUD.update_user(session, message.from_user.id, goal=code)
        await return_to_edit(message, session, state)

@router.callback_query(F.data == "prof_activity")
async def ask_activity(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("🏃 Выберите активность:", reply_markup=get_activity_keyboard())

@router.message(F.text.in_(ACTIVITY_MAP.values()) | F.text.contains("Сидячий") | F.text.contains("Малая") | F.text.contains("Средняя") | F.text.contains("Высокая"))
async def save_activity(message: Message, session: AsyncSession, state: FSMContext):
    val = "sedentary"
    if "Малая" in message.text: val = "light"
    elif "Средняя" in message.text: val = "moderate"
    elif "Высокая" in message.text: val = "high"
    elif "Экстремальная" in message.text: val = "extreme"
    await UserCRUD.update_user(session, message.from_user.id, activity_level=val)
    await return_to_edit(message, session, state)

@router.callback_query(F.data == "prof_level")
async def ask_level(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("💪 Выберите уровень:", reply_markup=get_workout_level_keyboard())

@router.message(F.text.in_(LEVEL_MAP.values()) | F.text.contains("Новичок") | F.text.contains("Любитель") | F.text.contains("Продвинутый"))
async def save_level(message: Message, session: AsyncSession, state: FSMContext):
    code = "beginner"
    if "Любитель" in message.text: code = "intermediate"
    elif "ПРО" in message.text or "Продвинутый" in message.text: code = "advanced"
    await UserCRUD.update_user(session, message.from_user.id, workout_level=code)
    await return_to_edit(message, session, state)

@router.callback_query(F.data == "prof_days")
async def ask_days(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("📅 Дней в неделю:", reply_markup=get_workout_days_keyboard())

@router.message(F.text.contains("дн") | F.text.regexp(r'^\d+$'))
async def save_days(message: Message, session: AsyncSession, state: FSMContext):
    try:
        d = int(re.search(r'\d+', message.text).group())
        await UserCRUD.update_user(session, message.from_user.id, workout_days=d)
        await return_to_edit(message, session, state)
    except: pass

@router.callback_query(F.data == "prof_gender")
async def ask_gender(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("👫 Ваш пол:", reply_markup=get_gender_keyboard())

@router.message(F.text.in_(GENDER_MAP.values()))
async def save_gender(message: Message, session: AsyncSession, state: FSMContext):
    code = "male" if "Мужской" in message.text else "female"
    await UserCRUD.update_user(session, message.from_user.id, gender=code)
    await return_to_edit(message, session, state)

# --- 6. НАСТРОЙКА ВРЕМЕНИ ---
@router.callback_query(F.data == "change_notif_time")
async def ask_notif_time(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    hours = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
    for h in hours:
        builder.add(InlineKeyboardButton(text=f"{h}:00", callback_data=f"set_time_{h}"))
    builder.adjust(4)
    
    await callback.message.edit_text(
        "⏰ <b>Выберите время уведомлений:</b>", 
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("set_time_"))
async def save_notif_time(callback: CallbackQuery, session: AsyncSession):
    hour = int(callback.data.split("_")[-1])
    await UserCRUD.update_user(session, callback.from_user.id, notification_time=hour)
    await callback.answer(f"Время установлено: {hour}:00")
    
    user = await UserCRUD.get_user(session, callback.from_user.id)
    text = await get_full_profile_text(user, session)
    
    await callback.message.edit_text(
        text=text,
        reply_markup=get_profile_keyboard(user),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "buy_premium")
async def process_buy_premium(callback: CallbackQuery):
    await callback.answer("💳 Модуль оплаты будет доступен в следующем обновлении!", show_alert=True)

# ==========================================
# ДНЕВНИК РАБОЧИХ ВЕСОВ
# ==========================================
@router.callback_query(F.data == "exercise_diary")
async def show_exercise_diary(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    
    # Достаем все записи пользователя, сортируем от новых к старым
    stmt = select(ExerciseLog).where(ExerciseLog.user_id == user_id).order_by(desc(ExerciseLog.date))
    result = await session.execute(stmt)
    logs = result.scalars().all()
    
    if not logs:
        await callback.answer("Твой дневник пока пуст! Записывай веса во время тренировок.", show_alert=True)
        return
        
    # Оставляем только самую последнюю запись для каждого упражнения
    latest_logs = {}
    for log in logs:
        # Название приводим к нижнему регистру для проверки, чтобы "Жим" и "жим" считались одним и тем же
        name_key = log.exercise_name.lower().strip()
        if name_key not in latest_logs:
            latest_logs[name_key] = log
            
    # Формируем красивое сообщение
    text = "📖 <b>Твой дневник рабочих весов:</b>\n\n"
    
    for log in latest_logs.values():
        date_str = log.date.strftime("%d.%m") # Формат даты: 26.02
        
        # Убираем ".0", если вес целое число (например, 80.0 -> 80)
        weight_display = int(log.weight) if log.weight.is_integer() else log.weight
        
        text += f"🏋️‍♂️ <b>{log.exercise_name.capitalize()}:</b> {weight_display} кг х {log.reps} <i>({date_str})</i>\n"
        
    text += "\n<i>💡 Чтобы обновить результат или исправить ошибку, просто запиши новый вес для этого упражнения на тренировке.</i>"
    
    # Кнопка возврата в профиль (используем уже готовую и надежную логику)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в профиль", callback_data="close_edit_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")    