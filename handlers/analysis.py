import logging
import datetime
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
from services.graph_service import GraphService
from keyboards.main_menu import get_main_menu

router = Router()
logger = logging.getLogger(__name__)

class AnalysisState(StatesGroup):
    waiting_for_weight = State()

@router.message(F.text == "📊 Анализ")
async def start_analysis(message: Message, state: FSMContext):
    await message.answer(
        "📈 <b>Введите ваш новый вес (кг):</b>\nНапример: 75.5", 
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AnalysisState.waiting_for_weight)

@router.message(AnalysisState.waiting_for_weight)
async def process_analysis(message: Message, state: FSMContext, session: AsyncSession):
    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

        try:
            new_weight = float(message.text.replace(',', '.'))
        except ValueError:
            await message.answer("⚠️ Введите число (например: 80.5)")
            return

        user = await UserCRUD.get_user(session, message.from_user.id)
        if not user:
            await message.answer("Ошибка: Профиль не найден. /start")
            await state.clear()
            return

        # --- ЛОГИКА "УМНОЙ" ИСТОРИИ ---
        # 1. Проверяем, есть ли вообще история
        history_check = await session.execute(
            select(WeightHistory).where(WeightHistory.user_id == user.telegram_id)
        )
        has_history = history_check.scalars().first() is not None

        # 2. Если истории НЕТ, но у пользователя был старый вес в профиле
        # Значит, это первое взвешивание после регистрации.
        # Сохраним старый вес как "начальную точку" (с датой создания профиля)
        old_weight_value = user.weight
        if not has_history and old_weight_value:
            # Используем дату регистрации или (если её нет) вчерашний день
            start_date = user.created_at if user.created_at else datetime.datetime.now() - datetime.timedelta(days=1)
            
            init_record = WeightHistory(
                user_id=user.telegram_id,
                weight=old_weight_value,
                date=start_date
            )
            session.add(init_record)
            logger.info(f"Added initial history point: {old_weight_value} at {start_date}")

        # 3. Теперь сохраняем НОВЫЙ вес (сегодняшний)
        session.add(WeightHistory(user_id=user.telegram_id, weight=new_weight))
        
        # Обновляем профиль
        await UserCRUD.update_user(session, user.telegram_id, weight=new_weight)
        
        # --- КОНЕЦ ЛОГИКИ ИСТОРИИ ---

        # Расчет разницы для текста
        delta = new_weight - (old_weight_value if old_weight_value else new_weight)
        if delta < -0.1: trend = f"📉 <b>Минус {abs(delta):.1f} кг</b>"
        elif delta > 0.1: trend = f"📈 <b>Плюс {abs(delta):.1f} кг</b>"
        else: trend = "⚖️ <b>Вес без изменений</b>"

        temp_msg = await message.answer(f"{trend}\n⏱ <b>Сохраняю и строю график...</b>", parse_mode=ParseMode.HTML)

        # Получаем полную историю (теперь там минимум 2 точки, если это первый анализ)
        history_result = await session.execute(
            select(WeightHistory).where(WeightHistory.user_id == user.telegram_id).order_by(WeightHistory.date)
        )
        history_data = history_result.scalars().all()

        # Получаем количество тренировок за неделю
        workouts_count = await UserCRUD.get_weekly_workouts_count(session, message.from_user.id)

        # AI Анализ с учетом тренировок
        ai = AIManager()
        ai_feedback = await ai.analyze_progress({
            "name": user.name,
            "weight": old_weight_value if old_weight_value else new_weight, 
            "goal": user.goal or "Поддержание",
            "workout_days": user.workout_days
        }, new_weight, workouts_count)

        # Рисуем график
        graph_bytes = None
        if history_data:
            try:
                graph_buf = await GraphService.create_weight_graph(history_data)
                if graph_buf:
                    graph_bytes = BufferedInputFile(graph_buf.getvalue(), filename="chart.png")
            except Exception as e:
                logger.error(f"Graph Error: {e}")

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
            
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_main_menu())
    
    finally:
        await state.clear()