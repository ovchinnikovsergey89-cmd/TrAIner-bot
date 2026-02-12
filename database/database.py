from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import Config

# 1. Создаем движок (подключение к БД)
# Исправлено: используем Config.DATABASE_URL вместо Config.DB_URL
engine = create_async_engine(url=Config.DATABASE_URL, echo=False)

# 2. Создаем фабрику сессий
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# 3. Базовый класс для моделей
class Base(DeclarativeBase):
    pass

# 4. Функция инициализации таблиц
async def init_db():
    # Импорт внутри функции, чтобы избежать ошибки Circular Import
    from database.models import User
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)