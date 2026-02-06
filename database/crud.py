from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from database.models import User

class UserCRUD:
    
    @staticmethod
    async def get_or_create_user(session: AsyncSession, telegram_id: int, **kwargs):
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
    async def update_user(session: AsyncSession, telegram_id: int, **kwargs):
        """Обновляет ТОЛЬКО переданные поля, игнорируя None"""
        # 🔥 ВАЖНО: Фильтруем None, чтобы не стереть другие данные
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            for key, value in clean_kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            await session.commit()
            return True
        return False

    @staticmethod
    async def get_user(session: AsyncSession, telegram_id: int):
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_stats(session: AsyncSession):
        total = await session.scalar(select(func.count(User.telegram_id)))
        active = await session.scalar(select(func.count(User.telegram_id)).where(User.weight.isnot(None)))
        workouts = await session.scalar(select(func.count(User.telegram_id)).where(User.current_workout_program.isnot(None)))
        nutrition = await session.scalar(select(func.count(User.telegram_id)).where(User.current_nutrition_program.isnot(None)))
        
        return {"total": total, "active": active, "workouts": workouts, "nutrition": nutrition}
    
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
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
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

    # --- 👇 НОВАЯ ФУНКЦИЯ СТАТИСТИКИ 👇 ---
    @staticmethod
    async def get_stats(session: AsyncSession):
        """Собирает статистику по пользователям"""
        # Всего пользователей
        total_users = await session.scalar(select(func.count(User.telegram_id)))
        
        # Пользователей с заполненным весом (считаем их активными)
        active_users = await session.scalar(
            select(func.count(User.telegram_id)).where(User.weight.isnot(None))
        )
        
        # Пользователей с программой тренировок
        workout_users = await session.scalar(
            select(func.count(User.telegram_id)).where(User.current_workout_program.isnot(None))
        )
        
        # Пользователей с меню питания
        nutrition_users = await session.scalar(
            select(func.count(User.telegram_id)).where(User.current_nutrition_program.isnot(None))
        )
        
        return {
            "total": total_users,
            "active": active_users,
            "workouts": workout_users,
            "nutrition": nutrition_users
        }