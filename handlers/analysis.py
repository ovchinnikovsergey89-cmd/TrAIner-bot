import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode, ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

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
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    try:
        text = message.text.replace(',', '.')
        new_weight = float(text)
    except:
        await message.answer("⚠️ Введите число (например: 80.5)")
        return

    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user: return

    old_weight = float(user.weight) if user.weight else new_weight
    
    # Считаем разницу
    delta = new_weight - old_weight
    if delta < -0.1: trend = f"📉 Минус {abs(delta):.1f} кг"
    elif delta > 0.1: trend = f"📈 Плюс {abs(delta):.1f} кг"
    else: trend = "⚖️ Вес стоит"

    temp_msg = await message.answer(f"{trend}\n📊 <b>Тренер анализирует...</b>", parse_mode=ParseMode.HTML)

    ai = GroqService()
    try:
        feedback = await ai.analyze_progress({
            "weight": old_weight, 
            "goal": user.goal
        }, new_weight)
        
        await UserCRUD.update_user(session, message.from_user.id, weight=new_weight)
        
        await temp_msg.delete()
        await message.answer(
            f"📊 <b>Результат:</b> {old_weight} -> <b>{new_weight}</b>\n"
            f"{trend}\n\n{feedback}",
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.HTML
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Analysis handler error: {e}")
        await temp_msg.edit_text("Ошибка анализа.")
        await state.clear()