from sqlalchemy import BigInteger, String, Float, Integer, Column, DateTime, func, ForeignKey, Boolean, Float  # <-- Добавь Boolean сюда
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
    
    
    # --- СИСТЕМА МОНЕТИЗАЦИИ ---
    is_premium = Column(Boolean, default=False)  # Оставим для обратной совместимости или админов
    sub_level = Column(Integer, default=0)       # 0 - Free, 1 - Base, 2 - Pro, 3 - Elite
    sub_end_date = Column(DateTime, nullable=True) # Дата окончания подписки
    
    workout_limit = Column(Integer, default=3)   # Бесплатные генерации
    chat_limit = Column(Integer, default=5)      # Бесплатные вопросы AI
    last_analysis_date = Column(DateTime, nullable=True)
    # ---------------------------

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
    
    # Какое это было занятие (например, "Грудь/Спина" или "День 1")
    workout_type = Column(String, nullable=True) 
    
    # То, что ты сказал боту (например, "жим на наклонной 30 град")
    exercise_name = Column(String, nullable=False) 
    
    # 🔥 ТО САМОЕ ПОЛЕ для графиков (например, "Жим штанги в наклоне")
    canonical_name = Column(String, nullable=False) 
    
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
    exercise_name = Column(String, nullable=False)
    weight = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    date = Column(DateTime, default=datetime.datetime.now)    

class NutritionLog(Base):
    __tablename__ = 'nutrition_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete="CASCADE"))
    meal_type = Column(String, default="Перекус") # <-- ДОБАВИТЬ ЭТУ СТРОКУ
    product_name = Column(String, nullable=False)
    weight = Column(Float, default=0.0)
    
    # КБЖУ
    calories = Column(Float, default=0.0)
    protein = Column(Float, default=0.0)
    fat = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    
    date = Column(DateTime, default=func.now())    