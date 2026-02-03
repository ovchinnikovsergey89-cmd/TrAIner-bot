from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
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

# ========== КОМАНДЫ РЕДАКТИРОВАНИЯ ==========

@router.message(Command("edit"))
async def cmd_edit(message: Message):
    """Начало редактирования профиля"""
    await message.answer(
        "📝 *Редактирование профиля*\n\n"
        "Что вы хотите изменить?\n\n"
        "1. Возраст - отправьте 'возраст'\n"
        "2. Пол - отправьте 'пол'\n"
        "3. Вес - отправьте 'вес'\n"
        "4. Рост - отправьте 'рост'\n"
        "5. Активность - отправьте 'активность'\n"
        "6. Цель - отправьте 'цель'\n"
        "7. Уровень тренировок - отправьте 'уровень'\n"
        "8. Дни тренировок - отправьте 'дни'\n\n"
        "Или /cancel для отмены",
        parse_mode="Markdown"
    )

@router.message(F.text.lower() == "возраст")
async def edit_age(message: Message, state: FSMContext):
    await message.answer("Введите новый возраст:")
    await state.set_state(UserForm.age)

@router.message(F.text.lower() == "вес")
async def edit_weight(message: Message, state: FSMContext):
    await message.answer("Введите новый вес (кг):")
    await state.set_state(UserForm.weight)

@router.message(F.text.lower() == "рост")
async def edit_height(message: Message, state: FSMContext):
    await message.answer("Введите новый рост (см):")
    await state.set_state(UserForm.height)

@router.message(F.text.lower() == "пол")
async def edit_gender(message: Message, state: FSMContext):
    await message.answer("Выберите новый пол:", reply_markup=get_gender_keyboard())
    await state.set_state(UserForm.gender)

@router.message(F.text.lower() == "активность")
async def edit_activity(message: Message, state: FSMContext):
    await message.answer("Выберите новый уровень активности:", reply_markup=get_activity_keyboard())
    await state.set_state(UserForm.activity_level)

@router.message(F.text.lower() == "цель")
async def edit_goal(message: Message, state: FSMContext):
    await message.answer("Выберите новую цель:", reply_markup=get_goal_keyboard())
    await state.set_state(UserForm.goal)

@router.message(F.text.lower() == "уровень")
async def edit_workout_level(message: Message, state: FSMContext):
    await message.answer("Выберите новый уровень тренировок:", reply_markup=get_workout_level_keyboard())
    await state.set_state(UserForm.workout_level)

@router.message(F.text.lower() == "дни")
async def edit_workout_days(message: Message, state: FSMContext):
    await message.answer("Сколько дней в неделю готовы тренироваться?", 
                         reply_markup=get_workout_days_keyboard())
    await state.set_state(UserForm.workout_days)

@router.message(Command("cancel"))
async def cancel_edit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Редактирование отменено.")

# ========== ОБРАБОТЧИКИ СОСТОЯНИЙ ==========

@router.message(UserForm.age)
async def process_age(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка возраста"""
    try:
        age = int(message.text)
        if 10 <= age <= 100:
            success = await UserCRUD.update_user(
                session=session,
                telegram_id=message.from_user.id,
                age=age
            )
            if success:
                await message.answer(f"✅ Возраст обновлен: {age} лет", reply_markup=get_main_menu())
                await state.clear()
            else:
                await message.answer("❌ Ошибка обновления")
        else:
            await message.answer("❌ Возраст должен быть от 10 до 100 лет")
    except ValueError:
        await message.answer("❌ Введите число (например: 25)")

@router.message(UserForm.weight)
async def process_weight(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка веса"""
    try:
        weight = float(message.text)
        if 30 <= weight <= 250:
            success = await UserCRUD.update_user(
                session=session,
                telegram_id=message.from_user.id,
                weight=weight
            )
            if success:
                await message.answer(f"✅ Вес обновлен: {weight} кг", reply_markup=get_main_menu())
                await state.clear()
            else:
                await message.answer("❌ Ошибка обновления")
        else:
            await message.answer("❌ Вес должен быть от 30 до 250 кг")
    except ValueError:
        await message.answer("❌ Введите число (например: 75.5)")

@router.message(UserForm.height)
async def process_height(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка роста"""
    try:
        height = float(message.text)
        if 100 <= height <= 250:
            success = await UserCRUD.update_user(
                session=session,
                telegram_id=message.from_user.id,
                height=height
            )
            if success:
                await message.answer(f"✅ Рост обновлен: {height} см", reply_markup=get_main_menu())
                await state.clear()
            else:
                await message.answer("❌ Ошибка обновления")
        else:
            await message.answer("❌ Рост должен быть от 100 до 250 см")
    except ValueError:
        await message.answer("❌ Введите число (например: 180)")

@router.message(UserForm.gender)
async def process_gender(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка выбора пола"""
    if message.text == "👨 Мужской":
        gender = "male"
    elif message.text == "👩 Женский":
        gender = "female"
    else:
        await message.answer("Выберите пол из кнопок:", reply_markup=get_gender_keyboard())
        return
    
    success = await UserCRUD.update_user(
        session=session,
        telegram_id=message.from_user.id,
        gender=gender
    )
    
    if success:
        await message.answer(f"✅ Пол обновлен!", reply_markup=get_main_menu())
        await state.clear()
    else:
        await message.answer("❌ Ошибка обновления")

@router.message(UserForm.activity_level)
async def process_activity(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка уровня активности"""
    activity_map = {
        "🛌 Сидячий образ жизни": "sedentary",
        "🚶 Легкая активность (1-3 тренировки/неделю)": "light",
        "🏃 Средняя активность (3-5 тренировок/неделю)": "medium",
        "🏋️ Высокая активность (6-7 тренировок/неделю)": "high"
    }
    
    if message.text in activity_map:
        activity = activity_map[message.text]
        success = await UserCRUD.update_user(
            session=session,
            telegram_id=message.from_user.id,
            activity_level=activity
        )
        if success:
            await message.answer(f"✅ Активность обновлена", reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer("❌ Ошибка обновления")
    else:
        await message.answer("❌ Выберите вариант из кнопок", reply_markup=get_activity_keyboard())

@router.message(UserForm.goal)
async def process_goal(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка цели"""
    goal_map = {
        "⚖️ Похудение": "weight_loss",
        "💪 Набор массы": "muscle_gain",
        "🏃 Поддержание формы": "maintenance"
    }
    
    if message.text in goal_map:
        goal = goal_map[message.text]
        success = await UserCRUD.update_user(
            session=session,
            telegram_id=message.from_user.id,
            goal=goal
        )
        if success:
            await message.answer(f"✅ Цель обновлена", reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer("❌ Ошибка обновления")
    else:
        await message.answer("❌ Выберите вариант из кнопок", reply_markup=get_goal_keyboard())

@router.message(UserForm.workout_level)
async def process_workout_level(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка уровня тренировок"""
    level_map = {
        "👶 Начинающий": "beginner",
        "👨‍🎓 Продолжающий": "intermediate",
        "🏆 Продвинутый": "advanced"
    }
    
    if message.text in level_map:
        level = level_map[message.text]
        success = await UserCRUD.update_user(
            session=session,
            telegram_id=message.from_user.id,
            workout_level=level
        )
        if success:
            await message.answer(f"✅ Уровень тренировок обновлен", reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer("❌ Ошибка обновления")
    else:
        await message.answer("❌ Выберите вариант из кнопок", reply_markup=get_workout_level_keyboard())

@router.message(UserForm.workout_days)
async def process_workout_days(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка дней тренировок"""
    days_map = {
        "2 дня": 2,
        "3 дня": 3,
        "4 дня": 4,
        "5 дней": 5,
        "6 дней": 6
    }
    
    if message.text in days_map:
        days = days_map[message.text]
        success = await UserCRUD.update_user(
            session=session,
            telegram_id=message.from_user.id,
            workout_days=days
        )
        if success:
            await message.answer(f"✅ Дни тренировок обновлены: {days} дней/неделю", 
                               reply_markup=get_main_menu())
            await state.clear()
        else:
            await message.answer("❌ Ошибка обновления")
    else:
        await message.answer("❌ Выберите вариант из кнопок", reply_markup=get_workout_days_keyboard())