import logging
import datetime
import pytz
from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.crud import UserCRUD
from services.ai_manager import AIManager

logger = logging.getLogger(__name__)

async def send_morning_motivation(bot: Bot, session_pool: async_sessionmaker):
    """
    Запускается каждый час.
    Выбирает пользователей, у которых notification_time совпадает с текущим часом.
    """
    # 1. Получаем текущий час в Москве
    msk_tz = pytz.timezone("Europe/Moscow")
    now_hour = datetime.datetime.now(msk_tz).hour
    
    logger.info(f"⏰ Scheduler tick: Checking users for {now_hour}:00")

    async with session_pool() as session:
        # 2. Берем только тех, кто ждет уведомление сейчас
        users = await UserCRUD.get_users_by_notification_hour(session, now_hour)
        
        if not users:
            return

        # 3. Генерируем 1 мотивацию на всех (для экономии токенов)
        ai = AIManager()
        # Промпт зависит от времени суток
        if 5 <= now_hour < 12:
            prompt = "Напиши короткую мотивацию на утро (1 предложение) для тренировок."
        elif 12 <= now_hour < 18:
            prompt = "Напиши короткую мотивацию на день (1 предложение), чтобы не пропускать тренировку."
        else:
            prompt = "Напиши короткое напоминание подготовиться к завтрашнему дню или лечь вовремя."

        try:
            # Используем "сырой" запрос к модели для простоты
            if ai.client:
                r = await ai.client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}], 
                    model=ai.model, temperature=0.9
                )
                text = r.choices[0].message.content
            else:
                text = "🔥 Время становиться лучше! Не забудь про тренировку или питание!"
        except:
            text = "🚀 Дисциплина — это ключ к победе!"

        # 4. Рассылаем
        count = 0
        for user in users:
            try:
                msg = f"⏰ <b>Напоминание ({now_hour}:00):</b>\n\n{text}"
                await bot.send_message(user.telegram_id, msg, parse_mode="HTML")
                count += 1
            except Exception as e:
                logger.warning(f"Failed to send to {user.telegram_id}: {e}")
        
        logger.info(f"✅ Sent motivation to {count} users.")