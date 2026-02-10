import asyncio
import logging
import sys
import warnings

# Глушим лишние предупреждения
warnings.filterwarnings("ignore", message="Field.*has conflict with protected namespace")

from typing import Callable, Dict, Any, Awaitable
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import TelegramObject
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from database.database import init_db, AsyncSessionLocal
from services.scheduler import send_morning_motivation

# --- ИМПОРТЫ ХЕНДЛЕРОВ ---
from handlers.start import router as start_router
from handlers.profile import router as profile_router
from handlers.ai_workout import router as ai_workout_router
from handlers.nutrition import router as nutrition_router
from handlers.workout import router as workout_router
from handlers.edit import router as edit_router
from handlers.help import router as help_router
from handlers.ai_chat import router as ai_chat_router
from handlers.common import router as common_router
from handlers.analysis import router as analysis_router
from handlers.admin import router as admin_router

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# --- MIDDLEWARE ДЛЯ БД ---
class DBSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)

async def main():
    Config.validate()
    
    try:
        await init_db()
    except Exception as e:
        logging.error(f"❌ Ошибка БД: {e}")
        return
    
    bot = Bot(
        token=Config.BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    dp.update.middleware(DBSessionMiddleware())

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        send_morning_motivation, 
        trigger='cron', 
        hour=9, 
        minute=0, 
        kwargs={'bot': bot, 'session_pool': AsyncSessionLocal}
    )
    scheduler.start()
    
    # --- ПОДКЛЮЧАЕМ РОУТЕРЫ (ВАЖЕН ПОРЯДОК!) ---
    
    # 1. Админка и общие команды
    dp.include_router(admin_router)
    dp.include_router(common_router)
    
    # 2. Основные модули (имеют приоритет над чатом)
    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(nutrition_router)
    dp.include_router(analysis_router)  # 👈 ВАЖНО: Анализ должен быть ВЫШЕ чата
    dp.include_router(workout_router)
    dp.include_router(edit_router)
    dp.include_router(ai_workout_router)
    
    # 3. Помощь
    dp.include_router(help_router)

    # 4. Чат с ИИ (ловит всё остальное) - СТАВИМ В САМЫЙ КОНЕЦ
    dp.include_router(ai_chat_router)
    
    print("\n" + "=" * 40)
    print("🚀 TrAIner Bot успешно запущен!")
    print(f"👤 Бот: @{(await bot.get_me()).username}")
    print("📝 Логи пишутся в bot.log")
    print("=" * 40 + "\n")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")