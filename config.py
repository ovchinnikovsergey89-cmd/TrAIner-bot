import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

class Config:
    # Токен бота
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Ключи AI
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    
    # --- ВОТ ЭТОЙ СТРОКИ НЕ ХВАТАЛО 👇 ---
    # Если в .env нет ссылки, используем базу по умолчанию (sqlite)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trainer.db")

    @staticmethod
    def validate():
        if not Config.BOT_TOKEN:
            raise ValueError("❌ Ошибка: BOT_TOKEN не найден в файле .env или переменных среды!")
        
        # Проверка базы данных
        if not Config.DATABASE_URL:
             # На всякий случай, хотя у нас есть значение по умолчанию выше
             raise ValueError("❌ Ошибка: DATABASE_URL не настроен.")