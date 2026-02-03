from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
import html

from database.crud import UserCRUD
from keyboards.builders import get_main_menu

router = Router()

async def show_profile(message_obj: Message, telegram_id: int, session: AsyncSession):
    user = await UserCRUD.get_user(session, telegram_id)
    
    if not user:
        await message_obj.answer("Профиль не найден. Нажмите /start")
        return

    safe_name = html.escape(message_obj.chat.full_name or "Пользователь")
    
    text = (
        f"👤 <b>Ваш профиль:</b>\n\n"
        f"🔹 Имя: {safe_name}\n"
        f"🔹 Вес: {user.weight} кг\n"
        f"🔹 Рост: {user.height} см\n"
        f"🔹 Возраст: {user.age}\n"
        f"🔹 Цель: {user.goal}\n"
        f"🔹 Активность: {user.activity_level}\n"
        f"🔹 Дней тренировок: {user.workout_days}"
    )
    
    await message_obj.answer(text, parse_mode=ParseMode.HTML, reply_markup=get_main_menu())

@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession):
    await show_profile(message, message.from_user.id, session)

# 🔥 НОВОЕ: Обработка текстовой кнопки
@router.message(F.text == "👤 Профиль")
async def btn_text_profile(message: Message, session: AsyncSession):
    await show_profile(message, message.from_user.id, session)

@router.callback_query(F.data == "profile")
async def btn_profile(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    await show_profile(callback.message, callback.from_user.id, session)