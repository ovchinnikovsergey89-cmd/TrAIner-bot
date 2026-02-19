import logging
import time
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ParseMode, ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from handlers.admin import is_admin
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

        # 1. Валидация веса
        try:
            new_weight = float(message.text.replace(',', '.'))
            if not (30 <= new_weight <= 250): raise ValueError
        except ValueError:
            await message.answer("⚠️ Введите корректное число (например: 80.5)")
            return

        # 2. Получение пользователя
        user = await UserCRUD.get_user(session, message.from_user.id)
        if not user:
            user = await UserCRUD.get_or_create_user(session, message.from_user.id)

        if not user:
            await message.answer("⚠️ Профиль не найден. Пожалуйста, введите /start")
            await state.clear()
            return

        # 3. СТРОГИЙ БЛОК ОГРАНИЧЕНИЙ (22 часа и 3 попытки)
        current_time = datetime.now()

        if not is_admin(message.from_user.id):
            # Проверка времени из базы
            if user.last_analysis_date:
                last_date = user.last_analysis_date
                # Конвертация, если SQLite вернул строку
                if isinstance(last_date, str):
                    try:
                        last_date = datetime.strptime(last_date, '%Y-%m-%d %H:%M:%S.%f')
                    except:
                        last_date = datetime.strptime(last_date, '%Y-%m-%d %H:%M:%S')

                delta = current_time - last_date
                
                if delta < timedelta(hours=22):
                    wait_time = timedelta(hours=22) - delta
                    hours = wait_time.seconds // 3600
                    minutes = (wait_time.seconds // 60) % 60
                    
                    await message.answer(
                        f"⏳ <b>Доступ ограничен!</b>\n\nАнализ можно делать раз в 22 часа.\n"
                        f"Приходите через: <b>{hours} ч. {minutes} мин.</b>",
                        parse_mode="HTML"
                    )
                    await state.clear()
                    return

            # Проверка недельного лимита
            if (user.workout_limit or 0) <= 0:
                await message.answer("❌ У вас закончились бесплатные попытки анализа.")
                await state.clear()
                return

        # 4. ЛОГИКА СОХРАНЕНИЯ
        old_weight_value = user.weight
        session.add(WeightHistory(user_id=user.telegram_id, weight=new_weight))
        await UserCRUD.update_user(session, user.telegram_id, weight=new_weight)
        
        # Расчет разницы
        delta = new_weight - (old_weight_value if old_weight_value else new_weight)
        if delta < -0.1: trend = f"📉 <b>Минус {abs(delta):.1f} кг</b>"
        elif delta > 0.1: trend = f"📈 <b>Плюс {abs(delta):.1f} кг</b>"
        else: trend = "⚖️ <b>Вес без изменений</b>"

        temp_msg = await message.answer(f"{trend}\n⏱ <b>Сохраняю и строю график...</b>", parse_mode=ParseMode.HTML)

        # 5. ДАННЫЕ ДЛЯ ГРАФИКА И ИИ
        history_result = await session.execute(
            select(WeightHistory).where(WeightHistory.user_id == user.telegram_id).order_by(WeightHistory.date)
        )
        history_data = history_result.scalars().all()
        workouts_count = await UserCRUD.get_weekly_workouts_count(session, message.from_user.id)

        ai = AIManager()
        ai_feedback = await ai.analyze_progress({
            "name": user.name,
            "weight": old_weight_value if old_weight_value else new_weight, 
            "goal": user.goal or "Поддержание",
            "workout_days": user.workout_days
        }, new_weight, workouts_count)

        graph_bytes = None
        if history_data:
            graph_buf = await GraphService.create_weight_graph(history_data)
            if graph_buf:
                graph_bytes = BufferedInputFile(graph_buf.getvalue(), filename="chart.png")

        try: await temp_msg.delete()
        except: pass

        result_text = (
            f"📊 <b>Новый вес: {new_weight} кг</b>\n"
            f"{trend}\n\n"
            f"💬 <b>Совет тренера:</b>\n{ai_feedback}"
        )

        # 6. ОТПРАВКА
        if graph_bytes:
            await message.answer_photo(graph_bytes, caption=result_text, reply_markup=get_main_menu())
        else:
            await message.answer(result_text, reply_markup=get_main_menu())

        # 7. СПИСАНИЕ ЛИМИТОВ (ТОЛЬКО ЮЗЕРАМ)
        if not is_admin(message.from_user.id):
            if user.workout_limit and user.workout_limit > 0:
                user.workout_limit -= 1
            
            user.last_analysis_date = datetime.now()
            
            try:
                await session.flush()
                await session.commit()
                logger.info(f"Limits updated for user {user.telegram_id}")
            except Exception as e:
                await session.rollback()
                logger.error(f"DB Commit Error: {e}")
            
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_main_menu())
    finally:
        await state.clear()