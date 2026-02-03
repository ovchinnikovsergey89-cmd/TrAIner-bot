import os
from dotenv import load_dotenv
from aiogram import Bot

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("❌ Токен не найден! Проверьте .env файл")
else:
    print(f"✅ Токен загружен: {TOKEN[:10]}...")
    
    # Проверка подключения
    import asyncio
    async def test():
        bot = Bot(token=TOKEN)
        me = await bot.get_me()
        print(f"🤖 Бот: {me.first_name} (@{me.username})")
        await bot.session.close()
    
    asyncio.run(test())
