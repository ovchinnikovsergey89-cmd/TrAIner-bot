from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from config import Config

# 1. Сначала объявляем Base
Base = declarative_base()

# 2. Создаем движок
# 🔥 ИСПРАВЛЕНИЕ: echo=False отключает "хлам" в консоли
engine = create_async_engine(Config.DATABASE_URL, echo=False)

# 3. Создаем фабрику сессий
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# 4. Функция создания таблиц
async def init_db():
    async with engine.begin() as conn:
        # Импортируем модели внутри функции (чтобы избежать кругового импорта)
        import database.models
        # Создаем таблицы
        await conn.run_sync(Base.metadata.create_all)