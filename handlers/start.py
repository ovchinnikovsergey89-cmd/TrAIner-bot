import html
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession

from states.user_states import UserForm
from database.crud import UserCRUD
from keyboards.builders import (
    get_gender_keyboard,
    get_activity_keyboard,
    get_goal_keyboard,
    get_workout_level_keyboard,
    get_workout_days_keyboard,
    get_main_menu
)

router = Router()

# --- 1. ЛОГИКА /start ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """
    Если пользователь новый -> Регистрация.
    Если старый -> Главное меню.
    """
    await state.clear()
    
    # Проверяем, есть ли такой пользователь
    user = await UserCRUD.get_user(session, message.from_user.id)
    
    if user:
        # Если есть — просто показываем меню
        safe_name = html.escape(message.from_user.full_name)
        await message.answer(
            f"👋 С возвращением, <b>{safe_name}</b>!\n"
            f"Используй меню для навигации 👇",
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.HTML
        )
    else:
        # Если нет — запускаем регистрацию
        await start_registration(message, state)

# --- 2. КНОПКА "ИЗМЕНИТЬ ДАННЫЕ" ---
@router.message(F.text == "🔄 Изменить данные")
async def btn_change_data(message: Message, state: FSMContext):
    """Запускает опрос заново принудительно"""
    await message.answer("Хорошо, давайте обновим ваши параметры.", reply_markup=ReplyKeyboardRemove())
    await start_registration(message, state)

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ЗАПУСКА ---
async def start_registration(message: Message, state: FSMContext):
    await message.answer(
        "🏋️‍♂️ <b>Добро пожаловать в TrAIner!</b>\n\n"
        "Я - ваш персональный AI-тренер. Сначала создадим ваш профиль.\n\n"
        "Выберите ваш пол:",
        reply_markup=get_gender_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(UserForm.gender)

# --- ДАЛЕЕ ТОТ ЖЕ КОД ОПРОСА (БЕЗ ИЗМЕНЕНИЙ) ---

@router.message(UserForm.gender)
async def process_gender_start(message: Message, state: FSMContext):
    if message.text not in ["👨 Мужской", "👩 Женский"]:
        await message.answer("Пожалуйста, выберите пол кнопкой ниже.")
        return
    
    gender_code = "male" if "Мужской" in message.text else "female"
    await state.update_data(gender=gender_code)
    
    await message.answer("Отлично! Сколько вам лет?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(UserForm.age)

@router.message(UserForm.age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите возраст числом (например: 25).")
        return
    
    age = int(message.text)
    if not (10 <= age <= 100):
        await message.answer("Введите реальный возраст (от 10 до 100).")
        return
        
    await state.update_data(age=age)
    await message.answer("Ваш вес (в кг)?")
    await state.set_state(UserForm.weight)

@router.message(UserForm.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        text = message.text.replace(',', '.')
        weight = float(text)
        if not (30 <= weight <= 200): raise ValueError
        await state.update_data(weight=weight)
        await message.answer("Ваш рост (в см)?")
        await state.set_state(UserForm.height)
    except ValueError:
        await message.answer("Пожалуйста, введите корректный вес (например: 75.5).")

@router.message(UserForm.height)
async def process_height(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите рост целым числом (например: 180).")
        return
    height = int(message.text)
    if not (100 <= height <= 250):
        await message.answer("Введите реальный рост (в см).")
        return
    await state.update_data(height=height)
    await message.answer("Какой у вас уровень активности?", reply_markup=get_activity_keyboard())
    await state.set_state(UserForm.activity_level)

@router.message(UserForm.activity_level)
async def process_activity(message: Message, state: FSMContext):
    activity_map = {
        "Сидячий (без спорта)": "sedentary", "Малая (1-3 тренировки)": "light",
        "Средняя (3-5 тренировок)": "moderate", "Высокая (6-7 тренировок)": "high",
        "Экстремальная (физ. труд)": "extreme"
    }
    selected_code = None
    for key, value in activity_map.items():
        if key in message.text:
            selected_code = value; break
    if not selected_code:
        if message.text in activity_map.values(): selected_code = message.text
        else: await message.answer("Выберите вариант из меню."); return

    await state.update_data(activity_level=selected_code)
    await message.answer("Ваша главная цель?", reply_markup=get_goal_keyboard())
    await state.set_state(UserForm.goal)

@router.message(UserForm.goal)
async def process_goal(message: Message, state: FSMContext):
    goal_map = {"📉 Похудение": "weight_loss", "⚖️ Поддержание": "maintenance", "💪 Набор массы": "muscle_gain"}
    goal_code = goal_map.get(message.text)
    if not goal_code: await message.answer("Пожалуйста, выберите цель кнопкой."); return
    await state.update_data(goal=goal_code)
    await message.answer("Ваш опыт тренировок?", reply_markup=get_workout_level_keyboard())
    await state.set_state(UserForm.workout_level)

@router.message(UserForm.workout_level)
async def process_workout_level(message: Message, state: FSMContext):
    level_code = "beginner"
    if "Любитель" in message.text: level_code = "intermediate"
    elif "Продвинутый" in message.text: level_code = "advanced"
    elif "Новичок" in message.text: level_code = "beginner"
    else: await message.answer("Выберите уровень кнопкой."); return
    await state.update_data(workout_level=level_code)
    await message.answer("Сколько дней в неделю готовы тренироваться?", reply_markup=get_workout_days_keyboard())
    await state.set_state(UserForm.workout_days)

@router.message(UserForm.workout_days)
async def process_workout_days(message: Message, state: FSMContext, session: AsyncSession):
    text = message.text
    days = 3
    if text.isdigit(): days = int(text)
    else:
        match = re.search(r'\d+', text)
        if match: days = int(match.group())
    if days < 1: days = 1
    if days > 7: days = 7
    
    data = await state.get_data()
    data['workout_days'] = days
    telegram_id = message.from_user.id
    
    # СОХРАНЕНИЕ
    user = await UserCRUD.get_user(session, telegram_id)
    if not user: await UserCRUD.add_user(session, telegram_id)
    await UserCRUD.update_user(session=session, telegram_id=telegram_id, **data)
    
    await state.clear()
    safe_name = html.escape(message.from_user.full_name)
    summary = (
        f"✅ <b>Профиль успешно создан!</b>\n\n"
        f"👤 Имя: {safe_name}\n"
        f"📊 Вес: {data.get('weight')} кг\n"
        f"📅 Тренировок: {days} в неделю\n\n"
        f"Теперь вам доступны все функции бота! 👇"
    )
    await message.answer(summary, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)