import os
import asyncio
import logging
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from services.ai_manager import AIManager 
from states.chat_states import AIChatState
from keyboards.main_menu import get_main_menu
from handlers.admin import is_admin

# Настройка логгера
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

# --- ОБРАБОТКА КОМАНДЫ /RESET ---
@router.message(Command("reset"))
async def handle_reset_command(message: Message, state: FSMContext):
    await state.update_data(chat_history=[])
    await message.answer("🔄 История диалога очищена!")

# ==========================================
# ОБРАБОТКА ГОЛОСОВЫХ В ЧАТЕ (ТОЛЬКО PREMIUM)
# ==========================================
@router.message(AIChatState.chatting, F.voice)
async def process_voice_message(message: Message, session: AsyncSession, state: FSMContext, bot: Bot):
    user = await UserCRUD.get_user(session, message.from_user.id)
    is_admin_user = is_admin(message.from_user.id)
    
    # 1. ПРОВЕРКА НА PRO ТАРИФ (Standard и Ultra)
    user_sub = user.subscription_level or "free"
    if not is_admin_user and user_sub in ["free", "lite"]:
        premium_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Улучшить подписку", callback_data="buy_premium")]
        ])
        await message.answer(
            "🎙 <b>Голосовой помощник — это функция тарифов Standard и Ultra!</b>\n\nОформи подписку, чтобы общаться голосом.",
            reply_markup=premium_kb,
            parse_mode="HTML"
        )
        return

    # 2. ПРОВЕРКА ЛИМИТОВ
    if not is_admin_user and (user.chat_limit or 0) <= 0:
        await message.answer("🚀 Лимит сообщений на сегодня исчерпан!")
        return

    status_msg = await message.answer("🎧 <i>Слушаю...</i>", parse_mode="HTML")
    
    # 3. СКАЧИВАЕМ АУДИО
    temp_filename = f"voice_chat_{message.from_user.id}.ogg"
    voice_file_info = await bot.get_file(message.voice.file_id)
    await bot.download_file(voice_file_info.file_path, temp_filename)
    await asyncio.sleep(0.1)

    try:
        manager = AIManager()
        # 4. ПЕРЕВОДИМ ГОЛОС В ТЕКСТ (через Groq в AIManager)
        recognized_text = await manager.transcribe_voice(temp_filename)

        if not recognized_text:
            await status_msg.edit_text("❌ Не удалось разобрать слова. Попробуй сказать четче.")
            return

        # 5. СПИСЫВАЕМ ЛИМИТ
        if not is_admin_user:
            user.chat_limit -= 1
            await session.commit()

        await status_msg.edit_text(f"🎤 Вы сказали: <i>{recognized_text}</i>\n\n⏳ Тренер думает...", parse_mode="HTML")

        # 6. ОТПРАВЛЯЕМ В ИИ (DeepSeek)
        state_data = await state.get_data()
        current_history = state_data.get("chat_history", [])
        current_history.append({"role": "user", "content": recognized_text})
        
        u_ctx = {"name": user.name, "goal": user.goal, "weight": user.weight}
        ai_answer = await manager.get_chat_response(current_history, u_ctx)

        current_history.append({"role": "assistant", "content": ai_answer})
        await state.update_data(chat_history=current_history[-6:])

        await message.answer(ai_answer, parse_mode="HTML")
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Ошибка голоса в чате: {e}")
        await status_msg.edit_text("🔧 Произошла системная ошибка при обработке аудио.")
    
    finally:
        # 7. ЧИСТОТА: Удаляем аудиофайл с диска
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

# ==========================================
# ОБРАБОТКА ТЕКСТА В ЧАТЕ
# ==========================================
@router.message(AIChatState.chatting, F.text)
async def process_chat_message(message: Message, state: FSMContext, session: AsyncSession):
    user_text = message.text or ""
    loading_msg = None
    
    # Выход из чата
    if user_text in ["🔙 Вернуться в меню", "стоп", "выход", "/start"]:
        await state.clear()
        await message.answer("Чат завершен.", reply_markup=get_main_menu())
        return

    # Проверка на пустое сообщение
    if not user_text.strip():
        await message.answer("📝 Пожалуйста, введите текст сообщения.")
        return

    try:
        user = await UserCRUD.get_user(session, message.from_user.id)
        is_admin_user = is_admin(message.from_user.id)

        # Проверка лимитов
        if not is_admin_user and (user.chat_limit or 0) <= 0:
            await message.answer("🚀 Попытки закончились!")
            return

        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        loading_msg = await message.answer("💬 <b>Тренер думает...</b>", parse_mode="HTML")

        state_data = await state.get_data()
        current_history = state_data.get("chat_history", [])
        current_history.append({"role": "user", "content": user_text})

        # ЗАПРОС К ИИ
        manager = AIManager()
        u_ctx = {"name": user.name, "goal": user.goal, "weight": user.weight}
        
        ai_answer = await manager.get_chat_response(current_history, u_ctx)

        # Списание лимита 
        if not is_admin_user:
            user.chat_limit -= 1
            await session.commit()

        # Сохраняем историю
        current_history.append({"role": "assistant", "content": ai_answer})
        await state.update_data(chat_history=current_history[-6:])

        if loading_msg:
            try:
                await loading_msg.delete()
            except:
                pass
        
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

# ==========================================
# УНИВЕРСАЛЬНАЯ КНОПКА ЗАКРЫТЬ/НАЗАД
# ==========================================
@router.callback_query(F.data.in_(["back", "close", "cancel"]))
async def universal_close_button(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass 
    finally:
        await callback.answer()