from sqlalchemy import BigInteger, String, Float, Integer, Column, DateTime, func, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database.database import Base
import datetime 

class User(Base):
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=True)
    
    # --- Данные подписки ---
    subscription_level = Column(String, default="free")
    subscription_expires_at = Column(DateTime, nullable=True)
    
    age = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    gender = Column(String, nullable=True)
    activity_level = Column(String, nullable=True)
    goal = Column(String, nullable=True)
    workout_level = Column(String, nullable=True)
    workout_days = Column(Integer, default=3)
    completed_workouts = Column(Integer, default=0)
    
    # --- СИСТЕМА МОНЕТИЗАЦИИ (старые поля для совместимости) ---
    is_premium = Column(Boolean, default=False)
    sub_level = Column(Integer, default=0)
    sub_end_date = Column(DateTime, nullable=True)
    
    workout_limit = Column(Integer, default=3)
    chat_limit = Column(Integer, default=5)
    nutrition_limit = Column(Integer, default=3)
    last_analysis_date = Column(DateTime, nullable=True)

    notification_time = Column(Integer, default=8)
    current_workout_program = Column(String, nullable=True)
    current_nutrition_program = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    weight_history = relationship("WeightHistory", back_populates="user", cascade="all, delete-orphan")

class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id")) 
    date = Column(DateTime, default=datetime.datetime.now)
    workout_type = Column(String, nullable=True) 
    
    # ИСПРАВЛЕНО: nullable=True позволяет записывать данные, даже если ИИ не распознал имя
    exercise_name = Column(String, nullable=True) 
    canonical_name = Column(String, nullable=True) 
    
    weight = Column(Float, default=0.0)
    reps = Column(Integer, default=0)
    sets = Column(Integer, default=0)

class WeightHistory(Base):
    __tablename__ = 'weight_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id'))
    weight = Column(Float, nullable=False)
    date = Column(DateTime, default=func.now())
    
    user = relationship("User", back_populates="weight_history")

class ExerciseLog(Base):
    __tablename__ = "exercise_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    # Исправлено на nullable=True
    exercise_name = Column(String, nullable=True) 
    weight = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    date = Column(DateTime, default=datetime.datetime.now)    

class NutritionLog(Base):
    __tablename__ = 'nutrition_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="CASCADE"))
    meal_type = Column(String, default="Перекус")
    # Исправлено на nullable=True
    product_name = Column(String, nullable=True)
    weight = Column(Float, default=0.0)
    
    calories = Column(Float, default=0.0)
    protein = Column(Float, default=0.0)
    fat = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    
    date = Column(DateTime, default=func.now())

class WorkoutProgramHistory(Base):
    __tablename__ = 'workout_program_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="CASCADE"))
    program_text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

class NutritionProgramHistory(Base):
    __tablename__ = 'nutrition_program_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="CASCADE"))
    program_text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)   

class PromoCode(Base):
    __tablename__ = 'promocodes'

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False) # Сам код (например, 'BLOGER100')
    target_level = Column(String, default='ultra') # Какой уровень дает (lite, standard, ultra)
    uses_left = Column(Integer, default=1) # Сколько раз можно активировать
    expiry_date = Column(DateTime, nullable=True) # До какого числа работает     
