from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
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
    async def get_weekly_workouts_count(session: AsyncSession, telegram_id: int) -> int:
        from database.models import WorkoutLog
        # Считаем количество записей в логах за последние 7 дней
        one_week_ago = datetime.now() - timedelta(days=7)
        query = select(func.count(WorkoutLog.id)).where(
            WorkoutLog.user_id == telegram_id,
            WorkoutLog.date >= one_week_ago
        )
        result = await session.execute(query)
        return result.scalar() or 0
    
    @staticmethod
    async def add_user(session: AsyncSession, telegram_id: int, **kwargs):
        """Обертка для совместимости"""
        return await UserCRUD.get_or_create_user(session, telegram_id, **kwargs)

    @staticmethod
    async def get_user(session: AsyncSession, telegram_id: int):
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_user(session: AsyncSession, telegram_id: int, **kwargs):
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            for key, value in clean_kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            # 🔥 ВАЖНО: Явно обновляем время
            user.updated_at = datetime.now()
                
            await session.commit()
            await session.refresh(user)
        return user

    @staticmethod
    async def get_all_users(session: AsyncSession):
        result = await session.execute(select(User))
        return result.scalars().all()
    
    @staticmethod
    async def get_users_by_notification_hour(session: AsyncSession, hour: int):
        result = await session.execute(select(User).where(User.notification_time == hour))
        return result.scalars().all()

    @staticmethod
    async def get_stats(session: AsyncSession):
        total = await session.scalar(select(func.count(User.telegram_id)))
        return {"total": total or 0}

    @staticmethod
    async def get_stats(session: AsyncSession):
        total = await session.scalar(select(func.count(User.telegram_id))) or 0
        
        active = await session.scalar(
            select(func.count(User.telegram_id)).where(User.weight.isnot(None))
        ) or 0
        
        workouts = await session.scalar(
            select(func.count(User.telegram_id)).where(User.current_workout_program.isnot(None))
        ) or 0
        
        nutrition = await session.scalar(
            select(func.count(User.telegram_id)).where(User.current_nutrition_program.isnot(None))
        ) or 0

        active_24h = 0
        try:
            one_day_ago = datetime.now() - timedelta(days=1)
            active_24h = await session.scalar(
                select(func.count(User.telegram_id)).where(User.updated_at >= one_day_ago)
            ) or 0
        except:
            pass

        return {
            'total': total,
            'active_profile': active,
            'has_workout': workouts,
            'has_nutrition': nutrition,
            'active_24h': active_24h
        }