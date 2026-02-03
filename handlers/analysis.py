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

# --- ВХОД В АНАЛИЗ (Универсальный) ---
@router.message(F.text == "📊 Анализ")
@router.callback_query(F.data == "ai_analysis")
async def start_analysis(event: Union[Message, CallbackQuery], state: FSMContext):
    """
    Обрабатывает и нажатие кнопки меню (Message), 
    и нажатие инлайн-кнопки (CallbackQuery).
    """
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
    # Пытаемся понять число
    text = message.text.replace(',', '.')
    
    if text.startswith('/'):
        return

    try:
        new_weight = float(text)
        if not (30 <= new_weight <= 250):
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректный вес числом (например: 80.5)")
        return

    # Получаем данные пользователя
    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Ошибка: Профиль не найден. Нажмите /start")
        await state.clear()
        return

    # --- 🔥 ИСПРАВЛЕНИЕ ЗДЕСЬ 🔥 ---
    # Сохраняем старый вес в переменную ДО обновления базы
    old_weight = user.weight
    # -------------------------------

    msg = await message.answer("🤔 <b>Сравниваю с прошлыми данными...</b>", parse_mode=ParseMode.HTML)

    # Запускаем AI
    ai = GroqService()
    user_data = {
        "weight": old_weight, # Отправляем старый вес
        "goal": user.goal,
        "gender": user.gender
    }
    
    try:
        feedback = await ai.analyze_progress(user_data, new_weight)
        
        # Чистка текста от мусора
        if feedback:
            feedback = feedback.replace("<p>", "").replace("</p>", "\n\n")
            feedback = feedback.replace("###", "")
        else:
            feedback = "Не удалось получить анализ."

        # Обновляем вес в базе данных (только сейчас!)
        await UserCRUD.update_user(session, message.from_user.id, weight=new_weight)
        
        await msg.delete()
        
        # Формируем ответ, используя сохраненную переменную old_weight
        result_text = (
            f"📊 <b>Результат анализа:</b>\n"
            f"Было: {old_weight} кг ➡️ Стало: {new_weight} кг\n\n"
            f"💬 <b>Мнение тренера:</b>\n{feedback}\n\n"
            f"<i>(Я обновил твой вес в профиле)</i>"
        )
        
        await message.answer(result_text, reply_markup=get_main_menu(), parse_mode=ParseMode.HTML)
        await state.clear()
        
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка анализа: {e}")
        await state.clear()