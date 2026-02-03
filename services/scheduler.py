import asyncio
from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker
from database.crud import UserCRUD

# Функция, которая выполняется каждое утро
async def send_morning_motivation(bot: Bot, session_pool: async_sessionmaker):
    async with session_pool() as session:
        users = await UserCRUD.get_all_users(session)
        
        count = 0
        for user in users:
            try:
                # Тут можно сделать умную логику: проверять, какой сегодня день
                # Но для начала просто напомним о себе
                text = (
                    f"☀️ <b>Доброе утро, {user.first_name or 'чемпион'}!</b>\n\n"
                    "Не забудь сегодня уделить время здоровью. "
                    "Если сегодня тренировка — выкладывайся на 100%! 💪\n\n"
                    "<i>Жми 'AI Тренировка', чтобы получить план.</i>"
                )
                
                await bot.send_message(user.telegram_id, text, parse_mode="HTML")
                count += 1
                # Делаем паузу, чтобы Telegram не забанил за спам (30 сообщений в секунду)
                await asyncio.sleep(0.05) 
            except Exception as e:
                print(f"Не удалось отправить юзеру {user.telegram_id}: {e}")
        
        print(f"✅ Рассылка завершена. Отправлено: {count}")