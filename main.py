import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from database.database import init_db, async_session

# 👇 Убрали edit, так как он теперь часть profile.py
# Добавили common и nutrition
from handlers import start, help, profile, workout, nutrition, ai_workout, ai_chat, analysis, admin, common
from middlewares.db_middleware import DbSessionMiddleware
from services.scheduler import send_morning_motivation

# 1. Основная настройка (оставляем INFO, чтобы видеть твои ракеты и галочки)
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 2. А теперь "прикручиваем звук" только у библиотек
# Это уберет сообщения "Update id=... is handled" и прочий шум
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)

# Планировщик оставим в INFO, чтобы видеть, что работа добавлена, 
# либо тоже в WARNING, если он слишком часто спамит
logging.getLogger("apscheduler").setLevel(logging.INFO) 

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

    # --- НАСТРОЙКА ПЛАНИРОВЩИКА ---
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    # 🔥 ВАЖНО: Запускаем job каждый час (в 00 минут), чтобы проверять notification_time
    scheduler.add_job(
        send_morning_motivation, 
        trigger='cron', 
        minute=0, # Каждые 00 минут каждого часа (0:00, 1:00 ... 23:00)
        kwargs={'bot': bot, 'session_pool': async_session}
    )
    scheduler.start()
    logger.info("⏰ Планировщик запущен (Проверка каждый час)")

    # --- ПОРЯДОК РОУТЕРОВ (ВАЖЕН!) ---
    dp.include_routers(
        admin.router,     # Админка (всегда первая)
        ai_workout.router,# Перенесите сюда (теперь он приоритетный)
        common.router,    # Общие команды (/cancel, Техника)
        analysis.router,  # Анализ веса (чтобы перехватывать числа)
        nutrition.router, # Питание
        start.router,     # Регистрация
        profile.router,   # Профиль и настройки
        workout.router,   # Тренировки (старые)
        ai_chat.router,   # Чат с тренером
        help.router       # Помощь (в конце)
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