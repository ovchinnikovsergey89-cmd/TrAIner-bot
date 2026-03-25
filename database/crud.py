from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from database.models import User
from database.database import async_session as AsyncSessionLocal 

class UserCRUD:
    
    @staticmethod
    async def get_or_create_user(session: AsyncSession, telegram_id: int, **kwargs):
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            # Извлекаем referrer_id, если он был передан в ссылке
            referrer_id = kwargs.pop('referrer_id', None)
            # Защита: чтобы юзер не мог указать сам себя как реферера
            if referrer_id and referrer_id == telegram_id:
                referrer_id = None
                
            user = User(telegram_id=telegram_id, referrer_id=referrer_id, **kwargs)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        return user

    # ==========================================
    # НОВЫЙ БЛОК: РЕФЕРАЛКА И БОНУСЫ
    # ==========================================
    @staticmethod
    async def apply_registration_bonus(session: AsyncSession, telegram_id: int):
        """Устанавливает стартовые лимиты тарифа Free (3/5) после завершения регистрации"""
        user = await UserCRUD.get_user(session, telegram_id)
        
        if user and not user.is_bonus_used:
            # Жестко фиксируем лимиты Free (3 генерации и 5 вопросов)
            user.workout_limit = 3
            user.chat_limit = 5
            user.is_bonus_used = True
            await session.commit()
            return True
        return False

    @staticmethod
    async def add_referral_reward(session: AsyncSession, buyer_id: int, payment_amount: float):
        """Начисляет 15% кэшбэка пригласившему юзеру после оплаты подписки"""
        buyer = await UserCRUD.get_user(session, buyer_id)
        
        if buyer and buyer.referrer_id:
            referrer = await UserCRUD.get_user(session, buyer.referrer_id)
            if referrer:
                reward = payment_amount * 0.15
                referrer.referral_balance += reward
                await session.commit()
                return reward # Возвращаем сумму начисленного кэшбэка
        return 0.0

    # ==========================================

    @staticmethod
    async def get_weekly_workouts_count(session: AsyncSession, telegram_id: int) -> int:
        from database.models import WorkoutLog, WorkoutProgramHistory
        
        latest_prog_query = select(WorkoutProgramHistory.created_at).where(
            WorkoutProgramHistory.user_id == telegram_id
        ).order_by(WorkoutProgramHistory.created_at.desc()).limit(1)
        
        result_prog = await session.execute(latest_prog_query)
        program_start_date = result_prog.scalar()
        
        one_week_ago = datetime.now() - timedelta(days=7)
        if program_start_date and program_start_date > one_week_ago:
            start_date = program_start_date
        else:
            start_date = one_week_ago
            
        query = select(func.count(WorkoutLog.id)).where(
            WorkoutLog.user_id == telegram_id,
            WorkoutLog.date >= start_date,
            WorkoutLog.workout_type.like("Тренировка День%") 
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

        free = await session.scalar(
            select(func.count(User.telegram_id)).where(
                (User.subscription_level == 'free') | (User.subscription_level.is_(None))
            )
        ) or 0
        
        lite = await session.scalar(
            select(func.count(User.telegram_id)).where(User.subscription_level == 'lite')
        ) or 0
        
        standard = await session.scalar(
            select(func.count(User.telegram_id)).where(User.subscription_level == 'standard')
        ) or 0
        
        ultra = await session.scalar(
            select(func.count(User.telegram_id)).where(User.subscription_level == 'ultra')
        ) or 0

        return {
            'total': total,
            'active_profile': active,
            'has_workout': workouts,
            'has_nutrition': nutrition,
            'active_24h': active_24h,
            'free_users': free,
            'lite_users': lite,
            'standard_users': standard,
            'ultra_users': ultra
        }
    
    @staticmethod
    async def update_user_subscription(session: AsyncSession, user_id: int, level: str):
        print(f"DEBUG: Пытаюсь обновить юзера {user_id} на уровень {level}") 
        try:
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalar_one_or_none()
            
            if user:
                user.subscription_level = level
                user.subscription_expires_at = datetime.now() + timedelta(days=28)
                
                # --- НОВЫЕ ЛИМИТЫ ПО ТАРИФАМ ---
                if level == "ultra":
                    user.workout_limit = 40
                    user.chat_limit = 100
                elif level == "standard":   
                    user.workout_limit = 20 
                    user.chat_limit = 50
                elif level == "lite":   
                    user.workout_limit = 10 
                    user.chat_limit = 20
                    
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
    
    @staticmethod
    async def save_program_history(session: AsyncSession, telegram_id: int, program_type: str, program_text: str):
        """Сохраняет сгенерированную программу в историю"""
        from database.models import WorkoutProgramHistory, NutritionProgramHistory
        
        try:
            if program_type == 'workout':
                history_entry = WorkoutProgramHistory(user_id=telegram_id, program_text=program_text)
            elif program_type == 'nutrition':
                history_entry = NutritionProgramHistory(user_id=telegram_id, program_text=program_text)
            else:
                return False
                
            session.add(history_entry)
            await session.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка при сохранении истории {program_type}: {e}")
            await session.rollback()
            return False

    @staticmethod
    async def get_program_history(session: AsyncSession, telegram_id: int, program_type: str, limit: int = 3):
        """Достает последние N программ из истории"""
        from database.models import WorkoutProgramHistory, NutritionProgramHistory
        
        try:
            if program_type == 'workout':
                model = WorkoutProgramHistory
            elif program_type == 'nutrition':
                model = NutritionProgramHistory
            else:
                return []
                
            subq = (
                select(func.max(model.id))
                .where(model.user_id == telegram_id)
                .group_by(func.date(model.created_at))
            )
            
            result = await session.execute(
                select(model)
                .where(model.id.in_(subq))
                .order_by(desc(model.created_at))
                .limit(limit)
            )
            
            records = result.scalars().all()
            return [record.program_text for record in reversed(records)]
            
        except Exception as e:
            print(f"❌ Ошибка при получении истории {program_type}: {e}")
            return [] 
        
    @staticmethod
    async def activate_promo(session: AsyncSession, telegram_id: int, promo_text: str):
        from database.models import PromoCode, User
        
        result = await session.execute(
            select(PromoCode).where(PromoCode.code == promo_text.upper())
        )
        promo = result.scalar_one_or_none()
        
        if not promo or promo.uses_left <= 0:
            return "❌ Код неверный или закончился."

        user = await UserCRUD.get_user(session, telegram_id)
        
        user.subscription_level = promo.target_level
        if promo.target_level == 'ultra':
            user.workout_limit = 40 
            user.chat_limit = 100
        
        promo.uses_left -= 1
        
        await session.commit()
        return f"✅ Активирован режим {promo.target_level.upper()}! Лимиты обновлены."    
    
    @staticmethod
    async def delete_promo(session: AsyncSession, promo_text: str):
        from database.models import PromoCode
        result = await session.execute(
            select(PromoCode).where(PromoCode.code == promo_text.upper())
        )
        promo = result.scalar_one_or_none()
        if promo:
            await session.delete(promo)
            await session.commit()
            return True
        return False

    @staticmethod
    async def get_all_promos(session: AsyncSession):
        from database.models import PromoCode
        result = await session.execute(select(PromoCode))
        return result.scalars().all()
    
    @staticmethod
    def get_session():
        from database.database import async_session
        return async_session()

    # ИСПРАВЛЕННЫЙ ДУБЛЬ (теперь это безопасная ссылка на основную функцию)
    @staticmethod
    async def reduce_workout_limit(session: AsyncSession, telegram_id: int):
        """Обертка для совместимости. Вызывает универсальную reduce_limit"""
        return await UserCRUD.reduce_limit(session, telegram_id, 'workout')
    
    @staticmethod
    def get_session():
        from database.database import async_session
        return async_session()

    @staticmethod
    async def delete_user(session: AsyncSession, telegram_id: int):
        """Полное удаление пользователя из базы данных"""
        from database.models import User
        try:
            # Ищем пользователя в базе
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                await session.delete(user) # Удаляем объект
                await session.commit()     # Фиксируем изменения
                return True
            return False
        except Exception as e:
            print(f"❌ Ошибка при удалении юзера {telegram_id}: {e}")
            await session.rollback()
            return False
        
    @staticmethod
    async def add_upgrade_limits(session: AsyncSession, user_id: int):
        """Разовое добавление +5 генераций и +10 вопросов (Апгрейд)"""
        user = await UserCRUD.get_user(session, user_id)
        if user:
            user.workout_limit += 5
            user.chat_limit += 10
            await session.commit()
            return True
        return False    
    
    @staticmethod
    async def decrement_chat_limit(session: AsyncSession, user_id: int):
        """Списывает 1 вопрос в чате"""
        user = await UserCRUD.get_user(session, user_id)
        if user and user.chat_limit > 0:
            user.chat_limit -= 1
            await session.commit()
            return True
        return False

    @staticmethod
    async def decrement_workout_limit(session: AsyncSession, user_id: int):
        """Списывает 1 генерацию тренировки"""
        user = await UserCRUD.get_user(session, user_id)
        if user and user.workout_limit > 0:
            user.workout_limit -= 1
            await session.commit()
            return True
        return False
    
    
