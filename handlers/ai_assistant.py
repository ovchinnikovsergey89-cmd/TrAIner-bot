# handlers/ai_assistant.py
"""
Новый универсальный AI handler
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from keyboards.main_menu import get_main_keyboard

router = Router()

@router.message(Command("ai_workout"))
async def ai_workout_command(message: Message, state: FSMContext):
    """Генерация тренировки через AI"""
    from ai import get_ai_client
    from database.crud import UserCRUD
    from database.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        user = await UserCRUD.get_user(session, message.from_user.id)
    
    if not user:
        await message.answer("❌ Сначала заполните профиль (/profile)")
        return
    
    user_data = {
        'gender': user.gender,
        'weight': user.weight,
        'height': user.height,
        'age': user.age,
        'goal': user.goal,
        'workout_level': user.workout_level,
        'workout_days': user.workout_days,
        'activity_level': user.activity_level
    }
    
    await message.answer("🤖 ИИ генерирует персонализированную тренировку...")
    
    try:
        ai_client = get_ai_client()
        workout = await ai_client.generate_personalized_workout(user_data)
        await message.answer(workout)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("ai_nutrition"))
async def ai_nutrition_command(message: Message, state: FSMContext):
    """Генерация питания через AI"""
    from ai import get_ai_client
    from database.crud import UserCRUD
    from database.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        user = await UserCRUD.get_user(session, message.from_user.id)
    
    if not user:
        await message.answer("❌ Сначала заполните профиль (/profile)")
        return
    
    user_data = {
        'gender': user.gender,
        'weight': user.weight,
        'height': user.height,
        'age': user.age,
        'goal': user.goal,
        'activity_level': user.activity_level
    }
    
    await message.answer("🍎 ИИ анализирует ваше питание...")
    
    try:
        ai_client = get_ai_client()
        nutrition = await ai_client.generate_personalized_nutrition(user_data)
        await message.answer(nutrition)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(F.text == "🤖 AI Тренировка")
async def ai_workout_button(message: Message, state: FSMContext):
    """Обработка кнопки AI тренировки"""
    await ai_workout_command(message, state)

@router.message(F.text == "🍎 AI Питание")
async def ai_nutrition_button(message: Message, state: FSMContext):
    """Обработка кнопки AI питания"""
    await ai_nutrition_command(message, state)