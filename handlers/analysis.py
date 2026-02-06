from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

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
    
    msg_text = (
        "📈 <b>Анализ прогресса</b>\n\n"
        "Чтобы я мог оценить твой результат, напиши мне свой <b>текущий вес</b> (в кг).\n"
        "<i>Например: 75.5</i>\n\n"
        "Или нажми /cancel для отмены."
    )
    
    await message.answer(msg_text, parse_mode=ParseMode.HTML)
    await state.set_state(AnalysisState.waiting_for_weight)

# --- ОБРАБОТКА ВЕСА ---
@router.message(AnalysisState.waiting_for_weight)
async def process_analysis(message: Message, state: FSMContext, session: AsyncSession):
    text = message.text.replace(',', '.')
    if text.startswith('/'): return

    try:
        new_weight = float(text)
        if not (30 <= new_weight <= 250): raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректный вес числом (например: 80.5)")
        return

    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Ошибка: Профиль не найден. Нажмите /start")
        await state.clear()
        return

    old_weight = user.weight or new_weight # Если старого нет, считаем что он равен новому
    
    # 🔥 МАТЕМАТИКА (Считаем сами, не доверяем ИИ цифры)
    delta = new_weight - old_weight
    
    if delta < 0:
        trend = f"📉 Ты сбросил(а) {abs(delta):.1f} кг!"
    elif delta > 0:
        trend = f"📈 Ты набрал(а) {abs(delta):.1f} кг."
    else:
        trend = "⚖️ Вес не изменился."

    msg = await message.answer(f"{trend}\n🧠 <b>Анализирую данные...</b>", parse_mode=ParseMode.HTML)

    # Запускаем AI с полным контекстом
    ai = GroqService()
    user_data = {
        "weight": old_weight, # Старый вес
        "new_weight": new_weight, # Новый вес
        "goal": user.goal,
        "gender": user.gender,
        "height": user.height, # Добавили рост для ИМТ
        "age": user.age # Добавили возраст
    }
    
    try:
        # В сервисе нужно будет использовать эти поля
        feedback = await ai.analyze_progress(user_data, new_weight)
        
        # Чистка
        if feedback:
            feedback = feedback.replace("<p>", "").replace("</p>", "\n\n").replace("###", "")
        else:
            feedback = "Тренер задумался..."

        # Обновляем БД
        await UserCRUD.update_user(session, message.from_user.id, weight=new_weight)
        
        await msg.delete()
        
        result_text = (
            f"📊 <b>Результат:</b>\n"
            f"{old_weight} кг ➡️ <b>{new_weight} кг</b>\n"
            f"{trend}\n\n"
            f"💬 <b>Совет тренера:</b>\n{feedback}"
        )
        
        await message.answer(result_text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)
        await state.clear()
        
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка анализа: {e}")
        await state.clear()