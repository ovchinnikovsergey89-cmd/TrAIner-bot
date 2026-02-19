import html
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from services.ai_manager import AIManager 
from states.chat_states import AIChatState
from keyboards.main_menu import get_main_menu
from handlers.admin import is_admin  # Важно: импорт должен быть здесь!

# Настройка логгера, чтобы видеть ошибки в консоли
logger = logging.getLogger(__name__)

router = Router()

def get_chat_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Вернуться в меню")]],
        resize_keyboard=True
    )

async def start_chat_logic(message: Message, state: FSMContext):
    await state.update_data(chat_history=[]) 
    welcome_text = (
        "👨‍✈️ <b>Тренер на связи!</b>\n\n"
        "Я помню ваши параметры. Спрашивайте!\n"
        "<i>(Например: 'Можно ли мне сладкое? или Присутствует боль в ногах, дай меньше нагрузку на ноги!')</i>"
    )
    await message.answer(welcome_text, reply_markup=get_chat_kb(), parse_mode=ParseMode.HTML)
    await state.set_state(AIChatState.chatting)

@router.message(F.text == "💬 Чат с тренером")
async def start_chat_text(message: Message, state: FSMContext):
    await start_chat_logic(message, state)

# ... (в начале файла убедись, что импорты такие)
import html
from handlers.admin import is_admin
# ...

import html # Добавь в начало файла

@router.message(AIChatState.chatting)
async def process_chat_message(message: Message, state: FSMContext, session: AsyncSession):
    # Инициализируем всё в самом начале
    user_text = message.text or ""
    ai_answer = ""
    loading_msg = None
    
    # Выход из чата
    if user_text in ["🔙 Вернуться в меню", "стоп", "выход", "/start"]:
        await state.clear()
        await message.answer("Чат завершен.", reply_markup=get_main_menu())
        return

    try:
        # Получаем данные
        user = await UserCRUD.get_user(session, message.from_user.id)
        is_admin_user = is_admin(message.from_user.id)

        # Проверка лимитов
        if not is_admin_user and (user.chat_limit or 0) <= 0:
            await message.answer("🚀 Попытки закончились!")
            return

        # Показываем статус "печатает"
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        loading_msg = await message.answer("💬 <b>Тренер думает...</b>", parse_mode="HTML")

        # Работа с историей
        state_data = await state.get_data()
        current_history = state_data.get("chat_history", [])
        current_history.append({"role": "user", "content": user_text})

        # ЗАПРОС К ИИ
        manager = AIManager()
        u_ctx = {"name": user.name, "goal": user.goal, "weight": user.weight}
        
        ai_answer = await manager.get_chat_response(current_history, u_ctx)

        # Списание лимита (только после получения ответа)
        if not is_admin_user:
            user.chat_limit -= 1
            await session.commit()

        # Сохраняем историю
        current_history.append({"role": "assistant", "content": ai_answer})
        await state.update_data(chat_history=current_history[-6:])

        # Удаляем "лоадинг" и отправляем ответ
        if loading_msg:
            await loading_msg.delete()
        
        # Самая безопасная отправка: если HTML не проходит, шлем обычным текстом
        try:
            await message.answer(ai_answer, parse_mode="HTML")
        except:
            await message.answer(ai_answer)

    except Exception as e:
        logger.error(f"Final Chat Error: {e}")
        if loading_msg:
            try: await loading_msg.delete()
            except: pass
        await message.answer(f"⚠️ Ошибка: {e}")