import logging
import datetime
import pytz
import random
from aiogram import Bot
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.models import User
from database.crud import UserCRUD

logger = logging.getLogger(__name__)

# Настройки тарифов: {Уровень: (Генерации, Вопросы)}
SUBSCRIPTION_LIMITS = {
    "free": (3, 5),      # Free
    "lite": (10, 20),    # Lite
    "standard": (25, 50),    # Standard 
    "ultra": (50, 100)    # Ultra
}

async def send_morning_motivation(bot: Bot, session_pool: async_sessionmaker):
    """
    Запускается каждый час.
    Выбирает пользователей, у которых notification_time совпадает с текущим часом.
    """
    msk_tz = pytz.timezone("Europe/Moscow")
    now_hour = datetime.datetime.now(msk_tz).hour
    
    logger.info(f"⏰ Scheduler tick: Checking users for {now_hour}:00")

    async with session_pool() as session:
        users = await UserCRUD.get_users_by_notification_hour(session, now_hour)
        
        if not users:
            return

        motivations = [
            "Твое тело — это отражение твоих привычек. Начни день правильно! 💪",
            "Маленькие шаги сегодня — большие результаты завтра. Погнали на тренировку? 🔥",
            "Дисциплина — это решение делать то, что очень не хочется, чтобы достичь того, чего хочешь. 🏆",
            "Доброе утро! Твой единственный лимит — это ты сам. Раздвинь границы! 🚀",
            "Сила не в мышцах, сила в голове. Проснись и докажи себе, на что ты способен! 🧠✨",
            "Успех не падает с неба, он куется в зале. Жду тебя на занятии! 🏋️‍♂️",
            "Не жди вдохновения, создавай его своими действиями. Время действовать! ⚡",
            "Каждая тренировка приближает тебя к лучшей версии себя. Не останавливайся! 📈",
            "Твои оправдания не сожгут калории. Вставай и сделай это! 👊",
            "Сегодня — идеальный день, чтобы стать сильнее, чем вчера! 🌟",
            "Победа любит подготовленных. Ты готов выложиться на все 100? 🥇",
            "Твое будущее 'Я' скажет тебе спасибо за сегодняшнюю тренировку. 🤝",
            "Боль временна, триумф вечен. Оставь лень в кровати! ⏳🔥",
            "Не сравнивай себя с другими. Сравнивай себя с тем, кем ты был вчера. 🔄",
            "Сделай сегодня то, о чем другие завтра будут только мечтать. 💎",
            "Помни, зачем ты начал. Твоя цель ближе, чем кажется! 🎯",
            "Прогресс — это не прямая линия. Главное — продолжать движение! 📉📈",
            "Твое здоровье — это самая выгодная инвестиция. Инвестируй время в себя! 🍎",
            "Двигайся вперед, даже если темп кажется медленным. Ты всё равно обгоняешь тех, кто лежит на диване. 🐢💨",
            "Верь в себя так же сильно, как я верю в твой потенциал. Ты машина! 🤖💪"
        ]
        
        text = random.choice(motivations)

        count = 0
        for user in users:
            try:
                msg = f"☀️ <b>Доброе утро!</b>\n\n{text}"
                await bot.send_message(user.telegram_id, msg, parse_mode="HTML")
                count += 1
            except Exception as e:
                logger.warning(f"Failed to send to {user.telegram_id}: {e}")
        
        logger.info(f"✅ Sent motivation to {count} users.")

async def reset_daily_limits(session_pool: async_sessionmaker):
    """
    Сбрасывает лимиты пользователей каждый день в полночь в зависимости от их уровня подписки.
    Также проверяет, не истекла ли подписка.
    """
    logger.info("🔄 Запуск ежедневного сброса лимитов...")
    msk_tz = pytz.timezone("Europe/Moscow")
    now = datetime.datetime.now(msk_tz).replace(tzinfo=None) # Убираем tzinfo для совместимости со SQLite

        async with session_pool() as session:
        # 1. Проверяем просроченные подписки и сбрасываем их на Free ("free")
        await session.execute(
            update(User)
            .where((User.subscription_level != "free") & (User.subscription_expires_at < now))
            .values(subscription_level="free", subscription_expires_at=None)
        )
        await session.commit()

        # 2. Обновляем лимиты для каждого уровня
        for level, limits in SUBSCRIPTION_LIMITS.items():
            workout_lim, chat_lim = limits
            
            await session.execute(
                update(User)
                .where(User.subscription_level == level)
                .values(workout_limit=workout_lim, chat_limit=chat_lim)
            )
        
        await session.commit()
    logger.info("✅ Лимиты успешно обновлены!")