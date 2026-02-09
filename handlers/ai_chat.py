from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from services.groq_service import GroqService
from database.crud import UserCRUD
from states.chat_states import AIChatState 
from keyboards.main_menu import get_main_menu

router = Router()

@router.message(F.text == "💬 Чат с тренером")
@router.callback_query(F.data == "ai_chat")
async def start_chat_mode(event, state: FSMContext):
    msg = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(event, CallbackQuery): await event.answer()
        
    await msg.answer(
        "💬 <b>Режим чата активирован!</b>\n"
        "Спроси меня о питании, технике или жизни.\n\n"
        "<i>Напиши 'Стоп' для выхода.</i>",
        parse_mode="HTML"
    )
    await state.set_state(AIChatState.chatting)

@router.message(AIChatState.chatting)
async def process_chat_message(message: Message, state: FSMContext, session: AsyncSession):
    if message.text.lower() in ["стоп", "выход", "отмена"] or message.text.startswith("/"):
        await state.clear()
        await message.answer("Чат завершен.", reply_markup=get_main_menu())
        return

    user = await UserCRUD.get_user(session, message.from_user.id)
    
    user_context = {
        "name": user.name,
        "weight": user.weight,
        "goal": user.goal,
        # 🔥 Передаем стиль
        "trainer_style": user.trainer_style 
    }
    
    data = await state.get_data()
    history = data.get("history", [])
    history.append({"role": "user", "content": message.text})
    
    wait_msg = await message.answer("<i>Печатает...</i>", parse_mode="HTML")
    
    ai = GroqService()
    response = await ai.get_chat_response(history, user_context)
    
    await wait_msg.delete()
    await message.answer(response)
    
    history.append({"role": "assistant", "content": response})
    if len(history) > 6: history = history[-6:]
    await state.update_data(history=history)