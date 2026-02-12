from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from database.models import User

class UserCRUD:
    
    # --- 🟢 ОСНОВНЫЕ МЕТОДЫ (Для работы бота) ---

    @staticmethod
    async def get_or_create_user(session: AsyncSession, telegram_id: int, **kwargs):
        """Получает пользователя или создает нового, если его нет"""
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
    async def add_user(session: AsyncSession, telegram_id: int, **kwargs):
        """
        Обертка для совместимости со старым кодом. 
        Делает то же самое, что и get_or_create_user.
        """
        return await UserCRUD.get_or_create_user(session, telegram_id, **kwargs)

    @staticmethod
    async def get_user(session: AsyncSession, telegram_id: int):
        """Просто получить пользователя (без создания)"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_user(session: AsyncSession, telegram_id: int, **kwargs):
        """
        Обновляет данные пользователя.
        ВАЖНО: Игнорирует пустые значения (None), чтобы случайно не стереть данные.
        """
        # Фильтруем мусор, оставляем только реальные данные
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            for key, value in clean_kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            # Обновляем время активности
            if hasattr(user, 'updated_at'):
                user.updated_at = datetime.now()
                
            await session.commit()
            await session.refresh(user)
        return user

    # --- 🔴 НОВЫЕ МЕТОДЫ (Для админки и рассылки) ---

    @staticmethod
    async def get_all_users(session: AsyncSession):
        """Получить список ВСЕХ пользователей (для рассылки)"""
        result = await session.execute(select(User))
        return result.scalars().all()

    @staticmethod
    async def get_stats(session: AsyncSession):
        """Собирает статистику для команды /admin"""
        # 1. Всего пользователей
        total = await session.scalar(select(func.count(User.telegram_id))) or 0
        
        # 2. Активные профили (вес указан)
        active = await session.scalar(
            select(func.count(User.telegram_id)).where(User.weight.isnot(None))
        ) or 0
        
        # 3. Есть программа тренировок
        workouts = await session.scalar(
            select(func.count(User.telegram_id)).where(User.current_workout_program.isnot(None))
        ) or 0
        
        # 4. Есть программа питания
        nutrition = await session.scalar(
            select(func.count(User.telegram_id)).where(User.current_nutrition_program.isnot(None))
        ) or 0

        # 5. Активные за последние 24 часа
        active_24h = 0
        try:
            one_day_ago = datetime.now() - timedelta(days=1)
            active_24h = await session.scalar(
                select(func.count(User.telegram_id)).where(User.updated_at >= one_day_ago)
            ) or 0
        except:
            pass # Если вдруг в базе нет поля updated_at

        return {
            'total': total,
            'active_profile': active,
            'has_workout': workouts,
            'has_nutrition': nutrition,
            'active_24h': active_24h
        }