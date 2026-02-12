import logging
import asyncio
from typing import Union

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode, ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from services.groq_service import GroqService
from keyboards.builders import get_main_menu

router = Router()

class AnalysisState(StatesGroup):
    waiting_for_weight = State()

# --- ВХОД В АНАЛИЗ ---
@router.message(F.text == "📊 Анализ")
@router.callback_query(F.data == "ai_analysis")
async def start_analysis(event: Union[Message, CallbackQuery], state: FSMContext):
    if isinstance(event, Message):
        message = event
    else:
        await event.answer()
        message = event.message
    
    await message.answer(
        "📈 <b>Введите ваш текущий вес (кг):</b>\nНапример: 75.5", 
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AnalysisState.waiting_for_weight)

# --- ОБРАБОТКА ВЕСА ---
@router.message(AnalysisState.waiting_for_weight)
async def process_analysis(message: Message, state: FSMContext, session: AsyncSession):
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    try:
        text = message.text.replace(',', '.')
        new_weight = float(text)
        if not (30 <= new_weight <= 300): raise ValueError
    except:
        await message.answer("⚠️ Пожалуйста, введите число (например: 80.5)")
        return

    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Профиль не найден.")
        await state.clear()
        return

    old_weight = float(user.weight) if user.weight else new_weight
    delta = new_weight - old_weight
    
    if delta < -0.1: trend = f"📉 Минус {abs(delta):.1f} кг"
    elif delta > 0.1: trend = f"📈 Плюс {abs(delta):.1f} кг"
    else: trend = "⚖️ Вес без изменений"

    # 🔥 ИЗМЕНЕНО: Пишет Тренер
    temp_msg = await message.answer(f"{trend}\n📊 <b>Тренер оценивает прогресс...</b>", parse_mode=ParseMode.HTML)

    ai = GroqService()
    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        
        feedback = await ai.analyze_progress({
            "weight": old_weight, 
            "goal": user.goal or "Форма"
        }, new_weight)
        
        # Обновляем БД
        await UserCRUD.update_user(session, message.from_user.id, weight=new_weight)
        
        try:
            await temp_msg.delete()
        except:
            pass
        
        # Итоговое сообщение
        result_text = (
            f"📊 <b>Результат:</b> {old_weight} -> <b>{new_weight} кг</b>\n"
            f"{trend}\n\n"
            f"{feedback}\n\n"
            f"<i>Тренер обновил твой вес в профиле.</i>"
        )
        
        await message.answer(
            result_text,
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.HTML
        )
        await state.clear()
        
    except Exception as e:
        logging.error(f"Analysis handler error: {e}")
        await message.answer("⚠️ Вес сохранен, но Тренер не смог дать комментарий (ошибка сети).")
        await UserCRUD.update_user(session, message.from_user.id, weight=new_weight)
        await state.clear()