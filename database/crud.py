from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User
from database.database import async_session as AsyncSessionLocal # Убедись, что импорт правильный

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
    
    @staticmethod
    async def update_user_subscription(session: AsyncSession, user_id: int, level: str):
        print(f"DEBUG: Пытаюсь обновить юзера {user_id} на уровень {level}") # ДОБАВЬ ЭТО
        try:
            # 1. Ищем юзера
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalar_one_or_none()
            
            if user:
                # 2. Меняем данные
                user.subscription_level = level
                user.subscription_expires_at = datetime.now() + timedelta(days=28)
                
                if level == "ultra":
                    user.workout_limit = 100
                    user.chat_limit = 100
                elif level == "standard":   
                    user.workout_limit = 30 
                    user.chat_limit = 30
                # 3. Жестко фиксируем в базе
                await session.flush() 
                await session.commit()
                
                print(f"✅ БАЗА ДАННЫХ: Установлен статус {level} для {user_id}")
                return True
            return False
        except Exception as e:
            print(f"❌ ОШИБКА В CRUD: {e}")
            await session.rollback()
            return False

    @staticmethod
    async def add_workout_log(session: AsyncSession, **kwargs):
        from database.models import WorkoutLog
        
        # ЗАЩИТА: Если ИИ не выдал название упражнения, не пишем в базу
        if not kwargs.get('exercise_name'):
            print("⚠️ Ошибка: Название упражнения пустое. Запись в БД пропущена.")
            return None
            
        try:
            log = WorkoutLog(**kwargs)
            session.add(log)
            await session.commit()
            return log
        except Exception as e:
            print(f"❌ Ошибка при сохранении лога: {e}")
            await session.rollback()
            return None

    # ==========================================
    # ВОТ ЭТОТ НОВЫЙ КУСОК ВСТАВЛЯЕМ СЮДА:
    # ==========================================
    @classmethod
    async def reduce_limit(cls, session: AsyncSession, telegram_id: int, limit_type: str):
        """Списывает 1 лимит указанного типа у пользователя"""
        user = await cls.get_user(session, telegram_id)
        if not user:
            return False
            
        if limit_type == 'workout' and user.workout_limit > 0:
            user.workout_limit -= 1
        elif limit_type == 'chat' and user.chat_limit > 0:
            user.chat_limit -= 1
            
        await session.commit()
        return True