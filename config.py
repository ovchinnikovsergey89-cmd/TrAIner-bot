import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

class Config:
    # Токен бота
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    PAYMENTS_TOKEN = os.getenv("PAYMENTS_TOKEN")
    
    # Ключи AI
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    
    # База данных
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./database.db")

    # --- 👇 СПИСОК АДМИНОВ 👇 ---
    # Впиши сюда свой ID (числом). Можно добавить несколько через запятую.
    ADMIN_IDS = [
        7512936965, #5053846105 #1203994973
    ]

    @staticmethod
    def validate():
        if not Config.BOT_TOKEN:
            raise ValueError("❌ Ошибка: BOT_TOKEN не найден в файле .env или переменных среды!")
        
        if not Config.DATABASE_URL:
             raise ValueError("❌ Ошибка: DATABASE_URL не настроен.")