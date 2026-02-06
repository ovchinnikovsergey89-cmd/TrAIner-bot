from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from states.user_states import UserForm
from database.crud import UserCRUD
from keyboards.settings import get_personality_keyboard
from keyboards.main_menu import get_main_menu
from keyboards.builders import (
    get_gender_keyboard,
    get_activity_keyboard,
    get_goal_keyboard,
    get_workout_level_keyboard,
    get_workout_days_keyboard
)

router = Router()

# --- МЕНЮ РЕДАКТИРОВАНИЯ ---
def get_edit_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎂 Возраст", callback_data="edit_age"),
        InlineKeyboardButton(text="📏 Рост", callback_data="edit_height")
    )
    builder.row(
        InlineKeyboardButton(text="⚖️ Вес", callback_data="edit_weight"),
        InlineKeyboardButton(text="👫 Пол", callback_data="edit_gender")
    )
    builder.row(
        InlineKeyboardButton(text="🎯 Цель", callback_data="edit_goal"),
        InlineKeyboardButton(text="🏃 Активность", callback_data="edit_activity")
    )
    builder.row(
        InlineKeyboardButton(text="💪 Уровень", callback_data="edit_level"),
        InlineKeyboardButton(text="📅 Дни трен.", callback_data="edit_days")
    )
    # 🔥 КНОПКА СТИЛЯ ТРЕНЕРА 🔥
    builder.row(InlineKeyboardButton(text="🎭 Стиль Тренера", callback_data="edit_style"))
    
    builder.row(InlineKeyboardButton(text="🔙 Закончить", callback_data="cancel_edit"))
    return builder.as_markup()

# ========== ЗАПУСК ==========
@router.message(Command("edit"))
@router.message(F.text == "⚙️ Профиль")
async def cmd_edit(message: Message):
    await message.answer(
        "📝 <b>Редактирование профиля</b>\nВыберите пункт:",
        reply_markup=get_edit_keyboard(),
        parse_mode="HTML"
    )

# ========== ОБРАБОТКА СТИЛЯ ТРЕНЕРА ==========
@router.callback_query(F.data == "edit_style")
async def cb_edit_style(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎭 <b>Выберите характер тренера:</b>",
        reply_markup=get_personality_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("set_style_"))
async def cb_set_style(callback: CallbackQuery, session: AsyncSession):
    new_style = callback.data.replace("set_style_", "")
    await UserCRUD.update_user(session, callback.from_user.id, trainer_style=new_style)
    
    names = {"supportive": "🔥 Тони", "tough": "💀 Сержант", "scientific": "🧐 Доктор"}
    
    # 🔥 ИСПРАВЛЕНИЕ: Удаляем старое сообщение и шлем новое, 
    # так как get_main_menu() возвращает Reply-клавиатуру (которую нельзя вставить в edit_text)
    await callback.message.delete()
    await callback.message.answer(
        f"✅ Тренер теперь: <b>{names.get(new_style)}</b>",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

# ========== ОСТАЛЬНЫЕ КНОПКИ ==========
@router.callback_query(F.data == "edit_age")
async def cb_edit_age(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎂 Введите возраст:", parse_mode="HTML")
    await state.set_state(UserForm.age)

@router.callback_query(F.data == "edit_weight")
async def cb_edit_weight(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⚖️ Введите вес (кг):", parse_mode="HTML")
    await state.set_state(UserForm.weight)

@router.callback_query(F.data == "edit_height")
async def cb_edit_height(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📏 Введите рост (см):", parse_mode="HTML")
    await state.set_state(UserForm.height)

@router.callback_query(F.data == "edit_gender")
async def cb_edit_gender(callback: CallbackQuery, state: FSMContext):
    # Тут тоже используем answer + delete, так как get_gender_keyboard может быть Reply (проверьте builders.py)
    # Но если get_gender_keyboard - Inline, то можно edit_text. 
    # Для безопасности лучше использовать answer, если там кнопки ответа.
    # Если у вас там Inline кнопки - оставьте edit_text, но если Reply - замените на логику ниже.
    # По умолчанию в проекте это были Reply кнопки, так что меняем:
    await callback.message.delete()
    await callback.message.answer("👫 Выберите пол:", reply_markup=get_gender_keyboard())
    await state.set_state(UserForm.gender)

@router.callback_query(F.data == "edit_activity")
async def cb_edit_activity(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("🏃 Выберите активность:", reply_markup=get_activity_keyboard())
    await state.set_state(UserForm.activity_level)

@router.callback_query(F.data == "edit_goal")
async def cb_edit_goal(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("🎯 Выберите цель:", reply_markup=get_goal_keyboard())
    await state.set_state(UserForm.goal)

@router.callback_query(F.data == "edit_level")
async def cb_edit_level(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("💪 Выберите уровень:", reply_markup=get_workout_level_keyboard())
    await state.set_state(UserForm.workout_level)

@router.callback_query(F.data == "edit_days")
async def cb_edit_days(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("📅 Сколько дней тренироваться?", reply_markup=get_workout_days_keyboard())
    await state.set_state(UserForm.workout_days)

@router.callback_query(F.data == "cancel_edit")
async def cb_cancel_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("✅ Готово.", reply_markup=get_main_menu())

# ========== ЛОГИКА ВВОДА ==========
@router.message(UserForm.age)
async def process_age(message: Message, state: FSMContext, session: AsyncSession):
    if message.text.isdigit() and 10 <= int(message.text) <= 100:
        await UserCRUD.update_user(session, message.from_user.id, age=int(message.text))
        await message.answer(f"✅ Возраст: {message.text}", reply_markup=get_main_menu())
        await state.clear()
    else: await message.answer("❌ Введите число (10-100).")

@router.message(UserForm.weight)
async def process_weight(message: Message, state: FSMContext, session: AsyncSession):
    try:
        val = float(message.text.replace(',', '.'))
        if 30 <= val <= 250:
            await UserCRUD.update_user(session, message.from_user.id, weight=val)
            await message.answer(f"✅ Вес: {val} кг", reply_markup=get_main_menu())
            await state.clear()
        else: raise ValueError
    except: await message.answer("❌ Введите число (30-250).")

@router.message(UserForm.height)
async def process_height(message: Message, state: FSMContext, session: AsyncSession):
    try:
        val = float(message.text.replace(',', '.'))
        if 100 <= val <= 250:
            await UserCRUD.update_user(session, message.from_user.id, height=val)
            await message.answer(f"✅ Рост: {val} см", reply_markup=get_main_menu())
            await state.clear()
        else: raise ValueError
    except: await message.answer("❌ Введите число (100-250).")

# Остальные хендлеры (пол, цель...)
@router.message(UserForm.gender)
async def process_gender(message: Message, state: FSMContext, session: AsyncSession):
    g_map = {"👨 Мужской": "male", "👩 Женский": "female"}
    if message.text in g_map:
        await UserCRUD.update_user(session, message.from_user.id, gender=g_map[message.text])
        await message.answer("✅ Пол сохранен", reply_markup=get_main_menu())
        await state.clear()
    else: await message.answer("Используйте кнопки.")

@router.message(UserForm.activity_level)
async def process_activity(message: Message, state: FSMContext, session: AsyncSession):
    act_map = {"Сидячий": "sedentary", "Легкая": "light", "Средняя": "medium", "Высокая": "high"}
    found = next((v for k, v in act_map.items() if k in message.text), None)
    if found:
        await UserCRUD.update_user(session, message.from_user.id, activity_level=found)
        await message.answer("✅ Активность сохранена", reply_markup=get_main_menu())
        await state.clear()
    else: await message.answer("Используйте кнопки.")

@router.message(UserForm.goal)
async def process_goal(message: Message, state: FSMContext, session: AsyncSession):
    goal_map = {"Похудение": "weight_loss", "Набор": "muscle_gain", "Поддержание": "maintenance"}
    found = next((v for k, v in goal_map.items() if k in message.text), None)
    if found:
        await UserCRUD.update_user(session, message.from_user.id, goal=found)
        await message.answer("✅ Цель сохранена", reply_markup=get_main_menu())
        await state.clear()
    else: await message.answer("Используйте кнопки.")

@router.message(UserForm.workout_level)
async def process_level(message: Message, state: FSMContext, session: AsyncSession):
    l_map = {"Начинающий": "beginner", "Продолжающий": "intermediate", "Продвинутый": "advanced"}
    found = next((v for k, v in l_map.items() if k in message.text), None)
    if found:
        await UserCRUD.update_user(session, message.from_user.id, workout_level=found)
        await message.answer("✅ Уровень сохранен", reply_markup=get_main_menu())
        await state.clear()
    else: await message.answer("Используйте кнопки.")

@router.message(UserForm.workout_days)
async def process_days(message: Message, state: FSMContext, session: AsyncSession):
    try:
        days = int(''.join(filter(str.isdigit, message.text)))
        await UserCRUD.update_user(session, message.from_user.id, workout_days=days)
        await message.answer(f"✅ Дни: {days}", reply_markup=get_main_menu())
        await state.clear()
    except: await message.answer("Используйте кнопки.")