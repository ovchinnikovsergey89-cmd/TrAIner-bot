import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler # Добавили планировщик

from config import Config
from database.database import init_db, async_session
from handlers import start, help, profile, workout, nutrition, ai_workout, ai_chat, analysis, admin, edit
from middlewares.db_middleware import DbSessionMiddleware
from services.scheduler import send_morning_motivation # Импортируем нашу функцию

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    # Если в config.py есть ADMIN_IDS, уведомим их
    if Config.ADMIN_IDS:
        try:
            for admin_id in Config.ADMIN_IDS:
                await bot.send_message(admin_id, "🚀 <b>TrAIner запущен и готов к работе!</b>")
        except:
            pass

async def main():
    logger.info("🚀 Запуск бота TrAIner...")

    # 1. Инициализация БД
    try:
        await init_db()
        logger.info("✅ База данных подключена")
    except Exception as e:
        logger.critical(f"❌ Ошибка подключения к БД: {e}")
        return

    # 2. Настройка бота
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # 3. Подключаем миддлвари
    dp.update.middleware(DbSessionMiddleware(session_pool=async_session))

    # 4. Настройка Планировщика (Scheduler)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    # Задача: Каждое утро в 08:00
    scheduler.add_job(
        send_morning_motivation, 
        trigger='cron', 
        hour=8, 
        minute=0, 
        kwargs={'bot': bot, 'session_pool': async_session}
    )
    scheduler.start()
    logger.info("⏰ Планировщик запущен (08:00 MSK)")

    # 5. Регистрация роутеров
    dp.include_routers(
        admin.router,
        start.router,
        profile.router,
        workout.router,
        ai_workout.router,
        nutrition.router,
        analysis.router,
        ai_chat.router,
        edit.router,
        help.router
    )

    # 6. Запуск
    await on_startup(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🤖 Бот начал прослушивание...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Бот упал с ошибкой: {e}")
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Выход по Ctrl+C")