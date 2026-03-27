import logging
import datetime
import pytz
import random
import asyncio
from aiogram import Bot
from sqlalchemy import update, select, func, desc
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.models import User, WorkoutLog, NutritionLog
from database.crud import UserCRUD
from services.ai_manager import AIManager

logger = logging.getLogger(__name__)

# Настройки тарифов: {Уровень: (Генерации, Вопросы)}
SUBSCRIPTION_LIMITS = {
    "free": (3, 5),      
    "lite": (10, 20),    
    "standard": (25, 50),     
    "ultra": (50, 100)   
}

async def send_morning_motivation(bot: Bot, session_pool: async_sessionmaker):
    """
    Запускается каждый час.
    Выбирает пользователей, у которых notification_time совпадает с текущим часом.
    Индивидуальные сообщения для Premium тарифов.
    """
    msk_tz = pytz.timezone("Europe/Moscow")
    now_msk = datetime.datetime.now(msk_tz)
    now_hour = now_msk.hour
    today = now_msk.date()
    
    logger.info(f"⏰ Scheduler tick: Checking users for {now_hour}:00")

    async with session_pool() as session:
        users = await UserCRUD.get_users_by_notification_hour(session, now_hour)
        
        if not users:
            return

        motivations = [
            "Твое тело — это отражение твоих привычек. Начни день правильно! 💪",
            "Маленькие шаги каждый день ведут к большим результатам. Не останавливайся! 🚀",
            "Единственная плохая тренировка — та, которой не было. Вперед! 🏋️‍♂️",
            "Дисциплина — это мост между целями и достижениями. Построй свой мост сегодня! 🌉",
            "Ты сильнее, чем думаешь. Докажи это себе сегодня! 💥",
            "Не жди идеального момента, создай его! Время действовать. 🔥",
            "Капля пота сегодня — это океан гордости завтра. 🌊",
            "Победи свою лень, и ты победишь всё! 🏆"
            "Боль временна, триумф вечен. Выложись сегодня на полную! ⚡️",
            "Твой единственный соперник — это ты вчерашний. Стань лучше! 🥇",
            "Либо ты управляешь своим днем, либо день управляет тобой. Решай! 😤",
            "Успех начинается за чертой твоего комфорта. Выходи и делай! 🚪",
            "Тебе не нужно быть великим, чтобы начать. Тебе нужно начать, чтобы стать великим! ✨",
            "Оправдания калории не жгут. Просто иди и работай! ⏳",
            "Мотивация дает толчок, но только привычка заставляет двигаться дальше. ⚙️",
            "Твой завтрашний успех зависит от того, что ты сделаешь сегодня. 🗓",
            "Не рассказывай о своих целях — покажи свои результаты! 🤫",
            "Твое тело может всё, если ты убедишь свой разум. 🧠",
            "Прогресс — это не прямая линия. Главное — не останавливаться! 📈",
            "Слабость — это просто выбор. Выбери быть сильным! 🔥",
            "Сделай сегодня то, за что завтра скажешь себе 'спасибо'. 🙏",
            "Твое здоровье — это инвестиция, а не расход. Вкладывай в себя! 💎",
            "Через месяц ты поблагодаришь себя за то, что не сдался сегодня. 🦾"
        ]

        manager = AIManager()

        for user in users:
            try:
                sub_level = user.subscription_level or "free"
                
                # --- ЛОГИКА ДЛЯ FREE И LITE (Оставляем как было) ---
                if sub_level in ["free", "lite"]:
                    text = random.choice(motivations)
                    await bot.send_message(user.telegram_id, f"🌅 <b>Тренер напоминает:</b>\n\n{text}", parse_mode="HTML")
                    continue
                
                # --- ПОДГОТОВКА БАЗОВЫХ ДАННЫХ ДЛЯ PRO (Тренировки) ---
                stmt_w = select(WorkoutLog).where(WorkoutLog.user_id == user.telegram_id).order_by(desc(WorkoutLog.date)).limit(1)
                res_w = await session.execute(stmt_w)
                last_workout = res_w.scalar_one_or_none()
                
                if last_workout:
                    days_ago = (today - last_workout.date.date()).days
                    if days_ago == 0:
                        workout_info = "Тренировался СЕГОДНЯ"
                    elif days_ago == 1:
                        workout_info = "Тренировался ВЧЕРА"
                    else:
                        workout_info = f"Не тренировался уже {days_ago} дней"
                else:
                    workout_info = "Пока не записывал тренировки"

                # --- ЛОГИКА ДЛЯ STANDARD (Учитывает тренировки) ---
                if sub_level == "standard":
                    prompt = (
                        f"Ты фитнес-тренер. У клиента тариф Standard (Цель: {user.goal}). "
                        f"Его активность: {workout_info}. "
                        f"Напиши ОЧЕНЬ КОРОТКОЕ (максимум 150 символов) мотивирующее напоминание на сегодня. "
                        f"Без приветствий, сразу по делу, дружелюбно."
                    )
                    ai_text = await manager.get_chat_response([{"role": "user", "content": prompt}], {})
                    
                    await bot.send_message(user.telegram_id, f"⚡️ <b>Тренер на связи:</b>\n\n{ai_text}", parse_mode="HTML")

                # --- ЛОГИКА ДЛЯ ULTRA (Учитывает Тренировки + Питание + Общие советы) ---
                elif sub_level == "ultra":
                    stmt_n = select(
                        func.sum(NutritionLog.calories).label("kcal"),
                        func.sum(NutritionLog.protein).label("p")
                    ).where(NutritionLog.user_id == user.telegram_id, func.date(NutritionLog.date) == today)
                    
                    res_n = await session.execute(stmt_n)
                    nut_data = res_n.first()
                    
                    kcal = int(nut_data.kcal or 0)
                    protein = int(nut_data.p or 0)
                    
                    # Если данных о еде нет, даем ИИ свободу выбора темы
                    if kcal > 0:
                        nut_info = f"По питанию сегодня: {kcal} ккал, {protein}г белка."
                    else:
                        nut_info = "Данных по еде сегодня еще нет. Можешь дать совет по восстановлению, сну или мотивации."

                    prompt = (
                        f"Ты элитный фитнес-коуч уровня Ultra. Клиент (Цель: {user.goal}). "
                        f"Статус тренировок: {workout_info}. {nut_info} "
                        f"ЗАДАЧА: Напиши ОЧЕНЬ КОРОТКИЙ (до 180 симв.) персональный инсайт. "
                        f"Если данных мало — дай совет по биохакингу, режиму или психологии успеха. "
                        f"Без приветствий. Будь максимально разнообразным, не зацикливайся на одном питании!"
                    )
                    ai_text = await manager.get_chat_response([{"role": "user", "content": prompt}], {})
                    
                    await bot.send_message(user.telegram_id, f"👑 <b>Ultra Аналитика:</b>\n\n{ai_text}", parse_mode="HTML")

            except Exception as e:
                logger.error(f"Ошибка ИИ-уведомления для {user.telegram_id}: {e}")
                # Fallback: Если ИИ отвалился, отправляем обычную мотивацию
                fallback_text = random.choice(motivations)
                try:
                    await bot.send_message(user.telegram_id, f"⚡️ <b>Тренер на связи:</b>\n\n{fallback_text}", parse_mode="HTML")
                except:
                    pass

async def reset_daily_limits(session_pool: async_sessionmaker):
    """
    Сбрасывает лимиты пользователей каждый день в полночь в зависимости от их уровня подписки.
    Также проверяет, не истекла ли подписка.
    """
    logger.info("🔄 Запуск ежедневного сброса лимитов...")
    msk_tz = pytz.timezone("Europe/Moscow")
    now = datetime.datetime.now(msk_tz).replace(tzinfo=None)

    async with session_pool() as session:
        try:
            # 1. Проверяем просроченные подписки и сбрасываем их на "free"
            await session.execute(
                update(User)
                .where((User.subscription_level.in_(["lite", "standard", "ultra"])) & (User.sub_end_date < now))
                .values(subscription_level="free", is_premium=False, sub_end_date=None)
            )

            # 2. Обновляем лимиты генераций и сообщений
            for level, limits in SUBSCRIPTION_LIMITS.items():
                workout_lim, chat_lim = limits
                
                await session.execute(
                    update(User)
                    .where(User.subscription_level == level)
                    .values(
                        workout_limit=workout_lim, 
                        chat_limit=chat_lim
                    )
                )
            
            await session.commit()
            logger.info("✅ Лимиты успешно обновлены по новым тарифам!")
        except Exception as e:
            logger.error(f"❌ Ошибка при сбросе лимитов: {e}")


async def auto_post_to_channel(bot: Bot):
    """Генерирует и отправляет пост в маркетинговый канал"""
    manager = AIManager()
    channel_id = "@TrAIner_Life" # Наш крутой канал
    
    logger.info("📢 Запуск генерации автоматического поста в канал...")
    
    try:
        post_text = await manager.generate_marketing_post()
        await bot.send_message(chat_id=channel_id, text=post_text, parse_mode="HTML")
        logger.info("✅ Рекламный пост успешно опубликован в @TrAIner_Life!")
    except Exception as e:
        logger.error(f"❌ Ошибка автопостинга в канал: {e}")       

# В конец файла services/scheduler.py

async def auto_post_to_channel(bot: Bot):
    """Генерирует и отправляет пост с элементами случайности"""
    
    # 1. Вероятность публикации (30%)
    if random.random() > 0.3: 
        logger.info("🎲 Рандом решил не постить в этом часу.")
        return

    # 2. Случайная задержка от 1 до 50 минут.
    wait_time = random.randint(1, 50)
    logger.info(f"⏳ Рандом выбран! Пост выйдет через {wait_time} минут.")
    await asyncio.sleep(wait_time * 60)

    # 3. Сама генерация и отправка
    manager = AIManager()
    channel_id = "@TrAIner_Life"
    bot_username = "@TrAInerFitnessBot"

    try:
        post_text = await manager.generate_marketing_post()
        await bot.send_message(chat_id=channel_id, text=post_text, parse_mode="HTML")
        logger.info(f"✅ Автопост опубликован в @TrAIner_Life!")
    except Exception as e:
        logger.error(f"❌ Ошибка автопостинга: {e}")

def setup_scheduler(scheduler, bot, session_pool):
    """
    Регистрирует все фоновые задачи бота.
    """
    # 1. Сброс лимитов в полночь
    scheduler.add_job(
        reset_daily_limits, 
        trigger='cron', 
        hour=0, 
        minute=0, 
        kwargs={'session_pool': session_pool}
    )
    
    # 2. Утренняя мотивация (проверяет каждый час)
    scheduler.add_job(
        send_morning_motivation, 
        trigger='cron', 
        minute=0, 
        kwargs={'bot': bot, 'session_pool': session_pool}
    )
    
    # 3. Наш умный автопостинг в канал (каждый час с рандомом внутри)
    scheduler.add_job(
        auto_post_to_channel,
        trigger='cron',
        hour='9-21', 
        minute=0,
        kwargs={'bot': bot}
    )
    
    logger.info("📅 Все задачи планировщика успешно зарегистрированы!")             