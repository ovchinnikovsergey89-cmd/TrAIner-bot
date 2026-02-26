from aiogram import Bot
import io
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

# --- НОВОЕ: ОБРАБОТКА ГОЛОСОВЫХ СООБЩЕНИЙ (ТОЛЬКО PREMIUM) ---
@router.message(F.voice)
async def process_voice_message(message: Message, session: AsyncSession, state: FSMContext, bot: Bot):
    user = await UserCRUD.get_user(session, message.from_user.id)
    is_admin_user = is_admin(message.from_user.id)
    
    # 1. ПРОВЕРКА НА PREMIUM
    if not is_admin_user and not user.is_premium:
        premium_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Узнать про Premium", callback_data="buy_premium")]
        ])
        await message.answer(
            "🎙 <b>Голосовой помощник — это Premium функция!</b>\n\n"
            "Оформи подписку, чтобы общаться с ИИ-тренером голосовыми сообщениями (он понимает даже шепот во время подхода).",
            reply_markup=premium_kb,
            parse_mode="HTML"
        )
        return

    # 2. ПРОВЕРКА ЛИМИТОВ (если у Premium тоже есть лимиты, или убираем, если безлимит)
    if not is_admin_user and (user.chat_limit or 0) <= 0:
        await message.answer("🚀 Лимит сообщений на сегодня исчерпан!")
        return

    status_msg = await message.answer("🎧 <i>Слушаю...</i>", parse_mode="HTML")

    try:
        # 3. СКАЧИВАЕМ ГОЛОСОВОЕ СООБЩЕНИЕ
        voice_file_info = await bot.get_file(message.voice.file_id)
        voice_bytes = await bot.download_file(voice_file_info.file_path)
        
        # 4. ПЕРЕВОДИМ ГОЛОС В ТЕКСТ
        manager = AIManager()
        recognized_text = await manager.transcribe_voice(voice_bytes)
        
        if not recognized_text:
            await status_msg.edit_text("❌ Не удалось разобрать голосовое сообщение. Попробуй еще раз или напиши текстом.")
            return
            
        await status_msg.edit_text(f"🗣 <b>Вы сказали:</b> <i>«{recognized_text}»</i>\n\n🤔 <i>Тренер думает...</i>", parse_mode="HTML")
        
        # 5. ОТПРАВЛЯЕМ ТЕКСТ В DEEPSEEK (Как обычное сообщение)
        data = await state.get_data()
        current_history = data.get("chat_history", [])
        
        u_ctx = {
            "name": user.name, "age": user.age, "weight": user.weight, 
            "height": user.height, "goal": user.goal, "level": user.workout_level
        }
        
        current_history.append({"role": "user", "content": recognized_text})
        
        ai_answer = await manager.get_chat_response(current_history, u_ctx)
        
        # Списание лимита
        if not is_admin_user:
            user.chat_limit -= 1
            await session.commit()
            
        current_history.append({"role": "assistant", "content": ai_answer})
        # Ограничиваем историю (последние 10 сообщений)
        if len(current_history) > 10: current_history = current_history[-10:]
        await state.update_data(chat_history=current_history)
        
        # 6. ВЫДАЕМ ОТВЕТ
        await status_msg.edit_text(ai_answer, parse_mode="HTML")
        
    except Exception as e:
        print(f"Ошибка войса: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при обработке голоса.")
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