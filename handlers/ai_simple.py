from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from services.groq_new import GroqAITrainerService

router = Router()

@router.message(Command("ai_workout"))
async def cmd_ai_workout(message: Message, session: AsyncSession):
    """Простая ИИ-тренировка"""
    user = await UserCRUD.get_user(session, message.from_user.id)
    
    if not user:
        await message.answer("❌ Заполните профиль /start")
        return
    
    await message.answer("⚡ ИИ генерирует тренировку...")
    
    user_data = {
        "gender": user.gender,
        "weight": user.weight,
        "goal": user.goal,
        "workout_level": user.workout_level,
        "workout_days": user.workout_days,
        "age": user.age,
        "height": user.height
    }
    
    print(f"🎯 Данные для ИИ: {user_data}")
    
    ai_service = GroqAITrainerService()
    result = await ai_service.generate_personalized_workout(user_data)
    
    await message.answer(result)

@router.message(Command("groq_test"))
async def cmd_groq_test(message: Message):
    """Тест Groq"""
    from services.groq_new import GroqAITrainerService
    
    ai_service = GroqAITrainerService()
    
    if ai_service.use_mock:
        await message.answer("❌ Groq API не работает")
    else:
        await message.answer("✅ Groq API подключен!\nМодель: Llama 3.3 70B")