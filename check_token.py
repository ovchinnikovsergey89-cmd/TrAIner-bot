import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("BOT_TOKEN")
if token:
    print(f"✅ Токен найден: {token[:10]}...")
else:
    print("❌ Токен не найден!")
