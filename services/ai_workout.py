from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from services.groq_service import GroqAITrainerService  # ИЗМЕНИЛИ ИМПОРТ!
from services.calculators import NutritionCalculator

router = Router()

@router.message(Command("ai_workout"))
async def cmd_ai_workout(message: Message, session: AsyncSession):
    """Генерация ИИ-тренировки через Groq"""
    user = await UserCRUD.get_user(session, message.from_user.id)
    
    if not user or not user.workout_level:
        await message.answer(
            "❌ *Профиль не заполнен!*\n\n"
            "Для ИИ-рекомендаций нужно заполнить профиль.\n"
            "Используйте /start чтобы продолжить.",
            
        )
        return
    
    # Показываем сообщение о генерации
    msg = await message.answer(
        "⚡ *Groq AI генерирует вашу тренировку...*\n"
        "Используется модель Llama 3 70B (очень быстрая!)\n"
        "⏱️ ~5-10 секунд...",
        
    )
    
    # Подготавливаем данные пользователя
    user_data = {
        "workout_level": user.workout_level,
        "workout_days": user.workout_days,
        "goal": user.goal,
        "gender": user.gender,
        "weight": user.weight,
        "age": user.age,
        "height": user.height,
        "activity_level": user.activity_level
    }
    
    # Генерируем ИИ-тренировку через Groq
    ai_service = GroqAITrainerService()
    workout_text = await ai_service.generate_personalized_workout(user_data)
    
    # Удаляем сообщение о генерации
    await msg.delete()
    
    # Отправляем результат
    await message.answer(workout_text, )
    
    # Кнопки для дополнительных действий
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🍎 ИИ-питание", callback_data="ai_nutrition"),
        InlineKeyboardButton(text="📊 ИИ-анализ", callback_data="ai_analysis")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_ai_workout"),
        InlineKeyboardButton(text="💬 Чат с ИИ", callback_data="ai_chat")
    )
    
    await message.answer(
        "🤖 *Другие ИИ-функции:*",
        reply_markup=builder.as_markup(),
        
    )

@router.callback_query(lambda c: c.data == "ai_nutrition")
async def ai_nutrition(callback_query):
    await callback_query.answer("🧠 Генерирую ИИ-рекомендации по питанию...")
    
    from database.database import AsyncSessionLocal
    from services.calculators import NutritionCalculator
    
    async with AsyncSessionLocal() as session:
        user = await UserCRUD.get_user(session, callback_query.from_user.id)
        
        if user and user.daily_calories:
            # Расчет БЖУ
            calculator = NutritionCalculator()
            macros = calculator.calculate_macros(user.daily_calories, user.goal)
            
            # Генерация ИИ-советов через Groq
            ai_service = GroqAITrainerService()
            user_data = {
                "age": user.age,
                "gender": user.gender,
                "weight": user.weight,
                "goal": user.goal,
                "activity_level": user.activity_level
            }
            
            nutrition_text = await ai_service.generate_nutrition_advice(user_data, user.daily_calories, macros)
            
            await callback_query.message.answer(nutrition_text, )
        else:
            await callback_query.message.answer(
                "❌ Сначала заполните профиль и рассчитайте питание (/calculate)",
                
            )

@router.callback_query(lambda c: c.data == "ai_analysis")
async def ai_analysis(callback_query):
    await callback_query.answer("📊 Анализирую ваш прогресс...")
    
    # Пример данных прогресса (позже можно хранить в БД)
    progress_data = {
        "start_weight": 75,
        "current_weight": 72,
        "weeks": 4,
        "weight_change": -3,
        "mood": "хорошее"
    }
    
    from database.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        user = await UserCRUD.get_user(session, callback_query.from_user.id)
        
        if user:
            user_data = {
                "goal": user.goal,
                "workout_days": user.workout_days
            }
            
            ai_service = GroqAITrainerService()
            analysis_text = await ai_service.generate_progress_feedback(user_data, progress_data)
            
            await callback_query.message.answer(analysis_text, )
        else:
            await callback_query.message.answer(
                "❌ Заполните профиль (/start)",
                
            )

@router.callback_query(lambda c: c.data == "refresh_ai_workout")
async def refresh_ai_workout(callback_query):
    await callback_query.answer("🔄 Обновляю ИИ-тренировку...")
    from database.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await cmd_ai_workout(callback_query.message, session)

@router.callback_query(lambda c: c.data == "ai_chat")
async def ai_chat(callback_query):
    await callback_query.answer("💬 Чат с ИИ-тренером в разработке...")

@router.message(Command("groq_test"))
async def cmd_groq_test(message: Message):
    """Тест подключения к Groq API"""
    from services.groq_service import GroqAITrainerService
    
    ai_service = GroqAITrainerService()
    
    if ai_service.use_mock:
        await message.answer(
            "❌ *Groq API не настроен*\n\n"
            "1. Получите ключ на console.groq.com\n"
            "2. Добавьте в .env: GROQ_API_KEY=gsk_ваш_ключ\n"
            "3. Перезапустите бота\n\n"
            "💡 Пока используются демо-данные.",
            
        )
    else:
        await message.answer(
            "✅ *Groq API подключен!*\n\n"
            "Модель: Llama 3 70B\n"
            "Скорость: ~5 сек на ответ\n"
            "Используйте /ai_workout для ИИ-тренировок",
            
        )
