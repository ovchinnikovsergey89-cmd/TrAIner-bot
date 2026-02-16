from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import Config

# Создаем движок
engine = create_async_engine(url=Config.DATABASE_URL, echo=False)

# Фабрика сессий
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def init_db():
    # 🔥 ВАЖНО: Импортируем ВСЕ модели, чтобы SQLAlchemy знала, что создавать
    from database.models import User, WeightHistory 
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)