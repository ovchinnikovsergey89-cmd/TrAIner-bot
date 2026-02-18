from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from services.ai_manager import AIManager # <--- НОВЫЙ ИМПОРТ
from states.chat_states import AIChatState
from keyboards.main_menu import get_main_menu

router = Router()

def get_chat_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Вернуться в меню")]],
        resize_keyboard=True
    )

# --- УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ЗАПУСКА ---
async def start_chat_logic(message: Message, state: FSMContext):
    await state.update_data(chat_history=[]) 
    
    welcome_text = (
        "👨‍✈️ <b>Тренер на связи!</b>\n\n"
        "Я помню ваши параметры (вес, цель, возраст). Спрашивайте!\n"
        "<i>(Например: 'Можно ли мне сладкое?' или 'Почему болят колени?')</i>"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_chat_kb(),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AIChatState.chatting)

# 1. ВХОД ЧЕРЕЗ ТЕКСТОВУЮ КНОПКУ
@router.message(F.text == "💬 Чат с тренером")
async def start_chat_text(message: Message, state: FSMContext):
    await start_chat_logic(message, state)

# 2. ВХОД ЧЕРЕЗ ИНЛАЙН-КНОПКУ
@router.callback_query(F.data == "ai_chat")
async def start_chat_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_chat_logic(callback.message, state)

# 3. ОБРАБОТКА СООБЩЕНИЙ В ЧАТЕ
@router.message(AIChatState.chatting)
async def process_chat_message(message: Message, state: FSMContext, session: AsyncSession):
    if message.text in ["🔙 Вернуться в меню", "стоп", "выход", "/start"]:
        await state.clear()
        await message.answer("Чат завершен.", reply_markup=get_main_menu())
        return

    user = await UserCRUD.get_user(session, message.from_user.id)
    if not user:
        await message.answer("Заполни профиль!")
        return

    loading_msg = await message.answer("💬 <i>Тренер пишет сообщение...</i>", parse_mode=ParseMode.HTML)
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    data = await state.get_data()
    history = data.get("chat_history", [])
    history.append({"role": "user", "content": message.text})
    
    # --- ИСПОЛЬЗУЕМ НОВЫЙ МЕНЕДЖЕР ---
    ai_service = AIManager()
    
    user_context = {
        "gender": user.gender,
        "weight": user.weight,
        "height": user.height,
        "age": user.age,
        "goal": user.goal,
        "activity_level": user.activity_level,
        "name": user.name
    }
    
    try:
        answer = await ai_service.get_chat_response(history, user_context)
    except Exception as e:
        answer = "Прости, связь с сервером прервалась."

    history.append({"role": "assistant", "content": answer})
    await state.update_data(chat_history=history)
    
    await loading_msg.delete()
    await message.answer(answer, parse_mode=ParseMode.HTML)