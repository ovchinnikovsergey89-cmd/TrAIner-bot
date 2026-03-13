import logging
import re
from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func  # Вот этой строки тебе не хватает

from datetime import datetime
from services.calculators import NutritionCalculator
from database.crud import UserCRUD
from database.models import WeightHistory, User, NutritionLog, WorkoutLog
from states.user_states import Registration
from keyboards.builders import (
    get_gender_keyboard, 
    get_activity_keyboard, 
    get_goal_keyboard,
    get_workout_level_keyboard,
    get_workout_days_keyboard,
    get_main_menu
)
from keyboards.main_menu import get_main_menu

router = Router()
logger = logging.getLogger(__name__)

# --- СТАРТ ---
@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, message.from_user.id)

    # Если пользователя нет или он еще не принял соглашение
    if not user or not getattr(user, 'is_agreed', False):
        # Текст дисклеймера
        disclaimer_text = (
            "<b>TrAIner | Твой персональный ИИ-наставник</b> 🤖\n\n"
            "Привет! Я — прогрессивная нейросеть, обученная передовым методикам фитнеса и нутрициологии. "
            "В отличие от обычных ботов, я не просто выдаю шаблоны, а создаю <b>уникальную стратегию</b>, "
            "подстроенную под твой метаболизм, график и цели.\n\n"
            "<b>Что я умею:</b>\n"
            "📊 <b>Умный расчет:</b> Калории и КБЖУ с точностью до грамма.\n"
            "🏋️ <b>Адаптивные тренировки:</b> Планы, которые меняются вместе с твоим прогрессом.\n"
            "🧠 <b>ИИ-консультант:</b> Отвечу на любой вопрос по тренингу и биохимии питания.\n"
            "📈 <b>Аналитика:</b> Наглядные графики твоего пути к результату.\n\n"
            "<i>Чтобы открыть все функции и начать трансформацию:</i>"
        )
        
        # Ссылка на соглашение (можешь заменить на свою ссылку на Telegra.ph)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📄 Читать соглашение", url="https://drive.google.com/file/d/10zYEuPR925w3XzBIZa_STTlKw1QcTA5V/view?usp=sharing")],
            [InlineKeyboardButton(text="✅ Принимаю и продолжаю", callback_data="accept_terms")]
        ])
        
        # Если есть реферал, сохраним его в стейт временно, чтобы не потерять после нажатия кнопки
        if command.args:
            await state.update_data(referrer_id=command.args)
            
        await message.answer(disclaimer_text, reply_markup=kb, parse_mode="HTML")
        return

    # Если уже зарегистрирован и согласие есть — в главное меню
    await message.answer(
        f"👋 С возвращением, <b>{user.name}</b>!\nГотов к тренировке?", 
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

# --- 2. ХЕНДЛЕР НАЖАТИЯ КНОПКИ "СОГЛАСЕН" ---
@router.callback_query(F.data == "accept_terms")
async def process_accept_terms(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    user = await UserCRUD.get_user(session, callback.from_user.id)
    
    if user:
        # Старый юзер: просто фиксируем согласие
        user.is_agreed = True
        user.agreed_at = datetime.now()
        await session.commit()
        await callback.message.edit_text("✅ Согласие подтверждено! Рад видеть тебя снова.")
        await callback.message.answer("Выберите действие:", reply_markup=get_main_menu())
    else:
        # Новый юзер: начинаем регистрацию
        await callback.message.edit_text("✅ Согласие получено! Начнем настройку твоего профиля.")
        
        # ВНИМАНИЕ: Проверь название стейта в states/user_states.py!
        # Если там написано "age = State()", то нужно Registration.age
        # Если "waiting_age = State()", то Registration.waiting_age
        
        try:
            # Пробуем самые вероятные варианты названий стейтов
            if hasattr(Registration, 'age'):
                await state.set_state(Registration.age)
            elif hasattr(Registration, 'waiting_age'):
                await state.set_state(Registration.waiting_age)
            else:
                # Если не нашли, выводим ошибку в консоль, чтобы ты увидел название
                logger.error(f"Стейты в Registration: {Registration.__dict__.keys()}")
                await callback.message.answer("⚠️ Ошибка конфигурации состояний. Обратитесь к админу.")
                return

            await callback.message.answer("Введите ваш возраст (полных лет):")
        except Exception as e:
            logger.error(f"Ошибка при установке стейта: {e}")
            await callback.message.answer("❌ Произошла ошибка при начале регистрации.")
    
    await callback.answer()
    
    if user:
        await message.answer(
            f"👋 С возвращением, <b>{user.name}</b>!\nГотов к тренировке?", 
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    else:
        # --- ЛОВИМ РЕФЕРАЛЬНУЮ ССЫЛКУ ---
        if command.args and command.args.isdigit():
            await state.update_data(referrer_id=int(command.args))
            
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
    
    await message.answer("Сколько тебе лет?")
    await state.set_state(Registration.age)

# 2. ВОЗРАСТ -> ВЕС
@router.message(Registration.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text.strip())
        if not (10 <= age <= 90):
            await message.answer("🤔 Укажи, пожалуйста, реальный возраст (от 10 до 90 лет):")
            return
            
        await state.update_data(age=age)
        await message.answer("⚖️ Принято! Теперь введи свой вес (кг).")
        await state.set_state(Registration.weight)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введи возраст числом (например: 25):")

# 3. ВЕС -> РОСТ
@router.message(Registration.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        clean_input = message.text.strip().replace(',', '.')
        w = float(clean_input)
        if not (30 <= w <= 250):
            await message.answer("🤔 Хмм, кажется вес указан неверно. Введи реальный вес (от 30 до 250 кг):")
            return

        await state.update_data(weight=w)
        await message.answer("📏 Отлично! Теперь введи свой рост в см (например: 180):")
        await state.set_state(Registration.height)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введи только число (например: 75.5 или 80).")

# 4. РОСТ -> ЦЕЛЬ
@router.message(Registration.height)
async def process_height(message: Message, state: FSMContext):
    try:
        clean_input = message.text.strip().replace(',', '.')
        h = float(clean_input)
        if not (100 <= h <= 250):
            await message.answer("🤔 Кажется, в росте ошибка. Введи рост в сантиметрах (от 100 до 250):")
            return
            
        await state.update_data(height=h)
        await message.answer("🎯 Почти готово! Какая у тебя цель?", reply_markup=get_goal_keyboard())
        await state.set_state(Registration.goal)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введи рост числом (например: 175):")

# 5. ЦЕЛЬ -> УРОВЕНЬ
@router.message(Registration.goal)
async def process_goal(message: Message, state: FSMContext):
    goals = {
        "📉 Похудение": "weight_loss", 
        "⚖️ Поддержание": "maintenance", 
        "💪 Набор массы": "muscle_gain",
        "🔄 Рекомпозиция": "recomposition"
    }
    selected = goals.get(message.text, "maintenance")
    await state.update_data(goal=selected, goal_text=message.text)
    
    await message.answer("Уровень подготовки?", reply_markup=get_workout_level_keyboard())
    await state.set_state(Registration.workout_level)

# 6. УРОВЕНЬ -> АКТИВНОСТЬ
@router.message(Registration.workout_level)
async def process_level(message: Message, state: FSMContext):
    levels = {"🐣 Новичок": "beginner", "🏃 Любитель": "intermediate", "🏋️‍♂️ Продвинутый": "advanced"}
    selected = levels.get(message.text, "beginner")
    await state.update_data(workout_level=selected)
    
    await message.answer("Уровень активности?", reply_markup=get_activity_keyboard())
    await state.set_state(Registration.activity_level)

# 7. АКТИВНОСТЬ -> ДНИ
@router.message(Registration.activity_level)
async def process_activity(message: Message, state: FSMContext):
    val = "moderate"
    if "Сидячая" in message.text: val = "sedentary"
    elif "Малая" in message.text: val = "light"
    elif "Высокая" in message.text: val = "high"
    elif "Экстремальная" in message.text: val = "extreme"
    
    await state.update_data(activity_level=val)
    await message.answer("Сколько дней в неделю готов тренироваться?", reply_markup=get_workout_days_keyboard())
    await state.set_state(Registration.workout_days)

# 8. ДНИ -> ФИНАЛ
@router.message(Registration.workout_days)
async def process_days(message: Message, state: FSMContext, session: AsyncSession):
    try:
        days = int(re.search(r'\d+', message.text).group())
        if days > 7:  # НОВОЕ: Защита от больших чисел или ID
            days = 3
    except:
        days = 3
    
    data = await state.get_data()
    
    # ЗАЩИТА ОТ ОШИБОК: Используем .get() для предотвращения KeyError
    gender = data.get('gender', 'male')
    age = data.get('age', 25)
    weight = data.get('weight', 70.0)
    height = data.get('height', 170.0)
    goal = data.get('goal', 'maintenance')
    workout_level = data.get('workout_level', 'beginner')
    activity_level = data.get('activity_level', 'moderate')
    referrer_id = data.get('referrer_id')
    
    # Создаем пользователя
    await UserCRUD.add_user(
        session,
        telegram_id=message.from_user.id,
        referrer_id=referrer_id,  # Учитываем реферала!
        name=message.from_user.first_name,
        age=age,
        weight=weight,
        height=height,
        gender=gender,
        goal=goal,
        workout_level=workout_level,
        activity_level=activity_level,
        workout_days=days
    )
    
    # Добавляем историю веса
    session.add(WeightHistory(user_id=message.from_user.id, weight=weight))
    await session.commit()

    # ==========================================
    # 🔥 НОВОЕ: Фиксируем согласие для новичка!
    # ==========================================
    new_user = await UserCRUD.get_user(session, message.from_user.id)
    if new_user:
        new_user.is_agreed = True
        new_user.agreed_at = datetime.now()
        await session.commit()
    
    # 🔥 НАЧИСЛЯЕМ БОНУС ЗА РЕГИСТРАЦИЮ (5 генераций, 10 вопросов) 🔥
    await UserCRUD.apply_registration_bonus(session, message.from_user.id)
    
    goals_map_rev = {
        "weight_loss": "📉 Похудение", 
        "maintenance": "⚖️ Поддержание", 
        "muscle_gain": "💪 Набор массы",
        "recomposition": "🔄 Рекомпозиция"
    }
    goal_label = data.get('goal_text', goals_map_rev.get(goal, "Форма"))

    await state.clear()
    
    await message.answer(
        f"✅ <b>Профиль успешно создан!</b>\n\n"
        f"👤 <b>Имя:</b> {message.from_user.first_name}\n"
        f"📊 <b>Вес:</b> {weight} кг\n"
        f"🎯 <b>Цель:</b> {goal_label}\n"
        f"📅 <b>Режим:</b> {days} дн/нед\n\n"
        "Теперь я могу составлять для тебя программы тренировок и питания! Жми кнопки в меню 👇",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

# Обработчик команды /journal
@router.message(Command("journal"))
async def cmd_journal(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    user_id = message.from_user.id
    
    # Получаем профиль пользователя
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return await message.answer("Сначала пройдите регистрацию /start")

    # 1. Считаем ФАКТ (Питание из логов за сегодня)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    stats_query = select(
        func.sum(NutritionLog.calories).label("total_cal"),
        func.sum(NutritionLog.protein).label("total_prot"),
        func.sum(NutritionLog.fat).label("total_fat"),
        func.sum(NutritionLog.carbs).label("total_carb")
    ).where(NutritionLog.user_id == user_id, NutritionLog.date >= today_start)
    
    stats_result = await session.execute(stats_query)
    stats = stats_result.fetchone()
    
    cur_cal = stats.total_cal if stats and stats.total_cal else 0
    cur_prot = stats.total_prot if stats and stats.total_prot else 0
    cur_fat = stats.total_fat if stats and stats.total_fat else 0
    cur_carb = stats.total_carb if stats and stats.total_carb else 0

    # 2. Берем ЦЕЛИ ИЗ БАЗЫ (если план еще не составлен, ставим 0)
    goal_cal = user.target_calories or 0
    goal_prot = user.target_protein or 0
    goal_fat = user.target_fat or 0
    goal_carb = user.target_carbs or 0

    # 3. Проверяем наличие тренировки сегодня
    workout_today_query = select(WorkoutLog).where(
        WorkoutLog.user_id == user_id, 
        WorkoutLog.date >= today_start
    )
    workout_today_result = await session.execute(workout_today_query)
    has_workout_today = workout_today_result.scalars().first() is not None

    # 4. Прогресс тренировок ИЗ БАЗЫ
    done_workouts = user.completed_workouts or 0
    plan_days = user.workout_days or 0 
    
    workout_status = "✅ Выполнена" if has_workout_today else "❌ Еще не было"

    report_text = (
        "📊 <b>Ваш отчет за сегодня:</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <b>Калории:</b> {cur_cal:.0f} / {goal_cal:.0f} ккал\n"
        f"🥩 <b>Белки:</b> {cur_prot:.1f} / {goal_prot:.1f}г\n"
        f"🥑 <b>Жиры:</b> {cur_fat:.1f} / {goal_fat:.1f}г\n"
        f"🍝 <b>Углеводы:</b> {cur_carb:.1f} / {goal_carb:.1f}г\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🏋️ <b>Тренировки:</b> {done_workouts} из {plan_days} за неделю\n"
        f"📅 <b>Сегодня:</b> {workout_status}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"⚖️ <b>Ваш вес:</b> {user.weight if user.weight else '—'} кг\n\n"
        "<i>Данные формируются из вашего текущего плана и записей за сегодня.</i>"
    )
    
    await message.answer(report_text, reply_markup=get_main_menu())  

@router.message(Command("fast"))
async def cmd_fast(message: Message, state: FSMContext):
    await state.clear()
    
    # Кнопки в один ряд
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏋️ Рабочие веса", callback_data="log_weight_press"),
            InlineKeyboardButton(text="🍎 Прием пищи", callback_data="log_nutrition_press")
        ]
    ])
    
    await message.answer(
        "⚡ <b>Быстрая запись</b>\n"
        "Выберите, что нужно зафиксировать:", 
        reply_markup=kb
    )
