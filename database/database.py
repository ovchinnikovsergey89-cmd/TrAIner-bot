from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base, User
from config import Config

# --- ИСПРАВЛЕНИЕ: echo=False отключает вывод SQL-запросов в консоль ---
engine = create_async_engine(Config.DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    """
    Создает таблицы в базе данных, если их нет.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)