import logging
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ParseMode, ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.crud import UserCRUD
from database.models import WeightHistory
from services.ai_manager import AIManager
from services.graph_service import GraphService # <--- Новый сервис
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
    except ValueError:
        await message.answer("⚠️ Введите число (например: 80.5)")
        return

    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Ошибка: Профиль не найден. /start")
        await state.clear()
        return

    old_weight = float(user.weight) if user.weight else new_weight
    delta = new_weight - old_weight
    
    if delta < -0.1: trend = f"📉 <b>Минус {abs(delta):.1f} кг</b>"
    elif delta > 0.1: trend = f"📈 <b>Плюс {abs(delta):.1f} кг</b>"
    else: trend = "⚖️ <b>Вес без изменений</b>"

    temp_msg = await message.answer(f"{trend}\n⏱ <b>Сохраняю и строю график...</b>", parse_mode=ParseMode.HTML)

    # 1. Сохраняем в БД
    try:
        session.add(WeightHistory(user_id=message.from_user.id, weight=new_weight))
        await UserCRUD.update_user(session, message.from_user.id, weight=new_weight)
    except Exception as e:
        logger.error(f"DB Error: {e}")

    # 2. Получаем историю для графика
    history_result = await session.execute(
        select(WeightHistory).where(WeightHistory.user_id == message.from_user.id).order_by(WeightHistory.date)
    )
    history_data = history_result.scalars().all()

    # 3. AI Анализ
    ai = AIManager()
    ai_feedback = await ai.analyze_progress({
        "weight": old_weight, 
        "goal": user.goal or "Поддержание"
    }, new_weight)

    # 4. Рисуем график
    graph_bytes = None
    if len(history_data) >= 2:
        try:
            graph_buf = await GraphService.create_weight_graph(history_data)
            if graph_buf:
                graph_bytes = BufferedInputFile(graph_buf.getvalue(), filename="chart.png")
        except Exception as e:
            logger.error(f"Graph Error: {e}")

    # 5. Отправка результата
    try: await temp_msg.delete()
    except: pass

    result_text = (
        f"📊 <b>Новый вес: {new_weight} кг</b>\n"
        f"{trend}\n\n"
        f"💬 <b>Совет тренера:</b>\n{ai_feedback}"
    )

    if graph_bytes:
        await message.answer_photo(graph_bytes, caption=result_text, reply_markup=get_main_menu())
    else:
        await message.answer(result_text, reply_markup=get_main_menu())
        
    await state.clear()