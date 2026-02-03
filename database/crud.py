from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database.models import User

class UserCRUD:
    
    @staticmethod
    async def get_or_create_user(session: AsyncSession, telegram_id: int, **kwargs):
        """Получить или создать пользователя (Тихий режим)"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            user = User(telegram_id=telegram_id, **kwargs)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        return user
    
    @staticmethod
    async def add_user(session: AsyncSession, telegram_id: int):
        """Создать пользователя (обертка)"""
        await UserCRUD.get_or_create_user(session, telegram_id)
    
    @staticmethod
    async def update_user(session: AsyncSession, telegram_id: int, **kwargs):
        """Обновить данные пользователя (Тихий режим)"""
        # Фильтруем пустые значения
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Молча обновляем данные
            for key, value in clean_kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            await session.commit()
            return True
        else:
            return False
    
    @staticmethod
    async def get_user(session: AsyncSession, telegram_id: int):
        """Получить пользователя по telegram_id"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_users(session: AsyncSession):
        """Получить всех пользователей (для рассылки)"""
        result = await session.execute(select(User))
        return result.scalars().all()