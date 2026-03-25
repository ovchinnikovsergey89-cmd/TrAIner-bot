import logging
import datetime
import asyncio
from aiogram.exceptions import TelegramBadRequest
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode, ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, distinct

from handlers.admin import is_admin
from database.crud import UserCRUD
from database.models import WeightHistory, WorkoutLog, NutritionLog, ExerciseLog
from services.ai_manager import AIManager
from services.graph_service import GraphService
from keyboards.main_menu import get_main_menu

router = Router()
logger = logging.getLogger(__name__)

class AnalysisState(StatesGroup):
    waiting_for_weight = State()

# --- 1. ГЛАВНОЕ МЕНЮ АНАЛИЗА ---
@router.message(F.text == "📊 Анализ")
async def show_analysis_menu(message: Message, session: AsyncSession):
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        return await message.answer("Сначала заполни профиль (/start)!")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Динамика веса тела", callback_data="analyze_weight")],
        [InlineKeyboardButton(text="🏋️‍♂️ Прогресс тренировок", callback_data="analyze_workouts")],
        [InlineKeyboardButton(text="🍏 Разбор питания", callback_data="analyze_nutrition")],
        [InlineKeyboardButton(text="🏆 Комплексный разбор", callback_data="analyze_full")]
    ])
    
    await message.answer("📊 <b>Аналитический центр</b>\n\nКакой отчет подготовить для тебя?", reply_markup=kb, parse_mode="HTML")

# --- 2. МГНОВЕННЫЙ АНАЛИЗ (ТРЕНИРОВКИ И ПИТАНИЕ) ---
@router.callback_query(F.data.in_(["analyze_workouts", "analyze_nutrition"]))
async def process_instant_analysis(callback: CallbackQuery, session: AsyncSession):
    user = await UserCRUD.get_user(session, callback.from_user.id)
    
    if not is_admin(user.telegram_id) and user.workout_limit <= 0:
        return await callback.answer("Лимит анализа исчерпан. Оформи Premium!", show_alert=True)

    analysis_type = callback.data
    
    # --- 🔥 ДОБАВЛЕНА ЗАЩИТА ОТ ДВОЙНОГО НАЖАТИЯ ---
    try:
        status_msg = await callback.message.edit_text("⏳ <i>Тренер изучает твои данные...</i>", parse_mode="HTML")
    except TelegramBadRequest:
        # Если текст уже "Тренер изучает...", Telegram выдаст ошибку. Мы её игнорируем!
        status_msg = callback.message
    # -----------------------------------------------

    manager = AIManager()
    
    # 🔥 Оборачиваем ВЕСЬ код в try, чтобы бот не зависал при сбоях БД или графиков
    try:
        graph_bytes = None
        ai_prompt = ""

        if analysis_type == "analyze_workouts":
            workouts_count = user.completed_workouts 
            
            fourteen_days_ago = datetime.datetime.now() - datetime.timedelta(days=14)
            
            stmt_ex = (
                select(WorkoutLog)
                .where(
                    WorkoutLog.user_id == user.telegram_id,
                    WorkoutLog.exercise_name.is_not(None),
                    WorkoutLog.date >= fourteen_days_ago.date()
                )
                .order_by(desc(WorkoutLog.date))
                .limit(100)
            )
            res_ex = await session.execute(stmt_ex)
            exercises = res_ex.scalars().all()
            exercises.reverse()
            
            if exercises:
                try:
                    graph_buf = await GraphService.create_workouts_graph(exercises)
                    if graph_buf: graph_bytes = BufferedInputFile(graph_buf.getvalue(), filename="workouts.png")
                except Exception as e:
                    logger.error(f"Ошибка графика тренировок: {e}")

                # 🔥 УМНЫЙ ПОИСК РАБОЧИХ ВЕСОВ (Берем только максимальные)
                ex_dict = {}
                for ex in exercises:
                    name = ex.exercise_name.lower().strip()
                    try:
                        weight = float(ex.weight or 0)
                    except:
                        weight = 0.0
                    reps = getattr(ex, 'reps', '')
                    
                    if name not in ex_dict:
                        ex_dict[name] = {"w": weight, "r": reps}
                    else:
                        # Если нашли вес больше записанного — обновляем (игнорируем разминки с 0 кг)
                        if weight > ex_dict[name]["w"]:
                            ex_dict[name] = {"w": weight, "r": reps}
                
                ex_list = []
                for k, v in list(ex_dict.items())[:15]:
                    w_str = f"{int(v['w']) if v['w'].is_integer() else v['w']}кг"
                    r_str = f" х {v['r']}" if v['r'] else ""
                    ex_list.append(f"{k.capitalize()}: {w_str}{r_str}")
                
                ex_text = "; ".join(ex_list)
            else:
                ex_text = "Нет свежих данных за последние 14 дней."

            # 🔥 ПРОДВИНУТЫЙ ПРОМПТ ДЛЯ ИИ
            ai_prompt = (f"Ты продвинутый фитнес-тренер. Проанализируй рабочие веса клиента. "
                         f"Его собственный вес: {user.weight}кг, Цель: {user.goal}. "
                         f"В ТЕКУЩЕМ цикле выполнено тренировок: {workouts_count}. "
                         f"Его ЛУЧШИЕ рабочие веса за 14 дней: {ex_text}. "
                         f"Сделай профессиональный вывод о его силовых показателях (сопоставь рабочие веса с его весом тела {user.weight}кг). "
                         f"ВАЖНО: Клиент НЕ новичок, не пиши базовые советы про 'нулевые веса' или 'тело учится технике'. "
                         f"Не используй слово 'Вердикт'. Пиши строго по делу, как опытный тренер (максимум 600 символов).")

        elif analysis_type == "analyze_nutrition":
            seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
            stmt_nut = select(
                func.date(NutritionLog.date).label("day"),
                NutritionLog.meal_type,
                func.sum(NutritionLog.calories).label("kcal"),
                func.sum(NutritionLog.protein).label("p"),
                func.sum(NutritionLog.fat).label("f"),
                func.sum(NutritionLog.carbs).label("c")
            ).where(NutritionLog.user_id == user.telegram_id, NutritionLog.date >= seven_days_ago.date())\
             .group_by(func.date(NutritionLog.date), NutritionLog.meal_type).order_by("day")
            
            res_nut = await session.execute(stmt_nut)
            nut_days_raw = res_nut.all()
            
            if nut_days_raw:
                try:
                    user_sub = user.subscription_level or "free"
                    graph_buf = await GraphService.create_nutrition_graph(nut_days_raw, user_sub)
                    if graph_buf: 
                        graph_bytes = BufferedInputFile(graph_buf.getvalue(), filename="nutrition.png")
                except Exception as e:
                    logger.error(f"Ошибка графика питания: {e}")
            
            if nut_days_raw:
                days_dict = {}
                for d in nut_days_raw:
                    if d.day not in days_dict: days_dict[d.day] = []
                    # Подстраховка от пустых значений (None)
                    kcal = int(d.kcal or 0)
                    p = int(d.p or 0)
                    days_dict[d.day].append(f"{d.meal_type}: {kcal}ккал(Б{p})")
                
                nut_text = "\n".join([f"• {day}: " + ", ".join(meals) for day, meals in days_dict.items()])
            else:
                nut_text = "Нет данных."

            target_cal = user.target_calories or "не задана"
            ai_prompt = (f"Ты нутрициолог. Оцени рацион клиента за 7 дней (Цель: {user.goal}, Вес: {user.weight}кг). "
                         f"🎯 ЕГО РАССЧИТАННАЯ НОРМА: {target_cal} ккал. "
                         f"Сводка КБЖУ: {nut_text}. Дай профессиональный совет. "
                         f"🚨 ЗАПРЕЩЕНО советовать клиенту другую калорийность! Оценивай только то, как он соблюдает свою норму ({target_cal} ккал). "
                         f"ВАЖНО: Не используй слово 'Вердикт' в своем ответе, сразу пиши по делу. "
                         f"Пиши строго только про питание. Без приветствий (максимум 600 символов).")

        # Генерация ответа ИИ
        analysis = await manager.get_chat_response([{"role": "user", "content": ai_prompt}], {})
        
        if not is_admin(user.telegram_id): user.workout_limit -= 1
        await session.commit()
        await status_msg.delete()
        
        title = "🏋️‍♂️ Анализ тренировок" if analysis_type == "analyze_workouts" else "🍏 Анализ питания"
        caption_text = f"<b>{title}</b>\n\n💬 <b>Вердикт тренера:</b>\n{analysis}"
        
        # 🔥 НОВЫЙ БЛОК: Механизм повторных попыток для отправки в Telegram
        # 🔥 Механизм повторных попыток с умным фолбэком (отправка без картинки при сбое)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Если это последняя попытка — принудительно убираем график, чтобы спасти отправку
                if attempt == max_retries - 1 and graph_bytes:
                    logger.warning("Последняя попытка: пробуем отправить только текст (без графика)...")
                    graph_bytes = None 
                    caption_text += "\n\n<i>(📊 График временно недоступен из-за проблем со связью)</i>"

                if graph_bytes:
                    if len(caption_text) <= 1024:
                        await callback.message.answer_photo(graph_bytes, caption=caption_text, parse_mode="HTML")
                    else:
                        await callback.message.answer_photo(graph_bytes)
                        await callback.message.answer(caption_text, parse_mode="HTML")
                else:
                    await callback.message.answer(caption_text, parse_mode="HTML")
                
                break # Успех! Выходим из цикла
                
            except Exception as send_error:
                logger.warning(f"Попытка отправки {attempt + 1} сорвалась: {send_error}")
                if attempt == max_retries - 1:
                    raise send_error # Если даже текст не ушел (совсем нет сети), сдаемся
                await asyncio.sleep(1.5) # Ждем полторы секунды перед новой попыткой

    except Exception as e:
        logger.error(f"Ошибка мгновенного анализа: {e}")
        try:
            await status_msg.edit_text("❌ Ошибка при составлении отчета. Тренер занят, попробуй позже.")
        except Exception:
            await callback.message.answer("❌ Ошибка при составлении отчета. Тренер занят, попробуй позже.")

# --- 3. АНАЛИЗ С ВВОДОМ ВЕСА ---
@router.callback_query(F.data.in_(["analyze_weight", "analyze_full"]))
async def ask_weight_for_analysis(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await UserCRUD.get_user(session, callback.from_user.id)
    if not is_admin(user.telegram_id) and user.workout_limit <= 0:
        return await callback.answer("Лимит анализа исчерпан. Оформи Premium!", show_alert=True)

    await state.update_data(analysis_type=callback.data)
    await callback.message.edit_text("📈 <b>Введи свой текущий вес (кг):</b>\nНапример: 75.5", parse_mode="HTML")
    await state.set_state(AnalysisState.waiting_for_weight)

@router.message(AnalysisState.waiting_for_weight)
async def process_weight_and_analyze(message: Message, state: FSMContext, session: AsyncSession):
    try:
        new_weight = float(message.text.replace(',', '.'))
        if not (30 <= new_weight <= 250): return await message.answer("❌ Введите реальный вес (30 - 250).")
    except ValueError:
        return await message.answer("❌ Введите число (например, 75.5).")

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    
    data = await state.get_data()
    analysis_type = data.get("analysis_type", "analyze_weight")
    await state.clear()

    async with session.begin():
        user = await UserCRUD.get_user(session, message.from_user.id)
        
        old_weight = user.weight
        trend_msg = "⚖️ Сохранил твой новый вес."
        
        if old_weight is not None:
            diff = new_weight - old_weight
            if diff > 0:
                trend_msg = f"📈 Плюс {diff:.1f} кг к прошлому весу. Сохранил!"
            elif diff < 0:
                trend_msg = f"📉 Минус {abs(diff):.1f} кг! Отличный результат, сохранил."
            else:
                trend_msg = "⚖️ Вес не изменился. Записал!"

        await message.answer(trend_msg)
        temp_msg = await message.answer("⏳ <i>Тренер анализирует данные...</i>", parse_mode="HTML")

        user.weight = new_weight
        
        history_stmt = select(WeightHistory).where(WeightHistory.user_id == user.telegram_id).order_by(WeightHistory.date)
        history_res = await session.execute(history_stmt)
        history_data = history_res.scalars().all()
        
        if not history_data or abs(history_data[-1].weight - new_weight) > 0.1:
            session.add(WeightHistory(user_id=user.telegram_id, weight=new_weight))
            history_data = (await session.execute(history_stmt)).scalars().all()
        
        # Вытаскиваем количество тренировок для всех видов анализа
        workouts_count = await UserCRUD.get_weekly_workouts_count(session, user.telegram_id)
        
        graph_bytes = None
        
        if analysis_type == "analyze_full":
            seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
            
            nut_stmt = (
                select(
                    func.date(NutritionLog.date).label("day"), 
                    func.sum(NutritionLog.calories).label("kcal")
                )
                .where(
                    NutritionLog.user_id == user.telegram_id, 
                    NutritionLog.date >= seven_days_ago
                )
                .group_by(func.date(NutritionLog.date))
                .order_by("day")
            )
            nut_res = await session.execute(nut_stmt)
            nut_days = nut_res.all()
            
            ex_stmt = (
                select(WorkoutLog)
                .where(
                    WorkoutLog.user_id == user.telegram_id,
                    WorkoutLog.exercise_name.is_not(None) 
                )
                .order_by(WorkoutLog.date.desc())
                .limit(5)
            )
            ex_res = await session.execute(ex_stmt)
            exercises = ex_res.scalars().all()
            
            nut_text = "\n".join([f"{d.day}: {int(d.kcal)} ккал" for d in nut_days]) if nut_days else "Нет данных"
            ex_text = "; ".join([f"{ex.exercise_name}: {ex.weight}кг" for ex in reversed(exercises)]) if exercises else "Нет данных"

            # Промпт не изменен, добавлены точечные запреты в конец
            target_cal = user.target_calories or "не задана"
            extended_goal = (f"Ты строгий фитнес-тренер. Сделай комплексный анализ: сравни питание, тренировки и вес клиента. "
                             f"Цель: {user.goal}. 🎯 УСТАНОВЛЕННАЯ НОРМА ПИТАНИЯ: {target_cal} ккал. "
                             f"Тренировок за неделю: {workouts_count}. Рабочие веса: {ex_text}. Питание(7дн): {nut_text}. "
                             f"🚨 КРИТИЧЕСКИ ВАЖНО: Запрещено выдумывать и советовать свою норму калорий (типа 1800-2000)! "
                             f"Оценивай прогресс строго относительно установленной нормы в {target_cal} ккал. "
                             f"Не используй слово 'Вердикт' в своем ответе, сразу пиши по делу. "
                             f"Строго без приветствий (максимум 800 символов).")
        else:
            graph_buf = await GraphService.create_weight_graph(history_data)
            if graph_buf: 
                graph_bytes = BufferedInputFile(graph_buf.getvalue(), filename="weight.png")
            
            # Промпт не изменен, добавлены точечные запреты в конец
            extended_goal = (f"Ты фитнес-тренер. Проанализируй динамику веса клиента. Цель: {user.goal}. "
                             f"Дай короткий совет. ВАЖНО: Не используй слово 'Вердикт' в своем ответе. "
                             f"Пиши строго только про вес. Без приветствий (максимум 500 символов).")

        ai = AIManager()
        ai_feedback = await ai.analyze_progress({
            "name": user.name, "weight": new_weight, "goal": extended_goal, "workout_days": user.workout_days
        }, new_weight, workouts_count)

        if not is_admin(user.telegram_id): 
            user.workout_limit -= 1

    try: 
        await temp_msg.delete()
    except: 
        pass

    title = "🏆 Комплексный разбор" if analysis_type == "analyze_full" else "📈 Динамика веса"
    caption_text = f"<b>{title}</b>\n\n💬 <b>Вердикт тренера:</b>\n{ai_feedback}"

    if graph_bytes:
        if len(caption_text) <= 1024:
            await message.answer_photo(graph_bytes, caption=caption_text, reply_markup=get_main_menu(), parse_mode="HTML")
        else:
            await message.answer_photo(graph_bytes)
            await message.answer(caption_text, reply_markup=get_main_menu(), parse_mode="HTML")
    else:
        await message.answer(caption_text, reply_markup=get_main_menu(), parse_mode="HTML")