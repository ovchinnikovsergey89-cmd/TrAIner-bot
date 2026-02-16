import logging
import re
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from database.models import WeightHistory
from states.user_states import Registration
from keyboards.builders import (
    get_gender_keyboard, 
    get_activity_keyboard, 
    get_goal_keyboard,
    get_workout_level_keyboard,
    get_workout_days_keyboard,
    get_main_menu
)

router = Router()
logger = logging.getLogger(__name__)

# --- СТАРТ ---
@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)
    
    if user:
        await message.answer(
            f"👋 С возвращением, <b>{user.name}</b>!\nГотов к тренировке?", 
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    else:
        # Автоматическое имя
        first_name = message.from_user.first_name
        await message.answer(
            f"👋 <b>Привет, {first_name}! Я TrAIner.</b>\n\n"
            "Я помогу тебе составить программу тренировок и питания.\n"
            "Давай настроим профиль. <b>Твой пол?</b>",
            reply_markup=get_gender_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(Registration.gender)

# 1. ПОЛ -> ВОЗРАСТ
@router.message(Registration.gender)
async def process_gender(message: Message, state: FSMContext):
    gender = "male" if "Мужской" in message.text else "female"
    await state.update_data(gender=gender)
    
    await message.answer("Сколько тебе лет?", reply_markup=None)
    await state.set_state(Registration.age)

# 2. ВОЗРАСТ -> ВЕС
@router.message(Registration.age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи число.")
        return
    
    await state.update_data(age=int(message.text))
    await message.answer("Введи свой вес (кг):")
    await state.set_state(Registration.weight)

# 3. ВЕС -> РОСТ
@router.message(Registration.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        w = float(message.text.replace(',', '.'))
        await state.update_data(weight=w)
        await message.answer("Введи свой рост (см):")
        await state.set_state(Registration.height)
    except ValueError:
        await message.answer("Введи число (например 75.5)")

# 4. РОСТ -> ЦЕЛЬ
@router.message(Registration.height)
async def process_height(message: Message, state: FSMContext):
    try:
        h = float(message.text.replace(',', '.'))
        await state.update_data(height=h)
        
        await message.answer("Твоя цель?", reply_markup=get_goal_keyboard())
        await state.set_state(Registration.goal)
    except ValueError:
        await message.answer("Введи число.")

# 5. ЦЕЛЬ -> УРОВЕНЬ
@router.message(Registration.goal)
async def process_goal(message: Message, state: FSMContext):
    goals = {"📉 Похудение": "weight_loss", "⚖️ Поддержание": "maintenance", "💪 Набор массы": "muscle_gain"}
    selected = goals.get(message.text, "maintenance")
    
    # Сохраняем и код для базы, и текст для красивого вывода
    await state.update_data(goal=selected, goal_text=message.text)
    
    await message.answer("Уровень подготовки?", reply_markup=get_workout_level_keyboard())
    await state.set_state(Registration.workout_level)

# 6. УРОВЕНЬ -> АКТИВНОСТЬ
@router.message(Registration.workout_level)
async def process_level(message: Message, state: FSMContext):
    levels = {"👶 Новичок": "beginner", "👨‍🎓 Любитель": "intermediate", "🏆 ПРО": "advanced"}
    selected = levels.get(message.text, "beginner")
    await state.update_data(workout_level=selected)
    
    await message.answer("Уровень активности?", reply_markup=get_activity_keyboard())
    await state.set_state(Registration.activity_level)

# 7. АКТИВНОСТЬ -> ДНИ
@router.message(Registration.activity_level)
async def process_activity(message: Message, state: FSMContext):
    acts = {
        "🪑 Сидячий": "sedentary", "🚶 Малая": "light", 
        "🏃 Средняя": "moderate", "🏋️ Высокая": "high", "🔥 Экстремальная": "extreme"
    }
    selected = acts.get(message.text, "sedentary")
    await state.update_data(activity_level=selected)
    
    await message.answer("Сколько дней в неделю готов тренироваться?", reply_markup=get_workout_days_keyboard())
    await state.set_state(Registration.workout_days)

# 8. ДНИ -> ФИНАЛ
@router.message(Registration.workout_days)
async def process_days(message: Message, state: FSMContext, session: AsyncSession):
    try:
        days = int(re.search(r'\d+', message.text).group())
    except:
        days = 3
    
    data = await state.get_data()
    
    # Создаем пользователя
    await UserCRUD.add_user(
        session,
        telegram_id=message.from_user.id,
        name=message.from_user.first_name,
        age=data['age'],
        weight=data['weight'],
        height=data['height'],
        gender=data['gender'],
        goal=data['goal'],
        workout_level=data['workout_level'],
        activity_level=data['activity_level'],
        workout_days=days
    )
    
    # Добавляем историю веса
    session.add(WeightHistory(user_id=message.from_user.id, weight=data['weight']))
    await session.commit()
    
    # Получаем красивое название цели (если нет в data, берем дефолт)
    goals_map_rev = {"weight_loss": "📉 Похудение", "maintenance": "⚖️ Поддержание", "muscle_gain": "💪 Набор массы"}
    goal_label = data.get('goal_text', goals_map_rev.get(data['goal'], "Форма"))

    await state.clear()
    
    # 🔥 ВОЗВРАЩАЕМ ИНФОРМАТИВНОЕ СООБЩЕНИЕ
    await message.answer(
        f"✅ <b>Профиль успешно создан!</b>\n\n"
        f"👤 <b>Имя:</b> {message.from_user.first_name}\n"
        f"📊 <b>Вес:</b> {data['weight']} кг\n"
        f"🎯 <b>Цель:</b> {goal_label}\n"
        f"📅 <b>Режим:</b> {days} дн/нед\n\n"
        "Теперь я могу составлять для тебя программы тренировок и питания! Жми кнопки в меню 👇",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )