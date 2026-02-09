import html
import re
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from states.user_states import UserForm
from database.models import User

# Импортируем клавиатуры, ВКЛЮЧАЯ НОВУЮ
from keyboards.builders import (
    get_gender_keyboard,
    get_activity_keyboard,
    get_goal_keyboard,
    get_workout_level_keyboard,
    get_workout_days_keyboard,
    get_trainer_style_keyboard # <--- Важно добавить импорт
)
from keyboards.main_menu import get_main_menu

router = Router()

# --- 1. ЛОГИКА /start ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    telegram_id = message.from_user.id
    
    result = await session.execute(select(User).filter_by(telegram_id=telegram_id))
    user = result.scalar_one_or_none()
    
    if user:
        db_name = user.name if user.name else message.from_user.first_name
        safe_name = html.escape(db_name)
        
        await message.answer(
            f"👋 С возвращением, <b>{safe_name}</b>!\n"
            f"Готов продолжить тренировки? 👇",
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.HTML
        )
    else:
        await start_registration(message, state)

# --- 2. ЛОГИКА РЕГИСТРАЦИИ ---

async def start_registration(message: Message, state: FSMContext):
    await message.answer(
        "🏋️‍♂️ <b>Добро пожаловать в TrAIner!</b>\n\n"
        "Я - ваш персональный AI-тренер. Сначала создадим ваш профиль.\n\n"
        "Выберите ваш пол:",
        reply_markup=get_gender_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(UserForm.gender)

@router.message(UserForm.gender)
async def process_gender(message: Message, state: FSMContext):
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
        if not (30 <= weight <= 250): raise ValueError
        await state.update_data(weight=weight)
        await message.answer("Ваш рост (в см)?")
        await state.set_state(UserForm.height)
    except ValueError:
        await message.answer("Пожалуйста, введите корректный вес (например: 75.5).")

@router.message(UserForm.height)
async def process_height(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(',', '.'))
        if not (100 <= val <= 250):
            await message.answer("Введите реальный рост (в см).")
            return
        await state.update_data(height=val)
        await message.answer("Какой у вас уровень активности?", reply_markup=get_activity_keyboard())
        await state.set_state(UserForm.activity_level)
    except ValueError:
        await message.answer("Введите рост числом.")

@router.message(UserForm.activity_level)
async def process_activity(message: Message, state: FSMContext):
    activity_map = {
        "Сидячий (без спорта)": "sedentary", 
        "Малая (1-3 тренировки)": "light",
        "Средняя (3-5 тренировок)": "moderate", 
        "Высокая (6-7 тренировок)": "high",
        "Экстремальная (физ. труд)": "extreme"
    }
    selected_code = None
    for key, value in activity_map.items():
        if key in message.text:
            selected_code = value
            break
    if not selected_code:
        await message.answer("Выберите вариант из меню.")
        return
    await state.update_data(activity_level=selected_code)
    await message.answer("Ваша главная цель?", reply_markup=get_goal_keyboard())
    await state.set_state(UserForm.goal)

@router.message(UserForm.goal)
async def process_goal(message: Message, state: FSMContext):
    goal_map = {
        "📉 Похудение": "weight_loss", 
        "⚖️ Поддержание": "maintenance", 
        "💪 Набор массы": "muscle_gain"
    }
    goal_code = goal_map.get(message.text)
    if not goal_code: 
        await message.answer("Пожалуйста, выберите цель кнопкой.")
        return
    await state.update_data(goal=goal_code)
    await message.answer("Ваш опыт тренировок?", reply_markup=get_workout_level_keyboard())
    await state.set_state(UserForm.workout_level)

@router.message(UserForm.workout_level)
async def process_workout_level(message: Message, state: FSMContext):
    level_code = "beginner"
    if "Любитель" in message.text: level_code = "intermediate"
    elif "Продвинутый" in message.text: level_code = "advanced"
    elif "Новичок" in message.text: level_code = "beginner"
    else: 
        await message.answer("Выберите уровень кнопкой.")
        return
    await state.update_data(workout_level=level_code)
    await message.answer("Сколько дней в неделю готовы тренироваться?", reply_markup=get_workout_days_keyboard())
    await state.set_state(UserForm.workout_days)

# --- ИЗМЕНЕНИЯ НАЧИНАЮТСЯ ЗДЕСЬ ---

@router.message(UserForm.workout_days)
async def process_workout_days(message: Message, state: FSMContext):
    text = message.text
    days = 3
    if text.isdigit():
        days = int(text)
    else:
        match = re.search(r'\d+', text)
        if match: 
            days = int(match.group())
    if days < 1: days = 1
    if days > 7: days = 7
    
    await state.update_data(workout_days=days)
    
    # 🔥 ВМЕСТО СОХРАНЕНИЯ СПРАШИВАЕМ ТРЕНЕРА
    await message.answer(
        "🎭 <b>Последний шаг: Выберите тренера!</b>\n\n"
        "🔥 <b>Тони:</b> Друг, мотиватор, позитив.\n"
        "💀 <b>Батя:</b> Жесткий, суровый, старая школа.\n"
        "🧐 <b>Доктор:</b> Научный подход, факты, биохакинг.",
        reply_markup=get_trainer_style_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(UserForm.trainer_style)

@router.message(UserForm.trainer_style)
async def process_trainer_style(message: Message, state: FSMContext, session: AsyncSession):
    # Определяем стиль
    style = "supportive" # По умолчанию Тони
    if "Батя" in message.text: style = "tough"
    elif "Доктор" in message.text: style = "scientific"
    
    # 🔥 ТЕПЕРЬ СОХРАНЯЕМ ВСЁ В БД
    data = await state.get_data()
    telegram_id = message.from_user.id
    first_name = message.from_user.first_name
    
    result = await session.execute(select(User).filter_by(telegram_id=telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(telegram_id=telegram_id)
        session.add(user)
    
    user.name = first_name
    user.gender = data.get('gender')
    user.age = data.get('age')
    user.weight = data.get('weight')
    user.height = data.get('height')
    user.activity_level = data.get('activity_level')
    user.goal = data.get('goal')
    user.workout_level = data.get('workout_level')
    user.workout_days = data.get('workout_days')
    user.trainer_style = style # <--- Сохраняем стиль
    
    await session.commit()
    await state.clear()
    
    safe_name = html.escape(first_name)
    
    # Персонализированное приветствие
    welcome_text = "Добро пожаловать в команду!"
    if style == "tough": welcome_text = "Ну наконец-то. Хватит болтать, за работу! 👊"
    elif style == "scientific": welcome_text = "Данные приняты. Система настроена. Приступаем. 🧬"
    elif style == "supportive": welcome_text = "Супер! Я так рад, что ты здесь! Погнали! 🔥"

    summary = (
        f"✅ <b>Профиль создан!</b>\n\n"
        f"👤 Имя: {safe_name}\n"
        f"📊 Вес: {data.get('weight')} кг\n"
        f"🎭 Тренер: {message.text}\n\n"
        f"<i>{welcome_text}</i>"
    )
    await message.answer(summary, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)