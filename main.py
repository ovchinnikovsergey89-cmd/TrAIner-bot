import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from database.database import init_db, async_session
# 👇 Порядок импортов не важен, важен порядок в include_routers
from handlers import start, help, profile, workout, nutrition, ai_workout, ai_chat, analysis, admin, edit, common
from middlewares.db_middleware import DbSessionMiddleware
from services.scheduler import send_morning_motivation

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
    if Config.ADMIN_IDS:
        try:
            for admin_id in Config.ADMIN_IDS:
                await bot.send_message(admin_id, "🚀 <b>TrAIner запущен и готов к работе!</b>")
        except:
            pass

async def main():
    logger.info("🚀 Запуск бота TrAIner...")

    try:
        await init_db()
        logger.info("✅ База данных подключена")
    except Exception as e:
        logger.critical(f"❌ Ошибка подключения к БД: {e}")
        return

    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.update.middleware(DbSessionMiddleware(session_pool=async_session))

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        send_morning_motivation, 
        trigger='cron', 
        hour=8, 
        minute=0, 
        kwargs={'bot': bot, 'session_pool': async_session}
    )
    scheduler.start()
    logger.info("⏰ Планировщик запущен (08:00 MSK)")

    # 👇 ИЗМЕНЕН ПОРЯДОК РОУТЕРОВ
    # analysis.router поднят НАВЕРХ, чтобы перехватывать ввод веса
    dp.include_routers(
        admin.router,
        common.router,  
        analysis.router, # <--- ПЕРЕНЕСЛИ СЮДА (теперь он приоритетнее профиля)
        start.router,
        profile.router,
        workout.router,
        ai_workout.router,
        nutrition.router,
        ai_chat.router,
        edit.router,
        help.router
    )

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