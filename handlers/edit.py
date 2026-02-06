from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from states.user_states import UserForm
from database.crud import UserCRUD
from keyboards import (
    get_gender_keyboard,
    get_activity_keyboard,
    get_goal_keyboard,
    get_workout_level_keyboard,
    get_workout_days_keyboard,
    get_main_menu
)

router = Router()

# --- КЛАВИАТУРА МЕНЮ РЕДАКТИРОВАНИЯ ---
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
    builder.row(InlineKeyboardButton(text="🔙 Закончить редактирование", callback_data="cancel_edit"))
    return builder.as_markup()

# ========== ЗАПУСК РЕДАКТИРОВАНИЯ ==========

@router.message(Command("edit"))
@router.message(F.text == "⚙️ Профиль") # Если вдруг добавишь такую кнопку
async def cmd_edit(message: Message):
    """Показывает меню редактирования"""
    await message.answer(
        "📝 <b>Редактирование профиля</b>\n\n"
        "Выберите, что хотите изменить:",
        reply_markup=get_edit_keyboard(),
        parse_mode="HTML"
    )

# ========== ОБРАБОТКА КНОПОК МЕНЮ ==========

@router.callback_query(F.data == "edit_age")
async def cb_edit_age(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎂 Введите новый <b>возраст</b> (числом):", parse_mode="HTML")
    await state.set_state(UserForm.age)

@router.callback_query(F.data == "edit_weight")
async def cb_edit_weight(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⚖️ Введите новый <b>вес</b> (в кг):", parse_mode="HTML")
    await state.set_state(UserForm.weight)

@router.callback_query(F.data == "edit_height")
async def cb_edit_height(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📏 Введите новый <b>рост</b> (в см):", parse_mode="HTML")
    await state.set_state(UserForm.height)

@router.callback_query(F.data == "edit_gender")
async def cb_edit_gender(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("👫 Выберите пол:", reply_markup=get_gender_keyboard())
    await callback.message.delete() # Удаляем старое меню для красоты
    await state.set_state(UserForm.gender)

@router.callback_query(F.data == "edit_activity")
async def cb_edit_activity(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🏃 Выберите активность:", reply_markup=get_activity_keyboard())
    await callback.message.delete()
    await state.set_state(UserForm.activity_level)

@router.callback_query(F.data == "edit_goal")
async def cb_edit_goal(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🎯 Выберите цель:", reply_markup=get_goal_keyboard())
    await callback.message.delete()
    await state.set_state(UserForm.goal)

@router.callback_query(F.data == "edit_level")
async def cb_edit_level(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💪 Выберите уровень:", reply_markup=get_workout_level_keyboard())
    await callback.message.delete()
    await state.set_state(UserForm.workout_level)

@router.callback_query(F.data == "edit_days")
async def cb_edit_days(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📅 Сколько дней тренироваться?", reply_markup=get_workout_days_keyboard())
    await callback.message.delete()
    await state.set_state(UserForm.workout_days)

@router.callback_query(F.data == "cancel_edit")
async def cb_cancel_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("✅ Редактирование завершено.", reply_markup=get_main_menu())

# ========== ОБРАБОТЧИКИ ВВОДА (ЛОГИКА) ==========
# (Осталась почти такой же, но с возвратом в меню редактирования или главное меню)

@router.message(UserForm.age)
async def process_age(message: Message, state: FSMContext, session: AsyncSession):
    try:
        age = int(message.text)
        if 10 <= age <= 100:
            await UserCRUD.update_user(session, message.from_user.id, age=age)
            await message.answer(f"✅ Возраст: {age}", reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer("❌ От 10 до 100 лет.")
    except ValueError:
        await message.answer("❌ Введите число.")

@router.message(UserForm.weight)
async def process_weight(message: Message, state: FSMContext, session: AsyncSession):
    try:
        val = float(message.text.replace(',', '.'))
        if 30 <= val <= 250:
            await UserCRUD.update_user(session, message.from_user.id, weight=val)
            await message.answer(f"✅ Вес: {val} кг", reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer("❌ От 30 до 250 кг.")
    except ValueError:
        await message.answer("❌ Введите число.")

@router.message(UserForm.height)
async def process_height(message: Message, state: FSMContext, session: AsyncSession):
    try:
        val = float(message.text.replace(',', '.'))
        if 100 <= val <= 250:
            await UserCRUD.update_user(session, message.from_user.id, height=val)
            await message.answer(f"✅ Рост: {val} см", reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer("❌ От 100 до 250 см.")
    except ValueError:
        await message.answer("❌ Введите число.")

# --- Обработчики кнопок (Пол, Цель и т.д.) ---
# Они остаются похожими, но я сократил код для удобства

@router.message(UserForm.gender)
async def process_gender(message: Message, state: FSMContext, session: AsyncSession):
    g_map = {"👨 Мужской": "male", "👩 Женский": "female"}
    if message.text in g_map:
        await UserCRUD.update_user(session, message.from_user.id, gender=g_map[message.text])
        await message.answer("✅ Пол обновлен", reply_markup=get_main_menu())
        await state.clear()
    else:
        await message.answer("Выберите кнопку.")

@router.message(UserForm.activity_level)
async def process_activity(message: Message, state: FSMContext, session: AsyncSession):
    # Упрощенная проверка на вхождение части текста
    act_map = {"Сидячий": "sedentary", "Легкая": "light", "Средняя": "medium", "Высокая": "high"}
    found = next((v for k, v in act_map.items() if k in message.text), None)
    if found:
        await UserCRUD.update_user(session, message.from_user.id, activity_level=found)
        await message.answer("✅ Активность обновлена", reply_markup=get_main_menu())
        await state.clear()
    else:
        await message.answer("Выберите кнопку.")

@router.message(UserForm.goal)
async def process_goal(message: Message, state: FSMContext, session: AsyncSession):
    goal_map = {"Похудение": "weight_loss", "Набор": "muscle_gain", "Поддержание": "maintenance"}
    found = next((v for k, v in goal_map.items() if k in message.text), None)
    if found:
        await UserCRUD.update_user(session, message.from_user.id, goal=found)
        await message.answer("✅ Цель обновлена", reply_markup=get_main_menu())
        await state.clear()
    else:
        await message.answer("Выберите кнопку.")

@router.message(UserForm.workout_level)
async def process_level(message: Message, state: FSMContext, session: AsyncSession):
    l_map = {"Начинающий": "beginner", "Продолжающий": "intermediate", "Продвинутый": "advanced"}
    found = next((v for k, v in l_map.items() if k in message.text), None)
    if found:
        await UserCRUD.update_user(session, message.from_user.id, workout_level=found)
        await message.answer("✅ Уровень обновлен", reply_markup=get_main_menu())
        await state.clear()
    else:
        await message.answer("Выберите кнопку.")

@router.message(UserForm.workout_days)
async def process_days(message: Message, state: FSMContext, session: AsyncSession):
    # Извлекаем число из строки "3 дня" -> 3
    try:
        days = int(''.join(filter(str.isdigit, message.text)))
        await UserCRUD.update_user(session, message.from_user.id, workout_days=days)
        await message.answer(f"✅ Дни: {days}", reply_markup=get_main_menu())
        await state.clear()
    except:
        await message.answer("Выберите кнопку.")