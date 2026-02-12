import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ParseMode, ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from services.groq_service import GroqService
from keyboards.builders import get_main_menu

router = Router()
logger = logging.getLogger(__name__)

class AnalysisState(StatesGroup):
    waiting_for_weight = State()

@router.message(F.text == "📊 Анализ")
async def start_analysis(message: Message, state: FSMContext):
    await message.answer(
        "📈 <b>Введите ваш текущий вес (кг):</b>\nНапример: 75.5", 
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AnalysisState.waiting_for_weight)

@router.message(AnalysisState.waiting_for_weight)
async def process_analysis(message: Message, state: FSMContext, session: AsyncSession):
    # Показываем, что бот "печатает"
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    try:
        text = message.text.replace(',', '.')
        new_weight = float(text)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите число (например: 80.5)")
        return

    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Ошибка: Профиль не найден. Напишите /start")
        await state.clear()
        return

    # Берем старый вес (если есть) или используем новый как старый
    old_weight = float(user.weight) if user.weight else new_weight
    
    # Считаем разницу
    delta = new_weight - old_weight
    
    if delta < -0.1: 
        trend = f"📉 <b>Минус {abs(delta):.1f} кг</b>"
    elif delta > 0.1: 
        trend = f"📈 <b>Плюс {abs(delta):.1f} кг</b>"
    else: 
        trend = "⚖️ <b>Вес без изменений</b>"

    # Отправляем временное сообщение
    temp_msg = await message.answer(f"{trend}\n⏱ <b>Тренер анализирует прогресс...</b>", parse_mode=ParseMode.HTML)

    # Запрашиваем анализ у ИИ
    ai = GroqService()
    try:
        # Передаем данные для анализа
        feedback = await ai.analyze_progress({
            "weight": old_weight, 
            "goal": user.goal or "Поддержание формы"
        }, new_weight)
        
        # Если ИИ вернул ошибку или пустоту, ставим заглушку
        if not feedback or "Ошибка" in feedback:
            feedback = "Данные обновлены. Продолжайте тренировки!"

        # 🔥 Сначала обновляем базу!
        await UserCRUD.update_user(session, message.from_user.id, weight=new_weight)
        
        # Удаляем "думающее" сообщение
        try:
            await temp_msg.delete()
        except:
            pass
        
        # Формируем красивый ответ
        result_text = (
            f"📊 <b>Отчет о прогрессе:</b>\n"
            f"Было: {old_weight} кг -> Стало: <b>{new_weight} кг</b>\n"
            f"{trend}\n\n"
            f"💬 <b>Комментарий Тренера:</b>\n"
            f"{feedback}"
        )
        
        await message.answer(
            result_text,
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Analysis critical error: {e}")
        # Даже если всё упало, сохраняем вес и говорим юзеру ок
        await UserCRUD.update_user(session, message.from_user.id, weight=new_weight)
        await message.answer(f"✅ Вес {new_weight} кг сохранен!", reply_markup=get_main_menu())
    
    finally:
        await state.clear()