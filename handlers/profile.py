import html
import re
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, cast, Date, distinct

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
SUB_MAP = {
    "free": "🆓 Бесплатный",
    "lite": "🥉 Лайт",
    "standard": "🥈 Стандарт",
    "ultra": "🥇 Ультра"
}

# --- 1. ГЕНЕРАЦИЯ КРАСИВОГО ТЕКСТА С РАНГОМ ---
async def get_full_profile_text(user, session: AsyncSession) -> str:
    # Считаем тренировки
    stmt = select(func.count(WorkoutLog.id)).where(WorkoutLog.user_id == user.telegram_id)
    result = await session.execute(stmt)
    total_workouts = result.scalar() or 0
    total_workouts = user.completed_workouts or 0

    # Вычисляем ранг
    if total_workouts < 3: rank = "🌱 Новичок"
    elif total_workouts < 10: rank = "🥉 Любитель"
    elif total_workouts < 30: rank = "🥈 Опытный атлет"
    elif total_workouts < 50: rank = "🥇 Машина"
    else: rank = "👑 Киборг-убийца"

    # Формируем главную шапку с тарифом
    current_sub = SUB_MAP.get(user.subscription_level, "🆓 Бесплатный")
    expire_text = ""
    if user.subscription_expires_at:
        date_str = user.subscription_expires_at.strftime("%d.%m.%Y")
        expire_text = f" <i>(до {date_str})</i>"
    
    tariff_header = f"💳 <b>Текущий тариф:</b> {current_sub}{expire_text}\n\n"

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

    # Формируем компактный статус для блока лимитов
    short_sub_map = {"free": "🆓 Free", "lite": "🥉 Lite", "standard": "🥈 Standard", "ultra": "🥇 Ultra"}
    short_status = short_sub_map.get(user.subscription_level, "🆓 Free")
    if user.subscription_expires_at:
        short_status += f" (до {user.subscription_expires_at.strftime('%d.%m.%y')})"

    return (
        f"{tariff_header}"
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
        f"💎 <b>Статус:</b> {short_status}\n"
        f"📊 <b>Остаток лимитов:</b>\n"
        f"├ 🍏 Питание/💪 Трен/📊 Анализ: <b>{user.workout_limit}</b>\n"
        f"└ 💬 Чат и запись: <b>{user.chat_limit}</b>\n"
        f"──────────────────\n"
        f"⏰ <b>Уведомления:</b> {txt_time}"
    )

# --- 2. ГЕНЕРАЦИЯ КЛАВИАТУРЫ ---
def get_profile_keyboard(user):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Редактировать данные", callback_data="open_edit_menu"))
         
    kb.row(InlineKeyboardButton(text="📖 Дневник весов", callback_data="exercise_diary"))
    kb.row(InlineKeyboardButton(text="🔔 Время уведомлений", callback_data="change_notif_time"))
    
    # --- НАША НОВАЯ КНОПКА ---
    kb.row(InlineKeyboardButton(text="💳 Баланс и Друзья", callback_data="show_balance"))
    if user.subscription_level == "free" or user.subscription_level is None:
        kb.row(InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_premium"))
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
        
    final_text = await get_full_profile_text(user, session)

    await message.answer(
        text=final_text, 
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

# --- 5. ОБРАБОТЧИК КНОПКИ "НАЗАД/ЗАКРЫТЬ" (ЕДИНЫЙ) ---
@router.callback_query(F.data == "close_edit_menu")
async def close_edit(callback: CallbackQuery, session: AsyncSession):
    user = await UserCRUD.get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден.", show_alert=True)
        return
        
    text = await get_full_profile_text(user, session)
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_profile_keyboard(user),
            parse_mode="HTML"
        )
    except Exception:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(
            text=text,
            reply_markup=get_profile_keyboard(user),
            parse_mode="HTML"
        )

    await callback.answer()

# --- 6. ЛОГИКА ВВОДА ДАННЫХ ---
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

@router.callback_query(F.data == "prof_goal")
async def ask_goal(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("🎯 Выберите цель:", reply_markup=get_goal_keyboard())

@router.message(StateFilter(None), F.text.in_(GOAL_MAP.values()))
async def save_goal(message: Message, session: AsyncSession, state: FSMContext):
    code = next((k for k, v in GOAL_MAP.items() if v == message.text), None)
    if code:
        await UserCRUD.update_user(session, message.from_user.id, goal=code)
        await return_to_edit(message, session, state)

@router.callback_query(F.data == "prof_activity")
async def ask_activity(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("🏃 Выберите активность:", reply_markup=get_activity_keyboard())

@router.message(StateFilter(None), F.text.in_(ACTIVITY_MAP.values()) | F.text.contains("Сидячий") | F.text.contains("Малая") | F.text.contains("Средняя") | F.text.contains("Высокая"))
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

@router.message(StateFilter(None), F.text.in_(LEVEL_MAP.values()) | F.text.contains("Новичок") | F.text.contains("Любитель") | F.text.contains("Продвинутый"))
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

@router.message(StateFilter(None), F.text.contains("дн") | F.text.regexp(r'^\d+$'))
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

@router.message(StateFilter(None), F.text.in_(GENDER_MAP.values()))
async def save_gender(message: Message, session: AsyncSession, state: FSMContext):
    code = "male" if "Мужской" in message.text else "female"
    await UserCRUD.update_user(session, message.from_user.id, gender=code)
    await return_to_edit(message, session, state)

# --- 7. НАСТРОЙКА ВРЕМЕНИ И ОПЛАТА ---
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
    try:
        hour = int(callback.data.split("_")[2])
        await UserCRUD.update_user(session, callback.from_user.id, notification_time=hour)
        
        user = await UserCRUD.get_user(session, callback.from_user.id)
        if not user:
            await callback.answer("Ошибка: пользователь не найден.", show_alert=True)
            return
            
        text = await get_full_profile_text(user, session)
        await callback.message.edit_text(text, reply_markup=get_profile_keyboard(user), parse_mode="HTML")
        await callback.answer(f"✅ Время уведомлений установлено на {hour}:00")
    except Exception:
        await callback.answer("❌ Произошла ошибка при установке времени.", show_alert=True)    

# ==========================================
# 8. ДНЕВНИК РАБОЧИХ ВЕСОВ
# ==========================================
@router.callback_query(F.data == "exercise_diary")
async def show_exercise_diary(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    user = await UserCRUD.get_user(session, user_id)
    
    from handlers.admin import is_admin
    if not is_admin(user_id) and user.subscription_level in ["free", "lite", None]:
        await callback.answer("📖 Дневник рабочих весов доступен начиная с тарифа Standard!", show_alert=True)
        return
    
    stmt = select(WorkoutLog).where(
        WorkoutLog.user_id == user_id,
        WorkoutLog.weight > 0
    ).order_by(desc(WorkoutLog.date))
    
    result = await session.execute(stmt)
    logs = result.scalars().all()
    
    if not logs:
        await callback.answer("Твой дневник пока пуст! Записывай веса во время тренировок.", show_alert=True)
        return
        
    latest_logs = {}
    for log in logs:
        name = log.canonical_name if log.canonical_name else log.exercise_name
        if not name:
            continue

        name_key = name.lower().strip()
        if name_key not in latest_logs:
            latest_logs[name_key] = log
            
    text = "📖 <b>Твой дневник рабочих весов:</b>\n\n"
    
    for log in latest_logs.values():
        date_str = log.date.strftime("%d.%m")
        weight_display = int(log.weight) if log.weight.is_integer() else log.weight
        name = log.canonical_name if log.canonical_name else log.exercise_name
        text += f"🏋️‍♂️ <b>{name.capitalize()}:</b> {weight_display} кг х {log.reps} <i>({date_str})</i>\n"
        
    text += "\n<i>💡 Чтобы обновить результат или исправить ошибку, просто запиши новый вес для этого упражнения на тренировке.</i>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в профиль", callback_data="close_edit_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# 1. Сначала показываем только баланс
@router.callback_query(F.data == "show_balance")
async def show_balance_callback(call: CallbackQuery, session: AsyncSession):
    user = await UserCRUD.get_user(session, call.from_user.id)
    
    # Собираем список кнопок
    buttons = [
        [InlineKeyboardButton(text="🔗 Реферальная ссылка", callback_data="show_ref_link")]
    ]
    
    # Если тариф уже платный, добавляем кнопку апгрейда прямо под реф. ссылку
    if user.subscription_level not in ["free", None]:
        buttons.append([InlineKeyboardButton(text="💎 Управление подпиской", callback_data="buy_premium")])
        
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await call.message.answer(
        f"💳 <b>Ваш баланс:</b> {user.referral_balance} руб.\n\n"
        f"<i>Средства с баланса можно использовать для оплаты подписки.</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await call.answer()

# 2. Выдаем ссылку по нажатию на новую кнопку
@router.callback_query(F.data == "show_ref_link")
async def show_ref_link_callback(call: CallbackQuery, session: AsyncSession, bot: Bot):
    user = await UserCRUD.get_user(session, call.from_user.id)
    bot_info = await bot.get_me()
    
    ref_link = f"https://t.me/{bot_info.username}?start={user.telegram_id}"
    
    text = (
        f"🎁 <b>Партнерская программа</b>\n\n"
        f"Приглашайте друзей и зарабатывайте на оплату подписки!\n\n"
        f"🔗 <b>Ваша личная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n"
        f"<i>(нажмите на ссылку, чтобы скопировать)</i>\n\n"
        f"<b>Что получает друг:</b>\n"
        f"➕ 5 генераций тренировок\n"
        f"➕ 10 вопросов AI-тренеру\n\n"
        f"<b>Что получаете вы:</b>\n"
        f"🔥 <b>15%</b> от любой оплаты друга моментально зачисляются на ваш баланс!" # <--- И ЗДЕСЬ 15%
    )
    
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()   