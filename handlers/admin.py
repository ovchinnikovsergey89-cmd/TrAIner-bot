from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import UserCRUD
from config import Config

router = Router()

@router.message(Command("admin"))
async def admin_stats(message: Message, session: AsyncSession):
    # Проверка на админа
    if message.from_user.id not in Config.ADMIN_IDS:
        # Можно вообще ничего не отвечать, чтобы никто не знал о команде
        return

    stats = await UserCRUD.get_stats(session)
    
    # Считаем конверсию (чтобы не делить на ноль)
    conversion = 0
    if stats['total'] > 0:
        conversion = int((stats['active'] / stats['total']) * 100)
    
    text = (
        "📊 <b>СТАТИСТИКА БОТА</b>\n\n"
        f"👥 <b>Всего пользователей:</b> {stats['total']}\n"
        f"👤 <b>Заполнили профиль:</b> {stats['active']}\n"
        f"🏋️ <b>Имеют программу:</b> {stats['workouts']}\n"
        f"🍏 <b>Имеют рацион:</b> {stats['nutrition']}\n\n"
        f"📈 <b>Конверсия в профиль:</b> {conversion}%"
    )
    
    await message.answer(text, parse_mode="HTML")