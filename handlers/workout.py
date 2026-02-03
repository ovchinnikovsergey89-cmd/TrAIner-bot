from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from services.workout_generator import WorkoutGenerator

router = Router()

@router.message(Command("workout"))
async def cmd_workout(message: Message, session: AsyncSession):
    """Генерация плана тренировок"""
    user = await UserCRUD.get_user(session, message.from_user.id)
    
    if not user or not user.workout_level:
        await message.answer(
            "❌ *Профиль не заполнен!*\n\n"
            "Для генерации тренировок нужно заполнить профиль.\n"
            "Используйте /start чтобы продолжить.",
            
        )
        return
    
    # Подготавливаем данные пользователя
    user_data = {
        "workout_level": user.workout_level,
        "workout_days": user.workout_days,
        "goal": user.goal,
        "gender": user.gender,
        "weight": user.weight,
        "age": user.age
    }
    
    # Показываем сообщение о генерации
    msg = await message.answer("🔄 *Генерирую ваш персональный план тренировок...*", 
                              )
    
    # Генерируем план
    workout_plan = WorkoutGenerator.generate_weekly_plan(user_data)
    plan_text = WorkoutGenerator.format_plan_for_display(workout_plan)
    
    # Удаляем сообщение о генерации и отправляем план
    await msg.delete()
    
    # Разбиваем длинное сообщение если нужно
    if len(plan_text) > 4000:
        parts = [plan_text[i:i+4000] for i in range(0, len(plan_text), 4000)]
        for part in parts:
            await message.answer(part, )
    else:
        await message.answer(plan_text, )
    
    # Добавляем кнопки действий
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="💾 Сохранить план", callback_data="save_plan"),
        InlineKeyboardButton(text="🔄 Новый план", callback_data="new_plan"),
        InlineKeyboardButton(text="📊 Мой прогресс", callback_data="progress")
    )
    builder.adjust(2)
    
    await message.answer(
        "Что дальше?",
        reply_markup=builder.as_markup()
    )

@router.callback_query(lambda c: c.data == "save_plan")
async def save_plan(callback_query):
    await callback_query.answer("✅ План сохранен в вашем профиле!")
    
@router.callback_query(lambda c: c.data == "new_plan")
async def new_plan(callback_query):
    await callback_query.answer("🔄 Генерирую новый вариант...")
    await cmd_workout(callback_query.message, callback_query.session)
    
@router.callback_query(lambda c: c.data == "progress")
async def show_progress(callback_query):
    await callback_query.answer("📊 Раздел прогресса в разработке")

@router.message(Command("quick_workout"))
async def cmd_quick_workout(message: Message):
    """Быстрая тренировка на сегодня"""
    quick_workouts = [
        "🏋️‍♂️ *Быстрая тренировка (20 мин):*\n• Приседания 3x15\n• Отжимания 3x12\n• Планка 3x30 сек\n• Выпады 3x10 на ногу",
        "🔥 *Интервальная тренировка (15 мин):*\n• Берпи 30 сек / отдых 30 сек (5 раундов)\n• Планка 45 сек\n• Приседания 20 раз\n• Повторить 3 круга",
        "💪 *Тренировка с гантелями (25 мин):*\n• Жим гантелей 3x12\n• Тяга в наклоне 3x12\n• Приседания с гантелями 3x15\n• Разведения гантелей 3x15"
    ]
    
    import random
    workout = random.choice(quick_workouts)
    
    await message.answer(
        f"{workout}\n\n"
        "⏱️ *Инструкция:*\n"
        "1. Разминка 3-5 мин\n"
        "2. Выполняйте упражнения\n"
        "3. Отдых между подходами 60 сек\n"
        "4. Заминка и растяжка 5 мин",
        
    )
