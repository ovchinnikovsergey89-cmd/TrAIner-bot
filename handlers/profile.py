import html
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
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
GOAL_MAP = {"weight_loss": "📉 Похудение", "maintenance": "⚖️ Поддержание", "muscle_gain": "💪 Набор массы"}
LEVEL_MAP = {"beginner": "👶 Новичок", "intermediate": "👨‍🎓 Любитель", "advanced": "🏆 ПРО"}
ACTIVITY_MAP = {
    "sedentary": "🪑 Сидячий", "light": "🚶 Малая", 
    "moderate": "🏃 Средняя", "high": "🏋️ Высокая", "extreme": "🔥 Экстремальная"
}
STYLE_MAP = {"supportive": "🔥 Тони (Мотиватор)", "tough": "💀 Сержант", "scientific": "🧐 Доктор"}

# --- ФУНКЦИЯ ГЕНЕРАЦИИ ТЕКСТА ---
def get_profile_text(user):
    txt_name = html.escape(user.name or "Атлет")
    txt_age = user.age or "-"
    txt_height = f"{user.height} см" if user.height else "-"
    txt_weight = f"{user.weight} кг" if user.weight else "-"
    txt_gender = GENDER_MAP.get(user.gender, "-")
    txt_goal = GOAL_MAP.get(user.goal, "-")
    txt_level = LEVEL_MAP.get(user.workout_level, "-")
    act_val = user.activity_level
    txt_activity = ACTIVITY_MAP.get(act_val, act_val) if act_val else "-"
    txt_days = f"{user.workout_days} дн/нед" if user.workout_days else "-"
    txt_style = STYLE_MAP.get(user.trainer_style, "🔥 Тони")

    return (
        f"👤 <b>Профиль: {txt_name}</b>\n"
        f"──────────────────\n"
        f"🎂 <b>Возраст:</b> {txt_age} | {txt_gender}\n"
        f"📏 <b>Рост:</b> {txt_height} | ⚖️ <b>Вес:</b> {txt_weight}\n"
        f"──────────────────\n"
        f"🏃 <b>Активность:</b> {txt_activity}\n"
        f"🎯 <b>Цель:</b> {txt_goal}\n"
        f"💪 <b>Уровень:</b> {txt_level}\n"
        f"📅 <b>Режим:</b> {txt_days}\n"
        f"──────────────────\n"
        f"🎭 <b>Тренер:</b> {txt_style}"
    )

# --- 1. ПРОСМОТР ПРОФИЛЯ (Только чтение) ---
@router.message(F.text == "👤 Профиль")
@router.message(Command("profile"))
async def show_profile_view(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Сначала пройдите регистрацию: /start")
        return

    text = get_profile_text(user)
    
    # Кнопка ведет в режим редактирования
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Редактировать данные", callback_data="open_edit_menu"))
    
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

# --- 2. МЕНЮ РЕДАКТИРОВАНИЯ (Сетка кнопок) ---
@router.callback_query(F.data == "open_edit_menu")
async def show_edit_menu(event, session: AsyncSession, state: FSMContext):
    await state.clear()
    
    # Определяем, кто вызвал функцию (Message или Callback)
    if isinstance(event, Message):
        message = event
        user_id = message.from_user.id
        is_callback = False
    else:
        message = event.message
        user_id = event.from_user.id
        is_callback = True

    user = await UserCRUD.get_user(session, user_id)
    if not user: return

    text = get_profile_text(user) + "\n\n👇 <b>Выберите параметр для изменения:</b>"

    # Сетка кнопок
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⚖️ Вес", callback_data="prof_weight"),
        InlineKeyboardButton(text="📏 Рост", callback_data="prof_height"),
        InlineKeyboardButton(text="🎂 Возраст", callback_data="prof_age")
    )
    kb.row(
        InlineKeyboardButton(text="🎯 Цель", callback_data="prof_goal"),
        InlineKeyboardButton(text="🏃 Активность", callback_data="prof_activity")
    )
    kb.row(
        InlineKeyboardButton(text="💪 Уровень", callback_data="prof_level"),
        InlineKeyboardButton(text="📅 Дни", callback_data="prof_days")
    )
    kb.row(
        InlineKeyboardButton(text="👫 Пол", callback_data="prof_gender"),
        InlineKeyboardButton(text="🎭 Тренер", callback_data="prof_style")
    )
    # Кнопка возврата к просмотру
    kb.row(InlineKeyboardButton(text="✅ Готово (Закрыть)", callback_data="close_edit_menu"))

    if is_callback:
        await message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

# --- ВОЗВРАТ В ПРОСМОТР ---
@router.callback_query(F.data == "close_edit_menu")
async def close_edit(callback: CallbackQuery, session: AsyncSession):
    user = await UserCRUD.get_user(session, callback.from_user.id)
    text = get_profile_text(user)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✏️ Редактировать данные", callback_data="open_edit_menu"))
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

# --- 3. ЛОГИКА ВВОДА ---
# Помощник: после изменения возвращаем в МЕНЮ РЕДАКТИРОВАНИЯ
async def return_to_edit(message: Message, session: AsyncSession, state: FSMContext):
    await show_edit_menu(message, session, state)

# Числа
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
            await message.answer("✅ Рост сохранен.")
            await return_to_edit(message, session, state)
        else: await message.answer("❌ Введите реальный рост (100-250).")
    except: await message.answer("❌ Введите число.")

@router.callback_query(F.data == "prof_age")
async def ask_age(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎂 Введите новый возраст:")
    await state.set_state(EditForm.age)

@router.message(EditForm.age)
async def save_age(message: Message, state: FSMContext, session: AsyncSession):
    if message.text.isdigit() and 10 <= int(message.text) <= 100:
        await UserCRUD.update_user(session, message.from_user.id, age=int(message.text))
        await message.answer("✅ Возраст сохранен.")
        await return_to_edit(message, session, state)
    else: await message.answer("❌ Введите число (10-100).")

# Кнопки выбора (Цель, Активность...)
@router.callback_query(F.data == "prof_goal")
async def ask_goal(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("🎯 Выберите цель:", reply_markup=get_goal_keyboard())

@router.message(F.text.in_(GOAL_MAP.values()))
async def save_goal(message: Message, session: AsyncSession, state: FSMContext):
    code = next((k for k, v in GOAL_MAP.items() if v == message.text), None)
    if code:
        await UserCRUD.update_user(session, message.from_user.id, goal=code)
        await message.answer("✅ Цель обновлена.", reply_markup=get_main_menu())
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
    await message.answer("✅ Активность обновлена.", reply_markup=get_main_menu())
    await return_to_edit(message, session, state)

@router.callback_query(F.data == "prof_level")
async def ask_level(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("💪 Выберите уровень:", reply_markup=get_workout_level_keyboard())

@router.message(F.text.in_(LEVEL_MAP.values()) | F.text.contains("Начинающий") | F.text.contains("Любитель") | F.text.contains("Продвинутый") | F.text.contains("Новичок"))
async def save_level(message: Message, session: AsyncSession, state: FSMContext):
    code = "beginner"
    if "Любитель" in message.text or "Продолжающий" in message.text: code = "intermediate"
    elif "ПРО" in message.text or "Продвинутый" in message.text: code = "advanced"
    await UserCRUD.update_user(session, message.from_user.id, workout_level=code)
    await message.answer("✅ Уровень обновлен.", reply_markup=get_main_menu())
    await return_to_edit(message, session, state)

@router.callback_query(F.data == "prof_days")
async def ask_days(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("📅 Дней в неделю:", reply_markup=get_workout_days_keyboard())

@router.message(F.text.contains("дн") | F.text.regexp(r'^\d+$'))
async def save_days(message: Message, session: AsyncSession, state: FSMContext):
    try:
        d = int(re.search(r'\d+', message.text).group())
        if 1 <= d <= 7:
            await UserCRUD.update_user(session, message.from_user.id, workout_days=d)
            await message.answer(f"✅ Дней в неделю: {d}", reply_markup=get_main_menu())
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
    await message.answer("✅ Пол обновлен.", reply_markup=get_main_menu())
    await return_to_edit(message, session, state)

# Стиль (Inline, возвращает в show_edit_menu)
def get_style_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔥 Тони", callback_data="set_style_supportive"))
    builder.row(InlineKeyboardButton(text="💀 Сержант", callback_data="set_style_tough"))
    builder.row(InlineKeyboardButton(text="🧐 Доктор", callback_data="set_style_scientific"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="open_edit_menu"))
    return builder.as_markup()

@router.callback_query(F.data == "prof_style")
async def ask_style(callback: CallbackQuery):
    await callback.message.edit_text("🎭 Выберите характер тренера:", reply_markup=get_style_keyboard())

@router.callback_query(F.data.startswith("set_style_"))
async def save_style(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    style = callback.data.replace("set_style_", "")
    await UserCRUD.update_user(session, callback.from_user.id, trainer_style=style)
    # Возвращаемся в меню редактирования
    await show_edit_menu(callback, session, state)